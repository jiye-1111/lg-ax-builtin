// 단순하게 정리한 화면 점검: 머리 버튼(새로 만들기·불러오기·저장), 채광·와이파이·동선 한 줄 패널, 문 달기, 막힌 제품 ✕
//   uv run lgb-api            (다른 창)
//   node tests/e2e/simple_live.js [http://localhost:8000]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const ROOT = path.resolve(__dirname, "../..");
const SKU = "G646GBB031";
const results = [];
const check = (name, ok, info = "") => {
  results.push({ name, ok: !!ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`);
};
const j = async (p, opt) => (await fetch(BASE + p, opt)).json();
const send = (method) => (p, body) => j(p, { method, headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
const post = send("POST"), put = send("PUT");

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => { try { localStorage.setItem("lgb.tour.v1", "1"); } catch { /* 저장소가 막혀 있어도 계속 */ } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const wait = (ms) => page.waitForTimeout(ms);
  const v3 = (fn, ...a) => page.evaluate(([f, a]) => document.getElementById("viewer").viewer[f](...a), [fn, a]);
  const toScreen = (pt, y = 0) => v3("toScreen", pt, y);
  const sheet = () => page.innerText("#simctl");

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await page.waitForSelector("#lib", { state: "attached" });
  await wait(2500);
  const room = await j(`/api/projects/${pid}/room`);
  const xs = room.walls.flatMap((w) => [w.start[0], w.end[0]]), ys = room.walls.flatMap((w) => [w.start[1], w.end[1]]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;

  // ---- 머리: 단계 표시 없음, 새로 만들기 · 불러오기 · 저장 ----
  const head = await page.innerText(".studio-head");
  check("머리에 새로 만들기 · 불러오기 · 저장", ["새로 만들기", "불러오기", "저장"].every((t) => head.includes(t)), head.replace(/\s+/g, " "));
  check("진행 단계와 '로그인 필요'가 없다", !(await page.$("#progress")) && !head.includes("로그인 필요") && !head.includes("STEP"));
  await page.click("#saveBtn");
  await page.waitForSelector("dialog[open]");
  check("로그인 없이 저장을 누르면 로그인 안내", (await page.innerText("dialog[open]")).includes("저장하려면 로그인해 주세요"));
  await page.click("dialog[open] .auth-x");
  await page.click("#loadBtn");
  await page.waitForSelector("dialog[open]");
  check("로그인 없이 불러오기를 누르면 로그인 안내", (await page.innerText("dialog[open]")).includes("불러오려면 로그인해 주세요"));
  await page.click("dialog[open] .auth-x");

  // ---- 살아 보기 ----
  await put(`/api/projects/${pid}/objects/hidden`, { hidden: true }); // 리모델링하듯 교실 책상·의자를 치운다
  await page.reload();
  await page.waitForSelector("#lib", { state: "attached" });
  await wait(2500);
  if (await page.locator("#liveBtn").isVisible()) await page.click("#liveBtn");
  await page.click('[data-sim="daylight"]');
  await page.waitForSelector("#simres .facing", { timeout: 20000 });
  let text = await sheet();
  check("채광: 주소 한 칸과 어느 향인지 한 줄", !!(await page.$("#addr")) && /향 집이에요/.test(text) && (await page.locator("#simctl input").count()) === 1, text.replace(/\s+/g, " "));
  check("참고 사항 칸이 없다", !text.includes("참고") && !(await page.$(".sim-notes")));

  await page.click('[data-sim="wifi"]');
  await wait(600);
  check("와이파이: 공유기 종류 둘과 놓기만", (await page.locator("#simctl [data-band]").count()) === 2 && (await page.locator("#simctl button").count()) === 3);
  { const [mx, my] = await toScreen([cx, cy]); await page.mouse.move(mx, my, { steps: 5 }); await wait(300); await page.mouse.click(mx, my); }
  await page.waitForSelector("#simres .wifi-legend", { timeout: 20000 });
  text = await sheet();
  const fills = await page.$$eval("#overlay rect[fill]", (els) => [...new Set(els.map((e) => e.getAttribute("fill")))]);
  check("와이파이: 바닥에 색만, 수치 글자 없음", fills.length >= 1 && fills.every((c) => ["#1f7a4d", "#e0a800", "#b3261e", null].includes(c)) && !/dBm|%/.test(text), `${fills} · ${text.replace(/\s+/g, " ")}`);

  // ---- 동선: 어디서 출발할까요? ----
  const lg = (await post(`/api/projects/${pid}/auto-place`, { sku: SKU })).placement;
  await page.click('[data-sim="flow"]');
  await wait(800);
  check("동선: 먼저 '어디서 출발할까요?'를 묻는다", (await sheet()).includes("어디서 출발할까요?"));
  const start = [cx, cy];
  { const [mx, my] = await toScreen(start); await page.mouse.move(mx, my, { steps: 5 }); }
  await page.waitForFunction(() => document.getElementById("viewer").viewer.starterInfo().loaded, null, { timeout: 20000 }).catch(() => {});
  const st = await v3("starterInfo");
  check("사람이 마우스를 따라온다", st.visible && st.loaded && Math.hypot(st.pos[0] - start[0], st.pos[1] - start[1]) < 0.3, JSON.stringify(st));
  { const [mx, my] = await toScreen(start); await page.mouse.click(mx, my); }
  await page.waitForFunction(() => document.getElementById("viewer").viewer.walkersInfo().length > 0, null, { timeout: 20000 }).catch(() => {});
  let pj = await j(`/api/projects/${pid}`);
  check("누른 자리가 출발 자리로 저장되고 사람이 걷는다", !!pj.scene_state.marks?.start && (await v3("walkersInfo")).length >= 1 && !(await v3("starterInfo")).visible, JSON.stringify(pj.scene_state.marks));
  check("동선 칸에 현관·싱크 지정 버튼이 없다", !/현관|싱크/.test(await sheet()));

  // 냉장고를 가벽으로 가두면 ✕가 뜨고, 누르면 빠진다
  const f = [Math.cos(lg.yaw_rad), Math.sin(lg.yaw_rad)], u = [-f[1], f[0]], [w, , d] = lg.size_m, c = lg.center_xz;
  const wall = (center, yaw, len) => post(`/api/projects/${pid}/placements`, { sku: "decor:wall", center_xz: center, yaw_rad: yaw, size_m: [len, 2.4, 0.1], snap: false });
  const off = d / 2 + 1.0, side = w / 2 + 0.5, len = 2 * side + 0.2;
  await wall([c[0] + f[0] * off, c[1] + f[1] * off], lg.yaw_rad, len);
  for (const k of [1, -1]) await wall([c[0] + u[0] * k * side + f[0] * (off / 2), c[1] + u[1] * k * side + f[1] * (off / 2)], lg.yaw_rad + Math.PI / 2, off + d);
  await page.waitForSelector(".flow-x", { timeout: 30000 });
  check("길이 막힌 제품에 ✕가 뜬다", (await page.locator(".flow-x").count()) === 1);
  await page.locator(".flow-x").click();
  await page.waitForFunction(() => !document.querySelector(".flow-x"), null, { timeout: 30000 });
  pj = await j(`/api/projects/${pid}`);
  check("✕를 누르면 그 제품이 빠진다", !pj.scene_state.placements.some((x) => x.placement_id === lg.placement_id));

  // ---- 문 달기: 가벽 옆을 눌러도 벽 가운데 줄에 달리고, 앞을 막으면 안 열린다 ----
  const pw = (await wall([cx, cy + 1.5], Math.PI / 2, 2.4)).placement;
  const door = (await post(`/api/projects/${pid}/placements`, { sku: "decor:door", center_xz: [cx, cy + 1.7], yaw_rad: 0 })).placement;
  check("문이 가벽 가운데 줄에 달리고 열린다", Math.hypot(door.center_xz[0] - pw.center_xz[0], door.center_xz[1] - pw.center_xz[1]) < 0.02 && door.verdict !== "no_fit", JSON.stringify([door.center_xz, door.verdict]));
  await post(`/api/projects/${pid}/placements`, { sku: "decor:dresser", center_xz: [cx, cy + 2.05], yaw_rad: Math.PI / 2, snap: false });
  pj = await j(`/api/projects/${pid}`);
  const shut = pj.scene_state.placements.find((x) => x.placement_id === door.placement_id);
  check("앞을 막으면 '문을 열 공간이 부족해요'", shut.verdict === "no_fit" && shut.reasons.some((r) => r.label === "문을 열 공간이 부족해요"), JSON.stringify(shut.reasons));

  check("페이지 오류 없음", errors.length === 0, errors.join(" | "));
  await browser.close();
  const fail = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - fail}/${results.length} 통과`);
  process.exit(fail ? 1 : 0);
})();
