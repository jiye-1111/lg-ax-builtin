// 벽에 붙일 때 방향 지키기 점검: 직접 옆으로 돌려 둔 냉장고를 벽으로 끌면 다시 돌아가지 않고 옆면이 벽에 붙는다.
//   uv run lgb-api            (다른 창)
//   node tests/e2e/wall_keep_turn.js [http://localhost:8000] [스크린샷 폴더]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3] || "";
const ROOT = path.resolve(__dirname, "../..");
let failed = 0;
const check = (name, ok, info = "") => { if (!ok) failed += 1; console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`); };
const turn = (a) => Math.abs(Math.atan2(Math.sin(a), Math.cos(a)));

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
  const reload = async () => { await page.reload(); await page.waitForFunction(() => !!document.querySelector("#lib [data-sku]") && document.getElementById("plan")?.children.length > 0, null, { timeout: 60000 }); await page.waitForTimeout(2500); };
  const until = async (fn, ms = 25000) => { for (const t0 = Date.now(); Date.now() - t0 < ms;) { if (await fn()) return true; await page.waitForTimeout(500); } return false; };
  const picked = () => page.evaluate(() => !document.getElementById("actBar").hidden);

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await api(`/api/projects/${pid}/objects/hidden`, { hidden: true });
  // 벽에 대지 않아도 되는 일반 냉장고 (폭과 깊이가 달라야 옆면이 붙었는지 알 수 있다)
  const fams = await api("/api/catalog/families", null, "GET");
  const sku = fams.filter((f) => f.category === "refrigerator").flatMap((f) => f.variants).find((v) => !v.mount && !v.slot)?.sku;
  check("벽에 안 대도 되는 냉장고가 있다", !!sku, sku);
  const at0 = (await api(`/api/projects/${pid}/auto-place`, { sku })).placement; // 벽에 등을 대고 놓인다
  const [w, , d] = at0.size_m, n = [Math.cos(at0.yaw_rad), Math.sin(at0.yaw_rad)], id = at0.placement_id;
  const out = (m) => [at0.center_xz[0] + n[0] * m, at0.center_xz[1] + n[1] * m];
  const get = async () => (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements.find((q) => q.placement_id === id);
  await api(`/api/projects/${pid}/placements/${id}`, { center_xz: out(1.2), yaw_rad: at0.yaw_rad, snap: false }, "PATCH");
  await reload();
  const eye = out(4.2), aim = out(0.6);
  await until(() => page.evaluate(() => document.getElementById("viewer").viewer.stats().products > 0));
  await page.evaluate(([e, a]) => document.getElementById("viewer").viewer.setCamera({ pos: [e[0], 3.6, e[1]], target: [a[0], 0.5, a[1]] }), [eye, aim]);
  await page.waitForTimeout(2500);

  for (let i = 0; i < 10 && !(await picked()); i++) { await page.mouse.click(...(await toScreen(out(1.2), 1.0))); await page.waitForTimeout(700); }
  check("냉장고를 누르면 골라진다", await picked());
  await page.keyboard.press("r"); await page.keyboard.press("r"); // 45°씩 두 번 = 옆으로
  await until(async () => turn((await get()).yaw_rad - at0.yaw_rad - Math.PI / 2) < 0.01);
  const side = (await get()).yaw_rad;
  check("R 두 번으로 옆을 본다", turn(side - at0.yaw_rad - Math.PI / 2) < 0.01, side.toFixed(3));

  // 벽으로 끌고 간다: 전에는 여기서 정면이 방 안을 보게 다시 돌아갔다
  const from = await toScreen(out(1.2), 1.0), to = await toScreen(out(0.05), 1.0);
  await page.mouse.move(...from); await page.mouse.down();
  for (let i = 1; i <= 14; i++) { await page.mouse.move(from[0] + ((to[0] - from[0]) * i) / 14, from[1] + ((to[1] - from[1]) * i) / 14); await page.waitForTimeout(40); }
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "1125-wall-keep-turn.png") });
  await page.mouse.up(); await page.waitForTimeout(2500);
  const x = await get();
  const off = (x.center_xz[0] - at0.center_xz[0]) * n[0] + (x.center_xz[1] - at0.center_xz[1]) * n[1]; // 등을 붙였을 때 자리에서 벽 반대쪽으로
  check("벽에 붙여도 돌려 둔 방향 그대로다", turn(x.yaw_rad - side) < 0.01, `${side.toFixed(3)} → ${x.yaw_rad.toFixed(3)}`);
  check("옆면이 벽에 붙었다", Math.abs(off - (w - d) / 2) < 0.06, `벽 쪽으로 ${off.toFixed(3)} (폭 ${w}, 깊이 ${d})`);

  check("화면 오류 없음", errors.length === 0, errors.slice(0, 2).join(" | "));
  await browser.close();
  console.log(failed ? `\n${failed}개 실패` : "\n모두 통과");
  process.exit(failed ? 1 : 0);
})();
