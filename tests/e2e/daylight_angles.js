// 채광 볕이 보는 각도·움직임에 따라 사라지지 않는지 점검
//   uv run lgb-api            (다른 창)
//   node tests/e2e/daylight_angles.js [http://localhost:8000]
// 느린 PC는 화면을 돌리는 동안 가볍게 그린다. 그때도 볕이 든 자리와 그늘이 멈춰 있을 때와 같아야 한다.
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const ROOT = path.resolve(__dirname, "../..");
const results = [];
const check = (name, ok, info = "") => {
  results.push({ name, ok: !!ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`);
};
const j = async (p) => (await fetch(BASE + p)).json();

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await ctx.addInitScript(() => { try { localStorage.setItem("lgb.tour.v1", "1"); } catch { /* 저장소가 막혀 있어도 계속 */ } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const wait = (ms) => page.waitForTimeout(ms);
  const v3 = (fn, ...a) => page.evaluate(([f, a]) => document.getElementById("viewer").viewer[f](...a), [fn, a]);

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/apt_living_kitchen.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await page.waitForSelector("#lib", { state: "attached" });
  await wait(2500);
  const room = await j(`/api/projects/${pid}/room`);
  const xs = room.walls.flatMap((w) => [w.start[0], w.end[0]]), ys = room.walls.flatMap((w) => [w.start[1], w.end[1]]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  // 방 바닥에 고르게 찍은 점들 (벽에서 30 cm 안쪽)
  const pts = [];
  for (let i = 0; i < 14; i++) for (let k = 0; k < 10; k++) pts.push([x0 + 0.3 + ((x1 - x0 - 0.6) * i) / 13, y0 + 0.3 + ((y1 - y0 - 0.6) * k) / 9]);

  if (await page.locator("#liveBtn").isVisible()) await page.click("#liveBtn");
  await page.click('[data-sim="daylight"]');
  await page.waitForSelector(".sim-res .facing", { timeout: 20000 });
  check("주소를 안 넣어도 볕이 든다 (큰 창을 남쪽으로 보고)", (await v3("sunInfo")).real && /큰 창이 남쪽/.test(await page.innerText("#simctl")));
  // 안내 패널이 바닥을 가리지 않게 접고, 바로 위에서 내려다본다 (가구에 덜 가린다)
  await page.evaluate(() => { document.querySelectorAll("#simctl, .order-card, #bot, .view-stack, .sim-switches").forEach((e) => { e.style.visibility = "hidden"; }); });
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, far = Math.max(x1 - x0, y1 - y0) * 1.5;
  const setTime = (min) => page.$eval("#sunTime", (el, m) => { el.value = String(m); el.dispatchEvent(new Event("input", { bubbles: true })); }, min);

  // 화면을 찍어 바닥 점마다 밝기를 읽는다
  const canvas = page.locator("#viewer canvas").first();
  const lum = async () => {
    const box = await canvas.boundingBox();
    const b64 = (await canvas.screenshot({ type: "png" })).toString("base64");
    const scr = await Promise.all(pts.map((p) => v3("toScreen", p, 0)));
    return page.evaluate(async ([b64, scr, box]) => {
      const img = new Image();
      img.src = "data:image/png;base64," + b64;
      await img.decode();
      const c = document.createElement("canvas");
      c.width = img.width; c.height = img.height;
      const g = c.getContext("2d", { willReadFrequently: true });
      g.drawImage(img, 0, 0);
      const k = img.width / box.width;
      return scr.map(([x, y]) => {
        const px = Math.round((x - box.x) * k), py = Math.round((y - box.y) * k);
        if (px < 2 || py < 2 || px > img.width - 3 || py > img.height - 3) return null;
        const d = g.getImageData(px - 2, py - 2, 5, 5).data;
        let s = 0;
        for (let i = 0; i < d.length; i += 4) s += 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
        return s / 25;
      });
    }, [b64, scr, box]);
  };
  // 볕이 든 점 = 가장 어두운 쪽과 가장 밝은 쪽 사이 중간보다 밝은 점
  const litOf = (L) => {
    const ok = L.filter((x) => x != null).sort((a, b) => a - b);
    const lo = ok[Math.floor(ok.length * 0.05)], hi = ok[Math.floor(ok.length * 0.95)];
    return { mask: L.map((x) => (x == null ? null : x > (lo + hi) / 2)), lo, hi };
  };
  const frac = (m) => m.mask.filter((x) => x).length / m.mask.filter((x) => x != null).length;
  const diff = (a, b) => a.mask.filter((x, i) => x != null && b.mask[i] != null && x !== b.mask[i]).length;

  // 곱게 그릴 때만 있는 접촉 그림자 때문에 가구 가장자리 점 몇 개는 갈릴 수 있다 (140점 가운데 20점까지). 볕이 사라지면 절반쯤이 달라진다
  const SAME = 20;
  const views = [
    ["위에서 똑바로", { pos: [cx, far, cy + 0.01], target: [cx, 0, cy] }],
    ["비스듬히 남동쪽", { pos: [cx + far * 0.5, far * 0.7, cy + far * 0.5], target: [cx, 0, cy] }],
    ["비스듬히 북서쪽", { pos: [cx - far * 0.5, far * 0.7, cy - far * 0.5], target: [cx, 0, cy] }],
    ["가까이", { pos: [cx + 1.5, 3.2, cy + 2.2], target: [cx, 0, cy] }],
  ];
  for (const min of [600, 900]) {
    await v3("setLite", false);
    await setTime(min);
    await wait(1800);
    for (const [name, c] of views) {
      await v3("setLite", false);
      await v3("setCamera", c);
      await wait(900);
      const full = litOf(await lum());
      // 느린 PC가 화면을 돌릴 때처럼 가볍게 그린다
      await v3("setLite", true);
      await wait(900);
      const lite = litOf(await lum());
      const f = frac(full), l = frac(lite), d = diff(full, lite);
      const t = `${Math.floor(min / 60)}시 ${name}`;
      check(`${t}: 볕 든 자리와 그늘이 나뉜다`, f > 0.03 && f < 0.85 && full.hi - full.lo > 25, `볕 ${(f * 100).toFixed(0)}% · 밝기 ${full.lo.toFixed(0)}~${full.hi.toFixed(0)}`);
      check(`${t}: 가볍게 그릴 때도 볕이 그대로다`, d <= SAME && Math.abs(f - l) <= 0.12 && lite.hi - lite.lo > 25, `볕 ${(l * 100).toFixed(0)}% · 다른 점 ${d}개 · 밝기 ${lite.lo.toFixed(0)}~${lite.hi.toFixed(0)}`);
    }
  }

  // 가볍게 그리는 중에 시각을 바꿔도 그림자가 따라온다
  await v3("setCamera", views[0][1]);
  await v3("setLite", true);
  await setTime(600);
  await wait(1800);
  const liteMoved = litOf(await lum());
  await v3("setLite", false);
  await wait(900);
  const fullAfter = litOf(await lum());
  check("가볍게 그리는 중에 시각을 바꿔도 볕이 따라 움직인다", diff(liteMoved, fullAfter) <= SAME, `다른 점 ${diff(liteMoved, fullAfter)}개`);

  // 채광을 껐다 켜도 (가볍게 그리는 중) 볕이 돌아온다
  await v3("setLite", true);
  await page.evaluate(() => document.querySelector('[data-sim="daylight"]').click());
  await wait(1200);
  await page.evaluate(() => document.querySelector('[data-sim="daylight"]').click());
  await page.waitForSelector(".sim-res .facing", { state: "attached", timeout: 20000 });
  await page.evaluate(() => { document.querySelectorAll("#simctl").forEach((e) => { e.style.visibility = "hidden"; }); });
  await wait(1800);
  const again = litOf(await lum());
  check("채광을 껐다 켜도 볕이 돌아온다", diff(again, fullAfter) <= SAME && (await v3("sunInfo")).shell, `다른 점 ${diff(again, fullAfter)}개`);
  await v3("setLite", false);

  check("화면 오류 없음", errors.length === 0, errors.join(" | "));
  await browser.close();
  const bad = results.filter((r) => !r.ok);
  console.log(`\n${results.length - bad.length}/${results.length} 통과`);
  process.exit(bad.length ? 1 : 0);
})();
