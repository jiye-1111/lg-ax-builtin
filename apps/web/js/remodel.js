// 화면: 우리 집 가상 리모델링 (제품 배치, 색·재질, 살아 보기)
import { $app, cleanup, LABEL, shownVerdict, PURPOSE, USE, CATEGORY, CATEGORY_GROUP, DIM, OBJ, NOTE, esc, mm, api, apiUrl, post, put, toast, guard,
  rememberHome, forgetHome, uiState, saveUiState } from "./core.js";
import { makeViewer } from "./viewer.js";
import { buildWorld } from "./walk.js";
import { planView, placedSvg } from "./plan.js";
import { wallTable, WALL_HEAD, floorplanBox, installCheck, installRequestBox } from "./pages.js";
import { swatchUrl, TEXTURE_KO } from "./finishes.js";
import { mountSaveBar } from "./account.js";
import { stepState, stepperHtml, fitCardHtml, VERDICT_LABEL } from "./guide.js";
import { optionSteps } from "./options.js";
import { startTour, tourSeen } from "./tour.js";

// 이 폭 이하(폰·태블릿·작은 앱 창)는 앱 배치: 3D 꽉 차게, 제품은 아래 서랍
const APP_MAX_W = 1100;

export async function customer(pid) {
  const token = new URLSearchParams(location.hash.split("?")[1] || "").get("t");
  const saved = uiState(pid); // 다른 화면에 다녀와도 보던 그대로
  $app.innerHTML = `
    <div class="studio" data-view="3d">
      <header class="studio-head">
        <div class="studio-title"><h1>우리 집 가상 리모델링</h1><p class="sub" id="sub">불러오는 중…</p></div>
        <ol class="steps5 steps3" id="progress" aria-label="진행 단계"></ol>
        <details class="home-menu" id="homeMenu"><summary aria-label="저장·다른 집"><i class="save-dot" aria-hidden="true"></i>저장 · 내 집 <span aria-hidden="true">▾</span></summary>
          <div class="home-pop">
            <div class="savebar" id="savebar" aria-label="저장"></div>
            <button class="btn ghost small app-only" id="extraBtn2">도면·실측 넣기</button>
            <a class="btn ghost small new-scan" href="#/new" title="지금 집은 그대로 남고, 다른 집을 새로 올려요">+ 다른 집 스캔</a>
          </div></details>
      </header>

      <aside class="lib" data-panel="lib" aria-label="LG 제품">
        <div class="lib-side">
          <div class="lib-head"><h2>LG 제품</h2><span class="muted" id="libCount"></span>
            <select id="sortBy" aria-label="정렬"><option value="">추천순</option><option value="price">낮은 가격순</option><option value="size">작은 크기순</option></select>
            <button class="primary small app-only" id="orderMini" hidden>구매·설치 신청</button>
            <button class="ghost small app-only" id="libMore" aria-expanded="false">전체 보기</button></div>
          <input id="q" type="search" placeholder="이름·모델명 검색" aria-label="제품 검색">
          <div class="ask" id="ask" aria-label="공간 용도"></div>
          <div class="chips" id="cats" aria-label="가전 종류"></div>
          <section class="sugg" id="sugg" aria-label="이 집에 들어가는 제품" hidden></section>
          <details class="more-filter" id="moreFilter"><summary>상세 필터 <span class="muted" id="filterOn"></span></summary>
            <ol class="opt-steps" id="steps" aria-label="옵션을 차례로 골라 좁히기"></ol>
            <div class="filters" aria-label="크기 필터">
              <select id="fW" aria-label="폭"><option value="">폭 전체</option><option value="0-650">650 mm 이하</option><option value="650-850">650~850 mm</option><option value="850-99999">850 mm 이상</option></select>
              <select id="fH" aria-label="높이"><option value="">높이 전체</option><option value="0-900">900 mm 이하</option><option value="900-1800">900~1,800 mm</option><option value="1800-99999">1,800 mm 이상</option></select>
            </div>
            <button class="small ghost reset-filter" id="resetFilter">필터 초기화</button>
          </details>
        </div>
        <ul class="list" id="lib" aria-label="LG 제품 목록. 누른 뒤 3D 바닥을 누르면 놓여요"></ul>
      </aside>

      <section class="stage" aria-label="우리 집">
        <section class="pd-modal" id="pdModal" role="dialog" aria-label="제품 상세" hidden></section>
        <section class="order-sheet" id="orderSheet" role="dialog" aria-label="구매 및 설치 신청" hidden></section>
        <div class="toolbar">
          <button class="furn-btn" id="beforeBtn" aria-pressed="false" title="스캔했을 때 모습과 견줘 봐요">처음과 비교</button>
          <button class="furn-btn live-btn" id="liveBtn" aria-pressed="false" title="실제로 살아 보듯 둘러보고, 볕·와이파이·동선을 봐요"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11 12 4l9 7v9H3z"/><path d="M9 20v-6h6v6"/></svg>살아 보기</button>
          <button class="furn-btn" id="finBtn" aria-expanded="false" aria-controls="finishPop" title="벽지·바닥재를 바꿔 봐요">벽지·바닥</button>
          <button class="furn-btn" id="furn" title="스캔에 잡힌 가구를 한꺼번에 치우거나 되돌려요">가구 치우기</button>
          <button class="furn-btn" id="extraBtn" aria-expanded="false" aria-controls="extraPop" title="도면을 올리거나 줄자로 잰 벽 길이를 넣어요">도면·실측</button>
          <span class="spacer"></span>
          <div class="icon-row" role="group" aria-label="되돌리기">
            <button class="icon-btn" id="undo" disabled aria-label="되돌리기" title="되돌리기 (Ctrl+Z)"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/></svg></button>
            <button class="icon-btn" id="redo" disabled aria-label="다시 실행" title="다시 실행 (Ctrl+Shift+Z)"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="m15 14 5-5-5-5"/><path d="M20 9H10a6 6 0 0 0 0 12h3"/></svg></button>
            <button class="icon-btn" id="fullBtn" aria-label="전체 화면" title="전체 화면"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg></button>
            <button class="icon-btn" id="tourBtn" aria-label="화면 안내 다시 보기" title="화면 안내 다시 보기"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6M12 17h.01"/></svg></button>
            <button class="icon-btn" id="keysBtn" aria-expanded="false" aria-controls="keysPop" aria-label="조작키" title="마우스·키보드 조작 방법"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/></svg></button>
          </div>
        </div>
        <div class="live-bar" id="liveBar" role="group" aria-label="살아 보기" hidden>
          <span class="live-tag">살아 보기</span>
          <div class="seg sims">
            <button class="furn-btn" id="walk" title="눈높이 1.6 m에서 집 안을 걸어 봐요 (WASD 걷기, 화면을 누르면 마우스로 둘러보기)">둘러보기</button><button data-sim="daylight"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>채광</button><button data-sim="wifi"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M2 9a15 15 0 0 1 20 0"/><circle cx="12" cy="19.5" r="1"/></svg>와이파이</button><button data-sim="flow"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="13" cy="4" r="2"/><path d="m9 21 2.5-6.5L14 17v4M7 11l3-3.5h4l2.5 4.5M10.5 7.5 9 14"/></svg>동선</button></div>
          <button class="ghost small" id="liveEnd">끝내기</button>
        </div>
        <div class="canvas">
          <div class="pane plan-pane"><svg class="plan" id="plan" aria-label="평면도"></svg>
            <button class="pip-swap" data-swap="plan" title="평면도를 크게 보기">평면도 보기</button></div>
          <div class="pane view-pane"><div class="viewer" id="viewer"><span class="hud" id="hud"></span></div>
            <button class="pip-swap" data-swap="3d" title="3D를 크게 보기">3D 보기</button>
            <button class="render-btn" id="render">렌더 이미지</button>
            <div class="before-pane" id="beforePane" hidden><div class="viewer" id="beforeViewer"></div><span class="before-tag">스캔했을 때 모습</span></div></div>
          <div class="keys-pop" id="keysPop" role="dialog" aria-label="조작키" hidden>
            <div class="keys-head"><b>조작키</b><button class="ghost small" id="keysClose">닫기</button></div>
            <h4>제품</h4>
            <p class="hint-sm">아래 이동·회전·자동 정렬·삭제 버튼으로 다 할 수 있어요. 키보드가 편하면:</p>
            <ul class="keys"><li><kbd>클릭</kbd> 집어 들기 · 내려놓기</li><li><kbd>R</kbd> 45° 돌리기 (<kbd>Shift</kbd> 반대, <kbd>Alt</kbd> 15°)</li>
              <li><kbd>←↑↓→</kbd> 10 cm 옮기기 (<kbd>Shift</kbd> 1 cm)</li><li><kbd>Delete</kbd> 지우기</li><li><kbd>Ctrl</kbd><kbd>Z</kbd> 되돌리기 · <kbd>Ctrl</kbd><kbd>Shift</kbd><kbd>Z</kbd> 다시 실행</li><li><kbd>Esc</kbd> 취소</li></ul>
            <h4>화면</h4>
            <ul class="keys"><li><kbd>빈 곳 끌기</kbd> 시점 돌리기</li><li><kbd>휠</kbd> 확대·축소</li><li><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> 카메라 이동 · <kbd>Q</kbd><kbd>E</kbd> 돌기</li></ul>
            <h4>둘러보기</h4>
            <ul class="keys"><li><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> 걷기 · <kbd>Shift</kbd> 빠르게</li><li><kbd>Esc</kbd> 마우스 풀기</li></ul>
            <h4>저장 (로그인하면)</h4>
            <ul class="keys"><li><kbd>Ctrl</kbd><kbd>S</kbd> 지금 상태 저장 (맥 <kbd>⌘</kbd><kbd>S</kbd>) · 10초마다 자동 저장</li></ul>
          </div>
          <section class="finish-pop" id="finishPop" role="dialog" aria-label="벽지·바닥" hidden>
            <div class="keys-head"><b>벽지 · 바닥</b><button class="ghost small" id="finClose">닫기</button></div>
            ${aiBoxHtml("finish")}
            <h3 class="gap">벽지 <span class="muted">2026 트렌드 실제 제품</span></h3><div class="fin-grid" id="finWall"></div>
            <h3 class="gap">바닥재</h3><div class="fin-grid" id="finFloor"></div>
            <p class="hint-sm fin-note">색은 화면용 근사색이에요. 실제 품번 색은 제조사 샘플북으로 확인해 주세요. 카드의 ‘출처’에서 원문을 볼 수 있어요.</p>
            <details class="gap"><summary>색만 바꾸기</summary><div id="mats"></div></details>
            <h3 class="gap">지금 스타일</h3><div id="style"></div>
          </section>
          <section class="extra-pop" id="extraPop" role="dialog" aria-label="도면·실측" hidden>
            <div class="keys-head"><b>도면·실측 <span class="muted">선택</span></b><button class="ghost small" id="extraClose">닫기</button></div>
            <p class="hint-sm">스캔만으로도 판정해요. 도면이나 줄자로 잰 값이 있으면 넣어 주세요. 더 촘촘하게 판정해요.</p>
            <h3>도면</h3><div id="fpBox"></div>
            <h3 class="gap">벽 실측값 (m)</h3>
            <p class="hint-sm">평면의 벽 번호를 보고, 잰 값만 넣으면 됩니다.</p>
            <div class="table-scroll"><table>${WALL_HEAD}<tbody id="walls"></tbody></table></div>
          </section>
          <figure class="render-shot" id="renderBox" hidden><img id="renderImg" alt="렌더 결과"><button class="ghost small" id="renderClose">닫기</button></figure>
          <section class="minimap" id="minimap" aria-label="작은 화면" hidden></section>
          <p class="hint" id="hint" aria-live="polite"></p>
          <div class="step-card" id="stepCard" aria-live="polite" hidden></div>
          <p class="fit-badge" id="fitBadge" aria-live="polite" hidden></p>
          <div class="act-bar" id="actBar" role="toolbar" aria-label="고른 제품 조작" hidden></div>
          <p class="need-tag" id="needTag" hidden><i aria-hidden="true"></i>점선 안은 제품과 문을 여는 데 필요한 공간이에요</p>
          <div class="sheet" id="simctl"></div>
        </div>
      </section>

      <aside class="side" aria-label="고른 제품">
        <div class="side-body">
          <section id="insp"></section>
          <section class="pl-box" id="plBox" aria-label="놓은 제품">
            <h3>놓은 제품 <span class="count" id="plCount">0</span></h3>
            <ul class="list" id="pls"></ul>
            <details class="gap ic-fold" id="icFold"><summary>설치 전에 확인할 것</summary><div id="icBox"></div></details></section>
        </div>
        <div class="order-bar"><button class="primary" id="orderBtn">구매 및 설치 신청 <span aria-hidden="true">›</span></button></div>
      </aside>
      ${botHtml()}
    </div>`;
  const studio = $app.querySelector(".studio");
  // 앱(폰·작은 창): 3D를 꽉 채우고, 제품은 아래 서랍, 고른 제품은 아래 카드로. 덜 쓰는 버튼은 숨긴다
  const appMq = matchMedia(`(max-width: ${APP_MAX_W}px)`);
  const libMore = document.getElementById("libMore");
  const openLib = (on) => { studio.classList.toggle("lib-open", on); libMore.textContent = on ? "접기" : "전체 보기"; libMore.setAttribute("aria-expanded", on); };
  const syncApp = () => { studio.classList.toggle("app", appMq.matches); if (!appMq.matches) openLib(false); };
  syncApp();
  appMq.addEventListener("change", syncApp);
  cleanup.push(() => appMq.removeEventListener("change", syncApp));
  libMore.onclick = () => openLib(!studio.classList.contains("lib-open"));
  studio.addEventListener("click", (e) => { if (e.target === studio) openLib(false); }); // 서랍 바깥 어두운 곳
  document.getElementById("q").addEventListener("focus", () => { if (studio.classList.contains("app")) openLib(true); });
  // 큰 화면이 아닌 쪽(평면 또는 3D)은 오른쪽 패널 아래 미니맵으로 옮겨서 시야를 가리지 않게 한다
  const canvasEl = studio.querySelector(".canvas"), minimap = document.getElementById("minimap");
  const planPane = studio.querySelector(".plan-pane"), viewPane = studio.querySelector(".view-pane");
  const placePanes = (v) => {
    const small = v === "3d" ? planPane : v === "plan" ? viewPane : null;
    canvasEl.prepend(planPane);
    planPane.after(viewPane);
    if (small) minimap.append(small);
    minimap.hidden = !small;
    studio.classList.toggle("has-mini", !!small);
  };
  placePanes(studio.dataset.view);
  const VIEWS = ["3d", "plan"];
  // 오른쪽은 탭 없이: 고른 제품 카드, 안 골랐으면 놓은 제품 목록. 벽지·바닥은 3D 위 버튼 창
  const setTab = (t) => {
    if (t === "finish") { showFin(true); return; }
    if (t === "list" && selPl) { selPl = null; selObj = null; draw(); renderInspector(); renderPlacements(); }
  };
  const finishPop = document.getElementById("finishPop"), finBtn = document.getElementById("finBtn");
  const showFin = (on) => { finishPop.hidden = !on; finBtn.classList.toggle("on", on); finBtn.setAttribute("aria-expanded", on); };
  finBtn.onclick = () => showFin(finishPop.hidden);
  document.getElementById("finClose").onclick = () => showFin(false);
  finishPop.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); showFin(false); finBtn.focus(); } });
  // 처음 모습: 스캔 그대로의 집을 같은 시점으로 3D 위에 겹쳐 보여 준다 (지금 꾸민 것은 건드리지 않는다)
  const beforeBtn = document.getElementById("beforeBtn"), beforePane = document.getElementById("beforePane");
  let beforeViewer = null;
  const showBefore = async (on) => {
    beforeBtn.setAttribute("aria-pressed", on);
    beforeBtn.textContent = on ? "지금 모습 보기" : "처음과 비교"; beforeBtn.classList.toggle("on", on);
    beforePane.hidden = !on;
    if (!on) { if (beforeViewer) viewer.setCamera(beforeViewer.camera()); beforeViewer?.dispose(); beforeViewer = null; return; }
    beforeViewer = makeViewer(document.getElementById("beforeViewer"));
    beforeViewer.setCamera(viewer.camera());
    const scan = await api(`/api/projects/${pid}/files/room.json`);
    if (!beforeViewer) return;
    beforeViewer.setObjects(scan.objects);
    beforeViewer.load(apiUrl(`/api/projects/${pid}/files/before.glb`));
  };
  beforeBtn.onclick = guard(() => showBefore(beforePane.hidden));
  cleanup.push(() => beforeViewer?.dispose());
  // 조작키 창: 버튼으로 열고 닫는다
  const keysPop = document.getElementById("keysPop"), keysBtn = document.getElementById("keysBtn");
  const showKeys = (on) => { keysPop.hidden = !on; keysBtn.classList.toggle("on", on); keysBtn.setAttribute("aria-expanded", on); };
  keysBtn.onclick = () => showKeys(keysPop.hidden);
  document.getElementById("keysClose").onclick = () => showKeys(false);
  // 도면·실측: 탭 대신 버튼 하나로 여는 창
  const extraPop = document.getElementById("extraPop"), extraBtn = document.getElementById("extraBtn");
  const showExtra = (on) => { extraPop.hidden = !on; extraBtn.classList.toggle("on", on); extraBtn.setAttribute("aria-expanded", on); if (on) showKeys(false); };
  extraBtn.onclick = () => showExtra(extraPop.hidden);
  document.getElementById("extraBtn2").onclick = () => { document.getElementById("homeMenu").open = false; showExtra(true); };
  document.getElementById("extraClose").onclick = () => showExtra(false);
  extraPop.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); showExtra(false); extraBtn.focus(); } });
  // 저장·다른 집 메뉴: 바깥을 누르면 닫는다
  const homeMenu = document.getElementById("homeMenu");
  const closeMenu = (e) => { if (homeMenu.open && !homeMenu.contains(e.target)) homeMenu.open = false; };
  document.addEventListener("pointerdown", closeMenu);
  cleanup.push(() => document.removeEventListener("pointerdown", closeMenu));
  // 전체 화면: 3D 쪽만 크게
  const fullBtn = document.getElementById("fullBtn");
  fullBtn.onclick = () => {
    if (document.fullscreenElement) document.exitFullscreen?.();
    else studio.querySelector(".stage").requestFullscreen?.().catch(() => toast("이 브라우저는 전체 화면을 지원하지 않아요", true));
  };
  const onFull = () => { fullBtn.classList.toggle("on", !!document.fullscreenElement); viewer?.reframe(true); };
  document.addEventListener("fullscreenchange", onFull);
  cleanup.push(() => document.removeEventListener("fullscreenchange", onFull));
  const setView = (v, keepCamera = false) => {
    if (v === "plan" && walking) setWalking(false); // 평면만 볼 때는 둘러보기를 끝낸다
    studio.dataset.view = v;
    placePanes(v);
    saveUiState(pid, { view: v });
    studio.querySelectorAll(".toolbar [data-view]").forEach((b) => b.classList.toggle("on", b.dataset.view === v));
    viewer?.reframe(keepCamera);
  };
  // ---- 1인칭 둘러보기: 눈높이에서 걸어 보기. 켜져 있는 동안 집어 들기·배치·건축 키는 꺼진다 ----
  let walking = false;
  const walkWorld = () => buildWorld(room, project.scene_state.placements, project.scene_state.hidden_objects);
  const setWalking = (on) => {
    walking = !!(on && room && viewer);
    if (walking) {
      if (studio.dataset.view === "plan") setView("3d");
      armed = null; ghost(null); renderLib();
      viewer.setWalk(walkWorld());
    } else viewer?.setWalk(null);
    const b = document.getElementById("walk");
    b.classList.toggle("on", walking);
    studio.classList.toggle("walking", walking);
    b.textContent = walking ? "걷기 끝내기" : "둘러보기";
    setHint();
    if (walking) document.getElementById("hint").textContent = "둘러보기: 화면을 누르면 마우스로 둘러봐요 · W A S D 걷기 · Shift 빠르게 · Esc 마우스 풀기 · 벽·가구·제품은 못 지나가요";
  };
  document.getElementById("walk").onclick = () => setWalking(!walking);
  // 살아 보기: 버튼 하나로 들어가서 둘러보기·채광·와이파이·동선을 고른다 (켜고 끄는 토글 줄은 이 안에만)
  const liveBtn = document.getElementById("liveBtn"), liveBar = document.getElementById("liveBar");
  const setLive = (on) => {
    liveBar.hidden = !on; liveBtn.classList.toggle("on", on); liveBtn.setAttribute("aria-pressed", on);
    studio.classList.toggle("living", on);
  };
  liveBtn.onclick = () => (liveBar.hidden ? setLive(true) : endLive());
  const endLive = () => { if (walking) setWalking(false); if (sim) { sim = ""; saveUiState(pid, { sim }); showSim(); } setLive(false); };
  document.getElementById("liveEnd").onclick = endLive;
  studio.querySelectorAll(".toolbar [data-view]").forEach((b) => (b.onclick = () => setView(b.dataset.view)));
  studio.querySelectorAll("[data-swap]").forEach((b) => (b.onclick = () => setView(b.dataset.swap)));
  // 3D 안에서 바로 놓기·옮기기·고르기 (plans/virtual-remodel.md S10)
  let drag3d = null;
  const viewer = makeViewer(document.getElementById("viewer"), {
    canDrag: () => mode === "move" && !armed && !armedRouter && !armedMark,
    onHover: (p) => { if (armed && mode === "move") preview({ sku: armed, center_xz: p, yaw_rad: Math.PI / 2 }); },
    onLeave: () => { if (armed) ghost(null); },
    onClick: ({ hit, point }) => {
      if (point && floorAction(point)) return;
      if (hit?.type === "router") { if (mode === "move" && !armed) pickUp(hit, point); return; }
      if (hit?.type === "placement") { selPl = hit.id; selObj = null; setTab("sel"); }
      else if (hit?.type === "object") { selObj = hit.id; selPl = null; setTab("sel"); }
      else { selPl = null; selObj = null; }
      draw(); renderInspector(); renderPlacements();
      // 누르면 고르기만 한다. 옮기기는 끌거나 아래 '이동' 버튼으로 (키보드 없이도 되게)
    },
    onHoldMove: (h, xz) => {
      if (h.kind !== "placement") return;
      const x = project.scene_state.placements.find((q) => q.placement_id === h.id);
      if (x) preview({ sku: x.sku, center_xz: xz, yaw_rad: h.yaw, placement_id: h.id }, (r) => viewer.holdVerdict(r.verdict));
    },
    onHoldClick: () => putDown(),
    onDragMove: (id, c) => {
      const x = project.scene_state.placements.find((q) => q.placement_id === id);
      if (!x) return;
      drag3d = id; selPl = id; selObj = null;
      preview({ sku: x.sku, center_xz: c, yaw_rad: x.yaw_rad, placement_id: id }, (r) => viewer.setDragVerdict(id, r.verdict));
    },
    onDragEnd: (id, c) => {
      const x = project.scene_state.placements.find((q) => q.placement_id === id);
      drag3d = null;
      setTab("sel");
      if (x) patch(id, { center_xz: c, yaw_rad: x.yaw_rad });
    },
    onDropSku: (sku, p) => placeAt(sku, p),
  });
  const saveCamera = () => { try { saveUiState(pid, { cam: viewer.camera() }); } catch { /* 이미 닫힌 화면 */ } };
  cleanup.push(saveCamera, () => viewer.dispose()); // 화면을 떠나기 전에 카메라부터 적어 둔다
  window.addEventListener("pagehide", saveCamera);
  cleanup.push(() => window.removeEventListener("pagehide", saveCamera));
  const restoredCam = viewer.setCamera(saved.cam);
  if (VIEWS.includes(saved.view) && saved.view !== "3d") setView(saved.view, restoredCam);
  const svg = document.getElementById("plan");
  let renderProgress = () => {}, setFlow = () => {}; // 3단계 진행 표시 (아래에서 채운다)
  let mode = "move", draft = [], dragging = null, version = -1, zoneSel = null, project, room, zones, pv;
  let armed = null, selPl = null, selObj = null, drag = null, cat = typeof saved.cat === "string" ? saved.cat : "", catalog = [];
  let sim = "", overlay = "", simState = { date: new Date().toISOString().slice(0, 10), time: "12:00", heat: false }, regions = null;
  const prodOf = (sku) => catalog.find((p) => p.sku === sku);
  const HINT = {
    move: "제품이나 가구를 누르면 고를 수 있어요. 아래 버튼으로 옮기고 돌려 보세요",
    rect: "평면도에서 드래그해 영역을 그리세요 (5cm 단위).",
    poly: "꼭짓점을 차례로 누르고, 첫 점을 다시 누르거나 더블클릭하면 완성됩니다.",
  };
  let renderAct = () => {}; // 3D 아래 조작 버튼 (아래에서 채운다)
  const setHint = (msg) => {
    renderAct();
    if (msg) { document.getElementById("hint").textContent = msg; return; }
    document.getElementById("hint").innerHTML = armed ? `3D 바닥에서 놓을 자리를 누르거나, 아래 <b>알맞은 자리에 놓기</b>를 눌러 보세요` : HINT[mode];
    const u = document.getElementById("unarm");
    if (u) u.onclick = (e) => { e.preventDefault(); armed = null; ghost(null); setHint(); renderLib(); };
  };

  // ---- 제품 서랍 ----
  catalog = await api("/api/catalog");
  // 먼저 이 공간을 어떤 용도로 쓸지 묻고, 그 용도에 맞는 가전 종류부터 보여 준다 (카탈로그 zone_fit 기준)
  const ORDER = CATEGORY_GROUP.flatMap(([, , cs]) => cs);
  const rank = (c) => (ORDER.indexOf(c) < 0 ? 999 : ORDER.indexOf(c));
  const catsFor = (pu) => [...new Set(catalog.filter((p) => (p.demo_only || !catalog.some((x) => x.sale_status) || p.sale_status === "ACTIVE" || p.sale_status === "SOLD_OUT") && (!pu || (p.zone_fit || []).includes(pu))).map((p) => p.category))].sort((a, b) => rank(a) - rank(b));
  const USES = Object.keys(USE).filter((k) => catsFor(k).length);
  let use = USES.includes(saved.use) ? saved.use : null; // null: 아직 안 고름, "": 전체 보기
  if (saved.use === "") use = "";
  let sel = saved.sel && typeof saved.sel === "object" ? saved.sel : {};
  if (!catsFor(use).includes(cat)) cat = "";
  const inScope = (c) => (cat ? c === cat : !use || catsFor(use).includes(c));
  const setScope = (patch) => {
    if ("use" in patch) { use = patch.use; cat = ""; sel = {}; }
    if ("cat" in patch) { cat = patch.cat; sel = sel.install ? { install: sel.install } : {}; }
    saveUiState(pid, { use, cat, sel });
    renderCats(); renderLib();
  };
  const renderCats = () => {
    const ask = document.getElementById("ask");
    ask.innerHTML = use == null
      ? `<p class="ask-q">이 공간을 어떤 용도로 쓰실 건가요?</p><div class="chips">${USES.map((k) => `<button class="chip" data-use="${esc(k)}">${esc(USE[k])}</button>`).join("")}<button class="chip" data-use="">전체 보기</button></div>`
      : `<p class="ask-a"><b>${esc(use ? USE[use] : "전체")}</b>${use ? "에 어울리는 가전" : " 가전"}<button class="linklike" id="useChange">용도 바꾸기</button></p>`;
    ask.querySelectorAll("[data-use]").forEach((b) => (b.onclick = () => setScope({ use: b.dataset.use })));
    const ch = document.getElementById("useChange");
    if (ch) ch.onclick = () => setScope({ use: null });
    document.getElementById("cats").innerHTML = use == null ? "" : [["", "전체"], ...catsFor(use).map((c) => [c, CATEGORY[c] || c])]
      .map(([k, v]) => `<button class="chip ${cat === k ? "on" : ""}" data-cat="${esc(k)}">${esc(v)}</button>`).join("");
    document.querySelectorAll("[data-cat]").forEach((b) => (b.onclick = () => setScope({ cat: b.dataset.cat })));
  };
  // 같은 모델의 색·재질 다른 SKU는 한 줄로 묶고, 색·재질은 동그라미로 고른다
  const families = await api("/api/catalog/families");
  const familyOf = (sku) => families.find((f) => f.variants.some((v) => v.sku === sku));
  const pick = {}; // family_id → 고른 SKU
  const finishLabel = (v) => [v.color, v.material].filter(Boolean).join(" · ");
  // 같은 모델 안에 색 이름이 같은 SKU가 여럿이면 (기능·연식만 다름) 모델명을 붙여 구분한다
  const optLabel = (f, x) => {
    const l = finishLabel(x) || "색상 표기 없음";
    return f.variants.filter((y) => finishLabel(y) === finishLabel(x)).length > 1 ? `${l} · ${x.sku}` : l;
  };
  // 목록 카드의 색 동그라미는 색마다 하나만
  const colorDots = (f) => f.variants.filter((x, i, a) => a.findIndex((y) => y.color === x.color && y.hex === x.hex) === i);
  // 단계별 옵션 필터: 종류를 고르면 설치 방식 → 종류 → 도어 수 → 용량 → … → 색상 순으로 좁힌다 (options.js)
  const inRange = (val, r) => { if (!r) return true; if (!val) return false; const [a, b] = r.split("-").map(Number); return val >= a && val <= b; };
  ["fW", "fH", "sortBy"].forEach((id) => (document.getElementById(id).onchange = () => renderLib()));
  // 지금 LGE.COM에서 파는 제품만 고를 수 있다 (판매중·일시품절). 비매품과 판매 여부를 확인 못 한 제품은 목록에 넣지 않는다
  // (API 서버가 아직 판매 여부를 안 주는 옛 버전이면 전부 보여 준다)
  const saleKnown = families.some((f) => f.variants.some((v) => v.sale_status));
  const sellable = (v) => !saleKnown || v.sale_status === "ACTIVE" || v.sale_status === "SOLD_OUT";
  const shop = families.map((f) => (f.demo_only ? f : { ...f, variants: f.variants.filter(sellable) })).filter((f) => f.variants.length);
  const renderSteps = (steps) => {
    const box = document.getElementById("steps");
    box.innerHTML = steps.map((st, i) => `<li class="step ${st.picked ? "done" : ""}"><span class="step-n">${i + 1}</span><span class="step-l">${esc(st.label)}</span>
      <div class="chips">${st.values.map((v) => `<button class="chip ${st.picked === v.label ? "on" : ""}" data-step="${esc(st.key)}" data-val="${esc(v.label)}" aria-pressed="${st.picked === v.label}">${esc(v.label)} <i>${v.count}</i></button>`).join("")}</div></li>`).join("");
    box.querySelectorAll("[data-step]").forEach((b) => (b.onclick = () => {
      if (sel[b.dataset.step] === b.dataset.val) delete sel[b.dataset.step]; else sel[b.dataset.step] = b.dataset.val;
      saveUiState(pid, { sel });
      renderLib();
    }));
  };
  // 이 집에 들어가는 제품: 지금 목록 앞쪽 후보를 서버가 벽을 따라 놓아 보고(find_spot) 들어가는 것만 3개
  let recSkus = new Set(), suggItems = [], suggKey = "", suggTimer = 0, suggPool = [];
  const isRec = (f) => f.variants.some((v) => recSkus.has(v.sku));
  const SUGG_POOL = 30;
  const renderSugg = () => {
    const box = document.getElementById("sugg");
    box.hidden = !suggItems.length;
    box.innerHTML = suggItems.length ? `<div class="sugg-head"><h3>이 집에 들어가는 제품</h3><button class="ghost small" id="askBot">하우니에게 묻기</button></div>
      <ul>${suggItems.map((it) => {
        const f = familyOf(it.sku), v = f?.variants.find((x) => x.sku === it.sku) || {};
        return `<li><button class="sugg-card" data-sugg="${esc(it.sku)}" title="${esc(f?.name || it.sku)}">
          <span class="ph" style="background-color:${esc(v.hex || "#fff")}">${v.thumb ? `<img src="${esc(v.thumb)}" alt="" loading="lazy">` : ""}</span>
          <span class="nm">${esc(f?.name || it.sku)}</span>${typeof v.price_krw === "number" ? `<span class="vv">${v.price_krw.toLocaleString("ko-KR")}원</span>` : ""}</button></li>`;
      }).join("")}</ul>` : "";
    box.querySelectorAll("[data-sugg]").forEach((b) => (b.onclick = () => openDetail(b.dataset.sugg)));
    box.querySelector("#askBot")?.addEventListener("click", () => openBot(true));
  };
  const scheduleSuggest = () => {
    if (!project) return;
    const key = JSON.stringify([suggPool, project.scene_state.placements.map((x) => x.placement_id), project.scene_state.hidden_objects]);
    if (key === suggKey) return;
    suggKey = key;
    clearTimeout(suggTimer);
    suggTimer = setTimeout(async () => {
      let got = [];
      try { got = suggPool.length ? (await post(`/api/projects/${pid}/suggest`, { skus: suggPool, limit: 3 })).items : []; }
      catch { got = []; } // 옛 API 서버면 줄을 숨긴다
      if (suggKey !== key) return;
      suggItems = got;
      const next = new Set(got.map((x) => x.sku)), changed = next.size !== recSkus.size || [...next].some((x) => !recSkus.has(x));
      recSkus = next;
      renderSugg();
      if (changed) renderLib();
    }, 400);
  };
  const filterCount = () => Object.keys(sel).length + (document.getElementById("fW").value ? 1 : 0) + (document.getElementById("fH").value ? 1 : 0);
  document.getElementById("resetFilter").onclick = () => {
    sel = {}; document.getElementById("fW").value = ""; document.getElementById("fH").value = ""; document.getElementById("q").value = "";
    saveUiState(pid, { sel });
    renderLib();
  };
  const renderLib = () => {
    renderProgress();
    const q = document.getElementById("q").value.trim().toLowerCase();
    const fW = document.getElementById("fW").value, fH = document.getElementById("fH").value;
    const scope = shop.filter((f) => inScope(f.category));
    // 종류를 아직 안 골랐으면 설치 방식(빌트인/일반)만, 골랐으면 그 종류의 옵션을 차례로
    const narrowed = optionSteps(scope.flatMap((f) => f.variants), sel, cat ? null : ["install"]);
    sel = narrowed.sel;
    renderSteps(narrowed.steps);
    const left = new Set(narrowed.remaining.map((v) => v.sku));
    scope.forEach((f) => { // 고른 옵션에 맞는 SKU를 그 모델의 대표로
      if (!left.has(pick[f.family_id] || f.variants[0].sku)) { const v = f.variants.find((x) => left.has(x.sku)); if (v) pick[f.family_id] = v.sku; }
    });
    const items = scope.filter((f) => f.variants.some((v) => left.has(v.sku)) && (!q || (CATEGORY[f.category] || "").includes(q) || f.name.toLowerCase().includes(q)
      || f.variants.some((v) => v.sku.toLowerCase().includes(q) || (v.color || "").toLowerCase().includes(q)))
      && inRange(f.product_dims_mm?.w, fW) && inRange(f.product_dims_mm?.h, fH));
    suggPool = items.filter((f) => !f.demo_only && f.product_dims_mm?.w && f.product_dims_mm?.h && f.product_dims_mm?.d)
      .slice(0, SUGG_POOL).map((f) => pick[f.family_id] || f.variants[0].sku);
    scheduleSuggest();
    const sortBy = document.getElementById("sortBy").value;
    const priceOf = (f) => (f.variants.find((v) => v.sku === pick[f.family_id]) || f.variants[0]).price_krw ?? Infinity;
    const sizeOf = (f) => { const d = f.product_dims_mm || {}; return d.w && d.d ? d.w * d.d : Infinity; };
    items.sort((a, b) => a.demo_only - b.demo_only || (sortBy === "price" ? priceOf(a) - priceOf(b) : sortBy === "size" ? sizeOf(a) - sizeOf(b) : 0)
      || isRec(b) - isRec(a)); // 기본: 이 집에 들어가는 제품을 위로
    const nf = filterCount();
    document.getElementById("filterOn").textContent = nf ? `${nf}개 적용` : "";
    document.getElementById("libCount").textContent = `${items.length}개 모델`;
    document.getElementById("lib").innerHTML = items.map((f) => {
      const d = f.product_dims_mm || {}, sized = d.w && d.h && d.d;
      const sku = pick[f.family_id] || f.variants[0].sku, v = f.variants.find((x) => x.sku === sku);
      const dots = colorDots(f), many = dots.length > 1, models = f.variants.length;
      return `<li class="prod ${f.variants.some((x) => x.sku === armed) ? "armed" : ""} ${sized ? "" : "nosize"}" draggable="${sized ? "true" : "false"}" data-sku="${esc(sku)}">
        <i class="dot tile thumb" style="--tint:${esc(v.hex || "#fff")}${v.thumb ? "" : `;background:${esc(v.hex || "#fff")}`}">${v.thumb ? `<img src="${esc(v.thumb)}" alt="${esc(f.name)} ${esc(finishLabel(v))}" loading="lazy" decoding="async" draggable="false">` : ""}<span>${esc(CATEGORY[f.category] || f.category)}</span></i>
        <div class="body"><div class="name">${esc(f.name)}</div>
          <div class="cat">${sized ? `${mm(d.w)}×${mm(d.h)}×${mm(d.d)} mm` : "치수 정보 없음"}</div>
          ${typeof v.price_krw === "number" ? `<div class="price">${v.price_krw.toLocaleString("ko-KR")}원</div>` : ""}
          ${many ? `<div class="variants" role="radiogroup" aria-label="색·재질">${dots.map((x) => { const on = x.color === v.color && x.hex === v.hex; return `<button class="vsw ${on ? "on" : ""}" data-fam="${esc(f.family_id)}" data-pick="${esc(on ? sku : x.sku)}" title="${esc(finishLabel(x))}" aria-label="${esc(finishLabel(x))}" role="radio" aria-checked="${on}"><i style="background:${esc(x.hex || "#fff")}"></i></button>`; }).join("")}
            <span class="vlabel">${esc(finishLabel(v))}${models > dots.length ? ` · 모델 ${models}개` : ""}</span></div>` : `<div class="vlabel solo">${esc(finishLabel(v) || "색상 표기 없음")}${models > 1 ? ` · 모델 ${models}개` : ""}</div>`}
          ${f.demo_only ? `<span class="badge demo">가상 데이터 · 실제 제품 아님</span>` : ""}</div></li>`;
    }).join("") || `<li class="muted">해당 제품이 없습니다.</li>`;
    document.querySelectorAll("#lib [data-pick]").forEach((b) => {
      b.onclick = (e) => {
        e.stopPropagation();
        const was = pick[b.dataset.fam];
        pick[b.dataset.fam] = b.dataset.pick;
        if (armed && familyOf(armed)?.family_id === b.dataset.fam && armed !== b.dataset.pick) armed = b.dataset.pick; // 든 채로 색만 바꾸기
        if (was !== b.dataset.pick) renderLib();
        setHint();
      };
    });
    document.querySelectorAll("#lib [data-sku]").forEach((li) => {
      li.onclick = () => {
        if (armed && armed === li.dataset.sku) { armed = null; ghost(null); setHint(); renderLib(); return; }
        openDetail(li.dataset.sku);
      };
      li.ondragstart = (e) => e.dataTransfer.setData("text/sku", li.dataset.sku);
    });
  };
  // ---- 제품 상세 창: 사진·모델명·크기·색상, 그리고 우리 집에 들어가는지(적합/부적합)만 크게 ----
  // 카탈로그 spec_notes(근거)·필요 공간 같은 숫자는 판정에만 쓰고 화면에는 내지 않는다
  const pdModal = document.getElementById("pdModal");
  const INSTALL = { built_in: "빌트인", built_in_look: "빌트인 핏 (Fit & Max)", freestanding: "일반 (프리스탠딩)", countertop: "조리대 위", undercounter: "하부장 안" };
  const OPT = { kind: "종류", doors: "도어 수", capacity_l: "용량", wash_kg: "세탁 용량", dry_kg: "건조 용량", capacity: "용량", screen_cm: "화면 크기", door_type: "문 여는 방향" };
  const OPT_UNIT = { capacity_l: " L", wash_kg: " kg", dry_kg: " kg", screen_cm: " cm" };
  const PD_VERDICT = { fit: "적합", conditional: "적합", no_fit: "부적합" };
  const closeDetail = () => { pdModal.hidden = true; pdModal.innerHTML = ""; };
  // 판정 한 줄: 놓은 제품이면 그 자리 판정, 그려 둔 영역이 있으면 그 영역 판정(코드가 계산한 값), 없으면 안내
  const verdictHtml = (verdict, where, why) => `<div class="pd-verdict v-${verdict}"><b>${PD_VERDICT[verdict] || "판정 불가"}</b><span>${esc(where)}</span>${why ? `<em>${esc(why)}</em>` : ""}</div>`;
  const WHY = { scan_based: "스캔 치수 기준이에요. 설치 전에 실측으로 한 번 더 확인해요", clearance_unknown: "옆·뒤 여유 공간은 설치 기사가 확인해요", no_wall_in_zone: "영역에 붙일 벽이 없어요" };
  const dimWhy = (fit) => {
    const bad = Object.entries(fit.dims || {}).find(([, d]) => d.verdict && d.verdict !== "fit" && d.verdict !== "unknown");
    if (!bad) return WHY[(fit.notes || []).find((n) => WHY[n])] || "";
    const [k, d] = bad;
    const name = { width: "폭이", height: "높이가", depth: "깊이가" }[k] || `${DIM[k] || k}이`;
    return d.slack_mm != null && d.slack_mm < 0 ? `${name} ${mm(-d.slack_mm)} mm 모자라요` : `${name} 빠듯해요`;
  };
  const fillVerdict = async (sku, p) => {
    const box = document.getElementById("pdVerdict");
    const placed = project.scene_state.placements.find((q) => q.sku === sku && q.verdict);
    if (placed && PD_VERDICT[placed.verdict]) {
      const r = (placed.reasons || []).find((x) => x.verdict !== "fit");
      box.innerHTML = verdictHtml(placed.verdict, "놓아 둔 자리 기준", placed.verdict === "fit" ? "" : r?.label);
      return;
    }
    const z = zones?.find((q) => (p.zone_fit || []).includes(q.purpose)) || zones?.[0];
    if (!z) { box.innerHTML = `<div class="pd-verdict v-none"><b>넣어 보면 알려 드려요</b><span>3D에 놓으면 그 자리에 들어가는지 바로 판정해요</span></div>`; return; }
    box.innerHTML = `<div class="pd-verdict v-none"><b>확인하는 중…</b></div>`;
    try {
      const rec = await api(`/api/projects/${pid}/zones/${z.zone_id}/recommendations?category=${encodeURIComponent(p.category)}`);
      if (document.getElementById("pdVerdict") !== box) return; // 그 사이 다른 제품을 열었으면 버린다
      const it = rec.items.find((q) => q.product.sku === sku);
      box.innerHTML = it && PD_VERDICT[it.fit.verdict] ? verdictHtml(it.fit.verdict, `'${z.name}' 기준`, it.fit.verdict === "fit" ? "" : dimWhy(it.fit))
        : `<div class="pd-verdict v-none"><b>넣어 보면 알려 드려요</b><span>3D에 놓으면 그 자리에 들어가는지 바로 판정해요</span></div>`;
    } catch { box.innerHTML = ""; }
  };
  const openDetail = (sku) => {
    const p = prodOf(sku), f = familyOf(sku);
    if (!p || !f) return;
    pick[f.family_id] = sku;
    const v = f.variants.find((x) => x.sku === sku) || {};
    const d = p.product_dims_mm || {}, sized = d.w && d.h && d.d;
    const rows = [
      ["제품 크기", sized ? `가로 ${mm(d.w)} × 높이 ${mm(d.h)} × 깊이 ${mm(d.d)} mm` : ""],
      ["설치 방식", esc(INSTALL[p.install_type] || p.install_type || "")],
      ...Object.entries(p.options || {}).filter(([k]) => OPT[k]).map(([k, val]) => [OPT[k], esc(`${val}${OPT_UNIT[k] || ""}`)]),
      ["색상 · 재질", esc(finishLabel(v))],
      ["모델명", `<span class="mono">${esc(sku)}</span>`],
    ].filter(([, val]) => val);
    pdModal.innerHTML = `
      <div class="pd-top">
        <div class="pd-photo${v.thumb ? " has-photo" : ""}" style="background-color:${esc(v.hex || "#fff")}${v.thumb ? `;background-image:url('${esc(v.thumb)}')` : ""}" role="img" aria-label="${esc(f.name)} ${esc(finishLabel(v))}"><span>${esc(CATEGORY[p.category] || p.category)}</span></div>
        <div class="pd-title">
          <h2>${esc(f.name)}</h2>
          <p class="muted">${esc(CATEGORY[p.category] || p.category)} · ${esc(sku)}</p>
          ${f.demo_only ? `<span class="badge demo">가상 데이터 · 실제 제품 아님</span>` : ""}
          <div class="pd-variants" role="radiogroup" aria-label="색상 옵션">${f.variants.filter((x) => f.demo_only || sellable(x) || x.sku === sku).map((x) => `<button class="swatch ${x.sku === sku ? "on" : ""}" data-pd-variant="${esc(x.sku)}" role="radio" aria-checked="${x.sku === sku}"><i style="background:${esc(x.hex || "#fff")}"></i>${esc(optLabel(f, x))}</button>`).join("")}</div>
        </div>
        <button class="ghost small pd-close" id="pdClose" aria-label="상세 창 닫기">닫기</button>
      </div>
      <div id="pdVerdict" aria-live="polite"></div>
      <table class="pd-spec"><tbody>${rows.map(([k, val]) => `<tr><th>${k}</th><td>${val}</td></tr>`).join("")}</tbody></table>
      <div class="pd-actions">
        <button class="primary" id="pdPlace" ${sized ? "" : "disabled"}>${sized ? "넣어 보기" : "치수가 없어 놓을 수 없어요"}</button>
        ${p.source_url ? `<a class="btn ghost" href="${esc(p.source_url)}" target="_blank" rel="noopener">LGE.COM에서 보기</a>` : ""}
      </div>`;
    pdModal.hidden = false;
    fillVerdict(sku, p);
    pdModal.querySelectorAll("[data-pd-variant]").forEach((b) => (b.onclick = () => { openDetail(b.dataset.pdVariant); renderLib(); }));
    document.getElementById("pdClose").onclick = closeDetail;
    const place = document.getElementById("pdPlace");
    if (sized) place.onclick = () => {
      closeDetail();
      if (walking) setWalking(false);
      armed = sku; mode = "move"; syncMode(); setHint(); renderLib();
      openLib(false); // 앱에서는 서랍을 내려 3D 바닥이 보이게
    };
    place.focus({ preventScroll: true });
    pdModal.scrollTop = 0;
  };
  pdModal.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); closeDetail(); } });
  document.getElementById("q").oninput = renderLib;
  renderCats(); renderLib();

  // ---- 미리 보기(저장 없이 판정) ----
  const ghost = (res) => {
    const g = document.getElementById("ghost");
    if (!g) return;
    g.innerHTML = res ? placedSvg({ center_xz: res.pose.center_xz, yaw_rad: res.pose.yaw_rad, size_m: res.size_m, verdict: res.verdict }, pv.sw, false, true) : "";
    viewer.setGhost(res && { ...res, sku: armed, hex: prodOf(armed)?.cmf_options[0]?.hex_approx });
  };
  let busy = false, queued = null, lastPreview = null;
  const preview = async (args, onRes) => {
    if (busy) { queued = [args, onRes]; return; }
    busy = true;
    try {
      lastPreview = await post(`/api/projects/${pid}/pose-check`, args);
      if (onRes) onRes(lastPreview);
      else if (lastPreview.size_m && (armed || drag)) ghost(lastPreview);
    } catch { /* 미리 보기 실패는 무시 */ }
    busy = false;
    if (queued) { const [a, cb] = queued; queued = null; preview(a, cb); }
  };

  // ---- 되돌리기: 놓기·옮기기·돌리기·빼기·가구 치우기를 한 단계씩 되돌린다 ----
  const undoStack = [], undoIds = {}; // 뺐다가 되돌린 제품은 번호가 새로 붙으므로 옛 번호 → 새 번호
  const undoBtn = document.getElementById("undo");
  const liveId = (id) => { while (undoIds[id]) id = undoIds[id]; return id; };
  const remember = (step) => { undoStack.push(step); if (undoStack.length > 30) undoStack.shift(); redoStack.length = 0; syncUndo(); };
  const rememberPlacement = (plid) => {
    const x = project.scene_state.placements.find((q) => q.placement_id === plid);
    if (x && !x.zone_id) remember({ kind: "pose", id: plid, body: { center_xz: [...x.center_xz], yaw_rad: x.yaw_rad, sku: x.sku, snap: false } });
  };
  const rememberRemoval = (plid) => {
    const x = project.scene_state.placements.find((q) => q.placement_id === plid);
    if (x && !x.zone_id) remember({ kind: "add", id: plid, body: { sku: x.sku, center_xz: [...x.center_xz], yaw_rad: x.yaw_rad, snap: false, ...(x.color ? { color: x.color } : {}) } });
  };
  // 단계 하나를 되돌리고, 그 반대 단계를 돌려준다 (되돌리기 ↔ 다시 실행)
  const applyStep = async (step) => {
    const id = liveId(step.id);
    if (step.kind === "remove") {
      const x = project.scene_state.placements.find((q) => q.placement_id === id);
      await api(`/api/projects/${pid}/placements/${id}`, { method: "DELETE" });
      if (selPl === id) selPl = null;
      return x && { kind: "add", id, body: { sku: x.sku, center_xz: [...x.center_xz], yaw_rad: x.yaw_rad, snap: false, ...(x.color ? { color: x.color } : {}) } };
    }
    if (step.kind === "pose") {
      const x = project.scene_state.placements.find((q) => q.placement_id === id);
      await api(`/api/projects/${pid}/placements/${id}`, { method: "PATCH", body: JSON.stringify(step.body) });
      return x && { kind: "pose", id, body: { center_xz: [...x.center_xz], yaw_rad: x.yaw_rad, sku: x.sku, snap: false } };
    }
    if (step.kind === "add") {
      const r = await post(`/api/projects/${pid}/placements`, step.body);
      undoIds[step.id] = r.placement.placement_id; selPl = r.placement.placement_id; selObj = null;
      return { kind: "remove", id: r.placement.placement_id };
    }
    if (step.kind === "objPose") {
      const o = objOf(id), had = (project.scene_state.object_poses || {})[id];
      if (step.pose) await put(`/api/projects/${pid}/objects/${id}/pose`, step.pose);
      else await api(`/api/projects/${pid}/objects/${id}/pose`, { method: "DELETE" });
      return { kind: "objPose", id, pose: had && o ? { center_xz: [o.position[0], o.position[2]], yaw_rad: o.yaw_rad } : null };
    }
    const hide = step.kind === "objHide";
    await put(`/api/projects/${pid}/objects/${id}/hidden`, { hidden: hide });
    return { kind: hide ? "objShow" : "objHide", id };
  };
  const redoStack = [];
  const redoBtn = document.getElementById("redo");
  const syncUndo = () => { undoBtn.disabled = !undoStack.length; redoBtn.disabled = !redoStack.length; };
  const travel = (from, to, msg) => guard(async () => {
    const step = from.pop();
    syncUndo();
    if (!step) return;
    viewer.cancelHold();
    const back = await applyStep(step);
    if (back) { to.push(back); if (to.length > 30) to.shift(); }
    syncUndo();
    toast(msg);
    setHint();
    await refresh(true);
  });
  const undo = travel(undoStack, redoStack, "되돌렸어요");
  const redo = travel(redoStack, undoStack, "다시 했어요");
  undoBtn.onclick = undo;
  redoBtn.onclick = redo;

  const placeAt = guard(async (sku, p) => {
    const r = await post(`/api/projects/${pid}/placements`, { sku, center_xz: p, yaw_rad: Math.PI / 2 });
    remember({ kind: "remove", id: r.placement.placement_id });
    selPl = r.placement.placement_id; selObj = null; armed = null; ghost(null); setTab("sel");
    toast(`${prodOf(sku)?.name || sku}: ${LABEL[r.placement.verdict]}`);
    setHint(); renderLib();
    await refresh(true);
  });
  const patch = guard(async (plid, body) => {
    rememberPlacement(plid);
    await api(`/api/projects/${pid}/placements/${plid}`, { method: "PATCH", body: JSON.stringify(body) });
    await refresh(true);
  });

  // ---- 평면도 조작 ----
  const syncMode = () => document.querySelectorAll("[data-mode]").forEach((x) => x.classList.toggle("on", x.dataset.mode === mode));
  document.querySelectorAll("[data-mode]").forEach((b) => (b.onclick = () => {
    mode = b.dataset.mode; draft = []; armed = null; ghost(null);
    if (mode !== "move") setView("plan"); // 영역 그리기는 평면에서
    syncMode(); setHint(); renderLib(); drawDraft();
  }));
  const drawDraft = () => {
    const g = document.getElementById("draft");
    if (!g || !pv) return;
    let pts = draft;
    if (mode === "rect" && dragging) { const [a, b] = dragging; pts = [a, [b[0], a[1]], b, [a[0], b[1]]]; }
    g.innerHTML = pts.length ? `<polygon class="draft" points="${pts.map((p) => p.join(",")).join(" ")}" stroke-width="${pv.sw(1.5)}"/>` + pts.map((p) => `<circle cx="${p[0]}" cy="${p[1]}" r="${pv.sw(4)}" fill="#a50034"/>`).join("") : "";
  };
  const createZone = guard(async (poly) => {
    const purpose = "kitchen";
    const n = zones.filter((z) => z.purpose === purpose).length;
    const z = await post(`/api/projects/${pid}/zones`, { purpose, polygon_m: poly, name: PURPOSE[purpose] + (n ? ` ${n + 1}` : "") });
    zoneSel = z.zone_id; draft = [];
    toast(`${z.name} 영역을 만들었어요. ‘추천’ 탭에서 들어가는 제품을 확인하세요`); setTab("zones");
    await refresh(true);
  });
  // 바닥을 눌렀을 때 할 일 (평면·3D 공통): 현관·싱크 지정, 공유기 놓기, 제품 놓기
  const floorAction = (p) => {
    if (mode !== "move") return false;
    if (armedMark) {
      const name = armedMark; armedMark = null;
      guard(async () => { project = await put(`/api/projects/${pid}/marks/${name}`, { center_xz: p }); if (sim === "flow") await flowCtl(); })();
      return true;
    }
    if (armedRouter) {
      armedRouter = false;
      guard(async () => { project = await put(`/api/projects/${pid}/router`, { center_xz: p, band }); if (sim === "wifi") await wifiCtl(); })();
      return true;
    }
    if (armed) { placeAt(armed, p); return true; }
    return false;
  };
  svg.onpointerdown = (e) => {
    if (!pv) return;
    const p = pv.toWorld(e);
    if (mode === "move") {
      if (floorAction(p)) return;
      const g = e.target.closest("[data-pl]");
      if (g) {
        const x = project.scene_state.placements.find((q) => q.placement_id === g.dataset.pl);
        drag = { plid: x.placement_id, sku: x.sku, start: p, orig: x.center_xz, yaw: x.yaw_rad, moved: false };
        selPl = x.placement_id; selObj = null;
        svg.setPointerCapture(e.pointerId);
        setTab("sel"); renderInspector();
        return;
      }
      const o = e.target.closest("[data-obj]");
      selObj = o ? o.dataset.obj : null;
      selPl = null;
      if (selObj) setTab("sel");
      draw(); renderInspector();
      return;
    }
    if (mode === "rect") { dragging = [p, p]; svg.setPointerCapture(e.pointerId); }
    else {
      if (draft.length >= 3 && Math.hypot(p[0] - draft[0][0], p[1] - draft[0][1]) < 0.15) { createZone(draft); return; }
      draft.push(p);
    }
    drawDraft();
  };
  svg.onpointermove = (e) => {
    if (!pv) return;
    const p = pv.toWorld(e);
    if (drag) {
      const c = [drag.orig[0] + p[0] - drag.start[0], drag.orig[1] + p[1] - drag.start[1]];
      if (Math.hypot(p[0] - drag.start[0], p[1] - drag.start[1]) > 0.04) drag.moved = true;
      if (drag.moved) {
        svg.querySelector(`[data-pl="${drag.plid}"]`)?.classList.add("dragging");
        preview({ sku: drag.sku, center_xz: c, yaw_rad: drag.yaw, placement_id: drag.plid });
      }
      return;
    }
    if (armed && mode === "move") { preview({ sku: armed, center_xz: p, yaw_rad: Math.PI / 2 }); return; }
    if (dragging) { dragging[1] = p; drawDraft(); }
  };
  svg.onpointerup = (e) => {
    if (drag) {
      const d = drag; drag = null; ghost(null);
      if (d.moved) {
        const p = pv.toWorld(e);
        patch(d.plid, { center_xz: [d.orig[0] + p[0] - d.start[0], d.orig[1] + p[1] - d.start[1]], yaw_rad: d.yaw });
      } else draw();
      return;
    }
    if (!dragging) return;
    const [a, b] = dragging; dragging = null;
    if (Math.abs(a[0] - b[0]) < 0.3 || Math.abs(a[1] - b[1]) < 0.3) { drawDraft(); return; }
    const x0 = Math.min(a[0], b[0]), x1 = Math.max(a[0], b[0]), y0 = Math.min(a[1], b[1]), y1 = Math.max(a[1], b[1]);
    createZone([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]);
  };
  svg.onpointerleave = () => { if (armed) ghost(null); };
  svg.ondblclick = () => { if (mode === "poly" && draft.length >= 3) createZone(draft); };
  svg.ondragover = (e) => e.preventDefault();
  svg.ondrop = (e) => { e.preventDefault(); const sku = e.dataTransfer.getData("text/sku"); if (sku && pv) placeAt(sku, pv.toWorld(e)); };
  // ---- 건축 모드: 집어 들기 · 내려놓기 · 키보드 ----
  const ROT_STEP = 45, ROT_FINE = 15, NUDGE = 0.1, NUDGE_FINE = 0.01;
  const objOf = (id) => room.objects.find((o) => o.object_id === id);
  const poseOf = (hit) => {
    if (hit.type === "router") {
      const rt = project.scene_state.router;
      return rt && { kind: "router", id: "router", xz: [...rt.center_xz], yaw: rt.yaw_rad ?? 0 };
    }
    if (hit.type === "placement") {
      const x = project.scene_state.placements.find((q) => q.placement_id === hit.id);
      return x && { kind: "placement", id: x.placement_id, xz: [...x.center_xz], yaw: x.yaw_rad };
    }
    const o = objOf(hit.id);
    return o && { kind: "object", id: o.object_id, xz: [o.position[0], o.position[2]], yaw: o.yaw_rad };
  };
  const pickUp = (hit, point) => {
    const item = poseOf(hit);
    if (item && viewer.hold(item, point)) setHint("들고 있어요: 놓을 곳을 누르세요 · R 돌리기(Shift 반대, Alt 15°) · 방향키 살짝 옮기기 · Esc 취소 · Delete 지우기");
  };
  // 저장 응답을 기다리지 않고 화면 상태부터 바꾼다 (바로 다시 집어도 새 자리에서 시작)
  let editSeq = 0; // 화면에서 바꾼 횟수: 읽는 도중 바뀌면 그 응답은 버리고 다시 읽는다
  const applyLocal = (it) => {
    editSeq++;
    if (it.kind === "router") {
      const rt = project.scene_state.router;
      if (rt) { rt.center_xz = [...it.xz]; rt.yaw_rad = it.yaw; }
    } else if (it.kind === "placement") {
      const x = project.scene_state.placements.find((q) => q.placement_id === it.id);
      if (x) { x.center_xz = [...it.xz]; x.yaw_rad = it.yaw; }
    } else {
      const o = objOf(it.id);
      if (o) { o.position = [it.xz[0], o.position[1], it.xz[1]]; o.yaw_rad = it.yaw; }
    }
  };
  const savePose = guard(async (it) => {
    if (it.kind === "placement") rememberPlacement(it.id);
    else { const o = objOf(it.id); if (o) remember({ kind: "objPose", id: it.id, pose: (project.scene_state.object_poses || {})[it.id] ? { center_xz: [o.position[0], o.position[2]], yaw_rad: o.yaw_rad } : null }); }
    applyLocal(it);
    if (it.kind === "router") {
      // 공유기를 내려놓으면 그 자리에서 신호를 다시 계산한다
      project = await put(`/api/projects/${pid}/router`, { center_xz: it.xz, yaw_rad: it.yaw, band });
      if (sim === "wifi") await runWifi();
      return;
    }
    if (it.kind === "placement") await api(`/api/projects/${pid}/placements/${it.id}`, { method: "PATCH", body: JSON.stringify({ center_xz: it.xz, yaw_rad: it.yaw, snap: false }) });
    else await put(`/api/projects/${pid}/objects/${it.id}/pose`, { center_xz: it.xz, yaw_rad: it.yaw });
    await refresh(true);
  });
  const putDown = () => { const it = viewer.dropHold(); setHint(); if (it) savePose(it); };
  const removeSelected = guard(async () => {
    viewer.cancelHold();
    if (selPl) { rememberRemoval(selPl); await api(`/api/projects/${pid}/placements/${selPl}`, { method: "DELETE" }); selPl = null; toast("제품을 뺐어요"); }
    else if (selObj) { remember({ kind: "objShow", id: selObj }); await put(`/api/projects/${pid}/objects/${selObj}/hidden`, { hidden: true }); toast("가구를 치웠어요 (놓은 제품 탭에서 되돌리기)"); selObj = null; }
    setHint();
    await refresh(true);
  });
  // 고른 것(들고 있지 않을 때)을 키보드로 바꾸면 잠깐 모았다가 한 번에 저장
  let pendingKey = null, keyTimer = 0;
  const nudgeSelected = (dx, dz, dyaw) => {
    const it = pendingKey || (selPl ? poseOf({ type: "placement", id: selPl }) : selObj ? poseOf({ type: "object", id: selObj }) : null);
    if (!it) return;
    pendingKey = { ...it, xz: [it.xz[0] + dx, it.xz[1] + dz], yaw: it.yaw + dyaw };
    clearTimeout(keyTimer);
    keyTimer = setTimeout(() => { const p = pendingKey; pendingKey = null; savePose(p); }, 350);
  };
  const rotate = (deg) => {
    const d = (deg * Math.PI) / 180;
    if (viewer.held()) viewer.rotateHeld(d); else nudgeSelected(0, 0, d);
  };
  const onKey = (e) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
    if (viewer.walking()) return; // 둘러보기 중에는 걷기 키만 (뷰어가 받는다)
    const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    if (k === "z" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); if (e.shiftKey) redo(); else undo(); return; }
    if (k === "y" && e.ctrlKey) { e.preventDefault(); redo(); return; }
    if (k === "Escape") { viewer.cancelHold(); armed = null; ghost(null); setHint(); renderLib(); return; }
    const in3d = studio.dataset.view !== "plan";
    // 카메라: WASD 이동, Q/E 돌기 (3D가 보일 때)
    const PAN = 0.3;
    if (in3d && !e.ctrlKey && !e.metaKey) {
      const cam = { w: [0, PAN], s: [0, -PAN], a: [-PAN, 0], d: [PAN, 0] }[k];
      if (cam) { viewer.panCamera(...cam); e.preventDefault(); return; }
      if (k === "q" || k === "e") { viewer.orbitCamera(k === "q" ? -15 : 15); e.preventDefault(); return; }
    }
    const held = viewer.held();
    if (!held && !selPl && !selObj) return;
    // 돌리기: R / . 오른쪽, Shift+R / , 왼쪽, Alt를 같이 누르면 15°
    const step = e.altKey ? ROT_FINE : ROT_STEP;
    if (k === "r") { rotate(e.shiftKey ? -step : step); e.preventDefault(); return; }
    if (k === "." || k === ",") { rotate(k === "." ? step : -step); e.preventDefault(); return; }
    // 방향키: 화면 기준으로 10 cm (Shift 1 cm)
    const dir = { ArrowUp: [0, 1], ArrowDown: [0, -1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] }[k];
    if (dir) {
      const { fwd, right } = viewer.screenAxes(), n = e.shiftKey ? NUDGE_FINE : NUDGE;
      const dx = (right[0] * dir[0] + fwd[0] * dir[1]) * n, dz = (right[1] * dir[0] + fwd[1] * dir[1]) * n;
      if (held) viewer.moveHeld(dx, dz); else nudgeSelected(dx, dz, 0);
      e.preventDefault();
      return;
    }
    if (k === "Enter" && held) { putDown(); return; }
    if (k === "Delete" || k === "Backspace") { e.preventDefault(); removeSelected(); }
  };
  document.addEventListener("keydown", onKey);
  cleanup.push(() => document.removeEventListener("keydown", onKey));

  // ---- 오른쪽 패널 ----
  // 3D 위: 고른 제품의 판정 한 줄, 아래 조작 버튼 (키보드 없이 다 되게)
  const actBar = document.getElementById("actBar"), fitBadge = document.getElementById("fitBadge");
  const BADGE = { fit: "배치가 가능합니다!", conditional: "배치가 가능합니다!", no_fit: "이 자리에는 안 들어가요", unknown: "판정할 정보가 부족해요" };
  const autoPlace = guard(async (sku) => {
    const r = await post(`/api/projects/${pid}/auto-place`, { sku });
    remember({ kind: "remove", id: r.placement.placement_id });
    selPl = r.placement.placement_id; selObj = null; armed = null; ghost(null);
    toast(`${prodOf(sku)?.name || sku}: 알맞은 자리에 놓았어요`);
    setHint(); renderLib();
    await refresh(true);
  });
  const autoAlign = guard(async (plid) => {
    rememberPlacement(plid);
    await post(`/api/projects/${pid}/placements/${plid}/auto-align`, {});
    toast("벽에 맞춰 정렬했어요");
    await refresh(true);
  });
  const ICON = {
    move: '<path d="M12 3v18M3 12h18M12 3l-3 3M12 3l3 3M12 21l-3-3M12 21l3-3M3 12l3-3M3 12l3 3M21 12l-3-3M21 12l-3 3"/>',
    rotate: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
    align: '<path d="M4 4v16"/><rect x="8" y="6" width="10" height="5" rx="1"/><rect x="8" y="13" width="7" height="5" rx="1"/>',
    del: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  };
  const actBtn = (id, icon, label, cls = "") => `<button class="act ${cls}" id="${id}"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true">${ICON[icon]}</svg><span>${label}</span></button>`;
  renderAct = () => {
    if (!project) return;
    const x = selPl && project?.scene_state.placements.find((q) => q.placement_id === selPl);
    fitBadge.hidden = !x || walking;
    if (x) { fitBadge.className = `fit-badge v-${shownVerdict(x.verdict)}`; fitBadge.textContent = BADGE[x.verdict] || BADGE.unknown; }
    if (walking) { actBar.hidden = true; return; }
    if (armed) {
      actBar.hidden = false;
      actBar.innerHTML = `<span class="act-tag">${esc(prodOf(armed)?.name || armed)}</span>
        <button class="primary small" id="actAuto">알맞은 자리에 놓기</button><button class="ghost small" id="actCancel">취소</button>`;
      document.getElementById("actAuto").onclick = () => autoPlace(armed);
      document.getElementById("actCancel").onclick = () => { armed = null; ghost(null); setHint(); renderLib(); };
      return;
    }
    const target = x ? { type: "placement", id: x.placement_id } : selObj ? { type: "object", id: selObj } : null;
    actBar.hidden = !target;
    if (!target) return;
    actBar.innerHTML = actBtn("actMove", "move", "이동") + actBtn("actRot", "rotate", "회전") + (x ? actBtn("actAlign", "align", "자동 정렬") : "") + actBtn("actDel", "del", "삭제", "danger");
    document.getElementById("actMove").onclick = () => { const it = poseOf(target); if (it && viewer.hold(it)) setHint("옮길 자리를 누르세요 · Esc 취소"); };
    document.getElementById("actRot").onclick = () => rotate(ROT_STEP);
    document.getElementById("actAlign")?.addEventListener("click", () => autoAlign(x.placement_id));
    document.getElementById("actDel").onclick = () => removeSelected();
  };
  const OPT_SHORT = (p) => {
    const o = p.options || {};
    return o.capacity_l ? `${o.capacity_l}L` : o.wash_kg ? `세탁 ${o.wash_kg}kg` : o.screen_cm ? `${o.screen_cm}cm` : o.capacity ? `${o.capacity}` : "";
  };
  const renderInspector = () => {
    renderAct();
    const box = document.getElementById("insp");
    const x = selPl && project.scene_state.placements.find((q) => q.placement_id === selPl);
    document.getElementById("plBox").hidden = !!(x || selObj);
    studio.classList.toggle("has-sel", !!(x || selObj));
    if (x) {
      const p = prodOf(x.sku) || { name: x.sku, cmf_options: [] };
      const fv = familyOf(x.sku)?.variants.find((q) => q.sku === x.sku);
      const pd = p.product_dims_mm || {};
      const f = familyOf(x.sku);
      box.innerHTML = `
        <div class="insp-photo" style="background-color:${esc(x.hex || fv?.hex || "#fff")}">${fv?.thumb ? `<img src="${esc(fv.thumb)}" alt="${esc(p.name)}">` : ""}
          <button class="ghost small insp-close" id="inspClose" aria-label="선택 풀기">닫기</button></div>
        <h2 class="insp-name">${esc(p.name)}</h2>
        <p class="insp-meta">${esc([OPT_SHORT(p), x.color].filter(Boolean).join(" · "))}${p.demo_only ? ` <span class="badge demo">가상 데이터 · 실제 제품 아님</span>` : ""}</p>
        ${pd.w && pd.h && pd.d ? `<p class="insp-dims">${mm(pd.w)} × ${mm(pd.h)} × ${mm(pd.d)} mm</p>` : ""}
        ${typeof fv?.price_krw === "number" ? `<p class="insp-price">${fv.price_krw.toLocaleString("ko-KR")}원 <span class="muted">LGE.COM 판매가</span></p>` : ""}
        ${fitCardHtml(x, life[x.placement_id])}
        ${f && f.variants.length > 1 ? `<div class="swatches" aria-label="색상">${f.variants.map((v) => `<button class="swatch ${v.sku === x.sku ? "on" : ""}" data-variant="${esc(v.sku)}" title="${esc(optLabel(f, v))}"><i style="background:${esc(v.hex || "#fff")}"></i>${esc(optLabel(f, v))}</button>`).join("")}</div>` : ""}
        <p class="insp-links"><button class="linklike" id="inspDetail">제품 상세</button>${p.source_url && !p.demo_only ? `<a href="${esc(p.source_url)}" target="_blank" rel="noopener">LGE.COM에서 보기 ↗</a>` : ""}</p>`;
      box.querySelector("#inspDetail").onclick = () => openDetail(x.sku);
      // 공유기 자리를 아직 안 정했으면 살아 보기 와이파이로 바로
      box.querySelectorAll("[data-life]").forEach((b) => (b.onclick = () => { setLive(true); sim = b.dataset.life; saveUiState(pid, { sim }); showSim(); }));
      box.querySelector("#inspClose").onclick = () => { selPl = null; draw(); renderInspector(); renderPlacements(); };
      box.querySelectorAll("[data-variant]").forEach((b) => (b.onclick = () => { if (b.dataset.variant !== x.sku) patch(x.placement_id, { sku: b.dataset.variant }); }));
      return;
    }
    const o = selObj && room.objects.find((q) => q.object_id === selObj);
    if (o) {
      const gone = (project.scene_state.hidden_objects || []).includes(o.object_id);
      const moved = !!(project.scene_state.object_poses || {})[o.object_id];
      box.innerHTML = `<div class="verdict-strip v-object"><span>스캔된 가구</span><em>${esc(o.object_id)}${moved ? " · 옮김" : ""}</em></div>
        <h2 class="insp-name">${esc(OBJ[o.category] || o.category)}</h2>
        <p class="insp-meta">${o.bbox_m.w.toFixed(2)} × ${o.bbox_m.d.toFixed(2)} m · 높이 ${o.bbox_m.h.toFixed(2)} m</p>
        <div class="tool-row">${gone ? "" : `<button class="small ghost" id="orl" title="왼쪽으로 45° (Shift+R)">⟲ 45°</button><button class="small ghost" id="orr" title="오른쪽으로 45° (R)">⟳ 45°</button>`}
          ${moved ? `<button class="small ghost" id="oreset">원래 자리로</button>` : ""}<span class="spacer"></span><button class="small danger" id="hide" title="Delete">${gone ? "되돌리기" : "치우기"}</button></div>
        <p class="hint-sm">누르면 집어 들고 다시 누르면 내려놔요. 옮기거나 치운 가구는 판정·동선에도 반영되고, 원래 스캔은 그대로 남습니다.</p>`;
      box.querySelector("#hide").onclick = guard(async () => {
        viewer.cancelHold(); setHint();
        await put(`/api/projects/${pid}/objects/${o.object_id}/hidden`, { hidden: !gone });
        if (!gone) selObj = null;
        await refresh(true);
      });
      box.querySelector("#orl")?.addEventListener("click", () => rotate(-ROT_STEP));
      box.querySelector("#orr")?.addEventListener("click", () => rotate(ROT_STEP));
      box.querySelector("#oreset")?.addEventListener("click", guard(async () => { await api(`/api/projects/${pid}/objects/${o.object_id}/pose`, { method: "DELETE" }); await refresh(true); }));
      return;
    }
    box.innerHTML = "";
  };
  // ---- 3단계 진행 표시 (공간 확인 → 제품 고르기 → 설치 확인): 지금 상태에서 계산한다 ----
  // ---- 3단계 진행: 단계마다 직접 해야 하나씩 체크된다 (공간 확인 버튼 → 제품 놓기 → 구매·설치 신청) ----
  let flow = { ...(saved.flow || {}) }, prevSteps = null, doneTimer = 0;
  setFlow = (patch) => { flow = { ...flow, ...patch }; saveUiState(pid, { flow }); renderProgress(); };
  const stepCard = document.getElementById("stepCard");
  const renderStepCard = (steps) => {
    const cur = steps.findIndex((s) => s.state !== "done");
    if (cur < 0) {
      if (flow.doneSeen) { stepCard.hidden = true; return; }
      stepCard.hidden = false;
      stepCard.innerHTML = `<span class="sc-n done" aria-hidden="true">✓</span><p><b>세 단계를 모두 마쳤어요</b><span>구매 및 설치 신청에서 상담을 이어 가요</span></p>`;
      clearTimeout(doneTimer);
      doneTimer = setTimeout(() => { flow = { ...flow, doneSeen: true }; saveUiState(pid, { flow }); stepCard.hidden = true; }, 6000);
      return;
    }
    const s = steps[cur];
    const TEXT = {
      scan: ["스캔한 우리 집이 맞는지 둘러보세요", `<button class="primary small" data-sc="ok">맞아요, 다음</button>`],
      pick: ["이 집에 들어가는 제품을 골라 3D에 놓아 보세요", ""],
      check: s.state === "warn" ? ["놓을 수 없는 제품이 있어요. 옮기거나 다른 제품으로 바꿔 보세요", ""]
        : ["놓은 제품을 눌러 보고, 마음에 들면 신청해요", `<button class="primary small" data-sc="order">구매 및 설치 신청</button>`],
    }[s.key];
    stepCard.hidden = false;
    stepCard.innerHTML = `<span class="sc-n${s.state === "warn" ? " warn" : ""}" aria-hidden="true">${cur + 1}</span><p><b>${esc(s.label)}</b><span>${esc(TEXT[0])}</span></p>${TEXT[1]}`;
    stepCard.querySelector('[data-sc="ok"]')?.addEventListener("click", () => setFlow({ space: true }));
    stepCard.querySelector('[data-sc="order"]')?.addEventListener("click", () => openOrder());
  };
  renderProgress = () => {
    const el = document.getElementById("progress");
    if (!el || !project) return;
    const steps = stepState(project, armed, flow);
    el.innerHTML = stepperHtml(steps);
    // 방금 끝낸 단계는 체크가 톡 하고 차오르게 (여러 개면 차례로)
    if (prevSteps) {
      let n = 0;
      steps.forEach((st, i) => {
        if (st.state === "done" && prevSteps[i] !== "done") {
          const li = el.children[i];
          li.classList.add("just-done");
          li.style.setProperty("--d", `${n++ * 350}ms`);
        }
      });
      const last = steps.filter((st, i) => st.state === "done" && prevSteps[i] !== "done").pop();
      if (last) toast(`${last.label} 완료!`);
    }
    prevSteps = steps.map((st) => st.state);
    renderStepCard(steps);
    el.querySelectorAll("[data-step]").forEach((b) => (b.onclick = () => {
      const k = b.dataset.step, pls = project.scene_state.placements;
      if (k === "scan") { if (!flow.space) setFlow({ space: true }); else showExtra(true); }
      else if (k === "pick") { openLib(studio.classList.contains("app")); document.getElementById("q").focus(); }
      else if (!pls.length) toast("제품을 놓으면 그 자리에 들어가는지 바로 확인해요");
      else openOrder();
    }));
  };
  // ---- 구매 및 설치 신청: 놓은 제품과 판정을 모아 보여 주고, 구매는 LGE.COM, 설치는 방문 신청으로 잇는다 ----
  const orderSheet = document.getElementById("orderSheet");
  const closeOrder = () => { orderSheet.hidden = true; orderSheet.innerHTML = ""; };
  const openOrder = () => {
    const pls = project.scene_state.placements;
    const bad = pls.filter((x) => x.verdict === "no_fit").length;
    if (pls.length && !bad && !flow.order) setTimeout(() => setFlow({ order: true }), 0);
    orderSheet.innerHTML = `
      <div class="order-head"><h2>구매 및 설치 신청</h2><button class="ghost small" id="orderClose">닫기</button></div>
      ${pls.length ? `<p class="order-sum">놓은 제품 <b>${pls.length}개</b>${bad ? ` · <b class="bad">${bad}개는 지금 자리에 설치하기 어려워요</b>` : " · 모두 설치할 수 있는 자리예요"}</p>
      <ul class="order-list">${pls.map((x) => { const p = prodOf(x.sku) || { name: x.sku }; return `<li>
        <i class="dot" style="background:${esc(x.hex || "#fff")}"></i>
        <span class="nm">${esc(p.name)}<small>${esc(x.sku)}${x.color ? ` · ${esc(x.color)}` : ""}</small></span>
        ${shownVerdict(x.verdict) === "fit" ? "" : `<span class="badge ${shownVerdict(x.verdict)}">${VERDICT_LABEL[x.verdict] || "판정 불가"}</span>`}
        ${p.source_url && !p.demo_only ? `<a class="btn ghost small" href="${esc(p.source_url)}" target="_blank" rel="noopener">LGE.COM에서 구매</a>` : ""}</li>`; }).join("")}</ul>
      <p class="order-note">구매는 LGE.COM 제품 페이지에서 하고, 설치는 방문 신청을 하면 기사가 실측한 뒤 진행해요. 전원·배관 위치도 그때 확인해요.</p>
      <div class="order-actions ir-box" id="irBox"></div>`
      : `<p class="order-sum">아직 놓은 제품이 없어요.</p><p class="order-note">왼쪽 목록에서 제품을 골라 3D에 놓으면, 설치할 수 있는 자리인지 검사한 결과와 함께 신청할 수 있어요.</p>`}`;
    orderSheet.hidden = false;
    // 방문 설치 신청: 놓은 제품과 설치 전 확인 목록을 그대로 기사에게 넘긴다
    const irBox = document.getElementById("irBox");
    if (irBox) installRequestBox(irBox, pid, project, () => refresh(true).then(() => { if (!orderSheet.hidden) openOrder(); }));
    document.getElementById("orderClose").onclick = closeOrder;
    document.getElementById("orderClose").focus({ preventScroll: true });
  };
  orderSheet.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); closeOrder(); } });
  document.getElementById("orderBtn").onclick = openOrder;
  document.getElementById("orderMini").onclick = openOrder;

  // ---- 놓은 제품 자리의 살아 보기 결과(채광·와이파이): 서버가 계산한 값을 문장으로 ----
  let life = {}, lifeKey = "", lifeBusy = false;
  const syncLife = async () => {
    const pls = project.scene_state.placements;
    const key = JSON.stringify([pls.map((x) => [x.placement_id, x.center_xz]), project.site?.north_deg, project.site?.lat, project.scene_state.router]);
    if (key === lifeKey || lifeBusy) return;
    lifeKey = key;
    if (!pls.length) { life = {}; return; }
    lifeBusy = true;
    try { life = (await api(`/api/projects/${pid}/life-check`)).items || {}; }
    catch { life = {}; } // 옛 API 서버면 채광·와이파이 줄만 빠진다
    lifeBusy = false;
    if (selPl) renderInspector();
  };
  const renderPlacements = () => {
    renderProgress();
    const pls = project.scene_state.placements;
    document.getElementById("plCount").textContent = pls.length;
    document.getElementById("orderMini").hidden = !pls.length;
    document.getElementById("pls").innerHTML = pls.length ? pls.map((x) => `
      <li data-sel="${esc(x.placement_id || "")}" class="${x.placement_id === selPl ? "on" : ""}">
        <i class="dot" style="background:${esc(x.hex || "#fff")}"></i><span style="flex:1">${esc(prodOf(x.sku)?.name || x.sku)}</span>${shownVerdict(x.verdict) === "fit" ? "" : `<span class="badge ${shownVerdict(x.verdict)}">${LABEL[x.verdict]}</span>`}</li>`).join("")
      : `<li class="muted">아직 없어요. 왼쪽 목록에서 제품을 골라 3D에 놓아 보세요.</li>`;
    document.querySelectorAll("#pls [data-sel]").forEach((li) => (li.onclick = () => { selPl = li.dataset.sel || null; selObj = null; setTab("sel"); draw(); renderInspector(); renderPlacements(); }));
    const fold = document.getElementById("icFold");
    fold.hidden = !pls.length;
    if (pls.length && fold.open) installCheck(document.getElementById("icBox"), pid);
    fold.ontoggle = () => { if (fold.open) installCheck(document.getElementById("icBox"), pid); };
    const gone = project.scene_state.hidden_objects || [];
    if (gone.length) document.getElementById("pls").insertAdjacentHTML("beforeend", `<li class="muted" style="font-size:12px">치운 기존 가구 ${gone.length}개 <span class="spacer"></span><button class="small ghost" id="restore">모두 되돌리기</button></li>`);
    const rb = document.getElementById("restore");
    if (rb) rb.onclick = guard(async () => { await put(`/api/projects/${pid}/objects/hidden`, { hidden: false }); await refresh(true); });
    // 스캔 가구 한꺼번에 치우기 / 되돌리기
    const fb = document.getElementById("furn");
    const all = room.objects.length, allGone = all > 0 && gone.length >= all;
    fb.hidden = all === 0;
    fb.textContent = allGone ? `가구 ${all}개 되돌리기` : "가구 치우기";
    fb.classList.toggle("on", allGone);
    fb.onclick = guard(async () => { await put(`/api/projects/${pid}/objects/hidden`, { hidden: !allGone }); toast(allGone ? "스캔 가구를 되돌렸어요" : "스캔 가구를 모두 치웠어요"); await refresh(true); });
  };
  const SWATCH = { wall: ["#F2EFEA", "#E8E4DC", "#D9D4CB", "#C9CFD3", "#3E4247"], floor: ["#C8A27A", "#A67C52", "#E3D5C1", "#8D8D8A", "#5B4636"] };
  const renderMats = () => {
    const m = project.scene_state.materials || {};
    document.getElementById("mats").innerHTML = Object.entries({ wall: "벽", floor: "바닥" }).map(([t, label]) => `
      <div class="mats-row"><span>${label}</span>
        ${SWATCH[t].map((h) => `<button class="sw ${m[t] === h ? "on" : ""}" data-mat="${t}" data-hex="${h}" style="background:${h}" title="${h}"></button>`).join("")}</div>`).join("");
    document.querySelectorAll("[data-mat]").forEach((b) => (b.onclick = guard(async () => {
      await post(`/api/projects/${pid}/materials`, { target: b.dataset.mat, hex_color: b.dataset.hex });
      await refresh(true);
    })));
  };

  document.getElementById("render").onclick = guard(async (e) => {
    e.target.disabled = true; e.target.textContent = "렌더 중…";
    try {
      // 채광을 보고 있으면 그 날짜·시각의 해로 렌더한다 (화면과 같은 빛)
      await post(`/api/projects/${pid}/render`, sim === "daylight" ? { date: simState.date, time: simState.time } : {});
      document.getElementById("renderImg").src = apiUrl(`/api/projects/${pid}/files/render.png?v=${Date.now()}`);
      document.getElementById("renderBox").hidden = false;
    } finally { e.target.disabled = false; e.target.textContent = "렌더 이미지"; }
  });
  document.getElementById("renderClose").onclick = () => (document.getElementById("renderBox").hidden = true);

  // ---- 실제 벽지·바닥재 (data/finishes, 2026 트렌드 조사) ----
  let FIN = [];
  const finById = (id) => FIN.find((f) => f.id === id);
  const curFinish = (kind) => project?.scene_state.finish_ids?.[kind] || null;
  const finishSet = () => Object.fromEntries(["wall", "floor"].map((k) => [k, finById(curFinish(k)?.id)]).filter(([, f]) => f));
  const finCard = (f) => {
    const cur = curFinish(f.kind), on = cur?.id === f.id, tone = on ? cur.tone : f.tones[0].hex;
    return `<article class="fin ${on ? "on" : ""}">
      <button class="fin-pick" data-fin="${esc(f.id)}" data-tone="${esc(tone)}" aria-pressed="${on}" title="${esc(f.name)} 적용">
        <img src="${swatchUrl(f, tone)}" alt="" width="120" height="120"><span class="tex">${TEXTURE_KO[f.texture]}</span>${on ? `<span class="chk">적용 중</span>` : ""}</button>
      <div class="fin-body"><b>${esc(f.name)}</b><span class="muted">${esc(f.brand)} · ${esc(f.line)}</span>
        ${f.tones.length > 1 ? `<div class="fin-tones" role="radiogroup" aria-label="톤">${f.tones.map((t) => `<button class="vsw ${on && t.hex === tone ? "on" : ""}" data-fin="${esc(f.id)}" data-tone="${esc(t.hex)}" title="${esc(t.name)}" aria-label="${esc(t.name)}" role="radio" aria-checked="${on && t.hex === tone}"><i style="background:${esc(t.hex)}"></i></button>`).join("")}</div>` : ""}
        <span class="fin-trend">${esc(f.trend || "")}</span>
        <a class="fin-src" href="${esc(f.source_url)}" target="_blank" rel="noopener">출처 · ${esc(f.source_checked_at)}</a></div></article>`;
  };
  const renderFinishes = () => {
    if (!FIN.length) return;
    document.getElementById("finWall").innerHTML = FIN.filter((f) => f.kind === "wall").map(finCard).join("");
    document.getElementById("finFloor").innerHTML = FIN.filter((f) => f.kind === "floor").map(finCard).join("");
    document.querySelectorAll("[data-panel=finish] [data-fin]").forEach((b) => (b.onclick = guard(async () => {
      const f = finById(b.dataset.fin);
      await post(`/api/projects/${pid}/finishes`, { finish_id: f.id, tone: b.dataset.tone });
      toast(`${f.kind === "wall" ? "벽" : "바닥"}에 ${f.name}을 입혔어요`);
      await refresh(true);
    })));
  };
  const AI_EX = ["따뜻한 오크 마루에 회벽 느낌", "대리석 바닥에 호텔처럼 차분하게", "밝은 화이트 미니멀", "린넨 느낌 벽에 그린 포인트", "어둡고 시크한 모던"];
  const aiRow = (m, applied) => `<li><img src="${swatchUrl(m.finish, m.tone.hex, 48)}" alt="" width="36" height="36">
      <div><b>${esc(m.finish.name)}</b> <span class="muted">${esc(m.tone.name)}</span>${applied ? ` <span class="badge fit">적용</span>` : ""}
        <span class="muted why">${esc(m.reasons.join(" · ") || "기본 순서")}</span></div>
      ${applied ? "" : `<button class="small ghost" data-fin="${esc(m.finish.id)}" data-tone="${esc(m.tone.hex)}">입히기</button>`}</li>`;
  const ENGINE = { claude: "Claude가 해석", openai: "OpenAI가 해석", rules: "키워드로 해석" };
  const engineBadge = (d) => `<span class="badge ${d.engine === "rules" ? "src" : "ai"}">${ENGINE[d.engine] || "키워드로 해석"}</span>`;
  const bindFinButtons = (root) => root.querySelectorAll("[data-fin]").forEach((b) => (b.onclick = guard(async () => {
    await post(`/api/projects/${pid}/finishes`, { finish_id: b.dataset.fin, tone: b.dataset.tone });
    await refresh(true);
  })));
  const aiResult = (d) => `<div class="ai-out">
      <p class="ai-sum">${esc(d.summary)}</p>
      <div class="row"><div class="palette">${d.style.palette.map((h) => `<i style="background:${esc(h)}" title="${esc(h)}"></i>`).join("")}</div>${engineBadge(d)}</div>
      ${["wall", "floor"].map((k) => `<h4>${k === "wall" ? "벽지" : "바닥재"} 추천</h4><ul class="ai-list">${d.finishes[k].map((m, i) => aiRow(m, i === 0 && d.applied[k])).join("")}</ul>`).join("")}</div>`;
  // 말로 꾸미기 한 번: 서버가 말을 해석하고 벽지·바닥재를 골라 입힌다. 순위는 서버 코드가 계산
  const askAi = async (prompt) => {
    const d = await post(`/api/projects/${pid}/style/ai`, { prompt });
    const styled = Object.keys(d.applied || {}).length > 0;
    if (styled) toast(d.engine === "rules" ? "키워드로 고른 스타일을 입혔어요" : "AI가 고른 스타일을 입혔어요");
    await refresh(true);
    return d;
  };
  // 마감재 탭·추천 탭의 같은 입력 칸
  studio.querySelectorAll("[data-ai]").forEach((box) => {
    const ta = box.querySelector(".ai-prompt"), go = box.querySelector(".ai-go"), res = box.querySelector(".ai-res");
    box.querySelector(".ai-ex").innerHTML = AI_EX.map((t) => `<button class="chip" data-ex="${esc(t)}">${esc(t)}</button>`).join("");
    box.querySelectorAll("[data-ex]").forEach((b) => (b.onclick = () => { ta.value = b.dataset.ex; ta.focus(); }));
    go.onclick = guard(async () => {
      const prompt = ta.value.trim();
      if (!prompt) { toast("원하는 분위기를 적어 주세요", true); return; }
      go.disabled = true; go.textContent = "분위기 읽는 중…";
      try {
        const d = await askAi(prompt);
        res.innerHTML = aiResult(d) + (box.dataset.ai === "finish"
          ? ""
          : `<button class="small ghost ai-next" data-go="finish">벽지·바닥재 더 보기</button>`);
        bindFinButtons(res);
        const go2 = res.querySelector("[data-go]");
        if (go2) go2.onclick = (e) => setTab(e.target.dataset.go);
      } finally { go.disabled = false; go.textContent = "추천 받기"; }
    });
  });

  // ---- LG 봇: 구석의 도우미. 누르면 말로 꾸미기 대화창 ----
  const bot = document.getElementById("bot"), botBtn = document.getElementById("botBtn"), botLog = document.getElementById("botLog");
  const botForm = document.getElementById("botForm"), botIn = document.getElementById("botIn");
  const say = (who, html) => {
    botLog.insertAdjacentHTML("beforeend", `<div class="msg ${who}">${html}</div>`);
    botLog.scrollTop = botLog.scrollHeight;
    return botLog.lastElementChild;
  };
  const openBot = (open) => {
    bot.classList.toggle("open", open);
    botBtn.setAttribute("aria-expanded", open);
    document.getElementById("botPanel").hidden = !open;
    if (open) { botIn.focus(); bot.classList.remove("nudge"); }
  };
  botBtn.onclick = () => openBot(!bot.classList.contains("open"));
  document.getElementById("botClose").onclick = () => { openBot(false); botBtn.focus(); };
  bot.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); openBot(false); botBtn.focus(); } });
  document.getElementById("botEx").innerHTML = AI_EX.slice(0, 3).map((t) => `<button class="chip" data-say="${esc(t)}">${esc(t)}</button>`).join("");
  document.querySelectorAll("[data-say]").forEach((b) => (b.onclick = () => { botIn.value = b.dataset.say; botForm.requestSubmit(); }));
  botForm.onsubmit = async (e) => {
    e.preventDefault();
    const prompt = botIn.value.trim();
    if (!prompt || botForm.dataset.busy) return;
    botIn.value = ""; botForm.dataset.busy = "1"; bot.classList.add("thinking");
    say("me", esc(prompt));
    const wait = say("hb", `<span class="dots" aria-label="생각하는 중"><i></i><i></i><i></i></span>`);
    try {
      const d = await askAi(prompt);
      const name = (k) => d.applied?.[k] ? esc(d.finishes[k][0].finish.name) : null;
      const used = [name("wall") && `벽은 <b>${name("wall")}</b>`, name("floor") && `바닥은 <b>${name("floor")}</b>`].filter(Boolean).join(", ");
      const styled = !!used;
      const prods = d.products?.items || [];
      // 제품을 물었으면 맞는 제품 카드(넣어 보기), 분위기를 말했으면 입힌 벽지·바닥
      wait.innerHTML = `<p>${esc(d.products?.message || d.summary)}</p>${used ? `<p>${used}로 입혀 봤어요.</p>` : ""}
        ${prods.length ? `<ul class="bot-prods">${prods.map((it) => `<li><span class="ph">${it.thumb ? `<img src="${esc(it.thumb)}" alt="" loading="lazy">` : ""}</span>
          <span class="nm"><b>${esc(it.family_name || it.product.name)}</b><small>${esc((it.reasons || []).join(" · "))}</small></span>
          <button class="small primary" data-try="${esc(it.product.sku)}">넣어 보기</button></li>`).join("")}</ul>` : ""}
        ${styled ? `<div class="row"><div class="palette">${(d.style?.palette || []).map((h) => `<i style="background:${esc(h)}"></i>`).join("")}</div>${engineBadge(d)}</div>
        <div class="msg-acts"><button class="small ghost" data-go="finish">다른 후보 보기</button></div>` : ""}`;
      wait.querySelectorAll("[data-go]").forEach((b) => (b.onclick = () => setTab(b.dataset.go)));
      wait.querySelectorAll("[data-try]").forEach((b) => (b.onclick = () => {
        const sku = b.dataset.try;
        if (!prodOf(sku)) return;
        openBot(false);
        if (walking) setWalking(false);
        armed = sku; ghost(null); setHint(); renderLib();
      }));
    } catch (err) {
      wait.innerHTML = `<p>앗, 지금은 해석이 안 됐어요. 잠시 뒤 다시 말해 주세요.</p>`;
    } finally { delete botForm.dataset.busy; bot.classList.remove("thinking"); botLog.scrollTop = botLog.scrollHeight; }
  };
  if (!saved.botSeen) { bot.classList.add("nudge"); saveUiState(pid, { botSeen: true }); }
  api("/api/finishes").then((r) => { FIN = r.finishes; renderFinishes(); lastSceneKey = null; refresh(true).catch(() => {}); }).catch(() => {});

  const renderStyle = () => {
    const s = project.style;
    document.getElementById("style").innerHTML = s.prompt || s.palette.length ? `
      <p style="margin:0 0 8px">“${esc(s.prompt || "")}”</p>${s.summary ? `<p class="hint-sm">${esc(s.summary)}</p>` : ""}
      <div class="row"><div class="palette">${s.palette.map((h) => `<i style="background:${esc(h)}" title="${esc(h)}"></i>`).join("")}</div>
      <span class="muted">${s.materials.map(esc).join(" · ")}</span></div>`
      : `<p class="muted" style="margin:0;font-size:12px">위 ‘말로 꾸미기’에 적거나, Claude·Codex에서 <b>“화이트 우드 톤으로 바꿔 줘”</b>처럼 말하면 스타일이 저장되고 추천에 반영됩니다.</p>`;
  };
  const draw = () => {
    pv = planView(svg, room, { zones, placements: project.scene_state.placements, hidden: project.scene_state.hidden_objects,
      selectedPl: selPl, selectedObj: selObj, overlay, northDeg: sim === "daylight" ? project.site?.north_deg ?? 0 : null });
    drawDraft();
    if (!drag3d) viewer.setPlacements(project.scene_state.placements, selPl);
    syncNeed();
  };
  // 고른 제품이 차지하는 공간(본체 + 문 여는 공간)을 3D 바닥에 표시. 판정과 같은 계산(pose-check)을 그대로 쓴다
  let needKey = "";
  const syncNeed = async () => {
    const x = project.scene_state.placements.find((q) => q.placement_id === selPl);
    const key = x ? `${x.placement_id}|${x.sku}|${x.center_xz}|${x.yaw_rad}` : "";
    if (key === needKey) return;
    needKey = key;
    if (!x) { viewer.setNeed(null); document.getElementById("needTag").hidden = true; return; }
    try {
      const r = await post(`/api/projects/${pid}/pose-check`, { sku: x.sku, center_xz: x.center_xz, yaw_rad: x.yaw_rad, snap: false, placement_id: x.placement_id });
      if (needKey !== key) return;
      viewer.setNeed(r.required);
      document.getElementById("needTag").hidden = !r.required?.length;
    } catch { viewer.setNeed(null); }
  };
  const setOverlay = (html) => {
    overlay = html;
    const g = document.getElementById("overlay");
    if (g) g.innerHTML = html;
    viewer.setOverlay(html, svg.getAttribute("viewBox")?.split(" ").map(Number));
  };

  // ---- 살아 보기: 채광 ----
  const heat = (grid, color, maxV) => {
    const out = [];
    const [x0, y0] = grid.origin, c = grid.cell_m;
    grid.values.forEach((row, j) => row.forEach((v, i) => {
      if (v == null || v <= 0) return;
      out.push(`<rect x="${x0 + i * c}" y="${y0 + j * c}" width="${c}" height="${c}" fill="${color}" fill-opacity="${Math.min(0.75, 0.12 + (0.63 * v) / maxV).toFixed(2)}"/>`);
    }));
    return out.join("");
  };
  let simTimer = null, playing = null;
  const stopPlay = () => {
    if (!playing) return;
    cancelAnimationFrame(playing.raf); playing = null;
    const b = document.getElementById("splay"); if (b) { b.textContent = "하루 재생"; b.setAttribute("aria-pressed", "false"); }
  };
  // 하루 직사광 격자는 무겁다: 날짜·위치·북쪽·놓은 제품이 같으면 다시 받지 않는다 (시간 슬라이더는 해만 받는다)
  let heatCache = { key: null, daily: null, assumptions: [] };
  const DIRS = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"];
  // 하루 해 경로(5분 간격)를 한 번 받아 두고 그 사이를 이어서 쓴다: 시간을 움직여도 서버를 기다리지 않고 바로, 끊김 없이
  let sunPath = { key: null, pts: null };
  const toMin = (t) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
  const hhmm = (v) => `${String(Math.floor(v / 60)).padStart(2, "0")}:${String(Math.floor(v % 60)).padStart(2, "0")}`;
  let simMin = toMin(simState.time); // 재생 중에는 분 단위 아래까지 이어진다
  const hexRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const sunAt = (min) => {
    const pts = sunPath.pts;
    if (!pts?.length) return null;
    const step = pts[1].minute - pts[0].minute;
    const f = Math.max(0, Math.min(pts.length - 1, (min - pts[0].minute) / step));
    const i = Math.min(pts.length - 2, Math.floor(f)), t = f - i, a = pts[i], b = pts[i + 1];
    const mix = (x, y) => x + (y - x) * t;
    const dir = a.direction.map((v, k) => mix(v, b.direction[k]));
    const n = Math.hypot(...dir) || 1;
    const [ra, ga, ba] = hexRgb(a.color), [rb, gb, bb] = hexRgb(b.color);
    const alt = mix(a.altitude_deg, b.altitude_deg);
    let daz = b.azimuth_deg - a.azimuth_deg; if (daz > 180) daz -= 360; if (daz < -180) daz += 360;
    return { direction: dir.map((v) => v / n), up: alt > 0, altitude_deg: alt, azimuth_deg: (a.azimuth_deg + daz * t + 360) % 360,
      color: "#" + [mix(ra, rb), mix(ga, gb), mix(ba, bb)].map((v) => Math.round(v).toString(16).padStart(2, "0")).join(""),
      kelvin: Math.round(mix(a.kelvin, b.kelvin)), intensity: mix(a.intensity, b.intensity), sky: mix(a.sky, b.sky) };
  };
  const runDaylight = async () => {
    const box = document.getElementById("simres");
    if (project.site?.north_deg == null) { setOverlay(""); viewer.setSun(null); box.innerHTML = `<p class="notice" style="margin:0">창이 없는 방이라 방향을 추정하지 못했어요. 북쪽 방향 슬라이더로 평면도의 나침반을 실제 북쪽에 맞춰 주세요.</p>`; return; }
    const key = JSON.stringify([simState.date, project.site, project.scene_state.placements.map((x) => [x.placement_id, x.center_xz]), version]);
    const needHeat = simState.heat && heatCache.key !== key;
    const pathKey = JSON.stringify([simState.date, project.site]);
    const needPath = sunPath.key !== pathKey;
    const d = await api(`/api/projects/${pid}/sim/daylight?date=${simState.date}&time=${simState.time}&heatmap=${needHeat}&path=${needPath}`);
    if (sim !== "daylight") return;
    if (needHeat) heatCache = { key, daily: d.daily, assumptions: d.assumptions };
    if (needPath && d.path) sunPath = { key: pathKey, pts: d.path };
    // 3D: 그 시각 해 방향·색·세기로 비추고 창으로 볕이 든다. 재생 중이면 응답이 늦게 와도 지금 시각의 해를 쓴다
    viewer.setSun(sunAt(simMin) || d.sun);
    const daily = simState.heat ? heatCache.daily : null;
    const maxH = daily ? Math.max(1, ...daily.values.flat().filter((v) => v != null)) : 1;
    setOverlay(daily ? heat(daily, "#f2a900", maxH) + d.patches.map((p) => `<polygon class="sunpatch" points="${p.polygon.map((q) => q.join(",")).join(" ")}" style="stroke-width:${pv.sw(1.5)}px"/>`).join("") : "");
    const s = d.sun, dir = DIRS[Math.round(s.azimuth_deg / 45) % 8];
    const pls = daily ? project.scene_state.placements.filter((x) => x.placement_id in daily.points) : [];
    const BASIS = { main_window_south: "가장 큰 창이 남쪽을 본다고 보고 추정했어요. 다르면 북쪽 방향을 고쳐 주세요", building_footprint: "주소의 건물 방향에 맞춰 추정했어요. 다르면 북쪽 방향을 고쳐 주세요", manual: "" };
    const fc = d.facings || [];
    const facing = fc.length ? `<p class="facing"><b>${esc(fc[0].label)}</b> 집이에요 <span class="muted">가장 큰 창 기준${fc.length > 1 ? ` · 다른 창 ${fc.slice(1).map((x) => esc(x.label)).join(", ")}` : ""}</span>${BASIS[project.site?.north_basis] ? `<em>${BASIS[project.site.north_basis]}</em>` : ""}</p>` : "";
    box.innerHTML = `${facing}
      <p style="margin:0 0 6px">${s.up ? `해 높이 <b>${s.altitude_deg.toFixed(0)}°</b> · <b>${dir}쪽</b> 하늘(방위 ${s.azimuth_deg.toFixed(0)}°) · 빛 색 ${s.kelvin.toLocaleString()} K${s.altitude_deg < 10 ? " (해 질 녘)" : ""} · 지금 볕 드는 창 ${d.patches.length}개` : "해가 진 시간입니다"}${daily ? ` · 진한 노랑일수록 하루 직사광이 깁니다 (최대 ${maxH.toFixed(1)}시간)` : ""}</p>
      ${pls.length ? `<ul class="reasons">${pls.map((x) => { const h = daily.points[x.placement_id]; return `<li>${esc(prodOf(x.sku)?.name || x.sku)}: 하루 직사광 <b>${h.toFixed(1)}시간</b>${h >= 2 ? ` <span class="badge conditional">햇빛 주의</span>` : ""}</li>`; }).join("")}</ul>` : ""}
      <details class="sim-notes"><summary>참고 사항</summary>참고용 시뮬레이션 · ${[...(daily ? heatCache.assumptions : d.assumptions)].map(esc).join(" · ")}</details>`;
  };
  const daylightCtl = async () => {
    regions = regions || (await api("/api/regions"));
    // 스캔에는 나침반이 없다 → 북쪽을 안 정했으면 가장 큰 창이 남쪽을 본다고 보고 먼저 잡아 준다 (슬라이더로 고칠 수 있다)
    if (project.site?.north_deg == null) { try { project = await put(`/api/projects/${pid}/site`, { auto_north: true }); draw(); } catch { /* 창이 없으면 안내문 */ } }
    const site = project.site || {};
    document.getElementById("simctl").innerHTML = `
      <div class="simgrid">
        <label class="addr-row">주소 <span class="muted" id="addrNow">${site.address ? esc(site.address) : "적으면 그 위치의 해로 계산해요"}</span>
          <span class="time-row"><input type="search" id="addr" placeholder="예) 서울 중구 세종대로 110" maxlength="200" autocomplete="street-address"><button class="small ghost" id="addrGo">찾기</button></span></label>
        <label>지역<select id="region">${Object.keys(regions).map((r) => `<option ${r === (site.region || "서울") ? "selected" : ""}>${r}</option>`).join("")}</select></label>
        <label>북쪽 방향 <span class="muted" id="nv">${site.north_deg ?? "미지정"}${site.north_deg != null ? "°" : ""}</span><input type="range" id="north" min="0" max="359" step="1" value="${Math.round(site.north_deg ?? 0)}"></label>
        <label>날짜<input type="date" id="sdate" value="${simState.date}"></label>
        <label>시각 <b id="tv">${simState.time}</b><span class="time-row"><button class="small ghost" id="splay" aria-pressed="false" title="하루 해의 움직임을 이어서 보여 줘요">하루 재생</button><input type="range" id="stime" min="300" max="1260" step="1" value="${Math.round(simMin)}"></span></label>
      </div>
      <div class="chips" style="margin:6px 0 8px">${[["동지", "-12-21"], ["춘분", "-03-20"], ["하지", "-06-21"]].map(([k, v]) => `<button class="chip" data-day="${v}">${k}</button>`).join("")}<button class="chip" data-day="today">오늘</button>
        <label class="chip" style="cursor:pointer;display:inline-flex;flex-direction:row;align-items:center;gap:6px;white-space:nowrap"><input type="checkbox" id="sheat" ${simState.heat ? "checked" : ""} style="margin:0;width:auto">하루 햇빛 시간 겹쳐 보기</label></div>
      <div id="simres"></div>`;
    const kick = () => { clearTimeout(simTimer); simTimer = setTimeout(() => guard(runDaylight)(), 120); };
    // 주소 → 위도·경도 (서버가 찾는다). 건물 방향을 알면 북쪽도 같이 잡힌다
    const findAddr = guard(async () => {
      const q = document.getElementById("addr").value.trim();
      if (!q) return;
      const b = document.getElementById("addrGo"); b.disabled = true; b.textContent = "찾는 중…";
      try {
        project = await put(`/api/projects/${pid}/site`, { address: q });
        sunPath = { key: null, pts: null };
        toast("주소 위치로 채광을 다시 계산했어요");
        draw(); await daylightCtl();
      } finally { const x = document.getElementById("addrGo"); if (x) { x.disabled = false; x.textContent = "찾기"; } }
    });
    document.getElementById("addrGo").onclick = findAddr;
    document.getElementById("addr").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); findAddr(); } };
    document.getElementById("region").onchange = guard(async (e) => { project = await put(`/api/projects/${pid}/site`, { region: e.target.value }); kick(); });
    document.getElementById("north").oninput = (e) => {
      document.getElementById("nv").textContent = `${e.target.value}°`;
      svg.querySelector(".compass")?.setAttribute("transform", svg.querySelector(".compass").getAttribute("transform").replace(/rotate\([^ ]+/, `rotate(${e.target.value}`));
    };
    document.getElementById("north").onchange = guard(async (e) => { project = await put(`/api/projects/${pid}/site`, { north_deg: Number(e.target.value) }); draw(); kick(); });
    document.getElementById("sdate").onchange = (e) => { simState.date = e.target.value; kick(); };
    document.getElementById("sheat").onchange = (e) => { simState.heat = e.target.checked; kick(); };
    // 시각을 옮기면 해는 받아 둔 경로로 바로(부드럽게) 따라오고, 볕 자리·설명은 손을 멈추면 다시 받는다
    const setMin = (v, fetchNow) => {
      simMin = v; simState.time = hhmm(v);
      document.getElementById("tv").textContent = simState.time;
      const s = sunAt(v); if (s) viewer.setSun(s);
      if (fetchNow) kick();
    };
    document.getElementById("stime").oninput = (e) => { stopPlay(); setMin(Number(e.target.value), true); };
    // 하루 재생: 1초에 1시간씩 해가 움직인다. 볕 자리는 0.7초마다만 다시 받는다
    let lastFetch = 0;
    const tick = (now) => {
      if (!playing || sim !== "daylight" || !document.getElementById("stime")) { stopPlay(); return; }
      const dt = Math.min(0.1, (now - (playing.t || now)) / 1000); playing.t = now;
      let v = simMin + dt * 60;
      if (v >= 1260) { v = 1260; stopPlay(); }
      document.getElementById("stime").value = Math.round(v);
      setMin(v, false);
      if (now - lastFetch > 700) { lastFetch = now; guard(runDaylight)(); }
      if (playing) playing.raf = requestAnimationFrame(tick);
      else kick();
    };
    document.getElementById("splay").onclick = () => {
      if (playing) { stopPlay(); kick(); return; }
      if (simMin >= 1255) setMin(300, false);
      playing = { t: 0 }; playing.raf = requestAnimationFrame(tick);
      const b = document.getElementById("splay"); b.textContent = "멈추기"; b.setAttribute("aria-pressed", "true");
    };
    document.querySelectorAll("[data-day]").forEach((b) => (b.onclick = () => {
      simState.date = b.dataset.day === "today" ? new Date().toISOString().slice(0, 10) : `${simState.date.slice(0, 4)}${b.dataset.day}`;
      document.getElementById("sdate").value = simState.date; kick();
    }));
    if (project.site?.north_deg == null) draw();
    await runDaylight();
  };
  // ---- 살아 보기: 와이파이 ----
  let armedRouter = false, band = "5";
  const WCOLOR = { good: "#1f7a4d", ok: "#e0a800", weak: "#b3261e" };
  const WLABEL = { good: "좋음", ok: "보통", weak: "약함" };
  const runWifi = async () => {
    const box = document.getElementById("simres");
    const rt = project.scene_state.router;
    if (!rt) { setOverlay(""); viewer.setRouter(null); box.innerHTML = `<p class="notice" style="margin:0">공유기를 평면도에 놓거나 '추천 자리 찾기'를 눌러 보세요.</p>`; return; }
    const g = await api(`/api/projects/${pid}/sim/wifi?band=${band}`);
    const gradeOf = (v) => (v >= -60 ? "good" : v >= -70 ? "ok" : "weak");
    const [x0, y0] = g.origin, c = g.cell_m, cells = [];
    g.values.forEach((row, j) => row.forEach((v, i) => { if (v != null) cells.push(`<rect x="${x0 + i * c}" y="${y0 + j * c}" width="${c}" height="${c}" fill="${WCOLOR[gradeOf(v)]}" fill-opacity="0.28"/>`); }));
    const [rx, ry] = g.router;
    // 평면도에는 실제 크기 윗면 기호(본체 + 안테나 4개), 3D에는 실제 공유기 모델
    const yawDeg = ((rt.yaw_rad ?? 0) * 180) / Math.PI;
    const ants = [-0.1, -0.045, 0.045, 0.1].map((x) => `M${x} 0.06v0.05`).join("");
    setOverlay(cells.join("") + `<g class="router-sym" transform="translate(${rx} ${ry}) rotate(${-yawDeg})"><rect x="-0.1305" y="-0.0672" width="0.261" height="0.1345" rx="0.012"/><path d="${ants}" style="stroke-width:0.018px;stroke-linecap:round"/></g>`);
    viewer.setRouter(rt);
    const pct = (v) => `${Math.round((v || 0) * 100)}%`;
    box.innerHTML = `
      <p style="margin:0 0 6px">${["good", "ok", "weak"].map((k) => `<span class="badge" style="background:${WCOLOR[k]}22;color:${WCOLOR[k]}">${WLABEL[k]} ${pct(g.share[k])}</span>`).join(" ")} · 가장 약한 곳 <b>${g.min_dbm} dBm</b></p>
      ${g.zones.length ? `<ul class="reasons">${g.zones.map((z) => `<li>${esc(z.name)}: ${z.min_dbm == null ? "영역 안 칸 없음" : `가장 약한 곳 ${z.min_dbm} dBm · 약함 ${pct(z.share.weak)}`}</li>`).join("")}</ul>` : `<p class="muted" style="font-size:12px;margin:0">영역을 그리면 영역별 요약도 보여 드려요.</p>`}
      <p class="muted" style="font-size:12px;margin:6px 0 0">3D에서 공유기를 누르면 집어 들어요. 옮기거나 R로 돌려 내려놓으면 다시 계산해요.</p>
      <details class="sim-notes"><summary>참고 사항</summary>공유기 모델: TP-Link Archer AX55 공개 치수 261.1×134.5×41 mm · 참고용 시뮬레이션 · ${g.assumptions.map(esc).join(" · ")}</details>`;
  };
  const wifiCtl = async () => {
    document.getElementById("simctl").innerHTML = `
      <div class="row" style="margin-top:8px">
        <div class="tabs" style="margin:0"><button data-band="5" class="${band === "5" ? "on" : ""}">5 GHz</button><button data-band="2.4" class="${band === "2.4" ? "on" : ""}">2.4 GHz</button></div>
        <button class="small ghost" id="putRouter">${armedRouter ? "놓을 자리를 누르세요…" : "공유기 놓기"}</button>
        <button class="small ghost" id="bestRouter">추천 자리 찾기</button></div>
      <div id="simres" style="margin-top:8px"></div>`;
    document.querySelectorAll("[data-band]").forEach((b) => (b.onclick = () => { band = b.dataset.band; wifiCtl(); }));
    document.getElementById("putRouter").onclick = () => { armedRouter = !armedRouter; armed = null; mode = "move"; syncMode(); wifiCtl(); };
    document.getElementById("bestRouter").onclick = guard(async (e) => {
      e.target.disabled = true; e.target.textContent = "찾는 중…";
      const b = await api(`/api/projects/${pid}/sim/wifi/best?band=${band}`);
      project = await put(`/api/projects/${pid}/router`, { center_xz: b.center_xz, band });
      toast(`가장 약한 곳이 ${b.min_dbm} dBm가 되는 자리로 옮겼습니다`);
      wifiCtl();
    });
    await runWifi();
  };
  // ---- 살아 보기: 동선 ----
  let armedMark = null;
  const runFlow = async () => {
    const box = document.getElementById("simres");
    const f = await api(`/api/projects/${pid}/sim/flow`);
    const parts = [];
    const lw = pv.sw(2);
    const paths = [];
    for (const [k, r] of Object.entries(f.routes)) {
      if (!r.reachable) continue;
      paths.push(r.path);
      parts.push(`<polyline class="route" points="${r.path.map((p) => p.join(",")).join(" ")}" style="stroke-width:${lw}px;stroke-dasharray:${pv.sw(6)} ${pv.sw(5)}"/>`);
      // 좁은 곳: 바닥에 얇은 빨간 고리 (0.9 m보다 좁음)
      for (const n of r.narrow) parts.push(`<circle class="narrow" cx="${n[0]}" cy="${n[1]}" r="0.18" style="stroke-width:0.03px"/>`);
    }
    // 현관·싱크는 바닥에 글자 표시 (그림 문자 대신)
    const tag = (x, y, t) => {
      const fs = 0.16, w = fs * 0.95 * t.length + 0.12, h = fs + 0.1;
      return `<g class="tag"><rect x="${x - w / 2}" y="${y - h / 2}" width="${w}" height="${h}" rx="${h / 2}"/><text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="central" style="font-size:${fs}px">${t}</text></g>`;
    };
    if (f.entrance) parts.push(tag(...f.entrance.point, "현관"));
    for (const [k, v] of Object.entries(f.marks || {})) if (k === "sink") parts.push(tag(v[0], v[1], "싱크"));
    setOverlay(parts.join(""));
    viewer.setWalkers(paths); // 실제 크기(170 cm) 사람이 현관에서 제품 앞까지 걷는다
    const rows = Object.entries(f.routes).map(([k, r]) => {
      const nm = esc(f.names[k] || k);
      if (!r.reachable) return `<li><span class="badge no_fit">못 감</span> ${nm}: 현관에서 갈 길이 막혔어요</li>`;
      const bad = r.min_width_m < 0.9;
      return `<li><span class="badge ${bad ? "conditional" : "fit"}">${bad ? "좁음" : "여유"}</span> ${nm}: ${r.length_m} m · 가장 좁은 곳 ${r.min_width_m} m</li>`;
    }).join("");
    const t = f.triangle;
    box.innerHTML = `
      ${rows ? `<ul class="reasons">${rows}</ul>` : `<p class="muted" style="margin:0">제품을 놓으면 현관에서 제품 앞까지 동선을 그려 드려요.</p>`}
      ${t ? `<p style="margin:6px 0 0">주방 작업 삼각형(냉장고·싱크·쿡탑) 합계 <b>${t.perimeter_m} m</b> (${t.legs_m.join(" / ")} m) <span class="badge ${t.ok ? "fit" : "conditional"}">${t.ok ? "권장 범위" : "권장 범위 밖"}</span></p>` : ""}
      <details class="sim-notes"><summary>참고 사항</summary>걷는 사람 키 170 cm, 보통 걸음 1.3 m/s · 빨간 고리 = 0.9 m보다 좁은 곳 · 참고용 시뮬레이션 · ${f.assumptions.map(esc).join(" · ")}</details>`;
  };
  const flowCtl = async () => {
    document.getElementById("simctl").innerHTML = `
      <div class="row" style="margin-top:8px">
        <button class="small ghost" id="mkEnt">${armedMark === "entrance" ? "현관 쪽을 누르세요…" : "현관 지정"}</button>
        <button class="small ghost" id="mkSink">${armedMark === "sink" ? "싱크 자리를 누르세요…" : "싱크 위치 지정"}</button>
        <span class="muted" style="font-size:12px">싱크를 지정하고 냉장고·쿡탑을 놓으면 작업 삼각형을 계산해요.</span></div>
      <div id="simres" style="margin-top:8px"></div>`;
    document.getElementById("mkEnt").onclick = () => { armedMark = armedMark === "entrance" ? null : "entrance"; armed = null; mode = "move"; syncMode(); flowCtl(); };
    document.getElementById("mkSink").onclick = () => { armedMark = armedMark === "sink" ? null : "sink"; armed = null; mode = "move"; syncMode(); flowCtl(); };
    await runFlow();
  };
  const SIMS = { daylight: daylightCtl, wifi: wifiCtl, flow: flowCtl };
  const showSim = guard(async () => {
    document.querySelectorAll("[data-sim]").forEach((x) => x.classList.toggle("on", x.dataset.sim === sim));
    if (sim !== "daylight") { stopPlay(); viewer.setSun(null); } // 채광이 아니면 보기 좋은 기본 해
    if (sim !== "wifi") viewer.setRouter(null);
    if (sim !== "flow") viewer.setWalkers([]);
    if (!sim) { document.getElementById("simctl").innerHTML = ""; setOverlay(""); draw(); return; }
    draw();
    if (SIMS[sim]) await SIMS[sim]();
    else { setOverlay(""); document.getElementById("simctl").innerHTML = `<p class="muted">준비 중입니다.</p>`; }
  });
  document.querySelectorAll("[data-sim]").forEach((b) => (b.onclick = () => { sim = sim === b.dataset.sim ? "" : b.dataset.sim; saveUiState(pid, { sim }); showSim(); }));
  let lastSceneKey = null;
  // 다시 읽기는 한 번에 하나씩 차례로: 겹치면 늦게 끝난 옛 응답이 새 상태를 덮는다
  let chain = Promise.resolve();
  const refresh = (force = false) => (chain = chain.catch(() => {}).then(() => load(force)));
  const load = async (force) => {
    if (drag || drag3d) return;
    const seen = editSeq;
    const v = (await api(`/api/projects/${pid}/version`)).version;
    if (!force && v === version) return;
    const got = await Promise.all([api(`/api/projects/${pid}`), api(`/api/projects/${pid}/room`), api(`/api/projects/${pid}/zones`)]);
    if (seen !== editSeq) return; // 저장이 끝나면 다시 읽는다
    version = v;
    [project, room, zones] = got;
    if (selPl && !project.scene_state.placements.some((q) => q.placement_id === selPl)) selPl = null;
    const measured = room.walls.filter((w) => w.measured).length, n = project.scene_state.placements.length;
    document.getElementById("sub").textContent = `${project.scan.scanned_by === "customer" ? "셀프 LiDAR 스캔" : "기사 방문 스캔"} · 벽 ${room.walls.length}개${measured ? ` (실측 ${measured}개)` : ""}${project.floorplan ? " · 도면 첨부" : ""} · 놓은 제품 ${n}개 · 마지막 갱신 ${new Date().toLocaleTimeString("ko-KR")}`;
    draw();
    if (walking) viewer.setWalk(walkWorld()); // 옮긴 제품·치운 가구로 충돌을 다시
    if (sim === "daylight" && document.getElementById("simres")) guard(runDaylight)();
    if (sim === "wifi" && document.getElementById("simres")) guard(runWifi)();
    if (sim === "flow" && document.getElementById("simres")) guard(runFlow)();
    renderInspector();
    renderPlacements();
    renderStyle();
    renderMats();
    renderFinishes();
    syncLife();
    scheduleSuggest();
    floorplanBox(document.getElementById("fpBox"), pid, project, () => refresh(true));
    wallTable(document.getElementById("walls"), pid, room, { by: "customer", onChange: () => refresh(true) });
    // glb(벽·가구·색)는 바뀌었을 때만 다시 받는다. 놓은 제품은 화면에서 직접 그린다.
    const sceneKey = JSON.stringify([project.scene_state.materials, project.scene_state.finish, project.scene_state.finish_ids, FIN.length, project.scene_state.hidden_objects, project.scene_state.object_poses, room.walls.map((w) => w.measured)]);
    if (sceneKey !== lastSceneKey) { lastSceneKey = sceneKey; viewer.setObjects(room.objects); viewer.setFinishes(finishSet()); viewer.load(apiUrl(`/api/projects/${pid}/files/scene.glb`)); }
    document.getElementById("hud").textContent = `빈 곳 끌기 회전 · 휠 확대 · 누르면 집어 들기 · WASD 카메라 · ${project.scene.engine === "blender" ? "Blender 장면" : "스캔 치수 장면"}`;
  };
  setHint();
  try { await refresh(true); }
  catch (e) {
    // 지워졌거나 잘못된 주소: 기억해 둔 집도 지우고 새로 올리게 한다
    if (e.status === 404) {
      forgetHome(pid);
      $app.innerHTML = `<div class="panel"><h1>집을 찾을 수 없어요</h1><p class="sub">${esc(pid)} 프로젝트가 서버에 없습니다. 서버의 저장 폴더(STORAGE_DIR)가 바뀌었거나 지워졌을 수 있어요.</p><a class="btn" href="#/new">새로 스캔 올리기</a></div>`;
      return;
    }
    toast(e.message, true);
  }
  if (project) {
    rememberHome(pid, token || project.share_token);
    mountSaveBar(document.getElementById("savebar"), pid, () => token || project.share_token);
  }
  if (["daylight", "wifi", "flow"].includes(saved.sim)) { sim = saved.sim; setLive(true); showSim(); }
  // ---- 첫 안내: 하우니가 스캔 결과를 알려 주고, 메뉴를 하나씩 짚은 뒤, 직접 놓아 보게 한다 ----
  const tryIt = guard(async () => {
    const pool = suggItems.length ? suggItems.map((x) => x.sku) : suggPool;
    const sku = pool[0];
    if (!sku) { toast("왼쪽 목록에서 제품을 하나 골라 3D 바닥을 눌러 보세요"); return; }
    setFlow({ space: true }); // 안내를 끝까지 봤으면 공간 확인은 한 것
    await autoPlace(sku);
    setHint("놓은 제품 아래 버튼으로 이동·회전·자동 정렬·삭제를 해 보세요. 오른쪽에서 설치 가능한지 바로 보여요");
  });
  const runTour = () => {
    if (!project || !room) return;
    const area = (() => { // 바닥 넓이(m², 벽 끝점으로 만든 다각형)
      const pts = room.walls.map((w) => w.start);
      let a = 0;
      pts.forEach((p, i) => { const q = pts[(i + 1) % pts.length]; a += p[0] * q[1] - q[0] * p[1]; });
      return Math.abs(a / 2);
    })();
    const objs = room.objects.length;
    const intro = { title: "집 스캔이 끝났어요!", text: `벽 ${room.walls.length}개${area > 1 ? `, 바닥 약 ${area.toFixed(1)}㎡` : ""}${objs ? `, 가구 ${objs}개` : ""}를 3D로 옮겨 왔어요. 이제 LG 가전을 직접 놓아 보면서 우리 집에 들어가는지 확인해 볼 수 있어요. 어떤 기능이 있는지 하나씩 알려 드릴게요.` };
    const outro = { title: "직접 체험해 볼까요?", text: "이 집에 들어가는 제품 하나를 알맞은 자리에 놓아 드릴게요. 놓은 뒤 아래 버튼으로 옮기거나 돌려 보세요.", cta: { label: "체험해 보기", run: tryIt } };
    openLib(false);
    // 앱(폰·작은 창)은 화면에 보이는 메뉴만 짧게
    const steps = studio.classList.contains("app") ? [
      intro,
      { sel: "#sugg", title: "이 집에 들어가는 제품", text: "우리 집 벽을 따라 실제로 놓아 보고, 들어가는 제품만 골라 드려요. 누르면 상세가 열리고 '넣어 보기'로 3D에 놓아요." },
      { sel: "#libMore", title: "전체 보기", text: "다른 제품을 찾거나 용량·색상·가격으로 좁히고 싶으면 여기를 눌러요." },
      { sel: ".canvas", title: "우리 집 3D", text: "놓은 제품을 누르면 아래에 이동·회전·자동 정렬·삭제 버튼이 나와요. 두 손가락으로 확대하고, 끌면 시점이 돌아가요." },
      { sel: ".icon-row", title: "되돌리기", text: "잘못 놓았으면 되돌리면 돼요. 물음표를 누르면 이 안내를 다시 볼 수 있어요." },
      { sel: "#liveBtn", title: "살아 보기", text: "눈높이로 걸어 보고, 볕·와이파이·동선을 봐요." },
      { sel: "#finBtn", title: "벽지 · 바닥", text: "실제 판매 중인 벽지와 바닥재로 바꿔 입혀 봐요." },
      { sel: "#homeMenu", title: "저장 · 내 집", text: "저장, 다른 집 스캔, 도면·실측 넣기는 여기 모여 있어요." },
      { sel: "#orderMini", title: "구매 및 설치 신청", text: "마음에 들면 LGE.COM에서 구매하고, 설치 기사 방문을 바로 신청할 수 있어요." },
      { sel: "#botBtn", title: "하우니에게 물어보기", text: "\"600리터 넘는 냉장고\"처럼 말로 물어보면 제가 골라 드려요." },
      outro,
    ] : [
      intro,
      { sel: "#progress", title: "진행 단계", text: "공간 확인 → 제품 고르기 → 설치 확인을 하나씩 해 나가면 차례로 체크돼요." },
      { sel: ".lib-side", title: "제품 찾기", text: "이름으로 찾거나 종류를 눌러 좁혀요. 용량·색상 같은 조건은 '상세 필터'를 열면 나와요." },
      { sel: "#sugg", title: "이 집에 들어가는 제품", text: "우리 집 벽을 따라 실제로 놓아 보고, 들어가는 제품만 골라 드려요." },
      { sel: "#lib", title: "제품 목록", text: "제품을 누르면 상세가 열리고, '넣어 보기'를 누르면 3D에 놓을 수 있어요." },
      { sel: ".canvas", title: "우리 집 3D", text: "바닥을 누르면 제품이 놓여요. 놓은 제품을 누르면 아래에 이동·회전·자동 정렬·삭제 버튼이 나와요. 빈 곳을 끌면 시점이 돌아가요." },
      { sel: ".icon-row", title: "되돌리기 · 다시 실행", text: "잘못 놓았으면 되돌리면 돼요. 전체 화면, 이 안내 다시 보기, 키보드 조작키도 여기 있어요." },
      { sel: "#liveBtn", title: "살아 보기", text: "눈높이로 집 안을 걸어 보고, 하루 동안 볕이 어떻게 드는지, 와이파이가 어디까지 닿는지, 동선이 어떤지 봐요." },
      { sel: "#finBtn", title: "벽지 · 바닥", text: "실제 판매 중인 벽지와 바닥재로 바꿔 입혀 봐요." },
      { sel: "#extraBtn", title: "도면 · 실측", text: "도면이나 줄자로 잰 값이 있으면 넣어서 더 정확하게 판정해요. 없어도 괜찮아요." },
      { sel: ".side", title: "설치 확인", text: "고른 제품이 설치 가능한지, 문 여는 공간과 지나다닐 통로, 그 자리의 채광·와이파이까지 한눈에 보여요." },
      { sel: "#orderBtn", title: "구매 및 설치 신청", text: "마음에 들면 LGE.COM에서 구매하고, 설치 기사 방문을 바로 신청할 수 있어요." },
      { sel: "#botBtn", title: "하우니에게 물어보기", text: "\"밝은 우드에 호텔처럼\", \"600리터 넘는 냉장고\"처럼 말로 물어보면 제가 골라 드려요." },
      outro,
    ];
    startTour(steps, { face: BOT_SVG });
  };
  document.getElementById("tourBtn").onclick = runTour;
  if (project && !tourSeen()) setTimeout(runTour, 600);
  // 채팅(Claude·Codex) 쪽 변경을 2초마다 확인
  const timer = setInterval(() => refresh().catch(() => {}), 2000);
  cleanup.push(() => clearInterval(timer));
}

