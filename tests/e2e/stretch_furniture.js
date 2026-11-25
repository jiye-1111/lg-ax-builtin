// 가구 끌어 늘리기: 식탁은 옆과 앞뒤 손잡이로 늘어나고, 책상은 손잡이가 없어 끌어도 그대로다.
//   uv run lgb-api            (다른 창)
//   node tests/e2e/stretch_furniture.js [http://localhost:8000] [스크린샷 폴더]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3] || "";
const ROOT = path.resolve(__dirname, "../..");
const OUT = 0.16; // 손잡이는 가구 끝에서 16 cm 밖 (js/stretch.js HANDLE_OUT_M)
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
  const until = async (fn, ms = 25000) => { for (const t0 = Date.now(); Date.now() - t0 < ms;) { if (await fn()) return true; await page.waitForTimeout(500); } return false; };
  const picked = () => page.evaluate(() => !document.getElementById("actBar").hidden);
  const drag = async (from, to, mid) => {
    await page.mouse.move(...from); await page.mouse.down();
    for (let i = 1; i <= 12; i++) { await page.mouse.move(from[0] + ((to[0] - from[0]) * i) / 12, from[1] + ((to[1] - from[1]) * i) / 12); await page.waitForTimeout(40); }
    if (mid) await mid();
    await page.mouse.up(); await page.waitForTimeout(2500);
  };

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/synthetic_room.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  const room = await api(`/api/projects/${pid}/files/room.json`, null, "GET");
  const xs = room.walls.flatMap((w) => [w.start[0], w.end[0]]), zs = room.walls.flatMap((w) => [w.start[1], w.end[1]]);
  const mid = [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...zs) + Math.max(...zs)) / 2];
  const UP = Math.PI / 2; // 정면 +z, 폭 축 +x
  const put = async (sku, size_m) => (await api(`/api/projects/${pid}/placements`, { sku, center_xz: mid, yaw_rad: UP, snap: false, size_m })).placement;
  const one = async (id) => (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements.find((q) => q.placement_id === id);
  const at = (u, v = 0) => [mid[0] + u, mid[1] + v];
  const open = async () => {
    await page.reload();
    await page.waitForFunction(() => !!document.querySelector("#lib [data-sku]") && document.getElementById("plan")?.children.length > 0, null, { timeout: 60000 });
    await until(() => page.evaluate(() => document.getElementById("viewer").viewer.stats().products > 0));
    await page.evaluate(([e, a]) => document.getElementById("viewer").viewer.setCamera({ pos: [e[0], 3.6, e[1]], target: [a[0], 0.3, a[1]] }), [at(0.3, 2.6), at(0, 0.2)]);
    await page.waitForTimeout(2500);
  };
  const pick = async (h) => { for (let i = 0; i < 10 && !(await picked()); i++) { await page.mouse.click(...(await toScreen(at(0.2, 0), h))); await page.waitForTimeout(700); } return picked(); };

  // 1) 식탁: 옆 손잡이로 폭, 앞 손잡이로 깊이
  const table = await put("decor:table", [1.6, 0.74, 0.8]);
  await open();
  check("식탁을 누르면 골라진다", await pick(0.74));
  await drag(await toScreen(at(0.8 + OUT, 0), 0), await toScreen(at(0.8 + OUT + 0.4, 0), 0), async () => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "1125-table-stretch.png") }); });
  let t = await one(table.placement_id);
  check("옆 손잡이를 끌면 식탁 폭이 40 cm 는다", Math.abs(t.size_m[0] - 2.0) < 0.03 && Math.abs(t.size_m[2] - 0.8) < 1e-6, t.size_m.map((v) => v.toFixed(3)).join(" x "));
  check("반대쪽 끝은 그대로다", Math.abs(t.center_xz[0] - t.size_m[0] / 2 - (mid[0] - 0.8)) < 0.005);
  await drag(await toScreen(at(0.2, 0.4 + OUT), 0), await toScreen(at(0.2, 0.4 + OUT + 0.3), 0));
  t = await one(table.placement_id);
  check("앞 손잡이를 끌면 식탁 깊이가 30 cm 는다", Math.abs(t.size_m[2] - 1.1) < 0.03 && Math.abs(t.size_m[0] - 2.0) < 0.03, t.size_m.map((v) => v.toFixed(3)).join(" x "));
  await api(`/api/projects/${pid}/placements/${table.placement_id}`, null, "DELETE");

  // 2) 책상: 손잡이가 없다. 같은 자리를 끌어도 크기는 그대로
  const desk = await put("decor:desk", [1.2, 0.73, 0.6]);
  await open();
  check("책상을 누르면 골라진다", await pick(0.73));
  await drag(await toScreen(at(0.6 + OUT, 0), 0), await toScreen(at(0.6 + OUT + 0.4, 0), 0));
  const d = await one(desk.placement_id);
  check("책상은 끌어도 크기가 그대로다", Math.abs(d.size_m[0] - 1.2) < 1e-6 && Math.abs(d.size_m[2] - 0.6) < 1e-6, d.size_m.join(" x "));
  check("책상에는 크기 조절(숫자 입력) 버튼이 있다", await page.evaluate(() => !!document.getElementById("actSize")));

  check("화면 오류 없음", errors.length === 0, errors.slice(0, 2).join(" | "));
  await browser.close();
  console.log(failed ? `\n${failed}개 실패` : "\n모두 통과");
  process.exit(failed ? 1 : 0);
})();
