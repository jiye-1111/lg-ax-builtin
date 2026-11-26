// 동선: 사람은 한 명, 가전마다 차례로 걷고 바닥에는 지금 걷는 길 하나만. 걷는 모습 캡처도 남긴다.
//   uv run lgb-api  (다른 창)
//   node tests/e2e/flow_one.js [http://localhost:8000]
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const BASE = process.argv[2] || "http://localhost:8000";
const ROOT = path.resolve(__dirname, "../..");
const OUT = path.join(ROOT, "docs/verification/flow-one");
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const check = (name, ok, info = "") => { results.push({ name, ok: !!ok }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`); };
const j = async (p, opt) => (await fetch(BASE + p, opt)).json();
const put = (p, body) => j(p, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
const postj = (p, body) => j(p, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await ctx.addInitScript(() => { try { localStorage.setItem("lgb.tour.v1", "1"); } catch { /* 안내 건너뜀 */ } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const wait = (ms) => page.waitForTimeout(ms);
  const v3 = (fn, ...a) => page.evaluate(([f, a]) => document.getElementById("viewer").viewer[f](...a), [fn, a]);

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await page.waitForSelector("#lib .prod");
  const room = await j(`/api/projects/${pid}/room`);
  const xs = room.walls.flatMap((w) => [w.start[0], w.end[0]]), ys = room.walls.flatMap((w) => [w.start[1], w.end[1]]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  await put(`/api/projects/${pid}/objects/hidden`, { hidden: true });
  await put(`/api/projects/${pid}/marks/start`, { center_xz: [cx, y0 + 1.2] });
  // 가전 셋: 방 여기저기 (정면은 방 가운데 쪽)
  const cat = await j(`/api/catalog`);
  const skus = ["refrigerator", "washer", "styler"].map((c) => cat.find((p) => p.category === c)?.sku).filter(Boolean);
  const spots = [[x0 + 0.6, cy, 0], [x1 - 0.6, cy + 1.5, Math.PI], [cx + 1, y1 - 0.7, -Math.PI / 2]];
  let placed = 0;
  for (let i = 0; i < spots.length && i < skus.length; i++) {
    const r = await postj(`/api/projects/${pid}/placements`, { sku: skus[i], center_xz: spots[i].slice(0, 2), yaw_rad: spots[i][2] });
    if (r.placement) placed += 1;
  }
  check("가전 셋 놓기", placed === 3, String(placed));
  await page.reload();
  await page.waitForSelector("#lib .prod");
  await wait(1500);
  await page.click('[data-sim="flow"]');
  await page.waitForFunction(() => document.getElementById("viewer").viewer.walkersInfo().length > 0, null, { timeout: 20000 }).catch(() => {});
  await wait(800);
  const w = await v3("walkersInfo");
  const f = await j(`/api/projects/${pid}/sim/flow`);
  const reach = Object.values(f.routes).filter((r) => r.reachable).length;
  check("걷는 사람은 한 명", w.length === 1, JSON.stringify(w));
  check("갈 수 있는 길마다 차례로 걷는다", w[0]?.legs === reach && reach >= 2, `${w[0]?.legs}/${reach}`);
  const routes = () => page.$eval("#overlay", (e) => e.querySelectorAll("polyline.route").length);
  check("바닥에는 지금 걷는 길 하나만", (await routes()) === 1, String(await routes()));
  const say = await page.textContent("#flowNow");
  check("지금 어디로 걷는지 한 문장", /앞까지 걸어가요$/.test(say || ""), say);

  // 사람 가까이 카메라: 옆에서 따라가며 몇 장
  const legs = new Set();
  for (let i = 0; i < 8; i++) {
    const p = (await v3("walkersInfo"))[0];
    legs.add(p.leg);
    await v3("setCamera", { pos: [p.pos[0] + 2.2, 1.35, p.pos[1] + 2.2], target: [p.pos[0], 0.85, p.pos[1]] });
    await wait(60);
    if (process.env.SHOTS) await page.screenshot({ path: path.join(OUT, `walk-${i}.png`), clip: { x: 320, y: 120, width: 800, height: 640 } });
    await wait(300);
  }
  // 다음 길로 넘어가는지 (첫 길 왕복이 끝날 때까지 기다린다)
  let changed = false;
  for (let t = 0; t < 40 && !changed; t++) { await wait(500); const p = (await v3("walkersInfo"))[0]; if (p.leg !== w[0].leg) changed = true; }
  check("한 길을 다녀오면 다음 가전으로 간다", changed);
  check("길이 바뀌어도 바닥 길은 하나", (await routes()) === 1);
  await v3("reframe");
  await wait(800);
  await page.screenshot({ path: path.join(OUT, "overview.png") });
  check("페이지 오류 없음", errors.length === 0, errors.join(" | "));
  await browser.close();
  const fail = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - fail}/${results.length} 통과`);
  process.exit(fail ? 1 : 0);
})();
