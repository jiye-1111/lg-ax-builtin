// 전달받은 모델만 내놓는지 점검: 목록에는 묶음 제품만, 놓으면 묶음 모델이 뜬다. 서버를 켠 뒤 실행:
//   uv run lgb-api            (다른 창)
//   node tests/e2e/lineup_only.js [http://localhost:8000] [스크린샷 폴더]
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3];
const ROOT = path.resolve(__dirname, "../..");
const LINEUP = Object.keys(JSON.parse(fs.readFileSync(path.join(ROOT, "data/catalog/lineup.json"), "utf-8")).models);
let failed = 0;
const check = (name, ok, info = "") => { if (!ok) failed += 1; console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`); };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => { try { localStorage.setItem("lgb.tour.v1", "1"); } catch { /* 안내만 건너뛴다 */ } });
  const page = await ctx.newPage();
  const errors = [], missing = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("response", (r) => { if (r.status() === 404 && /\/(models|img)\/products\//.test(r.url())) missing.push(r.url()); });
  const api = (url, body, method = "POST") => page.evaluate(async ([u, b, m]) =>
    (await fetch(u, { method: m, headers: { "Content-Type": "application/json" }, body: b ? JSON.stringify(b) : undefined })).json(), [url, body, method]);

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/apt_living_kitchen.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await page.waitForSelector("#lib [data-sku]", { state: "attached", timeout: 60000 });
  await page.waitForTimeout(1500);

  const listed = await page.evaluate(() => [...document.querySelectorAll("#lib [data-sku]")].map((li) => li.dataset.sku));
  check("목록에 제품이 나온다", listed.length > 0, `${listed.length}줄`);
  check("목록은 전달받은 묶음 제품뿐", listed.every((s) => LINEUP.includes(s)), listed.filter((s) => !LINEUP.includes(s)).join(","));
  const fams = await api("/api/catalog/families", null, "GET");
  const shown = fams.flatMap((f) => f.variants).filter((v) => v.listed && ["ACTIVE", "SOLD_OUT"].includes(v.sale_status));
  check("고를 수 있는 모델은 묶음에 있고 지금 파는 것", shown.length > 0 && shown.every((v) => LINEUP.includes(v.sku)), `${shown.length}개`);
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "lineup-list.png") });

  // 종류별로 하나씩 놓아 본다
  const firstOf = (cat) => fams.find((f) => f.category === cat && f.variants.some((v) => v.listed && v.sale_status === "ACTIVE")).variants.find((v) => v.listed && v.sale_status === "ACTIVE").sku;
  const cats = ["refrigerator", "dishwasher", "wine_cellar", "microwave", "cooktop", "oven"];
  let i = 0;
  for (const c of cats) {
    const r = await api(`/api/projects/${pid}/placements`, { sku: firstOf(c), center_xz: [-1.5 + 0.9 * i++, 0.6], yaw_rad: 0 });
    check(`${c} 놓기`, !!r.placement, r.placement ? r.placement.sku : JSON.stringify(r).slice(0, 120));
  }
  await page.reload();
  await page.waitForSelector("#lib [data-sku]", { state: "attached", timeout: 60000 });
  await page.waitForTimeout(6000);
  const meshes = await page.evaluate(() => {
    const v = document.getElementById("viewer").viewer;
    return v && v.modelStats ? v.modelStats() : null;
  });
  if (meshes) console.log("모델", JSON.stringify(meshes));
  check("없는 모델·사진을 찾지 않는다", missing.length === 0, missing.slice(0, 3).join(" "));
  check("화면 오류 없음", errors.length === 0, errors.slice(0, 2).join(" | "));
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "lineup-placed.png") });

  // 상세 창: 색이 같은 모델은 구성 차이를 같이 적는다
  await page.evaluate(() => document.querySelector('#lib [data-sku="DUE5BGE"], #lib [data-sku="DUE5BGHE"]')?.click());
  await page.waitForTimeout(800);
  const opts = await page.evaluate(() => [...document.querySelectorAll("#pdModel option")].map((o) => o.textContent));
  check("색이 같은 모델은 구성 차이가 보인다", opts.some((t) => t.includes("글라이드 레일")), opts.join(" / "));
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "lineup-detail.png") });

  await browser.close();
  console.log(failed ? `${failed}개 실패` : "모두 통과");
  process.exit(failed ? 1 : 0);
})();
