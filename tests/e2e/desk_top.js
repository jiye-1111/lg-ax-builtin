// 작은 가전을 책상 위로 점검: 바닥에 둔 미니 와인셀러를 책상으로 끌면 책상 위에 올라간다.
//   uv run lgb-api            (다른 창)
//   node tests/e2e/desk_top.js [http://localhost:8000] [스크린샷 폴더]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3] || "";
const ROOT = path.resolve(__dirname, "../..");
const WINE = "W0082GLE";
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

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  const desk = (await api(`/api/projects/${pid}/auto-place`, { sku: "decor:desk" })).placement;
  const f = [Math.cos(desk.yaw_rad), Math.sin(desk.yaw_rad)], out = (m) => [desk.center_xz[0] + f[0] * m, desk.center_xz[1] + f[1] * m];
  const wine = (await api(`/api/projects/${pid}/placements`, { sku: WINE, center_xz: out(1.3), yaw_rad: desk.yaw_rad, snap: false })).placement;
  check("바닥에 놓인 와인셀러", wine.base_m === 0 && wine.tabletop === true, `base ${wine.base_m} tabletop ${wine.tabletop}`);
  const get = async () => (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements.find((q) => q.placement_id === wine.placement_id);
  await page.reload();
  await page.waitForFunction(() => !!document.querySelector("#lib [data-sku]") && document.getElementById("plan")?.children.length > 0, null, { timeout: 60000 });
  await until(() => page.evaluate(() => document.getElementById("viewer").viewer.stats().products > 0));
  await page.evaluate(([e, a]) => document.getElementById("viewer").viewer.setCamera({ pos: [e[0], 3.2, e[1]], target: [a[0], 0.5, a[1]] }), [out(4.0), out(0.5)]);
  await page.waitForTimeout(2500);

  for (let i = 0; i < 10 && !(await picked()); i++) { await page.mouse.click(...(await toScreen(out(1.3), 0.25))); await page.waitForTimeout(700); }
  check("와인셀러를 누르면 골라진다", await picked());
  const from = await toScreen(out(1.3), 0.25), to = await toScreen(desk.center_xz, desk.size_m[1]);
  await page.mouse.move(...from); await page.mouse.down();
  for (let i = 1; i <= 14; i++) { await page.mouse.move(from[0] + ((to[0] - from[0]) * i) / 14, from[1] + ((to[1] - from[1]) * i) / 14); await page.waitForTimeout(40); }
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "1125-wine-on-desk-drag.png") });
  await page.mouse.up(); await page.waitForTimeout(2500);
  const x = await get();
  check("책상 위에 올라갔다", x.on === desk.placement_id && Math.abs(x.base_m - desk.size_m[1]) < 1e-6, `on ${x.on} base ${x.base_m}`);
  const codes = (q) => q.reasons.map((r) => r.code);
  check("책상과 겹친다고 나오지 않는다", !codes(x).includes("overlaps_placement") && !codes(x).includes("outside_room"), codes(x).join(","));
  const host = (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements.find((q) => q.placement_id === desk.placement_id);
  check("책상도 겹침으로 나오지 않는다", !codes(host).includes("overlaps_placement"), codes(host).join(","));
  await page.mouse.click(5, 300); await page.waitForTimeout(800);
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "1125-wine-on-desk.png") });

  check("화면 오류 없음", errors.length === 0, errors.slice(0, 2).join(" | "));
  await browser.close();
  console.log(failed ? `\n${failed}개 실패` : "\n모두 통과");
  process.exit(failed ? 1 : 0);
})();
