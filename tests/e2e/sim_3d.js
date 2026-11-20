// 와이파이 공유기 3D·동선 걷는 사람 3D 점검. 서버를 켠 뒤 실행:
//   uv run lgb-api            (다른 창)
//   node tests/e2e/sim_3d.js [http://localhost:8000]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const ROOT = path.resolve(__dirname, "../..");
const OUT = path.join(ROOT, "docs/verification");
const results = [];
const check = (name, ok, info = "") => {
  results.push({ name, ok: !!ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`);
};
const j = async (p, opt) => (await fetch(BASE + p, opt)).json();
const put = (p, body) => j(p, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
const emoji = /\p{Extended_Pictographic}/u;

(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const wait = (ms) => page.waitForTimeout(ms);
  const v3 = (fn, ...a) => page.evaluate(([f, a]) => document.getElementById("viewer").viewer[f](...a), [fn, a]);
  const toScreen = (pt, y = 0) => v3("toScreen", pt, y);

  // 실제 UGScan 스캔으로 집 만들기
  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await page.waitForSelector("#lib .prod");
  await wait(2500);
  const room = await j(`/api/projects/${pid}/room`);
  const xs = room.walls.flatMap((w) => [w.start[0], w.end[0]]), ys = room.walls.flatMap((w) => [w.start[1], w.end[1]]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;

  // ---- 와이파이 ----
  await page.click('[data-sim="wifi"]');
  await wait(500);
  await page.click("#bestRouter");
  await wait(4000);
  let pj = await j(`/api/projects/${pid}`);
  await page.waitForFunction(() => document.getElementById("viewer").viewer.routerInfo().visible, null, { timeout: 15000 }).catch(() => {});
  let ri = await v3("routerInfo");
  const r0 = pj.scene_state.router.center_xz;
  check("공유기 3D 모델이 추천 자리에 놓임", ri.visible && Math.hypot(ri.pos[0] - r0[0], ri.pos[1] - r0[1]) < 0.01, JSON.stringify(ri));
  check("와이파이 화면에 그림 문자 없음", !emoji.test(await page.$eval("#overlay", (e) => e.innerHTML)) && !emoji.test(await page.textContent("#simres")));
  await page.screenshot({ path: path.join(OUT, "wifi-router-3d.png") });
  // 3D에서 공유기를 눌러 집고, R로 돌리고, 1.5 m 옮겨 내려놓기
  const before = await page.textContent("#simres");
  let [sx, sy] = await toScreen(r0, 0.03);
  await page.mouse.click(sx, sy);
  await wait(300);
  const held = await page.evaluate(() => document.getElementById("viewer").viewer.held());
  check("3D에서 공유기 집어 들기", held?.kind === "router", JSON.stringify(held));
  await page.keyboard.press("r");
  const r1 = [r0[0] + (cx > r0[0] ? 1.5 : -1.5), r0[1] + (cy > r0[1] ? 0.5 : -0.5)];
  const [tx, ty] = await toScreen(r1);
  await page.mouse.move(tx, ty, { steps: 10 });
  await wait(200);
  await page.mouse.click(tx, ty);
  await wait(3500);
  pj = await j(`/api/projects/${pid}`);
  const rt = pj.scene_state.router;
  check("옮긴 자리·돌린 방향 저장", Math.hypot(rt.center_xz[0] - r0[0], rt.center_xz[1] - r0[1]) > 1 && Math.abs(rt.yaw_rad - Math.PI / 4) < 0.01, JSON.stringify(rt));
  ri = await v3("routerInfo");
  check("3D 공유기도 새 자리·방향", Math.hypot(ri.pos[0] - rt.center_xz[0], ri.pos[1] - rt.center_xz[1]) < 0.05 && Math.abs(ri.yaw - rt.yaw_rad) < 0.01, JSON.stringify(ri));
  check("옮기면 신호를 다시 계산", (await page.textContent("#simres")) !== before);
  await page.screenshot({ path: path.join(OUT, "wifi-router-moved.png") });

  // ---- 동선 ----
  // 리모델링하듯 교실 책상·의자를 치우고, 현관(문 안쪽)과 냉장고를 놓고 동선 보기
  await put(`/api/projects/${pid}/objects/hidden`, { hidden: true });
  const door = room.openings.find((o) => o.type === "door");
  const dw = room.walls.find((w) => w.wall_id === door.wall_id);
  const L = Math.hypot(dw.end[0] - dw.start[0], dw.end[1] - dw.start[1]), u = (door.offset_m + door.width_m / 2) / L;
  const d = [dw.start[0] + (dw.end[0] - dw.start[0]) * u, dw.start[1] + (dw.end[1] - dw.start[1]) * u];
  await put(`/api/projects/${pid}/marks/entrance`, { center_xz: [d[0] + (cx - d[0]) * 0.1, d[1] + (cy - d[1]) * 0.1] });
  const far = [cx + (cx - d[0]) * 0.6, cy + (cy - d[1]) * 0.6];
  await j(`/api/projects/${pid}/placements`, { method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ sku: "G646GBB031", center_xz: far, yaw_rad: 1.57 }) });
  await page.reload();
  await page.waitForSelector("#lib .prod");
  await wait(2000);
  await page.click('[data-sim="flow"]');
  await page.waitForFunction(() => document.getElementById("viewer").viewer.walkersInfo().length > 0, null, { timeout: 15000 }).catch(() => {});
  await wait(1500);
  const w1 = await v3("walkersInfo");
  await wait(1000);
  const w2 = await v3("walkersInfo");
  check("사람 3D 모델이 동선을 걷는다", w1.length >= 1 && w2.some((w, i) => Math.hypot(w.pos[0] - w1[i].pos[0], w.pos[1] - w1[i].pos[1]) > 0.5), JSON.stringify([w1, w2]));
  check("동선 화면에 그림 문자 없음", !emoji.test(await page.$eval("#overlay", (e) => e.innerHTML)));
  check("공유기는 와이파이 화면에서만", !(await v3("routerInfo")).visible);
  // 걷는 사람 가까이서 한 장
  await page.screenshot({ path: path.join(OUT, "flow-walker-3d.png") });
  await page.click('[data-sim=""]');
  await wait(500);
  check("동선을 끄면 사람도 사라짐", (await v3("walkersInfo")).length === 0);
  check("페이지 오류 없음", errors.length === 0, errors.join(" | "));
  await browser.close();
  const fail = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - fail}/${results.length} 통과`);
  process.exit(fail ? 1 : 0);
})();
