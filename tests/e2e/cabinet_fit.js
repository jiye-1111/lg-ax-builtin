// 빌트인 옆에 장 짜 넣기 점검: 가전 옆에 붙기, 남는 틈 표시, mm 입력, 프리셋, 빈틈 맞춤. 서버를 켠 뒤 실행:
//   uv run lgb-api            (다른 창)
//   node tests/e2e/cabinet_fit.js [http://localhost:8000] [스크린샷 폴더]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3] || "";
const ROOT = path.resolve(__dirname, "../..");
const FRIDGE = "G646GBB031"; // 핏 앤 맥스: 옆 4 mm (LGE.COM)
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
  const v3 = (fn, ...a) => page.evaluate(([f, a]) => document.getElementById("viewer").viewer[f](...a), [fn, a]);
  // 조작 메뉴는 고른 물건을 따라 움직여서, 느린 헤드리스에서는 마우스 클릭 대신 버튼을 바로 누른다
  const press = (sel) => page.$eval(sel, (el) => el.click());
  const loaded = async () => { // 다시 열고 놓은 물건이 3D에 다 올라올 때까지
    await page.reload();
    await page.waitForSelector("#decorLib [data-decor]", { state: "attached", timeout: 60000 });
    await wait(4000);
  };
  const shot = async (name) => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, name) }); };
  const placements = async (pid) => (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements;
  const gapsOf = async (pid, x) => (await api(`/api/projects/${pid}/pose-check`, { sku: x.sku, center_xz: x.center_xz, yaw_rad: x.yaw_rad, snap: false,
    placement_id: x.placement_id, ...(x.sku.startsWith("decor:") ? { size_m: x.size_m } : {}) })).gaps;

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/ugscan_2026-11-18.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await page.waitForSelector("#libTabs");
  const fr = (await api(`/api/projects/${pid}/auto-place`, { sku: FRIDGE })).placement;
  await loaded();

  // 수납 탭에 장롱·키큰장
  await page.click('#libTabs [data-tab="storage"]');
  const tiles = await page.$$eval("#decorLib [data-decor]", (els) => els.map((e) => e.dataset.decor));
  check("수납 탭에 장롱·키큰장이 있다", tiles.includes("decor:wardrobe") && tiles.includes("decor:tallcab"), tiles.join(" "));

  // 키큰장을 들고 냉장고 오른쪽 8 cm 떨어진 곳, 벽에서 6 cm 뜬 곳을 가리킨다 → 냉장고 옆 4 mm, 벽에 붙는다
  await page.click('#decorLib [data-decor="decor:tallcab"]');
  const ux = Math.cos(fr.yaw_rad - Math.PI / 2), uz = Math.sin(fr.yaw_rad - Math.PI / 2), fx = Math.cos(fr.yaw_rad), fz = Math.sin(fr.yaw_rad);
  const off = fr.size_m[0] / 2 + 0.08 + 0.3;
  const back = -fr.size_m[2] / 2 + 0.3 + 0.03; // 냉장고 등 선 근처에서 조금 앞
  const aim = [fr.center_xz[0] + ux * off + fx * back, fr.center_xz[1] + uz * off + fz * back];
  await v3("lookAt", fr.center_xz);
  await wait(800);
  const [sx, sy] = await v3("toScreen", aim, 0);
  await page.mouse.move(sx - 30, sy - 10);
  await page.mouse.move(sx, sy, { steps: 4 });
  await wait(1500);
  const tags = await page.$$eval("#gapTags .gap-tag", (els) => els.map((e) => e.textContent.trim()));
  check("잘 붙었으면 들고 있는 동안 숫자가 뜨지 않는다", tags.length === 0, tags.join(" | "));
  await shot("cabinet-snap-follow.png");
  await page.mouse.click(sx, sy);
  await wait(2500);
  let pls = await placements(pid);
  let cab = pls.find((x) => x.sku === "decor:tallcab");
  check("누르면 놓인다", !!cab);
  let g = cab && await gapsOf(pid, cab);
  const toFridge = g && [g.left, g.right].find((q) => q.ref === fr.placement_id);
  check("냉장고 옆에 설치 여유 4 mm를 남기고 붙었다", !!toFridge && Math.abs(toFridge.mm - 4) < 0.6 && toFridge.ok === true, toFridge ? `${toFridge.mm} mm` : "옆이 냉장고가 아님");
  check("냉장고는 여전히 설치할 수 있다", pls.find((x) => x.placement_id === fr.placement_id).verdict !== "no_fit");
  const selTags = await page.$$eval("#gapTags .gap-tag", (els) => els.map((e) => e.textContent.trim()));
  check("놓은 뒤에도 숫자 없이 깔끔하다", selTags.length === 0, selTags.join(" | "));
  await shot("cabinet-snapped.png");

  // 크기 조절: mm 입력
  await press("#actSize");
  await page.fill('#actBar [data-dim="w"]', "450");
  await page.press('#actBar [data-dim="w"]', "Enter");
  await wait(2000);
  cab = (await placements(pid)).find((x) => x.sku === "decor:tallcab");
  check("폭을 mm로 적으면 그 크기가 된다", Math.abs(cab.size_m[0] - 0.45) < 1e-6, `${cab.size_m[0]} m`);
  const chips = await page.$$eval("#actBar [data-preset]", (els) => els.map((e) => e.textContent.trim()));
  check("실제 제품 치수 칩이 있다", chips.length > 0 && chips[0].includes("IKEA"), chips.join(" | "));
  await press('#actBar [data-preset="0"]');
  await wait(2000);
  cab = (await placements(pid)).find((x) => x.sku === "decor:tallcab");
  check("칩을 누르면 그 제품 치수가 된다", cab.size_m.map((v) => Math.round(v * 1000)).join("x") === "600x2000x600", cab.size_m.join(" "));
  await shot("cabinet-size-panel.png");
  await press("#szDone");

  // 빈틈 맞춤: 장이 고른 채로 있으니 메뉴에서 바로 누른다 (한쪽은 냉장고, 반대쪽은 벽까지 비어 있다)
  await wait(800);
  const hasFill = await page.$("#actFill");
  check("장을 고르면 빈틈 맞춤 버튼이 있다", !!hasFill);
  if (hasFill) {
    await press("#actFill");
    await wait(2500);
    cab = (await placements(pid)).find((x) => x.sku === "decor:tallcab");
    g = await gapsOf(pid, cab);
    const a = [g.left, g.right].find((q) => q.ref === fr.placement_id), b = [g.left, g.right].find((q) => q.ref !== fr.placement_id);
    check("빈틈 맞춤: 냉장고 쪽 4 mm, 반대쪽은 꽉 차게", !!a && Math.abs(a.mm - 4) < 0.6 && b.mm < 0.6, `${a?.mm} / ${b?.mm} mm, 폭 ${Math.round(cab.size_m[0] * 1000)}`);
    await shot("cabinet-fill-gap.png");
  }
  check("콘솔 오류 없음", errors.length === 0, errors.slice(0, 3).join(" / "));
  await browser.close();
  console.log(failed ? `\n${failed}개 실패` : "\n모두 통과");
  process.exit(failed ? 1 : 0);
})();
