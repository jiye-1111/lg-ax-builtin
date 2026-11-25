// 가구 부위별 색 점검: 색 줄에 부위 칩이 뜨고, 3D에서 의자 등받이·침대 헤드를 누르면 그 부위로 넘어가고, 고른 색이 그 부위에만 저장된다.
//   uv run lgb-api            (다른 창)
//   node tests/e2e/part_colours.js [http://localhost:8000] [스크린샷 폴더]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3] || "";
const ROOT = path.resolve(__dirname, "../..");
let failed = 0;
const check = (name, ok, info = "") => { if (!ok) failed += 1; console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`); };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 }); // 소프트웨어 렌더러에서는 2배로 찍으면 화면이 멎는다
  await ctx.addInitScript(() => { try { localStorage.setItem("lgb.tour.v1", "1"); } catch { /* 안내만 건너뛴다 */ } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => { errors.push(String(e.stack || e)); console.log("ERR", String(e.stack || e).slice(0, 500)); });
  const api = (url, body, method = "POST") => page.evaluate(async ([u, b, m]) =>
    (await fetch(u, { method: m, headers: { "Content-Type": "application/json" }, body: b ? JSON.stringify(b) : undefined })).json(), [url, body, method]);
  const toScreen = (c, y = 0) => page.evaluate(([c, y]) => document.getElementById("viewer").viewer.toScreen(c, y), [c, y]);
  const shot = async (name) => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, name) }); };
  const reload = async () => { await page.reload(); await page.waitForFunction(() => document.getElementById("plan")?.children.length > 0, null, { timeout: 90000 }); await page.waitForTimeout(6000); };
  // 색 줄은 물건 옆을 따라다녀서 좌표로 누르면 놓칠 때가 있다. 버튼은 DOM으로 누른다
  const press = async (sel) => { await page.waitForSelector(sel, { state: "attached", timeout: 15000 }); await page.evaluate((q) => document.querySelector(q).click(), sel); await page.waitForTimeout(900); };
  const clickAt = async (c, y) => { const [x, yy] = await toScreen(c, y); await page.mouse.click(x, yy); await page.waitForTimeout(500); };

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  const one = async (id) => (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements.find((q) => q.placement_id === id);
  const room = await api(`/api/projects/${pid}/room`, null, "GET");
  await api(`/api/projects/${pid}/objects/hidden`, { hidden: true }, "PUT"); // 가구를 치우고 빈 방에서 본다
  const mid = room.walls.reduce((a, w) => [a[0] + (w.start[0] + w.end[0]) / 2 / room.walls.length, a[1] + (w.start[1] + w.end[1]) / 2 / room.walls.length], [0, 0]);
  const place = async (sku, dx) => (await api(`/api/projects/${pid}/placements`, { sku, center_xz: [mid[0] + dx, mid[1]], yaw_rad: 0, snap: false })).placement;
  const chair = await place("decor:chair", -1.2), bed = await place("decor:bed", 1.2), table = await place("decor:table", -1.2 - 1.6);
  await reload();
  await page.evaluate(([x, z]) => document.getElementById("viewer").viewer.setCamera({ pos: [x + 0.4, 3.2, z + 4.6], target: [x, 0.5, z] }), mid);
  await page.waitForTimeout(1200);

  // 1) 의자: 방석을 눌러 고르고 색을 열면 부위 칩 셋
  await clickAt([chair.center_xz[0] + 0.1, chair.center_xz[1]], 0.47); // 방향 0이면 가구 정면이 +x 쪽
  await press("#actColor");
  const tabs = () => page.locator("#actBar .cl-part").allTextContents();
  check("의자 색에는 방석·등받이·다리 칩이 있다", JSON.stringify(await tabs()) === JSON.stringify(["방석", "등받이", "다리"]), (await tabs()).join(","));
  check("처음에는 누른 곳(방석)이 골라져 있다", (await page.locator("#actBar .cl-part.on").textContent()) === "방석");

  // 2) 3D에서 등받이를 누르면 등받이로 넘어간다
  await clickAt([chair.center_xz[0] - 0.2, chair.center_xz[1]], 0.72);
  check("등받이를 누르면 등받이 칩이 골라진다", (await page.locator("#actBar .cl-part.on").textContent()) === "등받이");
  await press('#actBar .cl-dot[aria-label="캐러멜"]');
  await page.waitForTimeout(900);
  let c = await one(chair.placement_id);
  check("등받이 색만 바뀐다", c.part_colors?.back === "#B88A5E" && !c.hex, JSON.stringify([c.hex, c.part_colors]));
  check("색을 고른 뒤에도 등받이 칩 그대로", (await page.locator("#actBar .cl-part.on").textContent()) === "등받이");
  await shot("1-chair-back-colour.png");

  // 3) 칩으로 다리 → 블랙, 방석(대표 색) → 다크 그린
  await press('#actBar .cl-part[data-part="frame"]');
  await press('#actBar .cl-dot[aria-label="블랙"]');
  await page.waitForTimeout(900);
  await press('#actBar .cl-part[data-part="seat"]');
  await press('#actBar .cl-dot[aria-label="다크 그린"]');
  await page.waitForTimeout(900);
  c = await one(chair.placement_id);
  check("다리와 방석 색이 따로 저장된다", c.hex === "#44574A" && c.part_colors.frame === "#2A2A2B" && c.part_colors.back === "#B88A5E", JSON.stringify([c.hex, c.part_colors]));
  await press('#actBar .cl-part[data-part="back"]');
  await press("#clReset");
  await page.waitForTimeout(900);
  c = await one(chair.placement_id);
  check("원래 색으로는 그 부위만 되돌린다", !c.part_colors.back && c.hex === "#44574A" && c.part_colors.frame === "#2A2A2B", JSON.stringify([c.hex, c.part_colors]));
  await press("#clDone");

  // 4) 침대: 헤드를 눌러 고르고 색을 열면 헤드부터
  await clickAt([bed.center_xz[0] - 1.0, bed.center_xz[1]], 0.85);
  await press("#actColor");
  check("침대는 헤드·프레임·이불·담요", JSON.stringify(await tabs()) === JSON.stringify(["헤드", "프레임", "이불", "담요"]), (await tabs()).join(","));
  check("헤드를 눌렀으니 헤드가 골라져 있다", (await page.locator("#actBar .cl-part.on").textContent()) === "헤드");
  await press('#actBar .cl-dot[aria-label="블루"]');
  await page.waitForTimeout(900);
  await clickAt([bed.center_xz[0] + 0.3, bed.center_xz[1]], 0.6); // 이불
  check("이불을 누르면 이불 칩으로", (await page.locator("#actBar .cl-part.on").textContent()) === "이불");
  await press('#actBar .cl-dot[aria-label="세이지 그린"]');
  await page.waitForTimeout(900);
  const b = await one(bed.placement_id);
  check("침대 헤드와 이불 색이 따로 저장된다", b.hex === "#5F7896" && b.part_colors?.bedding === "#93A088", JSON.stringify([b.hex, b.part_colors]));
  await shot("2-bed-head-colour.png");
  await press("#clDone");

  // 5) 식탁: 상판을 누르면 상판, 나무 색 점에는 나뭇결 표시
  await clickAt(table.center_xz, 0.74);
  await press("#actColor");
  check("식탁은 상판·다리", JSON.stringify(await tabs()) === JSON.stringify(["상판", "다리"]));
  check("나무 색 점은 나뭇결로 구분된다", await page.locator('#actBar .cl-dot.wood[aria-label="월넛"]').count() === 1);
  await press('#actBar .cl-dot[aria-label="월넛"]');
  await page.waitForTimeout(900);
  await shot("3-table-top-colour.png");
  check("화면 오류가 없다", errors.length === 0, errors.join(" | ").slice(0, 300));
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
