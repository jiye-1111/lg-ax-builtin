// 빌트인을 장 칸에 끼워 넣기 점검: 하부장 위에 떨어뜨리면 칸이 나고 상판이 이어진다, 되돌리면 장도 돌아온다,
// 장 끝 손잡이를 끌면 늘어난다, 놓고 난 뒤에는 초록 바닥 표시가 없다.
//   uv run lgb-api            (다른 창)
//   node tests/e2e/slot_in.js [http://localhost:8000] [스크린샷 폴더]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3] || "";
const ROOT = path.resolve(__dirname, "../..");
const DISH = "DUE6BGE", OUT = 0.16; // 손잡이는 장 끝에서 16 cm 밖 (js/stretch.js HANDLE_OUT_M)
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
  const plates = () => page.evaluate(() => document.getElementById("viewer").viewer.shownPlates());
  const shot = async (name) => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, name) }); };
  const reload = async () => { await page.reload(); await page.waitForFunction(() => !!document.querySelector("#lib [data-sku]") && document.getElementById("plan")?.children.length > 0, null, { timeout: 60000 }); await page.waitForTimeout(2500); };
  const until = async (fn, ms = 25000) => { for (const t0 = Date.now(); Date.now() - t0 < ms;) { if (await fn()) return true; await page.waitForTimeout(500); } return false; };
  const menuShown = () => page.evaluate(() => !document.getElementById("actBar").hidden);

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  const all = async () => (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements;
  const cabs = async () => (await all()).filter((q) => q.sku === "decor:basecab");
  await api(`/api/projects/${pid}/objects/hidden`, { hidden: true }); // 가구를 치우고 빈 방에서 본다
  const cab = (await api(`/api/projects/${pid}/auto-place`, { sku: "decor:basecab", size_m: [1.8, 0.85, 0.6] })).placement;
  const ux = Math.cos(cab.yaw_rad - Math.PI / 2), uz = Math.sin(cab.yaw_rad - Math.PI / 2), fx = Math.cos(cab.yaw_rad), fz = Math.sin(cab.yaw_rad);
  const at = (u, v = 0) => [cab.center_xz[0] + ux * u + fx * v, cab.center_xz[1] + uz * u + fz * v];
  await reload();
  const eye = at(0.3, 1.7), aim = at(0, 0.1);
  const view = () => page.evaluate(([e, a]) => document.getElementById("viewer").viewer.setCamera({ pos: [e[0], 2.3, e[1]], target: [a[0], 0.6, a[1]] }), [eye, aim]);
  await until(() => page.evaluate(() => document.getElementById("viewer").viewer.stats().products > 0));
  await view();
  await page.waitForTimeout(2500);

  // 1) 목록에서 식기세척기를 끌어다 하부장 위에 떨어뜨리면 그 자리에 칸이 난다
  const [dx, dy] = await toScreen(at(0.1, 0.1), 0.85);
  await page.evaluate(([sku, x, y]) => {
    const dt = new DataTransfer(); dt.setData("text/sku", sku);
    document.querySelector("#viewer canvas").dispatchEvent(new DragEvent("drop", { clientX: x, clientY: y, dataTransfer: dt, bubbles: true, cancelable: true }));
  }, [DISH, dx, dy]);
  await page.waitForTimeout(2500);
  let dw = (await all()).find((q) => q.sku === DISH);
  check("하부장 위에 떨어뜨린 식기세척기가 놓였다", !!dw);
  if (dw) {
    check("설치할 수 있는 자리다", dw.verdict !== "no_fit", dw.reasons.map((r) => r.code).join(","));
    check("장과 같은 쪽을 본다", Math.abs(dw.yaw_rad - cab.yaw_rad) < 1e-6);
    check("상판이 이어진다", dw.slot?.look === "basecab" && dw.slot.top_m === 0.85, JSON.stringify(dw.slot));
    const cs = await cabs();
    check("하부장이 양옆 두 칸으로 갈라졌다", cs.length === 2 && Math.abs(cs[0].size_m[0] + cs[1].size_m[0] + dw.size_m[0] - 1.8) < 0.003, cs.map((q) => q.size_m[0].toFixed(3)).join(" + "));
  }
  await shot("1125-slot-dishwasher.png");

  // 2) 놓고 난 뒤 다른 곳을 누르면 초록 바닥 표시가 없다
  await page.mouse.click(...(await toScreen(at(0, 2.2), 0)));
  await page.waitForTimeout(800);
  check("놓고 난 뒤에는 초록 바닥 표시가 없다", (await plates()) === 0, `보이는 판 ${await plates()}개`);
  await shot("1125-slot-clean.png");

  // 3) 되돌리면 식기세척기가 빠지고 하부장이 한 칸으로 돌아온다. 다시 하면 다시 끼워진다
  await page.evaluate(() => document.getElementById("undo").click());
  await until(async () => (await cabs()).length === 1 && !(await page.evaluate(() => document.getElementById("redo").disabled)));
  let cs = await cabs();
  check("되돌리면 식기세척기가 빠진다", !(await all()).some((q) => q.sku === DISH));
  check("되돌리면 하부장이 한 칸으로 돌아온다", cs.length === 1 && Math.abs(cs[0].size_m[0] - 1.8) < 1e-6, cs.map((q) => q.size_m[0].toFixed(3)).join(" + "));
  await page.evaluate(() => document.getElementById("redo").click());
  await until(async () => (await all()).some((q) => q.sku === DISH && q.slot) && !(await page.evaluate(() => document.getElementById("undo").disabled)));
  cs = await cabs(); dw = (await all()).find((q) => q.sku === DISH);
  check("다시 하면 다시 끼워진다", !!dw && dw.verdict !== "no_fit" && !!dw.slot && cs.length === 2, `장 ${cs.length}칸`);

  // 4) 고른 하부장의 끝 손잡이를 끌면 그 끝만 늘어난다
  await reload();
  await view();
  await page.waitForTimeout(1000);
  cs = await cabs();
  const local = (q) => (q.center_xz[0] - cab.center_xz[0]) * ux + (q.center_xz[1] - cab.center_xz[1]) * uz;
  // 넓은 쪽 칸의 바깥 끝을 누른다 (식기세척기 회전 고리에 안 걸리는 자리)
  const piece = cs.sort((p, q) => q.size_m[0] - p.size_m[0])[0], u0 = local(piece), w0 = piece.size_m[0], side = u0 > local(dw) ? 1 : -1;
  const picked = () => page.evaluate(() => !document.getElementById("actBar").hidden && !!document.getElementById("actFill"));
  for (let i = 0; i < 10 && !(await picked()); i++) { await page.mouse.click(...(await toScreen(at(u0 + side * (w0 / 2 - 0.06)), 0.86))); await page.waitForTimeout(700); }
  check("하부장을 누르면 골라진다", await picked());
  const [hx, hy] = await toScreen(at(u0 + side * (w0 / 2 + OUT)), 0), [gx, gy] = await toScreen(at(u0 + side * (w0 / 2 + OUT + 0.4)), 0);
  await page.mouse.move(hx, hy); await page.mouse.down();
  for (let i = 1; i <= 10; i++) { await page.mouse.move(hx + ((gx - hx) * i) / 10, hy + ((gy - hy) * i) / 10); await page.waitForTimeout(40); }
  await shot("1125-slot-stretching.png");
  await page.mouse.up(); await page.waitForTimeout(2500);
  const after = (await all()).find((q) => q.placement_id === piece.placement_id);
  check("끝을 끌면 40 cm 늘어난다", Math.abs(after.size_m[0] - (w0 + 0.4)) < 0.03, `${w0.toFixed(3)} → ${after.size_m[0].toFixed(3)}`);
  check("반대쪽 끝은 그대로다", Math.abs((local(after) - side * after.size_m[0] / 2) - (u0 - side * w0 / 2)) < 0.005);
  check("식기세척기와는 여전히 붙어 있다", !!(await all()).find((q) => q.sku === DISH)?.slot);
  await page.mouse.click(...(await toScreen(at(0, 2.2), 0)));
  await page.waitForTimeout(800);
  await shot("1125-slot-stretched.png");

  check("화면 오류 없음", errors.length === 0, errors.slice(0, 2).join(" | "));
  await browser.close();
  console.log(failed ? `\n${failed}개 실패` : "\n모두 통과");
  process.exit(failed ? 1 : 0);
})();
