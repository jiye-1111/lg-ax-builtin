// 하우니 점검: 배치 추천이 1·2·3번 그림과 함께 뜨고 번호를 고르면 놓인다, 눌러서 답하면 생활에 맞는 가전을 고른다,
// 가구를 놓으면 '더하면 좋은 것'을 먼저 말해 주고 한 번에 더한다.
//   uv run lgb-api            (다른 창)
//   node tests/e2e/hauni.js [http://localhost:8000] [스크린샷 폴더] [샘플 usdz]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3] || "";
const ROOT = path.resolve(__dirname, "../..");
const HOME = process.argv[4] || path.join(ROOT, "data/samples/apt_living_kitchen.usdz");
let failed = 0;
const check = (name, ok, info = "") => { if (!ok) failed += 1; console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`); };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: SHOTS ? Number(process.env.SHOT_SCALE) || 2 : 1 });
  await ctx.addInitScript(() => { try { localStorage.setItem("lgb.tour.v1", "1"); } catch { /* 안내만 건너뛴다 */ } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.stack || e)));
  const api = (url, body, method = "POST") => page.evaluate(async ([u, b, m]) =>
    (await fetch(u, { method: m, headers: { "Content-Type": "application/json" }, body: b ? JSON.stringify(b) : undefined })).json(), [url, body, method]);
  const shot = async (name) => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, name), animations: "disabled", timeout: 60000 }).catch((e) => console.log("화면 캡처 실패", name, String(e).slice(0, 80))); };
  const placements = async (pid) => (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements;

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", HOME);
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await page.waitForFunction(() => document.getElementById("plan")?.children.length > 0, null, { timeout: 90000 });
  await page.waitForTimeout(4000);

  // 1) 배치 추천: 1·2·3번 + 놓아 본 그림
  await page.click("#botBtn");
  await page.fill("#botIn", "호텔 같은 침실로 꾸며 줘");
  await page.press("#botIn", "Enter");
  await page.waitForSelector("#botLog .combo", { timeout: 90000 });
  const n = await page.locator("#botLog .combo").count();
  check("배치 추천이 2~3개 뜬다", n >= 2 && n <= 3, `${n}개`);
  await page.waitForFunction((k) => document.querySelectorAll("#botLog .combo-shot img").length === k, n, { timeout: 60000 }).catch(() => {});
  const imgs = await page.$$eval("#botLog .combo-shot img", (els) => els.map((e) => [e.src.slice(0, 22), e.naturalWidth, e.src.length + ":" + e.src.slice(2000, 2040)]));
  check("추천마다 놓아 본 그림이 붙는다", imgs.length === n && imgs.every((i) => i[0].startsWith("data:image/jpeg") && i[1] >= 400), JSON.stringify(imgs));
  check("그림이 서로 다르다", new Set(imgs.map((i) => i[2])).size === imgs.length);
  const nos = await page.$$eval("#botLog .combo-no", (els) => els.map((e) => e.textContent));
  check("1·2·3 번호가 붙는다", nos.join("") === "123".slice(0, n), nos.join(","));
  check("그림을 찍은 뒤에도 놓인 것은 그대로다 (미리보기가 장면을 바꾸지 않는다)", (await placements(pid)).length === 0);
  await page.evaluate(() => document.querySelector("#botLog .combo")?.scrollIntoView({ block: "start" }));
  await shot("hauni-1-combos.png");
  // 말로 고르기
  await page.fill("#botIn", "2번");
  await page.press("#botIn", "Enter");
  await page.waitForFunction(() => document.querySelector("#botLog .combo.on"), null, { timeout: 30000 });
  const after = await placements(pid);
  check("'2번'이라고 말하면 2번 배치가 한 번에 놓인다", after.length >= 2 && after.every((x) => x.combo === "c2"), `${after.length}개`);
  check("LG 가전이 같이 놓인다", after.some((x) => x.kind !== "decor"));
  await page.click("#botClose");
  await page.waitForTimeout(2500);
  await shot("hauni-2-applied.png");

  // 2) 더하면 좋은 것: 조합을 놓은 뒤 하우니가 먼저 말을 건다
  await page.waitForSelector("#botHint:not([hidden])", { timeout: 15000 }).catch(() => {});
  const hintText = await page.$eval("#botHint span", (e) => e.textContent).catch(() => "");
  check("놓고 나면 하우니가 먼저 한 문장으로 권한다", !!hintText && hintText.endsWith("요"), hintText);
  await shot("hauni-3-hint.png");
  await page.click("#botHint [data-open]");
  await page.waitForFunction(() => document.querySelector("#botLog .addons [data-addon]"), null, { timeout: 10000 });
  const rows = await page.locator("#botLog .addons li").count();
  check("더하면 좋은 것이 1~3개", rows >= 1 && rows <= 3, `${rows}개`);
  await shot("hauni-4-addons.png");
  const before = (await placements(pid)).length;
  await page.click("#botLog .addons [data-addon]");
  await page.waitForFunction(() => [...document.querySelectorAll("#botLog .addons [data-addon]")].some((b) => b.textContent === "더했어요"), null, { timeout: 30000 });
  const now = await placements(pid);
  check("'더하기' 한 번으로 놓인다", now.length > before, `${before} → ${now.length}`);
  check("더한 것은 들어가는 자리에 놓였다", now.slice(before).every((x) => x.verdict !== "no_fit"));

  // 3) 내게 맞는 가전: 눌러서 답하기
  await page.click('#botEx [data-act="persona"]');
  await page.click('#botLog .persona [data-people="4인 가족"]');
  await page.click('#botLog .persona [data-life="맞벌이"]');
  await page.click('#botLog .persona [data-life="반려동물과 살아요"]');
  await page.evaluate(() => document.querySelector("#botLog .persona")?.scrollIntoView({ block: "center" }));
  await shot("hauni-5-persona.png");
  await page.click("#botLog .persona [type=submit]");
  await page.waitForFunction(() => document.querySelector("#botLog .msg.hb:last-child .bot-prods [data-try]"), null, { timeout: 90000 });
  const picks = await page.locator("#botLog .msg.hb:last-child .bot-prods li").count();
  const subs = await page.locator("#botLog .msg.hb:last-child .bot-sub").count();
  check("생활에 맞춘 가전이 이유와 함께 뜬다", picks >= 2, `${picks}개`);
  check("함께 보면 좋은 가전(식기세척기·공기청정기)이 따로 뜬다", subs === 1);
  await page.evaluate(() => { const l = document.getElementById("botLog"); l.scrollTop = l.scrollHeight; });
  await shot("hauni-6-persona-result.png");

  check("화면 오류 없음", errors.length === 0, errors.slice(0, 2).join(" | "));
  await browser.close();
  console.log(failed ? `\n${failed}개 실패` : "\n모두 통과");
  process.exit(failed ? 1 : 0);
})();
