// 실사: 와이파이 히트맵을 켠 채 눌러도 표시는 빼고 찍고, 화면에 보이는 물건 전부(놓은 것·스캔 가구·공유기)를 같이 보낸다.
// 이미지 AI는 부르지 않고 보낸 것만 본다. 보낸 화면은 docs/verification/photoreal-scene 에 남긴다.
//   uv run lgb-api  (다른 창)
//   node tests/e2e/photoreal_scene.js [http://localhost:8000]
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const BASE = process.argv[2] || "http://localhost:8000";
const ROOT = path.resolve(__dirname, "../..");
const OUT = path.join(ROOT, "docs/verification/photoreal-scene");
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

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await page.waitForSelector("#lib .prod");
  const room = await j(`/api/projects/${pid}/room`);
  const xs = room.walls.flatMap((w) => [w.start[0], w.end[0]]), ys = room.walls.flatMap((w) => [w.start[1], w.end[1]]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const cat = await j(`/api/catalog`);
  const fridge = cat.find((p) => p.category === "refrigerator")?.sku;
  const ids = [];
  for (const [sku, xz] of [["decor:bed", [cx - 1.5, cy]], ["decor:table", [cx + 1.2, cy]], [fridge, [cx, cy - 1.5]]]) {
    const r = await postj(`/api/projects/${pid}/placements`, { sku, center_xz: xz, snap: false });
    if (r.placement) ids.push(r.placement.placement_id);
  }
  check("침대·식탁·냉장고 놓기", ids.length === 3, String(ids.length));
  await put(`/api/projects/${pid}/router`, { center_xz: [cx + 1.2, cy] }); // 식탁 위
  await page.reload();
  await page.waitForSelector("#lib .prod");
  await wait(1500);
  await page.click('[data-sim="wifi"]');
  await wait(2500);
  await page.screenshot({ path: path.join(OUT, "3d-with-wifi.png") });

  let sent = null;
  await page.route("**/api/projects/*/photoreal", async (route) => {
    sent = JSON.parse(route.request().postData());
    await route.fulfill({ json: { url: "/img/hero-kitchen.webp", model: "test" } });
  });
  await page.click("#render");
  await page.waitForFunction(() => !document.getElementById("renderBox").hidden, null, { timeout: 15000 }).catch(() => {});
  check("실사 요청을 보냈다", !!sent);
  const refs = (sent?.objects || []).map((o) => o.ref);
  check("놓은 것 셋이 목록에 있다", ids.every((id) => refs.includes(id)), refs.join(","));
  check("공유기도 목록에 있다", refs.includes("router"));
  check("자리는 0~1 상자", (sent?.objects || []).every((o) => o.box.length === 4 && o.box.every((v) => v >= 0 && v <= 1) && o.box[2] > o.box[0]));
  if (sent?.image) {
    fs.writeFileSync(path.join(OUT, "sent-objects.json"), JSON.stringify(sent.objects, null, 1));
    fs.writeFileSync(path.join(OUT, "sent-view.png"), Buffer.from(sent.image.split(",")[1], "base64"));
    // 히트맵(초록·노랑)이 빠졌는지: 보낸 그림에서 채도 높은 초록·노랑 픽셀 비율
    const ratio = await page.evaluate(async (url) => {
      const img = new Image();
      img.src = url;
      await img.decode();
      const cv = Object.assign(document.createElement("canvas"), { width: 384, height: 256 });
      const g = cv.getContext("2d");
      g.drawImage(img, 0, 0, 384, 256);
      const d = g.getImageData(0, 0, 384, 256).data;
      let n = 0;
      for (let i = 0; i < d.length; i += 4) { const [r, gg, b] = [d[i], d[i + 1], d[i + 2]]; if (gg > 150 && gg - b > 60 && Math.abs(r - gg) < 90 && r + gg > 300) n++; }
      return n / (384 * 256);
    }, sent.image);
    check("와이파이 표시는 빼고 찍었다", ratio < 0.01, ratio.toFixed(4));
  }
  check("화면 오류 없음", errors.length === 0, errors.join(" | "));
  await browser.close();
  const bad = results.filter((r) => !r.ok);
  console.log(bad.length ? `${bad.length} FAIL` : "ALL PASS");
  process.exit(bad.length ? 1 : 0);
})();
