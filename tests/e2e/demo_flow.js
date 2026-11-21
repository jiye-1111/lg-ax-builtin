// 시연 흐름 전체 점검 (plans/virtual-remodel.md S1~S10). 서버를 켠 뒤 실행:
//   uv run lgb-api            (다른 창)
//   node tests/e2e/demo_flow.js [http://localhost:8000]
// Playwright가 필요하다: npm i -g playwright && npx playwright install chromium
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const ROOT = path.resolve(__dirname, "../..");
const results = [];
const check = (name, ok, info = "") => {
  results.push({ name, ok: !!ok, info });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`);
};
const j = async (p) => (await fetch(BASE + p)).json();

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  const toScreen = (pt, y = 0) => page.evaluate(([t, h]) => document.getElementById("viewer").viewer.toScreen(t, h), [pt, y]);
  const wait = (ms) => page.waitForTimeout(ms);
  const project = (pid) => j(`/api/projects/${pid}`);

  // S1 셀프 스캔: 실제 UGScan 파일 + 도면 올리기
  await page.goto(BASE + "/#/");
  check("첫 화면: 내 집 스캔", await page.isVisible('[data-slot="scan"]'));
  await page.setInputFiles("#fp", path.join(ROOT, "docs/specs/usdz-analysis-2026-11-18.png"));
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await page.waitForSelector("#lib .prod");
  await wait(2500);
  let pj = await project(pid);
  const room = await j(`/api/projects/${pid}/room`);
  check("셀프 스캔으로 프로젝트 생성", pj.scan.scanned_by === "customer", pid);
  check("스캔 변환: 벽·창·문", room.walls.length >= 4 && room.openings.length >= 1,
    `벽 ${room.walls.length}, 문·창 ${room.openings.length}, 가구 ${room.objects.length}`);
  check("도면 첨부", !!pj.floorplan);
  check("기본 보기 = 3D", (await page.getAttribute(".studio", "data-view")) === "3d");

  const xs = room.walls.flatMap((w) => [w.start[0], w.end[0]]);
  const ys = room.walls.flatMap((w) => [w.start[1], w.end[1]]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;

  // S10 3D에서 놓기 → 끌기 → 돌리기
  // 제품 카드를 누르면 상세 창(사진·치수·사양·색상) → "넣어 보기"로 집어 든다
  await page.click("#lib .prod:not(.nosize) >> nth=0");
  check("제품 상세 창", await page.isVisible("#pdModal") && /가로/.test(await page.textContent("#pdModal")) && (await page.$$("#pdModal [data-pd-variant]")).length >= 1);
  await page.click("#pdPlace");
  check("넣어 보기로 집어 들기", (await page.$$("#lib .prod.armed")).length === 1 && !(await page.isVisible("#pdModal")));
  let [sx, sy] = await toScreen([cx - 0.4, cy + 0.7]);
  await page.mouse.move(sx, sy);
  await wait(500);
  await page.mouse.click(sx, sy);
  await wait(2000);
  pj = await project(pid);
  const pl = pj.scene_state.placements[0];
  check("3D 바닥을 눌러 제품 놓기", pj.scene_state.placements.length === 1, pl && `${pl.verdict}`);
  [sx, sy] = await toScreen(pl.center_xz, 0.5);
  const [tx, ty] = await toScreen([pl.center_xz[0] + 0.8, pl.center_xz[1] - 0.6], 0.5);
  await page.mouse.move(sx, sy);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) { await page.mouse.move(sx + ((tx - sx) * i) / 10, sy + ((ty - sy) * i) / 10); await wait(30); }
  await page.mouse.up();
  await wait(2000);
  pj = await project(pid);
  const moved = pj.scene_state.placements[0];
  check("3D에서 끌어 옮기기", Math.hypot(moved.center_xz[0] - pl.center_xz[0], moved.center_xz[1] - pl.center_xz[1]) > 0.3);
  await page.keyboard.press("r");
  await wait(1500);
  pj = await project(pid);
  check("R 키로 45° 돌리기", Math.abs(pj.scene_state.placements[0].yaw_rad - moved.yaw_rad - Math.PI / 4) < 1e-3);

  // 건축 모드: 눌러서 집어 들기 → 커서 따라오기 → Shift+R → 다시 눌러 내려놓기
  const before = pj.scene_state.placements[0];
  [sx, sy] = await toScreen(before.center_xz, 0.5);
  await page.mouse.click(sx, sy);
  await wait(400);
  const h0 = await page.evaluate(() => document.getElementById("viewer").viewer.held());
  check("눌러서 집어 들기", !!h0);
  const [hx, hy] = await toScreen([before.center_xz[0] - 0.6, before.center_xz[1] + 0.4], 0.5);
  await page.mouse.move(hx, hy, { steps: 8 });
  await page.keyboard.press("Shift+R");
  await wait(300);
  await page.mouse.click(hx, hy);
  await wait(2000);
  pj = await project(pid);
  const after = pj.scene_state.placements[0];
  check("내려놓으면 자리·방향 저장", Math.hypot(after.center_xz[0] - before.center_xz[0], after.center_xz[1] - before.center_xz[1]) > 0.3
    && Math.abs(after.yaw_rad - before.yaw_rad + Math.PI / 4) < 1e-3,
    `${before.center_xz.map((v) => v.toFixed(2))} → ${after.center_xz.map((v) => v.toFixed(2))}, ${(((after.yaw_rad - before.yaw_rad) * 180) / Math.PI).toFixed(0)}°`);
  check("내려놓은 뒤 손이 빔", !(await page.evaluate(() => document.getElementById("viewer").viewer.held())));
  // 방향키로 살짝 옮기기 (고른 상태)
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await wait(1500);
  pj = await project(pid);
  const nud = pj.scene_state.placements[0];
  const nd = Math.hypot(nud.center_xz[0] - after.center_xz[0], nud.center_xz[1] - after.center_xz[1]);
  check("방향키로 20 cm 옮기기", Math.abs(nd - 0.2) < 0.02, `${nd.toFixed(3)} m`);
  // 카메라 WASD
  const cam0 = await toScreen(nud.center_xz);
  await page.keyboard.press("d");
  await wait(200);
  const cam1 = await toScreen(nud.center_xz);
  check("D 키로 카메라 이동", Math.abs(cam1[0] - cam0[0]) > 5);

  // 색·재질 (같은 모델의 LGE.COM 다른 SKU)
  await wait(1500); // 방향키로 옮긴 저장이 끝나 선택 칸이 다시 그려진 뒤에 누른다
  const sw = page.locator("#insp [data-variant]"), nsw = await sw.count();
  let want = null;
  if (nsw > 1) { want = await sw.nth(1).getAttribute("data-variant"); await sw.nth(1).click(); await wait(1500); pj = await project(pid); }
  check("같은 모델 안에서 색·재질 바꾸기", !want || pj.scene_state.placements[0].sku === want, `옵션 ${nsw}개`);
  const fams = await j("/api/catalog/families"), skus = await j("/api/catalog");
  check("제품 목록은 모델 단위", (await page.$$("#lib .prod")).length === fams.length && fams.length < skus.length, `${skus.length}개 SKU → ${fams.length}개 모델`);

  // 평면에서도 놓기
  await page.click('.studio-head [data-view="plan"]');
  await wait(500);
  await page.click("#lib .prod:not(.nosize) >> nth=1");
  await page.click("#pdPlace");
  const box = await (await page.$("#plan")).boundingBox();
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.75);
  await wait(2000);
  pj = await project(pid);
  check("평면을 눌러 제품 놓기", pj.scene_state.placements.length === 2);
  await page.click("#del");
  await wait(1500);
  pj = await project(pid);
  check("선택한 제품 빼기", pj.scene_state.placements.length === 1);

  // S4 스캔 가구 치우기 (3D에서 고르기)
  await page.click('.studio-head [data-view="3d"]');
  await wait(900);
  const ob = room.objects.find((o) => o.category === "table") || room.objects[0];
  [sx, sy] = await toScreen([ob.position[0], ob.position[2]], ob.bbox_m.h);
  await page.mouse.click(sx, sy);
  await wait(700);
  // 눌러서 집어 든 가구를 옮겨 내려놓기
  const [fx, fy] = await toScreen([ob.position[0] + 0.7, ob.position[2] + 0.5], ob.bbox_m.h);
  await page.mouse.move(fx, fy, { steps: 8 });
  await page.keyboard.press("r");
  await page.mouse.click(fx, fy);
  await wait(2500);
  pj = await project(pid);
  const op = (pj.scene_state.object_poses || {})[ob.object_id];
  check("스캔 가구 집어 옮기고 돌리기", !!op && Math.hypot(op.center_xz[0] - ob.position[0], op.center_xz[1] - ob.position[2]) > 0.4
    && Math.abs(op.yaw_rad - ob.yaw_rad - Math.PI / 4) < 1e-3);
  // Delete로 가구 지우기 (고른 상태)
  await page.keyboard.press("Delete");
  await wait(2000);
  pj = await project(pid);
  check("Delete로 가구 지우기", (pj.scene_state.hidden_objects || []).includes(ob.object_id));

  // 스캔 가구 한꺼번에 치우기 → 되돌리기
  await page.click("#furn");
  await page.click("#furnAll");
  await wait(2500);
  pj = await project(pid);
  check("가구 모두 치우기", (pj.scene_state.hidden_objects || []).length === room.objects.length);
  await page.click("#furnAll");
  await wait(2500);
  pj = await project(pid);
  check("가구 되돌리기", (pj.scene_state.hidden_objects || []).length === 0);
  await wait(1500);
  const st = await page.evaluate(() => document.getElementById("viewer").viewer.stats());
  check("3D 가구를 Blender 모델로 그리기", st.furniture > room.objects.length, `부품 ${st.furniture}개`);

  // 벽·바닥 색
  await page.click('.side-tabs [data-tab="finish"]');
  await page.click('[data-mat="wall"] >> nth=3');
  await wait(1500);
  pj = await project(pid);
  check("벽 색 바꾸기", !!pj.scene_state.materials?.wall, pj.scene_state.materials?.wall);

  // 영역 그리기 → 추천
  await page.click('[data-mode="rect"]');
  await wait(500);
  const pb = await (await page.$("#plan")).boundingBox();
  await page.mouse.move(pb.x + pb.width * 0.42, pb.y + pb.height * 0.12);
  await page.mouse.down();
  await page.mouse.move(pb.x + pb.width * 0.62, pb.y + pb.height * 0.3, { steps: 6 });
  await page.mouse.up();
  await wait(2500);
  const zones = await j(`/api/projects/${pid}/zones`);
  check("평면에 영역 그리기", zones.length === 1);
  await page.waitForSelector("#recs .card", { timeout: 5000 }).catch(() => {});
  const cards = (await page.$$("#recs .card")).length;
  check("영역 추천 카드", cards > 0, `${cards}개`);
  await page.click('[data-mode="move"]');

  // 도면·실측 (선택 입력)
  await page.click('.side-tabs [data-tab="extra"]');
  await page.fill('#walls tr:first-child input[name="length_m"]', room.walls[0].scanned.length_m.toFixed(3));
  await page.click("#walls tr:first-child [data-save]");
  await wait(1500);
  const room2 = await j(`/api/projects/${pid}/room`);
  check("벽 실측값 넣기", room2.walls[0].measured?.by === "customer");
  check("도면 보이기", await page.isVisible("#fpBox img.floorplan"));

  // S6 채광
  await page.click('[data-sim="daylight"]');
  await wait(800);
  await page.$eval("#north", (e) => { e.value = 90; e.dispatchEvent(new Event("change")); });
  await wait(2500);
  pj = await project(pid);
  check("채광: 북쪽 방향 저장", pj.site?.north_deg === 90);
  check("채광: 결과 표시", /해 높이|해가 진/.test(await page.textContent("#simres")));

  // S7 와이파이
  await page.click('[data-sim="wifi"]');
  await wait(500);
  await page.click("#bestRouter");
  await wait(4000);
  pj = await project(pid);
  check("와이파이: 추천 자리에 공유기", !!pj.scene_state.router);
  check("와이파이: 세기 요약", /좋음/.test(await page.textContent("#simres")));

  // S8 동선 (현관을 3D 바닥에서 지정)
  await page.click('[data-sim="flow"]');
  await wait(800);
  await page.click("#mkEnt");
  const door = room.openings.find((o) => o.type === "door");
  const dw = door && room.walls.find((w) => w.wall_id === door.wall_id);
  let ent = [cx, cy];
  if (dw) {
    const L = Math.hypot(dw.end[0] - dw.start[0], dw.end[1] - dw.start[1]);
    const u = (door.offset_m + door.width_m / 2) / L;
    const d = [dw.start[0] + (dw.end[0] - dw.start[0]) * u, dw.start[1] + (dw.end[1] - dw.start[1]) * u];
    ent = [d[0] + (cx - d[0]) * 0.1, d[1] + (cy - d[1]) * 0.1];
  }
  [sx, sy] = await toScreen(ent);
  await page.mouse.click(sx, sy);
  await wait(3000);
  pj = await project(pid);
  check("동선: 3D에서 현관 지정", !!pj.scene_state.marks?.entrance);
  check("동선: 경로 결과", /가장 좁은 곳|못 감/.test(await page.textContent("#simres")));

  // 1인칭 둘러보기: 눈높이 1.6 m, WASD로 걷고, 벽·가구는 못 지나가고, 집어 들기는 꺼진다
  await page.click('[data-sim=""]');
  await page.click('.studio-head [data-view="3d"]');
  await page.click("#walk");
  await wait(800);
  const walkInfo = () => page.evaluate(() => document.getElementById("viewer").viewer.walkInfo());
  const w0 = await walkInfo();
  check("둘러보기: 눈높이 1.6 m", !!w0 && Math.abs(w0.pos[1] - 1.6) < 1e-6 && !w0.blocked);
  await page.keyboard.down("w"); await wait(1200); await page.keyboard.up("w");
  const w1 = await walkInfo();
  check("둘러보기: W로 걷기", Math.hypot(w1.pos[0] - w0.pos[0], w1.pos[2] - w0.pos[2]) > 0.3, `${Math.hypot(w1.pos[0] - w0.pos[0], w1.pos[2] - w0.pos[2]).toFixed(2)} m`);
  await page.keyboard.down("w"); await wait(9000); await page.keyboard.up("w");
  const w2 = await walkInfo();
  const [bx0, by0, bx1, by1] = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  check("둘러보기: 벽·가구를 지나가지 않음", !w2.blocked && w2.pos[0] > bx0 && w2.pos[0] < bx1 && w2.pos[2] > by0 && w2.pos[2] < by1,
    w2.pos.map((v) => v.toFixed(2)).join(","));
  const vb = await page.$eval("#viewer canvas", (c) => { const r = c.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; });
  await page.mouse.click(vb[0] + vb[2] / 2, vb[1] + vb[3] / 2);
  await wait(400);
  check("둘러보기: 누르면 집어 들기 안 함", !(await page.evaluate(() => document.getElementById("viewer").viewer.held())));
  await page.keyboard.press("Escape");
  await page.evaluate(() => document.exitPointerLock?.()); // 사람은 Esc로 풀지만 자동 브라우저는 직접 푼다
  await page.$eval("#walk", (b) => b.click());
  await wait(500);
  check("둘러보기 끝내면 원래 보기", (await page.evaluate(() => document.getElementById("viewer").viewer.walking())) === false);

  // 렌더 이미지
  await page.click('[data-sim=""]');
  await page.click('.studio-head [data-view="3d"]');
  await page.click("#render");
  // Blender(Cycles) 렌더는 CPU에서 1분 가까이 걸린다. BLENDER_TIMEOUT_S(300초) 안에 끝나면 통과
  await page.waitForSelector("#renderBox:not([hidden])", { timeout: 300000 }).catch(() => {});
  check("렌더 이미지", await page.isVisible("#renderBox"));
  await page.click("#renderClose").catch(() => {});

  // 방문 신청 · 기사 화면
  const viewBefore = await page.getAttribute(".studio", "data-view");
  await page.goto(BASE + "/#/r");
  await wait(600);
  await page.click("#req button");
  await wait(1000);
  check("방문 스캔 신청", /요청 번호/.test(await page.textContent("#reqDone")));
  // 다른 화면에 다녀와도 내 집이 그대로: 내 집 스캔 → 꾸미던 집, 보던 보기도 그대로
  await page.click(".top .brand");
  await page.waitForFunction((id) => location.hash.startsWith("#/c/" + id), pid, { timeout: 10000 }).catch(() => {});
  await page.waitForSelector("#lib .prod", { timeout: 20000 }).catch(() => {});
  check("방문 신청 다녀와도 내 집 그대로", page.url().includes("#/c/" + pid) && (await page.$$('[data-slot="scan"]')).length === 0);
  const viewNow = await page.getAttribute(".studio", "data-view");
  check("보던 보기 그대로", viewNow === viewBefore, viewNow);
  check("작은 화면은 오른쪽 패널 아래 미니맵", viewNow === "split" || (await page.$$("#minimap .pane")).length === 1);
  await page.goto(BASE + `/#/t/${pid}`);
  await wait(1500);
  check("기사 화면 벽 표", (await page.$$("#walls tr")).length === room.walls.length);

  // 웹앱 설치
  const swState = await page.evaluate(async () => (await navigator.serviceWorker.ready).active?.state);
  check("웹앱: 서비스 워커", swState === "activated");

  // 휴대폰 폭
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const pp = await phone.newPage();
  await pp.goto(BASE + `/#/c/${pid}?t=${pj.share_token}`);
  await pp.waitForSelector("#lib .prod", { state: "attached" });
  await pp.waitForTimeout(2000);
  check("휴대폰 390px 가로 스크롤 없음", (await pp.evaluate(() => document.documentElement.scrollWidth - innerWidth)) <= 0);

  check("화면 오류 없음", errors.length === 0, errors.slice(0, 3).join(" | "));
  await browser.close();
  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} 통과`);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