// 말로 꾸미기 입력 칸 (마감재 탭·추천 탭 공통)
function aiBoxHtml(where) {
  return `<div class="ai-box" data-ai="${where}">
    <h3>말로 꾸미기 <span class="badge ai">AI 추천</span></h3>
    <p class="hint-sm">원하는 분위기를 편하게 적어 주세요. 벽지·바닥재를 골라 3D에 입히고, LG 가전 색 추천도 같이 바뀌어요.</p>
    <textarea class="ai-prompt" rows="3" maxlength="500" aria-label="원하는 분위기" placeholder="예) 따뜻한 오크 마루에 회벽 느낌으로, 호텔처럼 차분하게"></textarea>
    <div class="chips ai-ex"></div>
    <button class="primary ai-go">추천 받기</button>
    <div class="ai-res"></div>
  </div>`;
}

// LG 봇 ‘하우니’: HouseTwin 집 모양 오리지널 캐릭터 (웜그레이 몸, LG 레드 지붕)
const BOT_SVG = `<svg viewBox="0 0 64 64" aria-hidden="true" class="bot-art">
  <ellipse cx="32" cy="58" rx="16" ry="3" class="bot-shadow"/>
  <g class="bot-body">
    <path d="M12 30 L32 12 L52 30 V48 a7 7 0 0 1-7 7 H19 a7 7 0 0 1-7-7 Z" fill="#F4F0EA" stroke="#D9D2C7" stroke-width="1.5"/>
    <path d="M8 31 L32 9 L56 31" fill="none" stroke="#A50034" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"/>
    <rect x="42" y="12" width="5" height="9" rx="1.5" fill="#A50034"/>
    <rect x="18" y="31" width="28" height="17" rx="8.5" fill="#3B3633"/>
    <g class="bot-eyes" fill="#FFFFFF"><rect x="24" y="36" width="4" height="6" rx="2"/><rect x="36" y="36" width="4" height="6" rx="2"/></g>
    <path d="M29.5 44.5 q2.5 2 5 0" fill="none" stroke="#FFFFFF" stroke-width="1.6" stroke-linecap="round"/>
    <circle cx="19" cy="50" r="2.4" fill="#F2B8C6"/><circle cx="45" cy="50" r="2.4" fill="#F2B8C6"/>
  </g></svg>`;
function botHtml() {
  return `<div class="bot" id="bot">
    <section class="bot-panel" id="botPanel" role="dialog" aria-label="LG 봇 하우니" hidden>
      <header class="bot-head">${BOT_SVG}<div><b>하우니</b><span>LG 봇 · 말로 꾸미기</span></div>
        <button class="bot-x" id="botClose" aria-label="닫기">×</button></header>
      <div class="bot-log" id="botLog" aria-live="polite">
        <div class="msg hb"><p>안녕하세요, 하우니예요! 원하는 집 분위기를 말해 주면 실제 벽지·바닥재를 골라 3D에 바로 입혀 볼게요.</p></div>
      </div>
      <div class="chips bot-ex" id="botEx"></div>
      <form class="bot-form" id="botForm"><input id="botIn" maxlength="500" autocomplete="off" placeholder="예) 밝은 우드에 호텔처럼" aria-label="하우니에게 말하기">
        <button class="primary" aria-label="보내기">보내기</button></form>
    </section>
    <button class="bot-btn" id="botBtn" aria-expanded="false" aria-controls="botPanel" title="하우니에게 말로 꾸미기">${BOT_SVG}<span class="bot-tip">말로 꾸며 볼까요?</span></button>
  </div>`;
}
