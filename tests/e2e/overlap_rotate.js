// 겹친 물건 옆에서 돌리기: 책상 고리 손잡이가 옆 의자 위에 걸쳐 있어도 손잡이를 끌면 책상만 돈다. 서버를 켠 뒤 실행:
//   uv run lgb-api            (다른 창)
//   node tests/e2e/overlap_rotate.js [http://localhost:8000]
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
  const menuText = () => page.evaluate(() => (document.getElementById("actBar").hidden ? "" : document.getElementById("actBar").innerText));

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  const stateOf = async (id) => (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements.find((q) => q.placement_id === id);
  const room = await api(`/api/projects/${pid}/room`, null, "GET"); // 근처 스캔 책상은 치운다
  await api(`/api/projects/${pid}/objects/hidden`, { hidden: true, object_ids: room.objects.filter((o) => Math.hypot(o.position[0] + 2, o.position[2] + 2.5) < 2.5).map((o) => o.object_id) }, "PUT");
  const C = [-2, -2.5];
  const desk = (await api(`/api/projects/${pid}/placements`, { sku: "decor:desk", center_xz: C, yaw_rad: Math.PI / 2, snap: false })).placement;
  const r = Math.hypot(desk.size_m[0], desk.size_m[2]) / 2 + 0.18; // rotring.ringRadius
  // 손잡이(앞 0°) 자리에 의자를 붙여 둔다: 손잡이가 의자 위에 걸친다
  const chair = (await api(`/api/projects/${pid}/placements`, { sku: "decor:chair", center_xz: [C[0], C[1] + r], yaw_rad: Math.PI / 2, snap: false })).placement;
  await page.reload();
  await page.waitForSelector("#libTabs", { state: "attached", timeout: 60000 });
  await page.waitForTimeout(4000);

  let picked = false;
  for (let i = 0; i < 10 && !picked; i++) {
    await page.mouse.click(...(await toScreen([C[0] - 0.4, C[1]], 0.73)));
    await page.waitForTimeout(600);
    picked = (await menuText()).includes("크기 조절") && !(await menuText()).includes("상세");
  }
  check("책상이 골라진다", picked);
  await page.waitForTimeout(1000); // 고리가 깔리고 가구 모델이 다 올라올 때까지
  const at = (a) => toScreen([C[0] + r * Math.sin(a), C[1] + r * Math.cos(a)], 0.012);
  await page.mouse.move(...(await at(0)));
  await page.waitForTimeout(1000); // 느린 화면(소프트웨어 그리기)에서는 마우스 이벤트가 늦게 들어온다
  if (process.env.DBG) { await page.screenshot({ path: process.env.DBG }); console.log(JSON.stringify(await at(0)), JSON.stringify(desk.size_m), JSON.stringify(chair), r); }
  check("의자 위에 걸친 손잡이도 잡힌다", (await page.evaluate(() => document.querySelector("#viewer canvas").style.cursor)) === "grab");
  await page.mouse.down();
  for (let i = 1; i <= 12; i++) { await page.mouse.move(...(await at((Math.PI / 2 - 0.05) * i / 12))); await page.waitForTimeout(60); }
  await page.waitForTimeout(500);
  await page.mouse.up();
  await page.waitForTimeout(1500);
  const d1 = await stateOf(desk.placement_id), c1 = await stateOf(chair.placement_id);
  check("책상이 90° 돈다", Math.abs(d1.yaw_rad) < 1e-6, `yaw ${d1.yaw_rad}`);
  if (process.env.DBG) console.log(JSON.stringify(d1), JSON.stringify(c1));
  check("의자는 그대로", Math.abs(c1.yaw_rad - chair.yaw_rad) < 1e-6 && Math.hypot(c1.center_xz[0] - chair.center_xz[0], c1.center_xz[1] - chair.center_xz[1]) < 1e-6);
  check("오류 없음", errors.length === 0, errors.join(" | "));
  await api(`/api/projects/${pid}`, null, "DELETE").catch(() => {});
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
