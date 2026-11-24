// 회전 고리 점검: 고른 가구 둘레 고리 손잡이를 끌면 커서 쪽으로 돌고, 90° 근처에서 착 붙고, 자리는 그대로. 서버를 켠 뒤 실행:
//   uv run lgb-api            (다른 창)
//   node tests/e2e/rotate_ring.js [http://localhost:8000]
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

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  const sofa = (await api(`/api/projects/${pid}/auto-place`, { sku: "decor:sofa" })).placement;
  await api(`/api/projects/${pid}/placements/${sofa.placement_id}`, { center_xz: [-2, -2.5], yaw_rad: Math.PI / 2, snap: false }, "PATCH");
  await page.reload();
  await page.waitForSelector("#libTabs", { state: "attached", timeout: 60000 });
  await page.waitForTimeout(4000);

  const [sx, sy] = await toScreen([-2, -2.5], 0.4);
  await page.mouse.click(sx, sy);
  await page.waitForTimeout(600);
  const r = Math.hypot(sofa.size_m[0], sofa.size_m[2]) / 2 + 0.18; // rotring.ringRadius와 같다
  const at = (a) => toScreen([-2 + r * Math.sin(a), -2.5 + r * Math.cos(a)]);
  const [kx, ky] = await at(0); // 손잡이는 앞(0°)
  await page.mouse.move(kx, ky);
  await page.waitForTimeout(150);
  check("손잡이에 올리면 잡을 수 있는 커서", (await page.evaluate(() => document.querySelector("#viewer canvas").style.cursor)) === "grab");
  await page.mouse.down();
  for (let i = 1; i <= 12; i++) { const [x, y] = await at((Math.PI / 2 - 0.06) * i / 12); await page.mouse.move(x, y); await page.waitForTimeout(25); }
  check("돌리는 동안 각도가 보인다", (await page.evaluate(() => document.querySelector(".rot-chip")?.textContent)) === "90°");
  check("돌리는 동안 메뉴는 숨는다", await page.evaluate(() => document.querySelector(".canvas").classList.contains("moving-item")));
  await page.mouse.up();
  await page.waitForTimeout(1500);
  const after = (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements.find((q) => q.placement_id === sofa.placement_id);
  check("86°쯤 끌면 90°에 붙어 저장된다", Math.abs(after.yaw_rad) < 1e-6, `yaw ${after.yaw_rad}`);
  check("돌려도 자리는 그대로", Math.hypot(after.center_xz[0] + 2, after.center_xz[1] + 2.5) < 1e-6, JSON.stringify(after.center_xz));
  check("오류 없음", errors.length === 0, errors.join(" | "));
  await api(`/api/projects/${pid}`, null, "DELETE").catch(() => {});
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
