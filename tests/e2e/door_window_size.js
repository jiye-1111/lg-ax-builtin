// 문·창 폭 입력과 문 앞 막힘 점검: 스캔한 창을 눌러 폭을 바꾼다, 문 앞으로 옮긴 가구는 제자리로 돌아온다. 서버를 켠 뒤 실행:
//   uv run lgb-api            (다른 창)
//   node tests/e2e/door_window_size.js [http://localhost:8000] [스크린샷 폴더]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.argv[2] || "http://localhost:8000";
const SHOTS = process.argv[3] || null;
const ROOT = path.resolve(__dirname, "../..");
let failed = 0;
const check = (name, ok, info = "") => { if (!ok) failed += 1; console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  · " + info : ""}`); };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => { try { localStorage.setItem("lgb.tour.v1", "1"); } catch { /* 안내만 건너뛴다 */ } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.stack || e)));
  const api = (url, body, method = "POST") => page.evaluate(async ([u, b, m]) =>
    (await fetch(u, { method: m, headers: { "Content-Type": "application/json" }, body: b ? JSON.stringify(b) : undefined })).json(), [url, body, method]);
  const toScreen = (c, y = 0) => page.evaluate(([c, y]) => document.getElementById("viewer").viewer.toScreen(c, y), [c, y]);
  const shot = async (name) => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, name) }); };
  const sizing = () => page.evaluate(() => { const b = document.getElementById("actBar"); return !b.hidden && b.classList.contains("sizing"); });
  const reload = async () => { await page.reload(); await page.waitForSelector("#libTabs", { state: "attached", timeout: 60000 }); await page.waitForTimeout(4000); };

  await page.goto(BASE + "/#/");
  await page.setInputFiles("#file", path.join(ROOT, "data/samples/apt_living_kitchen.usdz"));
  await page.click("#go");
  await page.waitForFunction(() => location.hash.startsWith("#/c/"), null, { timeout: 60000 });
  const pid = page.url().split("#/c/")[1].split("?")[0];
  await page.waitForSelector("#libTabs", { state: "attached", timeout: 60000 });
  await page.waitForTimeout(4000);
  const getRoom = () => api(`/api/projects/${pid}/room`, null, "GET");
  let room = await getRoom();
  const at = (op, r = room) => { const w = r.walls.find((x) => x.wall_id === op.wall_id), L = Math.hypot(w.end[0] - w.start[0], w.end[1] - w.start[1]), u = (op.offset_m + op.width_m / 2) / L;
    return [[w.start[0] + (w.end[0] - w.start[0]) * u, w.start[1] + (w.end[1] - w.start[1]) * u], op.sill_m + op.height_m / 2]; };

  // 1) 스캔한 창을 누르면 폭·높이 입력이 뜬다
  let win = null;
  for (const op of room.openings.filter((o) => o.type === "window")) {
    const [xz, y] = at(op);
    await page.mouse.click(...(await toScreen(xz, y))); await page.waitForTimeout(700);
    if (await sizing()) { win = op; break; }
    await page.mouse.click(5, 5); await page.waitForTimeout(300);
  }
  check("창을 누르면 폭 입력이 뜬다", !!win, win?.opening_id);
  if (win) {
    const n = await page.locator("#actBar [data-dim]").count();
    check("입력은 폭과 높이 두 칸", n === 2, String(n));
    await shot("opening-size-bar.png");
    const mm = Math.round(win.width_m * 1000) - 400;
    await page.fill('#actBar [data-dim="w"]', String(mm));
    await page.keyboard.press("Enter"); await page.waitForTimeout(3000);
    room = await getRoom();
    const now = room.openings.find((o) => o.opening_id === win.opening_id);
    check("적은 폭대로 창이 바뀐다", Math.abs(now.width_m * 1000 - mm) < 1.5, `${now.width_m}`);
    check("가운데는 그대로", Math.abs(now.offset_m + now.width_m / 2 - win.offset_m - win.width_m / 2) < 0.01);
    await shot("opening-size-after.png");
    await page.click("#undo"); await page.waitForTimeout(2500);
    const back = (await getRoom()).openings.find((o) => o.opening_id === win.opening_id);
    check("되돌리기로 원래 폭", Math.abs(back.width_m - win.width_m) < 1e-3, `${back.width_m}`);
    room = await getRoom();
  }

  // 2) 문 앞: 판정은 불가, 문구는 한 줄
  const door = room.openings.find((o) => o.type === "door");
  const [dxz] = at(door);
  const mid = room.walls.reduce((a, w) => [a[0] + w.start[0] / room.walls.length, a[1] + w.start[1] / room.walls.length], [0, 0]);
  const dir = [mid[0] - dxz[0], mid[1] - dxz[1]], dl = Math.hypot(...dir);
  const front = [dxz[0] + (dir[0] / dl) * 0.5, dxz[1] + (dir[1] / dl) * 0.5];
  const pc = await api(`/api/projects/${pid}/pose-check`, { sku: "decor:chair", center_xz: front, yaw_rad: 0, snap: false });
  const why = (pc.reasons || []).find((r) => r.code === "door_blocked");
  check("문 앞은 불가", pc.verdict === "no_fit" && !!why, JSON.stringify((pc.reasons || []).map((r) => r.code)));
  check("문구", why?.label === "여기 두면 문을 열 수 없어요", why?.label);

  // 3) 가구를 문 앞으로 끌면 원래 자리로 돌아온다
  const far = [dxz[0] + (dir[0] / dl) * 1.9, dxz[1] + (dir[1] / dl) * 1.9];
  await api(`/api/projects/${pid}/objects/hidden`, { hidden: true }, "PUT");
  const ch = (await api(`/api/projects/${pid}/placements`, { sku: "decor:chair", center_xz: far, yaw_rad: 0, snap: false })).placement;
  check("문에서 떨어진 자리는 된다", ch.verdict !== "no_fit", JSON.stringify(ch.reasons.map((r) => r.code)));
  await reload();
  let picked = false;
  for (let i = 0; i < 6 && !picked; i++) {
    await page.mouse.click(...(await toScreen(ch.center_xz, 0.45))); await page.waitForTimeout(600);
    picked = await page.evaluate(() => !document.getElementById("actBar").hidden);
  }
  check("의자를 고른다", picked);
  const a = await toScreen(ch.center_xz, 0.45), b = await toScreen(front, 0.45);
  await page.mouse.move(...a); await page.mouse.down();
  for (let i = 1; i <= 12; i++) { await page.mouse.move(a[0] + ((b[0] - a[0]) * i) / 12, a[1] + ((b[1] - a[1]) * i) / 12); await page.waitForTimeout(40); }
  await page.waitForTimeout(500);
  await shot("door-front-dragging.png");
  await page.mouse.up();
  const said = await page.waitForFunction(() => document.body.innerText.includes("여기 두면 문을 열 수 없어요"), null, { timeout: 6000 }).then(() => true, () => false);
  await page.waitForTimeout(500);
  await shot("door-front-refused.png");
  await page.waitForTimeout(2000);
  const end = (await api(`/api/projects/${pid}`, null, "GET")).scene_state.placements.find((q) => q.placement_id === ch.placement_id);
  check("문 앞에는 안 놓인다", Math.hypot(end.center_xz[0] - ch.center_xz[0], end.center_xz[1] - ch.center_xz[1]) < 0.02, JSON.stringify(end.center_xz));
  check("문을 열 수 없다고 알려 준다", said);

  check("화면 오류 없음", errors.length === 0, errors[0] || "");
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
