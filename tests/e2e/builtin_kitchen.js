// 빌트인 주방 점검: 가전 맞춤장(냉장고·식기세척기), 측판 두께에 따른 판정, 기존 장 크기 유지, 문 열림 3D 근사,
// 헤드리스(소프트웨어 그리기)에서는 3D가 메인 스레드를 오래 잡아 다시 읽기가 10초쯤 걸린다. 그래서 기다림을 넉넉히 둔다
// 유리 상부장, 마감 바꾸기, 저장 후 다시 열기. 서버를 켠 뒤 실행:
//   uv run lgb-api            (다른 창)
//   node tests/e2e/builtin_kitchen.js [http://localhost:8000] [스크린샷 폴더]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3] || "";
const ROOT = path.resolve(__dirname, "../..");
const FRIDGE = "G646GBB031"; // 핏 앤 맥스 (공식 설치 기준 연결)
const DW = "DUE6BGL2E"; // 빌트인 식기세척기 DU (일반 걸레받이용)
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
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); if (process.env.DEBUG && m.text().startsWith("DBGL")) console.log("   ", m.text()); });
  const wait = (ms) => page.waitForTimeout(ms);
  const api = (url, body, method = "POST") => page.evaluate(async ([u, b, m]) => {
    const r = await fetch(u, { method: m, headers: { "Content-Type": "application/json" }, body: b ? JSON.stringify(b) : undefined });
    return r.json();
  }, [url, body, method]);
  // 패널은 움직이는 동안 요소 스크린샷이 멈추므로, 그 자리만 잘라 찍는다
  const shot = async (name, el) => {
    if (!SHOTS) return;
    const clip = el ? await page.$eval(el, (e) => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: Math.min(r.height, innerHeight - r.y) }; }) : undefined;
    await page.screenshot({ path: path.join(SHOTS, name), ...(clip && clip.width > 0 && clip.height > 0 ? { clip } : {}) });
  };
  const placements = async (pid) => (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements;
  const loaded = async () => {
    await page.reload();
    await page.waitForSelector("#libTabs", { state: "attached", timeout: 60000 });
    await wait(4000);
  };
  // 3D에서 장을 눌러 고른다 (장 가운데 높이)
  const pickPl = async (x, y = 0.5) => {
    await page.evaluate(([c]) => document.getElementById("viewer").viewer.lookAt?.(c), [x.center_xz]);
    await wait(900);
    const [sx, sy] = await page.evaluate(([c, h]) => document.getElementById("viewer").viewer.toScreen(c, h), [x.center_xz, y]);
    await page.mouse.click(sx, sy);
    await wait(900);
  };
  // 패널을 고친 뒤 서버 응답으로 패널이 다시 그려질 때까지 (느린 헤드리스에서는 3D 그리기가 몇 초 걸린다)
  const panelNode = () => page.evaluate(() => { const p = document.querySelector(".cab-panel"); if (p) p.dataset.old = "1"; });
  const freshPanel = () => page.waitForFunction(() => { const p = document.querySelector(".cab-panel"); return p && !p.dataset.old; }, null, { timeout: 45000 }).catch(() => {});
  const act = async (fn) => { await panelNode(); await fn(); await freshPanel(); await wait(300); };
  const setNum = (sel, v) => act(() => page.$eval(sel, (el, v) => { el.value = String(v); el.dispatchEvent(new Event("change", { bubbles: true })); }, v));
  const tap = (sel) => act(() => page.$eval(sel, (b) => b.click()));
  const choose = (v) => act(() => page.selectOption("#cabApp", v));

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await page.waitForSelector("#libTabs");
  await wait(3000);

  // 1. 빌트인 주방 탭
  await page.$eval('#libTabs [data-tab="kitchen"]', (b) => b.click()); await wait(500);
  const tiles = await page.$$eval("#decorLib [data-decor]", (els) => els.map((e) => e.dataset.decor));
  check("빌트인 주방 탭에 맞춤장·주방 모듈이 있다", ["fridge", "dishwasher", "sink", "drawer", "wall", "pantry", "glass_wall", "counter"].every((k) => tiles.includes(`decor:cab_${k}`)), tiles.join(" "));
  await shot("kitchen_lib.png");

  // 2. 제품 상세에서 '맞춤장에 넣기' → 새 장 + 공식 권장 안쪽 치수
  await page.$eval('#libTabs [data-tab="lg"]', (b) => b.click()); await wait(500);
  await page.evaluate((sku) => document.querySelector(`[data-sku="${sku}"]`)?.click(), FRIDGE);
  await wait(800);
  if (!(await page.$("#pdCab"))) { // 목록에 바로 안 보이면 상세를 직접 연다
    await page.evaluate((sku) => document.querySelector(`[data-sugg="${sku}"]`)?.click(), FRIDGE);
    await wait(800);
  }
  check("빌트인 냉장고 상세에 '맞춤장에 넣기'가 있다", !!(await page.$("#pdCab")));
  if (await page.$("#pdCab")) await page.$eval("#pdCab", (b) => b.click());
  else await api(`/api/projects/${pid}/cabinets`, { kind: "fridge", sku: FRIDGE });
  await wait(3000);
  let pls = await placements(pid);
  let cab = pls.find((q) => q.cab?.kind === "fridge");
  let fr = cab && pls.find((q) => q.in_cab === cab.placement_id);
  check("냉장고장이 생기고 냉장고가 장 안에 들어간다", !!(cab && fr && fr.sku === FRIDGE));
  check("새 장은 공식 권장 안쪽(설계값)으로 적합", cab?.cab_check?.verdict === "fit" && cab.cab_check.axes[0].source === "designed", JSON.stringify(cab?.cab_check?.axes?.map((a) => a.have_mm)));
  check("가전 3D 크기는 카탈로그 그대로", fr && Math.abs(fr.size_m[0] - 0.914) < 1e-6);
  await page.waitForSelector(".cab-panel .cab-verdict", { timeout: 45000 }).catch(() => {}); // 놓으면 그 장을 고른 채로 패널이 뜬다
  if (!(await page.$(".cab-panel"))) { console.log("  (놓은 뒤 패널이 안 떠서 3D에서 다시 고름)"); await pickPl(cab, 1.0); }
  check("오른쪽에 맞춤장 패널과 공식 판정이 뜬다", !!(await page.$(".cab-panel .cab-verdict.v-fit")));
  await shot("fridge_fit.png");
  await shot("fridge_panel.png", ".cab-panel");

  // 3. 같은 외경에서 왼쪽 측판을 25 mm로 → 불가, 폭 7 mm 부족
  await setNum("[data-p-side_l]", 25);
  pls = await placements(pid);
  cab = pls.find((q) => q.placement_id === cab.placement_id);
  const w = cab.cab_check.axes.find((a) => a.axis === "w");
  check("측판을 두껍게 하면 외경은 그대로, 판정이 불가로 바뀐다", cab.cab.outer_mm.w === 958 && cab.cab_check.verdict === "no_fit" && w.short_mm === 7, `${cab.cab_check.verdict} short ${w.short_mm}`);
  await page.waitForSelector(".cab-verdict.v-no_fit", { timeout: 30000 }).catch(() => {});
  const shortTxt = await page.$eval(".cab-verdict", (el) => el.textContent);
  check("패널에 부족 mm가 보인다", /7 mm 부족/.test(shortTxt) && !!(await page.$(".cab-verdict.v-no_fit")));
  await shot("fridge_nofit.png", ".cab-panel");
  await setNum("[data-p-side_l]", 18);

  // 4. 기존 장에 넣기: 실측값 그대로, 가전을 바꿔도 장 크기는 그대로
  await tap('.cab-mode [data-mode="existing"]');
  if (!(await page.waitForSelector("[data-md]", { state: "attached", timeout: 45000 }).catch(() => null))) {
    const now = (await placements(pid)).find((q) => q.placement_id === cab.placement_id);
    console.log("  기존 장 입력칸이 안 뜸 · 서버 mode", now.cab.mode, await page.evaluate(() => [...document.querySelectorAll(".toast,#toast")].map((t) => t.textContent).join("|")), errors);
  }
  await setNum("[data-md]", 715);
  pls = await placements(pid);
  cab = pls.find((q) => q.placement_id === cab.placement_id);
  check("기존 장은 실측값 기준", cab.cab.mode === "existing" && cab.cab_check.axes[0].source === "measured", cab.cab_check.verdict);
  const before = JSON.stringify(cab.cab.outer_mm);
  await choose("Z386GBB281");
  pls = await placements(pid);
  cab = pls.find((q) => q.placement_id === cab.placement_id);
  check("기존 장에서 가전을 바꿔도 장 크기는 그대로", JSON.stringify(cab.cab.outer_mm) === before && pls.find((q) => q.in_cab === cab.placement_id)?.sku === "Z386GBB281");

  // 5. 공식 기준 없는 가전 → 판정 불가 (외형만)
  const noRule = await page.$$eval("#cabApp optgroup:nth-of-type(2) option", (os) => os.map((o) => o.value));
  if (noRule.length) {
    await choose(noRule[0]);
    cab = (await placements(pid)).find((q) => q.placement_id === cab.placement_id);
    await page.waitForSelector(".cab-verdict.v-unknown", { timeout: 30000 }).catch(() => {});
    check("공식 기준이 없는 가전은 판정 불가, 외형 비교는 보인다", cab.cab_check.verdict === "unknown" && !!(await page.$(".cab-verdict.v-unknown .cab-tbl")));
  } else check("공식 기준이 없는 가전 후보가 목록에 있다", false);
  await tap('.cab-mode [data-mode="new"]');
  await choose(FRIDGE);

  // 6. 식기세척기 자리 + 걸레받이 간섭 (3D 근사)
  const dw = (await api(`/api/projects/${pid}/cabinets`, { kind: "dishwasher", sku: DW })).placement;
  await loaded();
  await page.$eval('#libTabs [data-tab="kitchen"]', (b) => b.click()); await wait(500);
  await pickPl(dw, 0.45);
  check("식기세척기 자리 패널이 뜬다", !!(await page.$(".cab-panel")) && (await page.$eval(".cab-panel", (e) => e.textContent)).includes("식기세척기"));
  const dwTxt = await page.$eval(".cab-panel", (e) => e.textContent);
  check("급수·배수·전원은 현장 확인으로 남는다", /현장 확인/.test(dwTxt));
  await shot("dw_panel.png", ".cab-panel");
  await act(() => page.$eval("[data-t-kick_across]", (el) => { el.checked = true; el.dispatchEvent(new Event("change", { bubbles: true })); }));
  await setNum("[data-p-toe_kick]", 180);
  const bad = await page.$(".cab-door.bad");
  check("걸레받이를 문 밑보다 높게 이으면 3D 문 열림 경고", !!bad, bad ? await bad.textContent() : "");
  await shot("dw_kick_warn.png");
  await setNum("[data-p-toe_kick]", 150);
  check("걸레받이를 낮추면 경고가 풀린다", !!(await page.$(".cab-door.ok")));

  // 7. 유리 상부장 + 마감 (여러 장 같이)
  const gl = (await api(`/api/projects/${pid}/cabinets`, { kind: "glass_wall" })).placement;
  await loaded();
  await pickPl(gl, (gl.base_m || 1.45) + 0.35);
  const hasPanel = !!(await page.$(".cab-panel"));
  check("유리 상부장 패널이 뜬다", hasPanel);
  if (hasPanel) {
    await tap('.cab-sw[data-fpart="glass"][data-fin="bronze"]');
    await tap('.cab-sw[data-fpart="front"][data-fin="sage_matte"]');
  }
  const meshes = await page.evaluate(() => {
    const v = document.getElementById("viewer").viewer, out = { glass: 0, shelf: 0, transparent: 0 };
    v.scene?.traverse?.((o) => { if (o.userData?.role === "glass") { out.glass++; if (o.material.transparent && o.material.opacity < 0.5) out.transparent++; } if (o.userData?.role === "shelf") out.shelf++; });
    return out;
  });
  check("유리장은 유리가 투명하고 안의 선반이 있다", meshes.glass > 0 && meshes.transparent === meshes.glass && meshes.shelf > 0, JSON.stringify(meshes));
  await shot("glass_wall.png");

  // 8. 저장 후 다시 열기: 치수·배치·가전 연결·마감이 그대로
  const snap = (await placements(pid)).filter((q) => q.cab).map((q) => JSON.stringify([q.cab.kind, q.cab.outer_mm, q.cab.parts, q.cab.finish, q.cab.glass, q.center_xz]));
  await loaded();
  const again = await placements(pid);
  const snap2 = again.filter((q) => q.cab).map((q) => JSON.stringify([q.cab.kind, q.cab.outer_mm, q.cab.parts, q.cab.finish, q.cab.glass, q.center_xz]));
  check("다시 열어도 장 치수·자리·마감이 그대로", JSON.stringify(snap) === JSON.stringify(snap2));
  check("다시 열어도 가전이 장 안에 그대로", again.some((q) => q.in_cab && q.sku === FRIDGE) && again.some((q) => q.in_cab && q.sku === DW));
  const g2 = again.find((q) => q.placement_id === gl.placement_id);
  check("유리·앞판 마감이 저장된다", g2?.cab?.glass === "bronze" && g2.cab.finish.front === "sage_matte", JSON.stringify(g2?.cab?.finish));

  check("화면 오류 없음", errors.length === 0, errors.slice(0, 3).join(" | "));
  await browser.close();
  console.log(failed ? `\n${failed}개 실패` : "\n모두 통과");
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
