// 왼쪽 필터와 화면 배치 점검. 서버를 켠 뒤 실행:
//   uv run lgb-api            (다른 창)
//   node tests/e2e/filter_panel.js [http://localhost:8000]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const ROOT = path.resolve(__dirname, "../..");
let failed = 0;
const check = (name, ok, info = "") => {
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`);
};

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => { try { localStorage.setItem("lgb.tour.v1", "1"); } catch { /* 안내만 건너뛴다 */ } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  const wait = (ms) => page.waitForTimeout(ms);
  const count = async () => Number((await page.textContent("#libCount b")).replace(/,/g, ""));
  const chips = () => page.$$eval("#applied .fchip span", (els) => els.map((e) => e.textContent));
  const width = (sel) => page.$eval(sel, (el) => el.getBoundingClientRect().width);

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await page.waitForSelector("#libTabs");
  await page.click('#libTabs [data-tab="lg"]');
  await page.waitForSelector("#lib .prod");
  await wait(1500);

  // 화면 비율: 3D 약 79%, 제품 탐색 약 21%
  const lib = await width(".lib"), stage = await width(".stage");
  const share = stage / (lib + stage);
  check("3D가 화면의 4분의 3 이상", share >= 0.75 && share <= 0.83, `${Math.round(share * 100)}%`);

  // 필터 순서
  const order = await page.$$eval("#filterBox .fsec h3", (els) => els.map((e) => e.textContent.trim()));
  check("필터 순서: 설치 방식 → 품목 → 가격 범위 → 상세 필터", order.join(">") === "설치 방식>품목>가격 범위>상세 필터", order.join(" > "));

  const all = await count();
  await page.click('#installSeg [data-install="일반"]');
  await wait(300);
  const general = await count();
  check("설치 방식 고르면 목록이 줄어든다", general < all && (await page.getAttribute('#installSeg [data-install="일반"]', "aria-pressed")) === "true", `${all} → ${general}`);

  await page.click('#cats [data-cat="refrigerator"]');
  await wait(300);
  const fridge = await count();
  check("품목 고르기", fridge < general, `${general} → ${fridge}`);

  // 가격: 최대값이 카탈로그 실제 가격 범위 안, 직접 넣기
  const maxMan = Number((await page.inputValue("#pHiIn")).replace(/,/g, ""));
  check("가격 최대값이 실제 가격 범위", maxMan > 0 && maxMan <= 1200, `${maxMan}만원`);
  const rail = await page.$eval("#budgetRail", (el) => { const r = el.getBoundingClientRect(), p = el.closest(".fsec").getBoundingClientRect(); return [r.left - p.left, p.right - r.right]; });
  check("가격 줄이 칸 밖으로 안 나간다", rail[0] >= 0 && rail[1] >= 0);
  await page.fill("#pHiIn", "300");
  await page.press("#pHiIn", "Enter");
  await wait(500);
  const cheap = await count();
  check("최대 금액을 직접 넣으면 목록이 줄어든다", cheap < fridge && cheap > 0, `${fridge} → ${cheap}`);
  const prices = await page.$$eval("#lib .prod .price", (els) => els.map((e) => Number(e.textContent.replace(/[^\d]/g, ""))));
  check("카드에 보이는 가격도 고른 범위 안", prices.length === cheap && prices.every((v) => v <= 3000000), `최고 ${Math.max(...prices).toLocaleString()}원`);

  check("적용된 필터 칩", (await chips()).join("|") === "일반|냉장고|300만원 이하", (await chips()).join(" · "));
  check("적용하기에 개수", (await page.textContent("#applyFilter")).trim() === "적용하기 (3)");

  // 상세 필터
  await page.click("#moreFilter > summary");
  await page.selectOption("#fW", "850-99999");
  await wait(300);
  check("상세 필터 개수 표시", (await page.textContent("#filterOn")).trim() === "1개 적용");

  // 적용하기: 필터를 접고 목록
  await page.click("#applyFilter");
  await wait(600);
  check("적용하기를 누르면 필터가 접히고 칩은 남는다", !(await page.$eval("#filterBox", (el) => el.open)) && (await chips()).length === 4);

  // 칩 ×
  await page.click('#applied [data-clear="fW"]');
  await wait(300);
  check("칩의 ×로 조건 하나만 빼기", (await chips()).length === 3 && (await count()) === cheap);

  // 카드: 사진·이름·모델명·가격·배치 버튼
  const card = await page.$eval("#lib .prod", (li) => ({ img: !!li.querySelector("img"), name: !!li.querySelector(".name")?.textContent, model: !!li.querySelector(".model")?.textContent, price: !!li.querySelector(".price"), place: !!li.querySelector(".place-btn") }));
  check("카드에 사진·이름·모델명·가격·배치 버튼", Object.values(card).every(Boolean), JSON.stringify(card));

  // 배치하기를 연달아 눌러도 놓인다
  const placed = async () => (await (await fetch(`${BASE}/api/projects/${pid}`)).json()).scene_state.placements.length;
  const before = await placed();
  await page.click("#lib .prod .place-btn >> nth=0");
  await wait(2500);
  await page.keyboard.press("Escape");
  await page.click("#lib .prod .place-btn >> nth=1");
  await wait(2500);
  await page.keyboard.press("Escape");
  check("배치하기로 3D에 놓기 (두 번 연달아)", (await placed()) === before + 2, `${before} → ${await placed()}`);

  // 필터 초기화
  await page.click("#filterBox > summary");
  await page.click("#resetFilter");
  await wait(400);
  check("필터 초기화", (await chips()).length === 0 && (await count()) === all);

  // 패널 접기: 3D가 넓어진다
  const w0 = await width(".stage");
  await page.click("#libFold");
  await wait(400);
  const w1 = await width(".stage");
  check("제품 패널을 접으면 3D가 넓어진다", w1 > w0 + 250 && !(await page.isVisible(".lib")), `${Math.round(w0)} → ${Math.round(w1)}px`);
  await page.click("#libFold");
  await wait(300);
  check("다시 펼치기", await page.isVisible(".lib"));

  // 아래 정보 칸 접기
  await page.click('.simsw[data-sim="wifi"]');
  await wait(1200);
  await page.click("#simFold");
  check("아래 정보 칸 접기", !(await page.isVisible("#simctl")));
  await page.click("#simFold");
  check("아래 정보 칸 펼치기", await page.isVisible("#simctl"));

  // 좁은 화면: 3D 꽉, 제품은 서랍
  await page.setViewportSize({ width: 390, height: 844 });
  await wait(600);
  check("좁은 화면은 서랍 배치", await page.$eval(".studio", (el) => el.classList.contains("app")) && !(await page.isVisible("#libFold")));
  check("가로로 넘치지 않는다", await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));

  check("콘솔 오류 없음", errors.length === 0, errors.slice(0, 3).join(" / "));
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
