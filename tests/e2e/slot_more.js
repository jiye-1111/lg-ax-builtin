// 끼워 넣기 더 보기: 아일랜드를 앞뒤로 늘린다, 끄는 동안에도 장이 칸을 내준 모습이 보인다,
// 아일랜드에 끼우면 상판이 이어지고 평면에도 그려진다, 싱크대는 끝에서만 준다.
//   uv run lgb-api            (다른 창)
//   node tests/e2e/slot_more.js [http://localhost:8000] [스크린샷 폴더]
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
  const shot = async (name) => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, name) }); };
  const reload = async () => { await page.reload(); await page.waitForFunction(() => !!document.querySelector("#lib [data-sku]") && document.getElementById("plan")?.children.length > 0, null, { timeout: 60000 }); await page.waitForTimeout(2500); };
  const until = async (fn, ms = 25000) => { for (const t0 = Date.now(); Date.now() - t0 < ms;) { if (await fn()) return true; await page.waitForTimeout(500); } return false; };
  const picked = () => page.evaluate(() => !document.getElementById("actBar").hidden);
  const drag = async (from, to, mid) => {
    await page.mouse.move(...from); await page.mouse.down();
    for (let i = 1; i <= 12; i++) { await page.mouse.move(from[0] + ((to[0] - from[0]) * i) / 12, from[1] + ((to[1] - from[1]) * i) / 12); await page.waitForTimeout(40); }
    if (mid) await mid();
    await page.mouse.up(); await page.waitForTimeout(2500);
  };

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  const all = async () => (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements;
  await api(`/api/projects/${pid}/objects/hidden`, { hidden: true }); // 가구를 치우고 빈 방에서 본다
  const isl = (await api(`/api/projects/${pid}/auto-place`, { sku: "decor:island", size_m: [1.8, 0.9, 0.9] })).placement;
  const ux = Math.cos(isl.yaw_rad - Math.PI / 2), uz = Math.sin(isl.yaw_rad - Math.PI / 2), fx = Math.cos(isl.yaw_rad), fz = Math.sin(isl.yaw_rad);
  const at = (u, v = 0) => [isl.center_xz[0] + ux * u + fx * v, isl.center_xz[1] + uz * u + fz * v];
  await reload();
  const view = () => page.evaluate(([e, a]) => document.getElementById("viewer").viewer.setCamera({ pos: [e[0], 3.4, e[1]], target: [a[0], 0.4, a[1]] }), [at(0.4, 3.0), at(0, 0.5)]);
  await until(() => page.evaluate(() => document.getElementById("viewer").viewer.stats().products > 0));
  await view();
  await page.waitForTimeout(2500);

  // 1) 아일랜드를 고르면 앞뒤 손잡이가 나오고, 앞쪽을 끌면 깊이가 는다 (뒤는 그대로)
  for (let i = 0; i < 10 && !(await picked()); i++) { await page.mouse.click(...(await toScreen(at(0.5, 0), 0.9))); await page.waitForTimeout(700); }
  check("아일랜드를 누르면 골라진다", await picked());
  await drag(await toScreen(at(0, 0.45 + OUT), 0), await toScreen(at(0, 0.45 + OUT + 0.3), 0), () => shot("1125-island-deepening.png"));
  let now = (await all()).find((q) => q.placement_id === isl.placement_id);
  check("앞쪽 손잡이를 끌면 깊이가 30 cm 는다", Math.abs(now.size_m[2] - 1.2) < 0.03 && Math.abs(now.size_m[0] - 1.8) < 1e-6, now.size_m.map((v) => v.toFixed(3)).join(" x "));
  const backOf = (q) => (q.center_xz[0] - isl.center_xz[0]) * fx + (q.center_xz[1] - isl.center_xz[1]) * fz - q.size_m[2] / 2;
  check("뒤쪽 끝은 그대로다", Math.abs(backOf(now) + 0.45) < 0.005, backOf(now).toFixed(3));
  await page.evaluate(() => document.getElementById("undo").click());
  await until(async () => Math.abs((await all()).find((q) => q.sku === "decor:island").size_m[2] - 0.9) < 1e-6);
  check("되돌리면 깊이가 돌아온다", Math.abs((await all()).find((q) => q.sku === "decor:island").size_m[2] - 0.9) < 1e-6);

  // 2) 바닥에 둔 식기세척기를 아일랜드로 끌면, 놓기 전에도 아일랜드가 칸을 내준 모습이 보인다
  const dw0 = (await api(`/api/projects/${pid}/placements`, { sku: DISH, center_xz: at(0, 1.6), yaw_rad: isl.yaw_rad, snap: false, slot: false })).placement;
  await reload();
  await view();
  await page.waitForTimeout(1000);
  for (let i = 0; i < 10 && !(await picked()); i++) { await page.mouse.click(...(await toScreen(at(0, 1.6), 0.5))); await page.waitForTimeout(700); }
  check("식기세척기를 누르면 골라진다", await picked());
  let seen = null;
  await drag(await toScreen(at(0, 1.6), 0.5), await toScreen(at(0.2, 0.3), 0.5), async () => {
    seen = await page.evaluate(() => document.getElementById("viewer").viewer.carved());
    await shot("1125-slot-drag-preview.png");
  });
  check("끄는 동안 아일랜드가 갈라진 모습으로 보인다", seen && seen.pieces >= 3 && seen.hidden >= 1, JSON.stringify(seen));
  const dw = (await all()).find((q) => q.placement_id === dw0.placement_id);
  check("놓으면 아일랜드 안에 끼워진다", !!dw?.slot && dw.slot.look === "island" && dw.verdict !== "no_fit", JSON.stringify(dw?.slot) + " " + dw?.reasons.map((r) => r.code).join(","));
  check("아일랜드가 양옆 두 칸으로 갈라졌다", (await all()).filter((q) => q.sku === "decor:island").length === 2);
  check("미리 보던 조각은 지워졌다", (await page.evaluate(() => document.getElementById("viewer").viewer.carved())).pieces === 0);
  check("평면에도 이어진 상판이 그려진다", await page.evaluate(() => !!document.querySelector("#plan .placed.under rect.counter")));
  await page.mouse.click(...(await toScreen(at(0, 2.6), 0)));
  await page.waitForTimeout(800);
  await shot("1125-slot-island.png");

  // 3) 싱크대 한가운데에 놓아도 싱크대는 갈라지지 않고 끝에서만 준다
  const sink = (await api(`/api/projects/${pid}/auto-place`, { sku: "decor:sink", size_m: [1.6, 0.88, 0.6] })).placement;
  const r = await api(`/api/projects/${pid}/placements`, { sku: DISH, center_xz: sink.center_xz, yaw_rad: sink.yaw_rad, snap: false });
  const sinks = (await all()).filter((q) => q.sku === "decor:sink");
  check("싱크대는 한 개 그대로이고 식기세척기만큼 줄었다", sinks.length === 1 && Math.abs(sinks[0].size_m[0] + r.placement.size_m[0] - 1.6) < 0.003 && !!r.placement.slot,
    sinks.map((q) => q.size_m[0].toFixed(3)).join(" + "));

  check("화면 오류 없음", errors.length === 0, errors.slice(0, 2).join(" | "));
  await browser.close();
  console.log(failed ? `\n${failed}개 실패` : "\n모두 통과");
  process.exit(failed ? 1 : 0);
})();
