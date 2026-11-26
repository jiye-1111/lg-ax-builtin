// 벽 길이 재기 점검: 벽을 누르고 잰 길이를 넣으면 그 벽은 잰 값, 나머지 벽은 그 값에 맞춰 바로잡힌다. 서버를 켠 뒤 실행:
//   uv run lgb-api            (다른 창)
//   node tests/e2e/measure_wall.js [http://localhost:8000] [스크린샷 폴더]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3];
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
  const get = (url) => page.evaluate(async (u) => (await fetch(u)).json(), url);
  const shot = async (name) => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, name) }); };

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/synthetic_room.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await page.waitForSelector("#libTabs", { state: "attached", timeout: 60000 });
  await page.waitForTimeout(4000);

  await page.click("#measureBtn");
  check("벽 재기를 켜면 할 일을 한 문장으로 알려 준다", (await page.isVisible("#measureAsk")) && !(await page.isVisible("#measureMm")), await page.textContent("#measureAsk"));
  await shot("1-ask.png");

  // 벽을 맞힐 때까지 3D 여러 곳을 눌러 본다
  const box = await page.locator("#viewer").boundingBox();
  let picked = false;
  for (const [fx, fy] of [[0.5, 0.3], [0.5, 0.22], [0.3, 0.35], [0.7, 0.35], [0.5, 0.4], [0.2, 0.45], [0.8, 0.45]]) {
    await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy);
    await page.waitForTimeout(400);
    if (await page.isVisible("#measureMm")) { picked = true; break; }
  }
  check("벽을 누르면 입력 카드가 뜬다", picked);
  check("벽 발치에 줄자 선", await page.evaluate(() => document.getElementById("viewer").viewer.tapeShown()));
  const scanText = await page.getAttribute("#measureMm", "placeholder");
  check("스캔 길이를 보기로 보여 준다", /^스캔 [\d,]+$/.test(scanText || ""), scanText);
  const inside = await page.evaluate(() => { const c = document.getElementById("measureCard").getBoundingClientRect(), s = document.querySelector(".canvas").getBoundingClientRect();
    return c.left >= s.left && c.right <= s.right && c.top >= s.top && c.bottom <= s.bottom; });
  check("카드가 3D 칸 안에 있다", inside);
  await shot("2-card.png");

  const scanMm = Number(scanText.replace(/[^\d]/g, ""));
  const target = Math.round(scanMm * 1.01);
  await page.fill("#measureMm", String(target));
  await page.evaluate(() => { window.__said = []; new MutationObserver(() => window.__said.push(document.getElementById("toast").textContent)).observe(document.getElementById("toast"), { childList: true, characterData: true, subtree: true }); });
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => window.__said.length > 0, null, { timeout: 60000, polling: 100 }).catch(() => {});
  const said = await page.evaluate(() => window.__said);
  const told = said.some((t) => t.includes("집 전체 치수"));
  await shot("3-done.png");
  const walls = (await get(`/api/projects/${pid}/room`)).walls;
  const taped = walls.filter((w) => w.measured?.by === "customer");
  check("고른 벽은 잰 값 그대로", taped.length === 1 && Math.round(taped[0].measured.length_m * 1000) === target, JSON.stringify(taped.map((w) => w.measured)));
  const rest = walls.filter((w) => w.measured?.by !== "customer");
  check("나머지 벽은 잰 벽 기준으로 길어졌다", rest.length > 0 && rest.every((w) => w.measured?.by === "reference" && w.measured.length_m > w.scanned.length_m));
  check("끝나면 카드와 줄자 선이 사라진다", !(await page.isVisible("#measureCard")) && !(await page.evaluate(() => document.getElementById("viewer").viewer.tapeShown())));
  check("한 문장으로 알려 준다", told, said.join(" / "));

  // 잰 벽을 다시 누르면 넣은 값이 보이고 지울 수 있다
  const tw = taped[0];
  await page.click("#measureBtn");
  const [mx, my] = await page.evaluate(([x, z]) => document.getElementById("viewer").viewer.toScreen([x, z], 1.2), [(tw.start[0] + tw.end[0]) / 2, (tw.start[1] + tw.end[1]) / 2]);
  await page.mouse.click(mx, my);
  await page.waitForTimeout(400);
  check("잰 벽을 다시 누르면 넣은 값이 보인다", (await page.inputValue("#measureMm")) === target.toLocaleString("ko-KR"), await page.inputValue("#measureMm"));
  await shot("4-again.png");
  await page.click("#measureClear");
  await page.waitForTimeout(2000);
  check("지우면 모두 스캔값으로", (await get(`/api/projects/${pid}/room`)).walls.every((w) => !w.measured));

  // Esc로 그만두기
  await page.click("#measureBtn");
  await page.keyboard.press("Escape");
  check("Esc로 고르기를 끝낸다", !(await page.isVisible("#measureCard")) && !(await page.evaluate(() => document.getElementById("viewer").style.cursor === "crosshair")));

  check("화면 오류 없음", errors.length === 0, errors.join(" | ").slice(0, 400));
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
