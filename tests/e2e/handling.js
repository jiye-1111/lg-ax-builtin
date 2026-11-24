// 물건 다루기 점검: 고른 것만 끌린다, 책상 위 정수기는 책상 위를 따라 움직인다, 고정하면 안 움직인다. 서버를 켠 뒤 실행:
//   uv run lgb-api            (다른 창)
//   node tests/e2e/handling.js [http://localhost:8000]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const ROOT = path.resolve(__dirname, "../..");
let failed = 0;
const check = (name, ok, info = "") => { if (!ok) failed += 1; console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`); };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => { try { localStorage.setItem("lgb.tour.v1", "1"); } catch { /* 안내만 건너뛴다 */ } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const api = (url, body, method = "POST") => page.evaluate(async ([u, b, m]) =>
    (await fetch(u, { method: m, headers: { "Content-Type": "application/json" }, body: b ? JSON.stringify(b) : undefined })).json(), [url, body, method]);
  const toScreen = (c, y = 0) => page.evaluate(([c, y]) => document.getElementById("viewer").viewer.toScreen(c, y), [c, y]);
  const stateOf = async (id) => (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements.find((q) => q.placement_id === id);
  const drag = async ([x, y], [dx, dy]) => {
    await page.mouse.move(x, y); await page.mouse.down();
    for (let i = 1; i <= 10; i++) { await page.mouse.move(x + (dx * i) / 10, y + (dy * i) / 10); await page.waitForTimeout(30); }
    await page.mouse.up(); await page.waitForTimeout(1500);
  };
  const menuShown = () => page.evaluate(() => !document.getElementById("actBar").hidden);
  const select = async (pt) => {
    for (let i = 0; i < 10; i++) {
      await page.mouse.click(...pt); await page.waitForTimeout(600);
      if (await menuShown()) return true;
      await page.mouse.click(5, 5); await page.waitForTimeout(300);
    }
    return false;
  };

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  const room = await api(`/api/projects/${pid}/room`, null, "GET"); // 근처 스캔 책상은 치워서 누르는 자리가 겹치지 않게
  await api(`/api/projects/${pid}/objects/hidden`, { hidden: true, object_ids: room.objects.filter((o) => Math.hypot(o.position[0] + 2, o.position[2] + 2.5) < 2.5 || Math.hypot(o.position[0] - 0.5, o.position[2] + 1) < 1.5).map((o) => o.object_id) }, "PUT");
  const fr = (await api(`/api/projects/${pid}/placements`, { sku: "G646GBB031", center_xz: [0.5, -1], yaw_rad: Math.PI / 2, snap: false })).placement;
  const desk = (await api(`/api/projects/${pid}/auto-place`, { sku: "decor:desk" })).placement;
  await api(`/api/projects/${pid}/placements/${desk.placement_id}`, { center_xz: [-2, -2.5], yaw_rad: Math.PI / 2, snap: false }, "PATCH");
  const pur = (await api(`/api/projects/${pid}/placements`, { sku: "WD523AWB", center_xz: [-2, -2.5], yaw_rad: Math.PI / 2, snap: false })).placement;
  check("정수기가 책상 위에 올라간다", Math.abs(pur.base_m - 0.73) < 1e-6, `base ${pur.base_m}`);
  await page.reload();
  await page.waitForSelector("#libTabs", { state: "attached", timeout: 60000 });
  await page.waitForTimeout(4000);
  const purAt = () => toScreen(pur.center_xz, 0.73 + 0.2);

  // 1) 안 고른 정수기를 끌면 화면만 돈다
  await drag(await purAt(), [40, 0]);
  const p0 = await stateOf(pur.placement_id);
  check("안 고른 물건은 끌어도 그대로", Math.hypot(p0.center_xz[0] + 2, p0.center_xz[1] + 2.5) < 1e-6, JSON.stringify(p0.center_xz));
  await page.reload();
  await page.waitForSelector("#libTabs", { state: "attached", timeout: 60000 });
  await page.waitForTimeout(4000);

  // 2) 골라서 끌면 책상 위를 따라 커서 쪽으로 조금만 움직인다
  check("누르면 골라진다", await select(await purAt()));
  const [sx, sy] = await purAt();
  const [ex, ey] = await toScreen([-2.25, -2.5], 0.73 + 0.2); // 책상 위 25 cm 옆
  await drag([sx, sy], [ex - sx, ey - sy]);
  const p1 = await stateOf(pur.placement_id);
  check("책상 위에 그대로 있다", Math.abs(p1.base_m - 0.73) < 1e-6, `base ${p1.base_m}`);
  check("커서만큼만 움직인다", Math.hypot(p1.center_xz[0] + 2.25, p1.center_xz[1] + 2.5) < 0.06, JSON.stringify(p1.center_xz));

  // 3) 고정하면 끌어도, R을 눌러도 안 움직인다
  if (!(await menuShown())) await select(await toScreen(p1.center_xz, 0.93));
  await page.waitForTimeout(1000); // 느린 화면에서는 메뉴가 물건을 따라 자리 잡는 데 시간이 걸린다
  await page.click("#actLock");
  await page.waitForFunction(() => document.getElementById("actLock")?.innerText.includes("고정 풀기"), null, { timeout: 5000 }).catch(() => {});
  if (process.env.SHOT) await page.screenshot({ path: process.env.SHOT, clip: { x: 520, y: 300, width: 720, height: 400 } });
  check("고정하면 메뉴에 고정 풀기가 보인다", (await page.textContent("#actLock")).includes("고정 풀기"));
  check("고정하면 옮기기 버튼이 없다", !(await page.$("#actMove")));
  check("고정 목록에 저장된다", (await api(`/api/projects/${pid}`, null, "GET")).scene_state.locked.includes(pur.placement_id));
  const at2 = await toScreen(p1.center_xz, 0.93);
  await drag(at2, [40, 0]);
  await page.keyboard.press("r");
  await page.waitForTimeout(1000);
  const p2 = await stateOf(pur.placement_id);
  check("고정한 물건은 끌어도 그대로", Math.hypot(p2.center_xz[0] - p1.center_xz[0], p2.center_xz[1] - p1.center_xz[1]) < 1e-6, JSON.stringify(p2.center_xz));
  check("고정한 물건은 R로도 안 돈다", Math.abs(p2.yaw_rad - p1.yaw_rad) < 1e-6);

  // 4) 고정 풀면 다시 움직인다
  if (!(await menuShown())) await select(await toScreen(p1.center_xz, 0.93));
  await page.click("#actLock");
  await page.waitForTimeout(800);
  check("고정을 풀면 옮기기 버튼이 돌아온다", !!(await page.$("#actMove")));
  check("고정 목록에서 빠진다", !(await api(`/api/projects/${pid}`, null, "GET")).scene_state.locked.includes(pur.placement_id));

  // 5) 책상 위 정수기도 고리 손잡이로 돌린다 (책상 윗면이 고리를 가리지 않는다)
  if (!(await menuShown())) await select(await toScreen(p1.center_xz, 0.93));
  const rr = Math.max(0.35, Math.hypot(pur.size_m[0], pur.size_m[2]) / 2 + 0.18); // rotring.ringRadius
  const at = (a) => toScreen([p1.center_xz[0] + rr * Math.sin(a), p1.center_xz[1] + rr * Math.cos(a)], 0.742);
  await page.mouse.move(...(await at(0)));
  await page.waitForTimeout(200);
  check("책상 위 정수기 손잡이가 잡힌다", (await page.evaluate(() => document.querySelector("#viewer canvas").style.cursor)) === "grab");
  await page.mouse.down();
  for (let i = 1; i <= 12; i++) { await page.mouse.move(...(await at((Math.PI / 2 - 0.05) * i / 12))); await page.waitForTimeout(25); }
  await page.mouse.up();
  await page.waitForTimeout(1500);
  const p3 = await stateOf(pur.placement_id);
  check("고리로 돌려도 책상 위 제자리", Math.abs(p3.yaw_rad) < 1e-6 && p3.base_m === 0.73 && Math.hypot(p3.center_xz[0] - p1.center_xz[0], p3.center_xz[1] - p1.center_xz[1]) < 1e-6, `yaw ${p3.yaw_rad} ${JSON.stringify(p3.center_xz)}`);

  // 6) 고른 냉장고 몸통을 끌면 돌지 않고 옮겨진다 (몸통 너머 고리가 잡히면 안 된다)
  await page.reload();
  await page.waitForSelector("#libTabs", { state: "attached", timeout: 60000 });
  await page.waitForTimeout(4000);
  const fpt = await toScreen(fr.center_xz, 1.0);
  check("냉장고가 골라진다", await select(fpt));
  await drag(fpt, (await toScreen([0, -1], 1.0)).map((v, i) => v - fpt[i]));
  const f1 = await stateOf(fr.placement_id);
  check("냉장고 몸통을 끌면 옮겨진다", Math.hypot(f1.center_xz[0], f1.center_xz[1] + 1) < 0.08 && Math.abs(f1.yaw_rad - fr.yaw_rad) < 1e-6, JSON.stringify(f1.center_xz));
  check("오류 없음", errors.length === 0, errors.join(" | "));
  await api(`/api/projects/${pid}`, null, "DELETE").catch(() => {});
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
