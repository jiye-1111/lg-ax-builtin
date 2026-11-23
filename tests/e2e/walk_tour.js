// 걸어 보기의 둘러보기 줄 점검: 들를 곳, 눌러서 걸어가기, 한 번에 둘러보기, 작은 도면 누르기. 서버를 켠 뒤 실행:
//   uv run lgb-api            (다른 창)
//   node tests/e2e/walk_tour.js [http://localhost:8000]
const { chromium } = require("playwright");

const BASE = process.argv[2] || "http://localhost:8000";
const results = [];
const check = (name, ok, info = "") => {
  results.push({ name, ok: !!ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`);
};

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => { try { localStorage.setItem("lgb.tour.v1", "1"); } catch { /* 안내만 건너뛴다 */ } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const wait = (ms) => page.waitForTimeout(ms);
  const info = () => page.evaluate(() => document.getElementById("viewer").viewer.walkInfo());
  const arrived = async () => { for (let i = 0; i < 30; i++) { await wait(1000); if (!(await info()).gliding) return true; } return false; };

  // 샘플 집에 냉장고 하나
  await page.goto(`${BASE}/#/new`);
  await page.click("[data-sample='0']");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"));
  await page.waitForSelector("#lib .prod");
  const pid = await page.evaluate(() => location.hash.match(/p_\d+/)[0]);
  await fetch(`${BASE}/api/projects/${pid}/placements`, { method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ sku: "G646GBB031", center_xz: [4.2, 0.45], yaw_rad: Math.PI / 2 }) });
  await page.reload();
  await page.waitForSelector("#lib .prod");
  await wait(2500);

  check("걷기 전에는 둘러보기 줄이 없다", await page.$eval("#walkTour", (e) => e.hidden));
  await page.click("#walk");
  await wait(1500);
  const names = await page.$$eval("#wtLine button", (bs) => bs.map((b) => b.textContent.trim()));
  check("들를 곳: 현관에서 시작, 놓은 냉장고와 창 앞 포함", names[0] === "현관" && names.includes("냉장고 앞") && names.includes("창 앞"), names.join(" > "));
  check("현관에 서서 시작", (await page.innerText("#wtName")) === "현관" && !(await info()).blocked);
  check("작은 도면에 들를 곳 점", (await page.$$eval("#stopDots circle", (c) => c.length)) === names.length);

  const at = names.indexOf("냉장고 앞");
  const from = (await info()).pos;
  await page.click(`#wtLine li:nth-child(${at + 1}) button`);
  await wait(700);
  check("누르면 걸어서 간다 (바로 옮겨지지 않는다)", (await info()).gliding);
  check("도착", await arrived());
  const there = (await info()).pos;
  check("냉장고 앞에 섰다", (await page.innerText("#wtName")) === "냉장고 앞" && Math.hypot(there[0] - from[0], there[2] - from[2]) > 1 && !(await info()).blocked, JSON.stringify(there));

  await page.click("#wtPlay");
  await wait(1200);
  check("한 번에 둘러보기를 누르면 이어서 걷는다", (await info()).gliding && (await page.innerText("#wtPlay")).includes("멈추기"));
  await page.keyboard.press("KeyW");
  await wait(400);
  check("직접 걸으면 멈춘다", !(await info()).gliding && (await page.innerText("#wtPlay")).includes("한 번에 둘러보기"));

  const box = await page.$eval("#minimap", (e) => { const r = e.getBoundingClientRect(); return [r.x + r.width * 0.6, r.y + r.height * 0.55]; });
  await page.mouse.click(box[0], box[1]);
  await wait(600);
  check("작은 도면을 누르면 그리로 걸어간다", (await info()).gliding);
  await arrived();

  // 실사로 둘러보기: 이미지 AI는 부르지 않고 서버 응답만 흉내 낸다
  let made = 0;
  await page.route("**/api/projects/*/photoreal", async (route) => {
    made += 1;
    const spot = JSON.parse(route.request().postData()).spot;
    await new Promise((r) => setTimeout(r, 800));
    await route.fulfill({ json: { url: `/img/hero-kitchen.webp?spot=${spot}`, model: "test" } });
  });
  const photoOn = () => page.$eval("#tourPhoto", (e) => !e.hidden && e.classList.contains("on") && e.src);
  await page.click("#wtLine li:nth-child(1) button");
  await arrived();
  await page.click("#render");
  await wait(400);
  check("실사를 누르면 만드는 동안 기다림 표시", !(await page.$eval("#renderWait", (e) => e.hidden)) && (await page.$eval("#render", (e) => e.classList.contains("on"))));
  await wait(2500);
  check("선 곳이 실사로 바뀐다", String(await photoOn()).includes("spot=door"), String(await photoOn()));
  await page.click(`#wtLine li:nth-child(${at + 1}) button`);
  await wait(600);
  check("걸어가는 동안은 3D로 돌아간다", !(await photoOn()));
  await arrived();
  await wait(2800);
  check("다음 곳도 실사로 바뀐다", String(await photoOn()).includes("spot=pl"), String(await photoOn()));
  await page.click("#wtLine li:nth-child(1) button");
  await arrived();
  await wait(1500);
  check("한 번 만든 곳은 다시 만들지 않는다", made === 2 && String(await photoOn()).includes("spot=door"), `만든 횟수 ${made}`);
  await page.click("#render");
  await wait(900);
  check("실사를 다시 누르면 꺼진다", !(await photoOn()));

  await page.click("#viewTop");
  await wait(500);
  check("위에서 보기로 돌아가면 줄이 사라진다", await page.$eval("#walkTour", (e) => e.hidden));
  check("페이지 오류 없음", errors.length === 0, errors.join(" | "));

  await browser.close();
  const ok = results.filter((r) => r.ok).length;
  console.log(`\n${ok}/${results.length} 통과`);
  process.exit(ok === results.length ? 0 : 1);
})();
