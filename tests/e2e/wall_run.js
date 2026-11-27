// 벽면 맞춤가구 편집기 점검 (docs/specs/wall-run.md 완료 조건):
// 1. 냉장고 카드 '맞춤장 만들기' → 이미 놓은 냉장고를 감싼 열린 냉장고장이 3D 미리보기에, 확정해도 냉장고는 하나
// 2. 주방: 팬트리 + 냉장고장 + 싱크 하부장 + 식기세척기 자리 + 위 유리 상부장. 순서·폭을 바꾸면 3D와 사용 폭이 바뀐다
// 3. 거실: TV 하부장·책장·유리장 (구매 흐름 없이), 장마다 색·폭 바꾸기
// 4. 장을 옮겨 창·문을 막으면 판정과 까닭이 바뀌고, 취소하면 그대로. 확정한 세트는 다시 열어도 남는다
//   uv run lgb-api            (다른 창)
//   node tests/e2e/wall_run.js [http://localhost:8000] [스크린샷 폴더]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3] || "";
const ROOT = path.resolve(__dirname, "../..");
const FRIDGE = "G646GBB031";
let failed = 0;
const check = (name, ok, info = "") => {
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`);
};

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: SHOTS ? 2 : 1 });
  await ctx.addInitScript(() => { try { localStorage.setItem("lgb.tour.v1", "1"); } catch { /* 안내만 건너뛴다 */ } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.stack || e).split("\n").slice(0, 3).join(" ")));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  const wait = (ms) => page.waitForTimeout(ms);
  const api = (url, body, method = "POST") => page.evaluate(async ([u, b, m]) => {
    const r = await fetch(u, { method: m, headers: { "Content-Type": "application/json" }, body: b ? JSON.stringify(b) : undefined });
    return r.json();
  }, [url, body, method]);
  const shot = async (name) => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, name) }); };
  const project = (pid) => api(`/api/projects/${pid}`, null, "GET");
  const loaded = async () => {
    await page.reload();
    await page.waitForSelector("#libTabs", { state: "attached", timeout: 60000 });
    await wait(4000);
  };
  // 미리보기가 다시 올 때까지: 정면도를 표시해 두고 새로 그려지길 기다린다
  let ver = "";
  const mark = async () => { ver = await page.evaluate(() => document.getElementById("runEd")?.dataset.ver || ""); };
  const fresh = () => page.waitForFunction((v) => { const e = document.getElementById("runEd"); return e && e.dataset.ver && e.dataset.ver !== v && document.getElementById("elSvg"); }, ver, { timeout: 45000 }).catch(() => {});
  const act = async (fn) => { await mark(); await fn(); await fresh(); await wait(400); };
  const click = (sel) => act(() => page.$eval(sel, (b) => b.click()));
  const usage = () => page.$eval(".re-usage", (e) => e.textContent).catch(() => "");
  const preview = () => page.evaluate(() => [...document.querySelectorAll(".el-mod")].map((g) => g.getAttribute("aria-label")));
  const scenePls = () => page.evaluate(() => window.__lgbScene?.() || null);

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await api(`/api/projects/${pid}/objects/hidden`, { hidden: true }, "PUT"); // 빈 방에서 본다
  const room = await api(`/api/projects/${pid}/room`, null, "GET");
  const len = (w) => Math.hypot(w.end[0] - w.start[0], w.end[1] - w.start[1]);
  const ops = (w) => room.openings.filter((o) => o.wall_id === w.wall_id);
  const byLen = [...room.walls].sort((a, b) => len(b) - len(a));
  const doorWall = room.walls.find((w) => ops(w).length) || null;

  // ---- 1. 냉장고 카드 → 놓인 냉장고 감싸기 ----
  const fr = await api(`/api/projects/${pid}/auto-place`, { sku: FRIDGE });
  const fid = fr.placement?.placement_id;
  await loaded();
  await page.$eval('#libTabs [data-tab="lg"]', (b) => b.click()); await wait(400);
  await page.evaluate((sku) => (document.querySelector(`[data-sku="${sku}"]`) || document.querySelector(`[data-sugg="${sku}"]`))?.click(), FRIDGE);
  await page.waitForSelector("#pdCab", { timeout: 15000 }).catch(() => {});
  const label = await page.$eval("#pdCab", (b) => b.textContent).catch(() => "");
  check("냉장고 상세 스펙 아래에 '맞춤장 만들기' 버튼", label.includes("맞춤장 만들기"), label);
  await mark();
  await page.$eval("#pdCab", (b) => b.click()).catch(() => {});
  await page.waitForSelector("#elSvg", { timeout: 60000 }).catch(() => {});
  await fresh(); await wait(1500);
  const note = await page.$eval(".re-note", (e) => e.textContent).catch(() => "");
  check("편집기가 놓인 냉장고 자리 벽으로 열리고, 새로 놓지 않는다고 알린다", note.includes("새로 놓지 않아요"), note);
  const pv1 = await page.evaluate(() => [...document.querySelectorAll(".el-mod")].length);
  const fridgesInPreview = await page.evaluate((sku) => window.__lgbScene().filter((x) => x.sku === sku).length, FRIDGE);
  const linked = await page.evaluate((id) => window.__lgbScene().find((x) => x.placement_id === id)?.in_cab, fid);
  check("미리보기: 냉장고장이 생기고 그 냉장고가 장 안에 (중복 없음)", pv1 === 1 && fridgesInPreview === 1 && !!linked, `장 ${pv1} · 냉장고 ${fridgesInPreview}`);
  const saved0 = (await project(pid)).scene_state.placements.filter((x) => x.cab).length;
  check("미리보기는 저장하지 않는다", saved0 === 0);
  const fitTxt = await page.$eval(".re-results", (e) => e.textContent).catch(() => "");
  check("결과가 셋으로 나뉜다 (들어가요? / 문·서랍 / 전기·급배수·방열)", ["들어가요?", "문·서랍이 열려요?", "전기·급배수·방열"].every((t) => fitTxt.includes(t)) && /적합/.test(fitTxt), fitTxt.slice(0, 120));
  await shot("run_fridge_preview.png");
  await page.$eval("#reOk", (b) => b.click());
  await page.waitForSelector("#runEd[hidden]", { state: "attached", timeout: 60000 }).catch(() => {});
  await wait(2500);
  let pls = (await project(pid)).scene_state.placements;
  const frCount = pls.filter((x) => x.sku === FRIDGE).length, frNow = pls.find((x) => x.placement_id === fid);
  const fcab = pls.find((x) => x.placement_id === frNow?.in_cab);
  check("확정: 냉장고는 하나, 원래 냉장고가 열린 냉장고장 안", frCount === 1 && fcab?.cab?.kind === "fridge" && frNow.cab_made === false, `${frCount}개`);
  check("냉장고장 판정은 LG 공식 기준", fcab?.cab_check?.rule_id === "fitmax-g646", fcab?.cab_check?.verdict);

  // ---- 2. 주방 벽: 시작 세트 → 순서·폭 ----
  const FWALL = fcab?.wall_id; // 냉장고장을 놓은 벽은 빼고 고른다
  const kitchenWall = byLen.find((w) => !ops(w).length && len(w) > 3.5 && w.wall_id !== FWALL) || byLen.find((w) => w.wall_id !== FWALL);
  const livingWall = byLen.find((w) => w !== kitchenWall && w.wall_id !== FWALL && len(w) > 3) || byLen[1];
  await page.$eval('#libTabs [data-tab="furniture"]', (b) => b.click()); await wait(400);
  await page.$eval("[data-run-new]", (b) => b.click());
  await page.waitForSelector("[data-rewall]", { timeout: 15000 });
  await page.$eval(`[data-rewall="${kitchenWall.wall_id}"]`, (b) => b.click());
  await page.waitForSelector('[data-starter="kitchen"]', { timeout: 15000 });
  await shot("run_start.png");
  await mark();
  await page.$eval('[data-starter="kitchen"]', (b) => b.click());
  await page.waitForSelector("#elSvg", { timeout: 60000 }); await fresh(); await wait(1500);
  let names = await preview();
  check("주방 시작 세트: 팬트리·냉장고장·싱크·식기세척기 자리 + 위 유리 상부장", ["선반형 팬트리", "냉장고·김치냉장고장", "싱크 하부장 800", "식기세척기 자리", "투명 유리 상부장"].every((n) => names.includes(n)), names.join(" · "));
  const u0 = await usage();
  // 3단 서랍장 폭 600 → 800
  const drawerId = await page.evaluate(() => [...document.querySelectorAll(".el-mod")].find((g) => g.getAttribute("aria-label") === "3단 서랍장")?.dataset.mid);
  await act(() => page.evaluate((id) => { const g = document.querySelector(`.el-mod[data-mid="${id}"]`); g.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, clientX: 10, clientY: 10, pointerId: 1 })); g.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, clientX: 10, clientY: 10, pointerId: 1 })); }, drawerId));
  const hasProps = await page.$('[data-w="800"]');
  if (hasProps) await click('[data-w="800"]');
  const u1 = await usage();
  check("폭을 바꾸면 사용 폭이 바로 바뀐다", !!hasProps && u0 !== u1 && /하부·키큰장 [\d,]+ mm 사용/.test(u1), `${u0} → ${u1}`);
  // 순서: 고른 장을 왼쪽으로
  const before = (await preview()).join("|");
  await click('[data-act="left"]');
  const after = (await preview()).join("|");
  check("순서를 바꾸면 정면도·3D 순서가 바뀐다", before !== after, after.split("|").slice(0, 4).join(" · "));
  const in3d = await page.evaluate(() => window.__lgbScene().filter((x) => x.cab?.run).length);
  check("3D 미리보기에 세트 장이 다 보인다", in3d >= 8, `${in3d}개`);
  await shot("run_kitchen.png");
  await page.$eval("#reOk", (b) => b.click());
  await page.waitForSelector("#runEd[hidden]", { state: "attached", timeout: 60000 }).catch(() => {});
  await wait(2500);
  let st = (await project(pid)).scene_state;
  check("주방 세트 확정", st.cab_runs.length === 2, `${st.cab_runs.length}개 세트`);

  // ---- 3. 거실: TV 하부장·책장·유리장, 색·폭 ----
  await page.$eval('#libTabs [data-tab="furniture"]', (b) => b.click()); await wait(400);
  await page.$eval("[data-run-new]", (b) => b.click());
  await page.waitForSelector("[data-rewall]", { timeout: 15000 });
  await page.$eval(`[data-rewall="${livingWall.wall_id}"]`, (b) => b.click());
  await page.waitForSelector('[data-starter="empty"]', { timeout: 15000 });
  await page.$eval('[data-starter="empty"]', (b) => b.click()); await wait(500);
  await page.$eval('[data-palroom="living"]', (b) => b.click()); await wait(300);
  for (const id of ["living_bookshelf", "tv_base_1800", "living_glass"]) await click(`[data-add="${id}"]`);
  names = await preview();
  check("거실 장 셋이 나란히", names.join(",") === "오픈 책장,TV 하부장 1800,투명 유리 진열장", names.join(" · "));
  // 고른 장(마지막 유리장) 색, 그리고 TV 하부장 폭
  await click('[data-sw="front"][data-fin="walnut"]');
  const tvId = await page.evaluate(() => [...document.querySelectorAll(".el-mod")].find((g) => g.getAttribute("aria-label") === "TV 하부장 1800")?.dataset.mid);
  await act(() => page.evaluate((id) => { const g = document.querySelector(`.el-mod[data-mid="${id}"]`); g.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, pointerId: 1 })); g.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, pointerId: 1 })); }, tvId));
  await click('[data-w="1200"]');
  await click('[data-sw="front"][data-fin="lightoak"]');
  const orderBefore = (await page.$eval("#orderBtn", (b) => b.textContent).catch(() => ""));
  await shot("run_living.png");
  await page.$eval("#reOk", (b) => b.click());
  await page.waitForSelector("#runEd[hidden]", { state: "attached", timeout: 60000 }).catch(() => {});
  await wait(2500);
  st = (await project(pid)).scene_state;
  const living = st.placements.filter((x) => x.cab?.run && st.cab_runs.find((r) => r.run_id === x.cab.run.id)?.room === "living");
  const tv = living.find((x) => x.cab.preset === "tv_base_1800"), glass = living.find((x) => x.cab.preset === "living_glass");
  check("거실 장마다 색·폭이 따로 저장된다", tv?.cab.outer_mm.w === 1200 && tv.cab.finish.front === "lightoak" && glass?.cab.finish.front === "walnut", `${tv?.cab.outer_mm.w} ${tv?.cab.finish.front} / ${glass?.cab.finish.front}`);
  check("거실 장은 구매 흐름에 안 들어간다 (꾸미기 가구)", living.length === 3 && living.every((x) => x.kind === "decor"), orderBefore);

  // ---- 4. 막기 → 판정·까닭 → 취소 → 다시 열기 ----
  if (doorWall) {
    const o = ops(doorWall)[0];
    await page.$eval('#libTabs [data-tab="furniture"]', (b) => b.click()); await wait(400);
    await page.$eval("[data-run-new]", (b) => b.click());
    await page.waitForSelector("[data-rewall]", { timeout: 15000 });
    await page.$eval(`[data-rewall="${doorWall.wall_id}"]`, (b) => b.click());
    await mark();
    await page.$eval('[data-starter="storage"]', (b) => b.click());
    await page.waitForSelector("#elSvg", { timeout: 60000 }); await fresh(); await wait(800);
    const opS = await page.evaluate(() => [...document.querySelectorAll(".el-win rect, .el-door rect")].map((r) => +r.getAttribute("x")));
    // 시작 위치를 그 창·문 자리로 → 막는다고 나와야
    await act(() => page.$eval("#reS0", (el, v) => { el.value = String(v); el.dispatchEvent(new Event("change", { bubbles: true })); }, Math.max(0, Math.round(opS[0] || o.offset_m * 1000) - 100)));
    const issues = await page.$eval(".run-ed", (e) => e.textContent);
    check("창·문을 막으면 자리와 까닭이 나온다", /창문을 가려요|문을 막아요|통로를 막아요/.test(issues), (issues.match(/[^.]*(가려요|막아요)/) || [""])[0].slice(-40));
    await shot("run_blocked.png");
    const runsBefore = (await project(pid)).scene_state.cab_runs.length;
    await page.$eval("#reCancel", (b) => b.click()); await wait(1500);
    const scene = await page.evaluate(() => window.__lgbScene().filter((x) => String(x.placement_id).startsWith("new")).length);
    check("취소하면 미리보기 장이 사라지고 저장도 안 된다", scene === 0 && (await project(pid)).scene_state.cab_runs.length === runsBefore);
  } else console.log("SKIP  문·창 있는 벽이 없음");
  // 세트 장 하나를 좁혀 냉장고 문이 막히는지: 냉장고장 외경 폭을 줄이면 판정이 바뀐다
  st = (await project(pid)).scene_state;
  const fc = st.placements.find((x) => x.cab?.kind === "fridge" && x.cab.run);
  if (fc) {
    const r = await api(`/api/projects/${pid}/cabinets/${fc.placement_id}`, { outer_mm: { w: 900 } }, "PATCH");
    const after2 = r.placement?.cab_check;
    check("냉장고장을 좁히면 판정과 까닭이 바뀐다", after2?.verdict === "no_fit" && /부족/.test(after2.summary), after2?.summary);
    await api(`/api/projects/${pid}/cabinets/${fc.placement_id}`, { outer_mm: { w: fc.cab.outer_mm.w } }, "PATCH");
  }
  await loaded();
  await page.waitForFunction(() => window.__lgbScene?.().some((x) => x.cab?.run), null, { timeout: 60000 }).catch(() => {});
  st = (await project(pid)).scene_state;
  const n3d = await page.evaluate(() => window.__lgbScene().filter((x) => x.cab?.run).length);
  check("다시 열어도 확정한 세트가 남는다 (3D에도)", st.cab_runs.length === 3 && n3d === st.placements.filter((x) => x.cab?.run).length, `${st.cab_runs.length}개 세트 · 3D 장 ${n3d}`);
  // 세트 장을 고르면 '벽면 세트 편집'으로 다시 연다
  const one = st.placements.find((x) => x.cab?.run);
  await page.evaluate((id) => window.__lgbSelect?.(id), one.placement_id); await wait(1500);
  check("세트 장을 고르면 '벽면 세트 편집' 버튼", !!(await page.$("#cabRunEdit")));
  await mark();
  await page.$eval("#cabRunEdit", (b) => b.click()).catch(() => {});
  await page.waitForSelector("#elSvg", { timeout: 60000 }).catch(() => {}); await fresh(); await wait(800);
  check("저장된 세트를 같은 순서로 다시 편집", (await preview()).length >= 1);
  await shot("run_reopen.png");
  await page.$eval("#reCancel", (b) => b.click()).catch(() => {});
  check("화면 오류 없음", errors.length === 0, errors.slice(0, 3).join(" | "));
  await browser.close();
  console.log(failed ? `\n${failed}개 실패` : "\n모두 통과");
  process.exit(failed ? 1 : 0);
})();
