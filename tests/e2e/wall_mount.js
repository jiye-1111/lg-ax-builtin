// 설치 방식대로 붙는지 점검: 벽걸이 TV는 벽에 걸리고 끌면 벽을 따라 높이까지 바뀐다, 월핏·빌트인은 벽에서 떨어지면 안 된다고 알려 준다.
//   uv run lgb-api            (다른 창)
//   node tests/e2e/wall_mount.js [http://localhost:8000] [스크린샷 폴더]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3] || "";
const ROOT = path.resolve(__dirname, "../..");
const TV = "OLED65C5ENA", WALLFIT = "AS186LSAA", AC = "SW09GS1EES";
let failed = 0;
const check = (name, ok, info = "") => { if (!ok) failed += 1; console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`); };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: SHOTS ? 2 : 1 });
  await ctx.addInitScript(() => { try { localStorage.setItem("lgb.tour.v1", "1"); } catch { /* 안내만 건너뛴다 */ } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.stack || e)));
  const api = (url, body, method = "POST") => page.evaluate(async ([u, b, m]) =>
    (await fetch(u, { method: m, headers: { "Content-Type": "application/json" }, body: b ? JSON.stringify(b) : undefined })).json(), [url, body, method]);
  const toScreen = (c, y = 0) => page.evaluate(([c, y]) => document.getElementById("viewer").viewer.toScreen(c, y), [c, y]);
  const shot = async (name) => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, name) }); };
  const reload = async () => { await page.reload(); await page.waitForFunction(() => !!document.querySelector("#lib [data-sku]") && document.getElementById("plan")?.children.length > 0, null, { timeout: 90000 }); await page.waitForTimeout(4000); };
  const menuShown = () => page.evaluate(() => !document.getElementById("actBar").hidden);

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  const stateOf = async (id) => (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements.find((q) => q.placement_id === id);
  const room = await api(`/api/projects/${pid}/room`, null, "GET");
  await api(`/api/projects/${pid}/objects/hidden`, { hidden: true }); // 가구를 치우고 빈 방에서 본다
  const mid = room.walls.reduce((a, w) => [a[0] + (w.start[0] + w.end[0]) / 2 / room.walls.length, a[1] + (w.start[1] + w.end[1]) / 2 / room.walls.length], [0, 0]);
  // 벽까지의 거리 (벽 가운데 줄 기준)
  const wallGapTo = (w, c) => {
    const ex = w.end[0] - w.start[0], ez = w.end[1] - w.start[1], l2 = ex * ex + ez * ez;
    const t = Math.max(0, Math.min(1, ((c[0] - w.start[0]) * ex + (c[1] - w.start[1]) * ez) / l2));
    return Math.hypot(c[0] - w.start[0] - ex * t, c[1] - w.start[1] - ez * t) - (w.thickness_m || 0.1) / 2;
  };
  const wallGap = (c) => Math.min(...room.walls.map((w) => wallGapTo(w, c)));

  // 1) 벽걸이 TV: 방 가운데를 눌러도 벽에 걸리고 바닥에서 떠 있다
  const tv = (await api(`/api/projects/${pid}/placements`, { sku: TV, center_xz: mid })).placement;
  check("벽걸이 TV는 벽에 걸린다", Math.abs(wallGap(tv.center_xz) - tv.size_m[2] / 2) < 0.01, `벽에서 ${wallGap(tv.center_xz).toFixed(3)} m`);
  check("바닥이 아니라 눈높이에 걸린다", tv.base_m > 0.5 && tv.base_m < 1.0, `밑면 ${tv.base_m} m`);
  check("걸린 자리는 설치할 수 있는 자리", tv.verdict !== "no_fit", tv.reasons.map((r) => r.code).join(","));

  // 2) 벽에서 떼어 두면 안 된다고 한 문장으로 알려 준다
  const far = await api(`/api/projects/${pid}/pose-check`, { sku: TV, center_xz: mid, yaw_rad: 0, snap: false });
  check("벽걸이 TV를 방 가운데 두면 안 된다", far.verdict === "no_fit" && far.reasons.some((r) => r.label === "벽에 걸어야 해요"));
  const wf = await api(`/api/projects/${pid}/pose-check`, { sku: WALLFIT, center_xz: mid, yaw_rad: 0, snap: false });
  check("월핏은 벽에서 떨어지면 안 된다", wf.verdict === "no_fit" && wf.reasons.some((r) => r.label === "뒷면을 벽에 붙여야 해요"));
  const wfNear = await api(`/api/projects/${pid}/pose-check`, { sku: WALLFIT, center_xz: [tv.center_xz[0] + Math.cos(tv.yaw_rad) * 0.5, tv.center_xz[1] + Math.sin(tv.yaw_rad) * 0.5], yaw_rad: 0 });
  check("월핏은 벽 50 cm 앞에서도 벽으로 붙는다", !wfNear.reasons.some((r) => r.code === "needs_wall") && wallGap(wfNear.pose.center_xz) < 0.2, `벽에서 ${wallGap(wfNear.pose.center_xz).toFixed(3)} m`);

  // 3) 고른 TV를 끌면 벽을 따라 옆으로, 위로 움직인다 (벽에서 떨어지지 않는다)
  await reload();
  const mid3 = (p) => toScreen(p.center_xz, p.base_m + p.size_m[1] / 2);
  for (let i = 0; i < 10 && !(await menuShown()); i++) { await page.mouse.click(...(await mid3(tv))); await page.waitForTimeout(700); }
  check("TV를 누르면 골라진다", await menuShown());
  check("벽에 건 것은 회전 버튼이 없다", await page.evaluate(() => !document.getElementById("actRot")));
  await shot("1125-wall-tv-selected.png");
  let ux = Math.sin(tv.yaw_rad), uz = -Math.cos(tv.yaw_rad); // 벽 방향 (걸린 벽의 가운데 쪽으로: 끝에는 기둥이 있다)
  const host = room.walls.filter((w) => Math.hypot(w.end[0] - w.start[0], w.end[1] - w.start[1]) > 2)
    .map((w) => ({ m: [(w.start[0] + w.end[0]) / 2, (w.start[1] + w.end[1]) / 2], g: Math.abs(wallGapTo(w, tv.center_xz) - tv.size_m[2] / 2) })).sort((p, q) => p.g - q.g)[0];
  if ((host.m[0] - tv.center_xz[0]) * ux + (host.m[1] - tv.center_xz[1]) * uz < 0) { ux = -ux; uz = -uz; }
  const goal = [tv.center_xz[0] + ux * 0.6, tv.center_xz[1] + uz * 0.6], goalY = tv.base_m + tv.size_m[1] / 2 + 0.5;
  const [sx, sy] = await mid3(tv), [ex, ey] = await toScreen(goal, goalY);
  await page.mouse.move(sx, sy); await page.mouse.down();
  for (let i = 1; i <= 12; i++) { await page.mouse.move(sx + ((ex - sx) * i) / 12, sy + ((ey - sy) * i) / 12); await page.waitForTimeout(40); }
  await shot("1125-wall-tv-dragging.png");
  await page.mouse.up(); await page.waitForTimeout(1800);
  const t1 = await stateOf(tv.placement_id);
  check("끌어도 벽에 붙어 있다", Math.abs(wallGap(t1.center_xz) - t1.size_m[2] / 2) < 0.01, `벽에서 ${wallGap(t1.center_xz).toFixed(3)} m`);
  check("벽을 따라 옆으로 갔다", Math.hypot(t1.center_xz[0] - goal[0], t1.center_xz[1] - goal[1]) < 0.12, JSON.stringify([tv.center_xz, goal, t1.center_xz]));
  check("위로 끈 만큼 높아졌다", Math.abs(t1.base_m - (tv.base_m + 0.5)) < 0.08, `밑면 ${tv.base_m} → ${t1.base_m}`);
  check("방향은 벽 그대로", Math.abs(t1.yaw_rad - tv.yaw_rad) < 1e-3);

  // 4) 목록에서 벽걸이 에어컨을 끌어다 바닥에 떨어뜨려도 가까운 벽에, 천장 아래에 걸린다
  await page.mouse.click(5, 5);
  const spot = [t1.center_xz[0] + ux * 2.4, t1.center_xz[1] + uz * 2.4];
  const [dxp, dyp] = await toScreen([spot[0] + Math.cos(tv.yaw_rad) * 0.8, spot[1] + Math.sin(tv.yaw_rad) * 0.8], 0); // 벽 앞 80 cm 바닥
  await page.evaluate(([sku, x, y]) => {
    const dt = new DataTransfer(); dt.setData("text/sku", sku);
    document.querySelector("#viewer canvas").dispatchEvent(new DragEvent("drop", { clientX: x, clientY: y, dataTransfer: dt, bubbles: true, cancelable: true }));
  }, [AC, dxp, dyp]);
  await page.waitForTimeout(2500);
  const ac2 = (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements.find((q) => q.sku === AC);
  check("떨어뜨린 에어컨이 걸렸다", !!ac2);
  if (ac2) {
    check("벽에 붙어 있다", Math.abs(wallGap(ac2.center_xz) - ac2.size_m[2] / 2) < 0.01, `벽에서 ${wallGap(ac2.center_xz).toFixed(3)} m`);
    check("천장 아래 높이에 걸렸다", ac2.base_m > 1.8, `밑면 ${ac2.base_m} m`);
    check("떨어뜨린 자리 앞 벽에 걸렸다", Math.hypot(ac2.center_xz[0] - spot[0], ac2.center_xz[1] - spot[1]) < 0.3, JSON.stringify(ac2.center_xz));
  }
  await shot("1125-wall-tv-ac.png");

  await page.click('[data-tab="lg"]');
  await page.fill("#q", AC);
  // 5) 목록에서 벽걸이 에어컨의 '배치하기'를 누르면 빈 벽을 찾아 천장 아래에 걸린다
  // (목록에 내놓지 않는 모델이면 같은 '알맞은 자리에 놓기'를 바로 부른다)
  const listed = await page.waitForFunction((sku) => !!document.querySelector(`#lib [data-place="${sku}"]`), AC, { timeout: 10000 }).then(() => true, () => false);
  if (listed) await page.evaluate((sku) => document.querySelector(`#lib [data-place="${sku}"]`).click(), AC);
  else await api(`/api/projects/${pid}/auto-place`, { sku: AC });
  await page.waitForTimeout(2500);
  const ac = (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements.find((q) => q.sku === AC && q.placement_id !== ac2?.placement_id);
  check("에어컨이 걸렸다", !!ac);
  if (ac) {
    check("에어컨도 벽에 붙어 있다", Math.abs(wallGap(ac.center_xz) - ac.size_m[2] / 2) < 0.01, `벽에서 ${wallGap(ac.center_xz).toFixed(3)} m`);
    check("천장 아래에 걸렸다", ac.base_m > 1.8, `밑면 ${ac.base_m} m`);
    check("설치할 수 있는 자리", ac.verdict !== "no_fit", ac.reasons.map((r) => r.code).join(","));
  }

  check("화면 오류 없음", errors.length === 0, errors.join(" | "));
  await browser.close();
  console.log(failed ? `\n${failed}개 실패` : "\n모두 통과");
  process.exit(failed ? 1 : 0);
})();
