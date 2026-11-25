// 아일랜드 식탁과 후드 점검: 가구 목록에 뜨고, 인덕션을 놓으면 후드가 같이 달리고(벽 쪽은 벽 후드, 아일랜드는 천장 후드), 인덕션을 옮기면 따라간다.
//   uv run lgb-api            (다른 창)
//   node tests/e2e/hood_island.js [http://localhost:8000] [스크린샷 폴더]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3] || "";
const ROOT = path.resolve(__dirname, "../..");
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
  const reload = async () => { await page.reload(); await page.waitForFunction(() => document.getElementById("plan")?.children.length > 0, null, { timeout: 90000 }); await page.waitForTimeout(5000); };

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  const all = async () => (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements;
  const hoods = async () => (await all()).filter((q) => q.sku === "decor:hood" || q.sku === "decor:islandhood");
  const room = await api(`/api/projects/${pid}/room`, null, "GET");
  await api(`/api/projects/${pid}/objects/hidden`, { hidden: true }, "PUT"); // 가구를 치우고 빈 방에서 본다
  const mid = room.walls.reduce((a, w) => [a[0] + (w.start[0] + w.end[0]) / 2 / room.walls.length, a[1] + (w.start[1] + w.end[1]) / 2 / room.walls.length], [0, 0]);
  const cat = (await api(`/api/catalog`, null, "GET"));
  const list = cat.products || cat.items || cat;
  const cook = list.find((p) => p.category === "cooktop" && p.listed !== false && p.sale_status === "ACTIVE");
  check("놓아 볼 인덕션이 목록에 있다", !!cook, cook?.sku);

  // 1) 가구 목록
  await reload();
  await page.click('#libTabs [data-tab="furniture"]');
  check("가구에 아일랜드 식탁이 있다", await page.locator('#decorLib [data-decor="decor:islandtable"]').count() === 1);
  await shot("1-furniture-tab.png");
  await page.click('#libTabs [data-tab="storage"]');
  check("수납에 후드가 있다", await page.locator('#decorLib [data-decor="decor:hood"]').count() === 1);
  check("아일랜드 후드는 목록에 따로 없다", await page.locator('#decorLib [data-decor="decor:islandhood"]').count() === 0);

  // 2) 아일랜드 식탁 위 인덕션 → 천장에서 내려오는 후드
  const isl = (await api(`/api/projects/${pid}/placements`, { sku: "decor:islandtable", center_xz: mid, yaw_rad: 0, snap: false })).placement;
  const c1 = (await api(`/api/projects/${pid}/placements`, { sku: cook.sku, center_xz: mid, yaw_rad: 0, snap: false })).placement;
  check("인덕션이 아일랜드 식탁 위에 놓인다", c1.on === isl.placement_id && c1.verdict !== "no_fit", c1.reasons.map((r) => r.code).join(","));
  let hs = await hoods();
  check("아일랜드 위 인덕션에는 천장 후드가 달린다", hs.length === 1 && hs[0].sku === "decor:islandhood" && hs[0].over === c1.placement_id);

  // 3) 벽에 붙인 하부장 위 인덕션 → 벽 후드
  const cab = (await api(`/api/projects/${pid}/auto-place`, { sku: "decor:basecab" })).placement;
  const c2 = (await api(`/api/projects/${pid}/placements`, { sku: cook.sku, center_xz: cab.center_xz, yaw_rad: cab.yaw_rad, snap: false })).placement;
  hs = await hoods();
  const wallHood = hs.find((h) => h.over === c2.placement_id);
  check("벽 쪽 인덕션에는 벽 후드가 달린다", !!wallHood && wallHood.sku === "decor:hood" && wallHood.hung === true, wallHood && `밑면 ${wallHood.base_m} m`);
  check("후드는 인덕션 윗면에서 70 cm 위", !!wallHood && Math.abs(wallHood.base_m - (c2.base_m + c2.size_m[1] + 0.7)) < 0.01);
  check("주문 목록에는 인덕션만 들어간다", (await all()).filter((q) => q.kind !== "decor").length === 2);

  await reload();
  await shot("2-island-and-wall-hood.png");
  if (SHOTS) { // 가까이에서 본 모습
    for (const [name, at] of [["2a-island-close.png", c1], ["2b-wall-close.png", c2]]) {
      const [zx, zy] = await toScreen(at.center_xz, 1.2);
      await page.mouse.move(zx, zy);
      for (let i = 0; i < 9; i++) { await page.mouse.wheel(0, -240); await page.waitForTimeout(120); }
      await page.waitForTimeout(1500);
      await shot(name);
      for (let i = 0; i < 9; i++) { await page.mouse.wheel(0, 240); await page.waitForTimeout(120); }
      await page.waitForTimeout(800);
    }
  }

  // 4) 화면에서 아일랜드 위 인덕션을 골라 끌면 후드가 따라간다
  const before = (await hoods()).find((h) => h.over === c1.placement_id);
  const [x0, y0] = await toScreen(c1.center_xz, c1.base_m + 0.03);
  await page.mouse.click(x0, y0);
  await page.waitForTimeout(600);
  const to = [c1.center_xz[0], c1.center_xz[1] + 0.25];
  const [x1, y1] = await toScreen(to, c1.base_m + 0.03);
  await page.mouse.move(x0, y0);
  await page.mouse.down();
  await page.mouse.move((x0 + x1) / 2, (y0 + y1) / 2, { steps: 6 });
  await page.mouse.move(x1, y1, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(2500);
  const moved = (await all()).find((q) => q.placement_id === c1.placement_id);
  const after = (await hoods()).find((h) => h.over === c1.placement_id);
  check("인덕션이 끌린다", Math.hypot(moved.center_xz[0] - c1.center_xz[0], moved.center_xz[1] - c1.center_xz[1]) > 0.05);
  check("후드가 인덕션을 따라간다", !!after && after.placement_id === before.placement_id && Math.hypot(after.center_xz[0] - moved.center_xz[0], after.center_xz[1] - moved.center_xz[1]) < 0.02);
  await shot("3-hood-follows.png");

  // 5) 후드를 지우면 다시 생기지 않고, 목록에서 후드를 누르면 다시 달린다
  await api(`/api/projects/${pid}/placements/${after.placement_id}`, null, "DELETE");
  check("지운 후드는 그대로 없다", !(await hoods()).some((h) => h.over === c1.placement_id));
  const again = await api(`/api/projects/${pid}/auto-place`, { sku: "decor:hood" });
  check("후드를 다시 넣으면 그 인덕션 위에 달린다", again.placement?.over === c1.placement_id);

  check("화면 오류 없음", errors.length === 0, errors[0] || "");
  await browser.close();
  console.log(failed ? `\n실패 ${failed}개` : "\n모두 통과");
  process.exit(failed ? 1 : 0);
})();
