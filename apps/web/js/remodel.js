// 화면: 우리 집 가상 리모델링 (제품 배치, 색·재질, 살아 보기)
import { $app, cleanup, LABEL, shownVerdict, PURPOSE, USE, CATEGORY, CATEGORY_GROUP, DIM, OBJ, NOTE, esc, mm, api, apiUrl, post, put, toast, guard,
  rememberHome, forgetHome, uiState, saveUiState } from "./core.js";
import { makeViewer } from "./viewer.js";
import { buildWorld } from "./walk.js";
import { planView, placedSvg } from "./plan.js";
import { wallTable, WALL_HEAD, floorplanBox, installRequestBox } from "./pages.js";
import { swatchUrl, TEXTURE_KO } from "./finishes.js";
import { mountSaveBar } from "./account.js";
import { stepState, stepperHtml, fitCardHtml, VERDICT_LABEL, INSTALL_NOTE } from "./guide.js";
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
        <details class="home-menu" id="homeMenu"><summary aria-label="저장·다른 집"><i class="save-dot" aria-hidden="true"></i><span id="saveSum">저장 · 내 집</span> <span aria-hidden="true">▾</span></summary>
          <div class="home-pop">
            <div class="savebar" id="savebar" aria-label="저장"></div>
            <button class="btn ghost small app-only" id="extraBtn2">도면·실측 넣기</button>
            <a class="btn ghost small new-scan" href="#/new" title="지금 집은 그대로 남고, 다른 집을 새로 올려요">+ 다른 집 스캔</a>
          </div></details>
      </header>

      <aside class="lib" data-panel="lib" aria-label="공간 꾸미기 라이브러리">
        <div class="lib-side">
          <nav class="lib-tabs" id="libTabs" role="tablist" aria-label="라이브러리 종류">
            <button role="tab" data-tab="all">전체</button><button role="tab" data-tab="lg">LG 가전</button><button role="tab" data-tab="furniture">가구</button><button role="tab" data-tab="storage">수납</button><button role="tab" data-tab="decor">소품</button></nav>
          <section class="decor-lib" id="decorLib" aria-label="벽체·가구·수납·소품"></section>
          <div class="lib-head lg-part"><h2>LG 가전</h2><span class="muted" id="libCount"></span>
            <select id="sortBy" aria-label="정렬"><option value="">추천순</option><option value="price">낮은 가격순</option><option value="size">작은 크기순</option></select>
            <button class="primary small app-only" id="orderMini" hidden>구매·설치 신청</button>
            <button class="ghost small app-only" id="libMore" aria-expanded="false">전체 보기</button></div>
          <input id="q" class="lg-part" type="search" placeholder="이름·모델명 검색" aria-label="제품 검색">
          <!-- 기본으로는 종류·설치 유형·크기만. 나머지는 상세 필터 안에 -->
          <div class="main-filter lg-part">
            <div class="chips" id="cats" aria-label="가전 종류"></div>
            <ol class="opt-steps main-steps" id="mainSteps" aria-label="설치 유형"></ol>
            <div class="filters" aria-label="크기 필터">
              <select id="fW" aria-label="폭"><option value="">폭 전체</option><option value="0-650">폭 650 mm 이하</option><option value="650-850">폭 650~850 mm</option><option value="850-99999">폭 850 mm 이상</option></select>
              <select id="fH" aria-label="높이"><option value="">높이 전체</option><option value="0-900">높이 900 mm 이하</option><option value="900-1800">높이 900~1,800 mm</option><option value="1800-99999">높이 1,800 mm 이상</option></select>
            </div>
            <div class="budget" id="budget" hidden aria-label="가격 범위">
              <div class="budget-head"><span>가격</span><b id="budgetOut"></b></div>
              <div class="budget-rail"><input type="range" id="pLo" aria-label="최저 가격"><input type="range" id="pHi" aria-label="최고 가격"></div>
            </div>
          </div>
          <details class="more-filter lg-part" id="moreFilter"><summary>상세 필터 <span class="muted" id="filterOn"></span></summary>
            <div class="ask" id="ask" aria-label="공간 용도"></div>
            <ol class="opt-steps" id="steps" aria-label="옵션을 차례로 골라 좁히기"></ol>
            <button class="small ghost reset-filter" id="resetFilter">필터 초기화</button>
          </details>
          <section class="sugg" id="sugg" aria-label="이 집에 들어가는 제품" hidden></section>
        </div>
        <ul class="list lg-part" id="lib" aria-label="LG 제품 목록. 누른 뒤 3D 바닥을 누르면 놓여요"></ul>
      </aside>

      <section class="stage" aria-label="우리 집">
        <section class="pd-modal" id="pdModal" role="dialog" aria-label="제품 상세" hidden></section>
        <section class="order-sheet" id="orderSheet" role="dialog" aria-label="구매 및 설치 신청" hidden></section>
        <div class="toolbar">
          <button class="furn-btn" id="beforeBtn" aria-pressed="false" title="스캔했을 때 모습과 견줘 봐요">처음과 비교</button>
          <button class="furn-btn live-btn" id="liveBtn" aria-pressed="false" title="실제로 살아 보듯 둘러보고, 볕·와이파이·동선을 봐요"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11 12 4l9 7v9H3z"/><path d="M9 20v-6h6v6"/></svg>살아 보기</button>
          <button class="furn-btn" id="finBtn" aria-expanded="false" aria-controls="finishPop" title="벽지·바닥재를 바꿔 봐요">벽지·바닥</button>
          <button class="furn-btn" id="furn" aria-pressed="false" title="스캔에 잡힌 가구를 한꺼번에 치우거나 되돌려요">가구 모두 지우기</button>
          <button class="furn-btn" id="extraBtn" aria-expanded="false" aria-controls="extraPop" title="도면을 올리거나 줄자로 잰 벽 길이를 넣어요">도면·실측</button>
          <span class="spacer"></span>
          <div class="sim-switches" role="group" aria-label="살아 보기"><button class="sw" data-sim="daylight" role="switch" aria-checked="false"><span class="sw-track" aria-hidden="true"><i></i></span>채광</button><button class="sw" data-sim="wifi" role="switch" aria-checked="false"><span class="sw-track" aria-hidden="true"><i></i></span>와이파이</button><button class="sw" data-sim="flow" role="switch" aria-checked="false"><span class="sw-track" aria-hidden="true"><i></i></span>동선</button></div>
          <button class="furn-btn" id="walk" title="눈높이 1.6 m에서 집 안을 걸어 봐요 (WASD 걷기, 화면을 누르면 마우스로 둘러보기)">둘러보기</button>
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
</div>
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
            <p class="hint-sm">제품을 누르면 바로 위에 뜨는 이동·회전·벽에 붙이기·삭제 메뉴로 다 할 수 있어요. 키보드가 편하면:</p>
            <ul class="keys"><li><kbd>클릭</kbd> 집어 들기 · 내려놓기</li><li><kbd>R</kbd> 45° 돌리기 (<kbd>Shift</kbd> 반대, <kbd>Alt</kbd> 15°)</li>
              <li><kbd>←↑↓→</kbd> 10 cm 옮기기 (<kbd>Shift</kbd> 1 cm)</li><li><kbd>Delete</kbd> 지우기</li><li><kbd>Ctrl</kbd><kbd>Z</kbd> 되돌리기 · <kbd>Ctrl</kbd><kbd>Shift</kbd><kbd>Z</kbd> 다시 실행</li><li><kbd>Esc</kbd> 취소</li></ul>
            <h4>화면</h4>
            <ul class="keys"><li><kbd>빈 곳 끌기</kbd> 시점 돌리기</li><li><kbd>휠</kbd> 확대·축소</li><li><kbd>휠 누르고 끌기</kbd> 화면 옮기기</li><li><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> 카메라 이동 · <kbd>Q</kbd><kbd>E</kbd> 돌기</li></ul>
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
          <section class="minimap" id="minimap" aria-label="도면" hidden></section>
          <p class="hint" id="hint" aria-live="polite"></p>
          <div class="step-card" id="stepCard" aria-live="polite" hidden></div>
          <p class="fit-badge" id="fitBadge" aria-live="polite" hidden></p>
          <div class="act-bar" id="actBar" role="toolbar" aria-label="고른 제품 조작" hidden></div>
          <p class="need-tag" id="needTag" hidden><i aria-hidden="true"></i>점선 안은 제품과 문을 여는 데 필요한 공간이에요</p>
          <div class="sheet" id="simctl"></div>
        </div>
      </section>

      <!-- 오른쪽 작업 정보: 고르면 그 제품 상세, 안 고르면 놓은 제품·설치 체크·추천·도면, 맨 아래 신청 -->
      <aside class="side" aria-label="작업 정보">
        <div class="side-body">
          <section id="insp"></section>
          <div class="chk" id="chkBox" aria-label="설치 체크"></div>
          <div class="side-slot" id="mapSlot"></div>
          <div class="side-slot" id="suggSlot"></div>
          <details class="pl-box" id="plBox" aria-label="놓은 제품">
            <summary><h3>놓은 제품 <span class="count" id="plCount">0</span></h3><span class="muted">목록 보기</span></summary>
            <ul class="list" id="pls"></ul>
          </details>
        </div>
        <div class="order-bar"><p class="order-total" id="orderTotal" hidden></p><button class="primary" id="orderBtn">구매 및 설치 신청 <span aria-hidden="true">›</span></button></div>
      </aside>
      ${botHtml()}
    </div>`;
  const studio = $app.querySelector(".studio");
  // 앱(폰·작은 창): 3D를 꽉 채우고, 제품은 아래 서랍, 고른 제품은 아래 카드로. 덜 쓰는 버튼은 숨긴다
  const appMq = matchMedia(`(max-width: ${APP_MAX_W}px)`);
  const libMore = document.getElementById("libMore");
  const openLib = (on) => { studio.classList.toggle("lib-open", on); libMore.textContent = on ? "접기" : "전체 보기"; libMore.setAttribute("aria-expanded", on); };
  const syncApp = () => { studio.classList.toggle("app", appMq.matches); if (!appMq.matches) openLib(false); placeSlots(); };
  syncApp();
  // 큰 화면: 추천과 도면은 오른쪽 작업 정보에. 앱 배치: 추천은 아래 서랍, 도면은 숨김
  function placeSlots() {
    const app = studio.classList.contains("app");
    const sugg = document.getElementById("sugg"), mini = document.getElementById("minimap");
    if (app) { studio.querySelector(".lib-side").append(sugg); studio.querySelector(".canvas").append(mini); }
    else { document.getElementById("suggSlot").append(sugg); studio.querySelector(".canvas").append(mini); } // 지예: 평면도는 3D 화면 구석에 작은 지도처럼
  }
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
    if (small && !minimap.querySelector(".mini-grow")) minimap.insertAdjacentHTML("afterbegin", `<button class="mini-grow" id="miniGrow" aria-pressed="false" title="도면 크게 보기">크게</button>`);
    minimap.hidden = !small;
    studio.classList.toggle("has-mini", !!small);
  };
  placePanes(studio.dataset.view);
  minimap.addEventListener("click", (e) => {
    const b = e.target.closest("#miniGrow");
    if (!b) return;
    const on = minimap.classList.toggle("big");
    b.setAttribute("aria-pressed", on); b.textContent = on ? "작게" : "크게";
  });
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
  let drag3d = null, hovering = false; // hovering: 마우스가 3D 위에 있는지 (버튼 위로 나가면 늦게 온 미리 보기를 버린다)
  let wallPicking = false, removeWall = () => {}; // 벽 철거: 3D에서 벽을 눌러 고르는 중 (아래에서 채운다)
  let wallDraw = null, wallPoint = () => {}; // 벽 추가: 바닥에서 시작점 → 끝점 ({start} 또는 {})
  const viewer = makeViewer(document.getElementById("viewer"), {
    canDrag: () => mode === "move" && !armed && !armedRouter && !armedMark,
    onSurface: () => armedRouter, // 공유기는 책상·선반 윗면에도 놓인다
    onHover: (p) => { hovering = true; follow(p); },
    onLeave: () => { hovering = false; if (armed) ghost(null); if (armedRouter) viewer.routerFollow(null); },
    onClick: ({ hit, point }) => {
      if (wallPicking) { if (hit?.type === "wall") removeWall(hit.id); return; }
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
      if (x) preview({ sku: x.sku, center_xz: xz, yaw_rad: h.yaw, placement_id: h.id, ...sizeArgs(x) }, (r) => viewer.holdVerdict(r.verdict));
    },
    onHoldClick: () => putDown(),
    onDragMove: (id, c) => {
      const x = project.scene_state.placements.find((q) => q.placement_id === id);
      if (!x) return;
      drag3d = id; selPl = id; selObj = null;
      preview({ sku: x.sku, center_xz: c, yaw_rad: x.yaw_rad, placement_id: id, ...sizeArgs(x) }, (r) => viewer.setDragVerdict(id, r.verdict));
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
  // 공간 꾸미기 가구 (제품 정보 없이 모양만, sku = "decor:종류"). 주문·설치 신청에는 넣지 않는다
  let decorList = [];
  const isDecor = (sku) => typeof sku === "string" && sku.startsWith("decor:");
  const decorOf = (sku) => decorList.find((d) => d.sku === sku);
  const nameOf = (sku) => prodOf(sku)?.name || decorOf(sku)?.name || sku;
  // 받침 있으면 "을", 없으면 "를" (한글이 아니면 "을(를)")
  const eul = (w) => { const c = w.charCodeAt(w.length - 1) - 0xac00; return c < 0 || c > 11171 ? "을(를)" : c % 28 ? "을" : "를"; };
  const sizeArgs = (x) => (isDecor(x?.sku) && x.size_m ? { size_m: [...x.size_m] } : {});
  const lgOnly = (pls) => pls.filter((x) => !isDecor(x.sku));
  const HINT = {
    move: "제품이나 가구를 누르면 고를 수 있어요. 제품 위에 뜨는 메뉴로 옮기고 돌려 보세요",
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
  decorList = (await api("/api/decor").catch(() => ({ items: [] }))).items;
  // ---- 공간 꾸미기 라이브러리: 전체 / LG 가전 / 가구 / 수납 / 소품. 벽체·구조 변경은 전체 맨 위 ----
  const libAside = studio.querySelector(".lib");
  const TABS = ["all", "lg", "furniture", "storage", "decor"];
  let libTab = TABS.includes(saved.libTab) ? saved.libTab : "all";
  const SECTION = [["structure", "벽체 & 구조 변경"], ["furniture", "가구"], ["storage", "수납 & 선반"], ["decor", "인테리어 소품"]];
  const tileHtml = (d) => `<button class="dtile" data-decor="${esc(d.sku)}" draggable="true" title="${esc(d.label)} 놓기">
      <span class="dimg"><img src="img/decor/${esc(d.model)}.webp" alt="" loading="lazy" decoding="async" draggable="false" onerror="this.remove()"></span><span>${esc(d.label)}</span></button>`;
  const wallTile = () => `<button class="dtile ${wallPicking ? "on" : ""}" id="wallRm" aria-pressed="${wallPicking}" title="3D에서 철거할 벽을 눌러요">
      <span class="dimg"><img src="img/decor/wall-remove.webp" alt="" loading="lazy" decoding="async" draggable="false" onerror="this.remove()"></span><span>${wallPicking ? "벽 고르는 중" : "벽 제거"}</span></button>`;
  function renderDecorLib() {
    const box = document.getElementById("decorLib");
    const groups = libTab === "all" ? SECTION : SECTION.filter(([g]) => g === libTab);
    box.innerHTML = libTab === "lg" ? "" : groups.map(([g, title]) => {
      const items = decorList.filter((d) => d.group === g);
      const tiles = (g === "structure" ? [items.find((d) => d.sku === "decor:wall")].filter(Boolean).map(tileHtml).join("") + wallTile() + items.filter((d) => d.sku !== "decor:wall").map(tileHtml).join("") : items.map(tileHtml).join(""));
      return `<section class="dsec"><h3>${esc(title)}</h3><div class="dgrid">${tiles}</div></section>`;
    }).join("") + (libTab === "all" ? `<button class="dsec-lg" data-go="lg">LG 가전 고르러 가기 <span aria-hidden="true">›</span></button>` : "");
    box.querySelectorAll("[data-decor]").forEach((b) => {
      b.classList.toggle("on", b.dataset.decor === "decor:wall" ? !!wallDraw : b.dataset.decor === armed);
      b.onclick = () => {
        if (wallPicking) setWallPick(false);
        openLib(false);
        if (b.dataset.decor === "decor:wall") { setWallDraw(!wallDraw); return; } // 벽은 바닥에 직접 그린다
        arm(b.dataset.decor); // 누르면 손에 들고, 바닥을 누르면 놓는다
      };
      b.ondragstart = (e) => e.dataTransfer.setData("text/sku", b.dataset.decor);
    });
    const wr = document.getElementById("wallRm");
    if (wr) wr.onclick = () => { openLib(false); if (wallDraw) setWallDraw(false); setWallPick(!wallPicking); };
    box.querySelector("[data-go]")?.addEventListener("click", () => setLibTab("lg"));
  }
  const setLibTab = (t) => {
    libTab = t;
    libAside.dataset.tab = t;
    document.querySelectorAll("#libTabs [data-tab]").forEach((b) => { const on = b.dataset.tab === t; b.classList.toggle("on", on); b.setAttribute("aria-selected", on); });
    saveUiState(pid, { libTab: t });
    renderDecorLib();
  };
  document.querySelectorAll("#libTabs [data-tab]").forEach((b) => (b.onclick = () => setLibTab(b.dataset.tab)));
  // 고른 꾸미기 가구: 위치·회전·크기 조절·주변 간격만 (가격·출처 같은 제품 정보는 없다)
  const LONG = new Set(["decor:wall", "decor:partition"]); // 길이만 바꾸는 것
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
    const l = finishLabel(x);
    if (!l) return x.sku; // LGE.COM에 색 정보가 없는 모델(TV 등): 색 대신 모델명만
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
  const stepsHtml = (steps) => steps.map((st) => `<li class="step ${st.picked ? "done" : ""}"><span class="step-l">${esc(st.label)}</span>
      <div class="chips">${st.values.map((v) => `<button class="chip ${st.picked === v.label ? "on" : ""}" data-step="${esc(st.key)}" data-val="${esc(v.label)}" aria-pressed="${st.picked === v.label}">${esc(v.label)} <i>${v.count}</i></button>`).join("")}</div></li>`).join("");
  const renderSteps = (steps) => {
    // 설치 유형(빌트인·일반)은 늘 보이게, 나머지 옵션은 상세 필터 안에
    document.getElementById("mainSteps").innerHTML = stepsHtml(steps.filter((st) => st.key === "install"));
    document.getElementById("steps").innerHTML = stepsHtml(steps.filter((st) => st.key !== "install"));
    document.querySelectorAll("#mainSteps [data-step], #steps [data-step]").forEach((b) => (b.onclick = () => {
      if (sel[b.dataset.step] === b.dataset.val) delete sel[b.dataset.step]; else sel[b.dataset.step] = b.dataset.val;
      saveUiState(pid, { sel });
      renderLib();
    }));
  };
  // 이 집에 들어가는 제품: 지금 목록 앞쪽 후보를 서버가 벽을 따라 놓아 보고(find_spot) 들어가는 것만 3개
  let recSkus = new Set(), suggItems = [], suggKey = "", suggTimer = 0, suggPool = [], suggReady = false;
  const isRec = (f) => f.variants.some((v) => recSkus.has(v.sku));
  const BUDGET_STEP = 50000; // 가격 손잡이 간격 5만 원
  const SUGG_POOL = 30, SUGG_WAIT_MS = 1200; // 연달아 놓는 동안에는 기다렸다가 한 번만
  const renderSugg = () => {
    const box = document.getElementById("sugg");
    box.hidden = !suggReady;
    // 들어가는 제품이 없으면 "없어요"로 끝내지 않고 다음에 볼 종류를 바로 고르게 한다
    const nextCats = catsFor(use || "").filter((c) => c !== cat).slice(0, 3);
    box.innerHTML = suggItems.length ? `<div class="sugg-head"><h3>이 집에 들어가는 제품</h3><button class="ghost small" id="askBot">하우니에게 묻기</button></div>
      <ul>${suggItems.map((it) => {
        const f = familyOf(it.sku), v = f?.variants.find((x) => x.sku === it.sku) || {};
        return `<li><div class="sugg-card"><button class="sugg-main" data-sugg="${esc(it.sku)}" title="${esc(f?.name || it.sku)} 상세 보기">
          <span class="ph" style="background-color:${esc(v.hex || "#fff")}">${v.thumb ? `<img src="${esc(v.thumb)}" alt="" loading="lazy">` : ""}</span>
          <span class="nm">${esc(f?.name || it.sku)}</span>${typeof v.price_krw === "number" ? `<span class="vv">${v.price_krw.toLocaleString("ko-KR")}원</span>` : ""}</button>
          <button class="small sugg-place" data-splace="${esc(it.sku)}" aria-label="${esc(f?.name || it.sku)} 공간에 배치하기">배치</button></div></li>`;
      }).join("")}</ul>`
      : `<div class="sugg-head"><h3>현재 공간에 어울리는 제품을 찾아보세요</h3></div>
        <p class="sugg-empty">${cat ? `지금 고른 ${esc(CATEGORY[cat] || cat)} 중에는 이 집 벽에 들어가는 제품이 없어요.` : "이 집 벽을 따라 놓아 볼 제품을 골라 주세요."}</p>
        <div class="chips">${nextCats.map((c) => `<button class="chip" data-scat="${esc(c)}">${esc(CATEGORY[c] || c)} 추천 보기</button>`).join("")}
          <button class="chip" id="askBot">하우니에게 묻기</button></div>`;
    box.querySelectorAll("[data-sugg]").forEach((b) => (b.onclick = () => openDetail(b.dataset.sugg)));
    box.querySelectorAll("[data-splace]").forEach((b) => (b.onclick = () => { openLib(false); autoPlace(b.dataset.splace); }));
    box.querySelectorAll("[data-scat]").forEach((b) => (b.onclick = () => { if (use == null) use = ""; setScope({ cat: b.dataset.scat }); }));
    box.querySelector("#askBot")?.addEventListener("click", () => openBot(true));
  };
  const scheduleSuggest = () => {
    if (!project) return;
    // 추천은 LG 가전 자리만 본다. 가구·가벽을 놓거나 옮길 때마다 다시 계산하면 서버가 몇 초씩 막혀 버벅인다
    const key = JSON.stringify([suggPool, lgOnly(project.scene_state.placements).map((x) => x.placement_id), project.scene_state.hidden_objects]);
    if (key === suggKey) return;
    suggKey = key;
    clearTimeout(suggTimer);
    suggTimer = setTimeout(async () => {
      let got = [];
      try { got = suggPool.length ? (await post(`/api/projects/${pid}/suggest`, { skus: suggPool, limit: 3 })).items : []; }
      catch { got = []; } // 옛 API 서버면 줄을 숨긴다
      if (suggKey !== key) return;
      suggItems = got; suggReady = true;
      const next = new Set(got.map((x) => x.sku)), changed = next.size !== recSkus.size || [...next].some((x) => !recSkus.has(x));
      recSkus = next;
      renderSugg();
      if (changed) renderLib();
    }, SUGG_WAIT_MS);
  };
  const filterCount = () => Object.keys(sel).length + (budget ? 1 : 0) + (document.getElementById("fW").value ? 1 : 0) + (document.getElementById("fH").value ? 1 : 0);
  document.getElementById("resetFilter").onclick = () => {
    sel = {}; document.getElementById("fW").value = ""; document.getElementById("fH").value = ""; document.getElementById("q").value = ""; budget = null;
    saveUiState(pid, { sel });
    renderLib();
  };
  // ---- 가격 범위: 지금 보이는 종류(예: 냉장고)의 최저가~최고가 사이에서 두 손잡이로 예산을 맞춘다 ----
  let budget = null, budgetScope = ""; // budget: {lo, hi} (원), 범위 전체면 null
  const pLo = document.getElementById("pLo"), pHi = document.getElementById("pHi"), budgetOut = document.getElementById("budgetOut");
  const won = (v) => v >= 1e8 ? `${+(v / 1e8).toFixed(1)}억` : `${Math.round(v / 1e4).toLocaleString("ko-KR")}만`;
  const pricesOf = (f) => f.variants.filter((v) => typeof v.price_krw === "number" && (f.demo_only || sellable(v))).map((v) => v.price_krw);
  const setupBudget = (list) => {
    const ps = list.flatMap(pricesOf), box = document.getElementById("budget");
    box.hidden = ps.length < 2;
    if (box.hidden) { budget = null; return; }
    const lo = Math.floor(Math.min(...ps) / BUDGET_STEP) * BUDGET_STEP, hi = Math.ceil(Math.max(...ps) / BUDGET_STEP) * BUDGET_STEP;
    const key = `${cat}|${use}`;
    if (key !== budgetScope) { budgetScope = key; budget = null; } // 종류가 바뀌면 그 종류의 전체 범위로
    for (const r of [pLo, pHi]) Object.assign(r, { min: lo, max: hi, step: BUDGET_STEP });
    pLo.value = budget ? Math.max(lo, budget.lo) : lo; pHi.value = budget ? Math.min(hi, budget.hi) : hi;
    budgetOut.textContent = `${won(+pLo.value)} ~ ${won(+pHi.value)}원`;
  };
  const inBudget = (f) => !budget || pricesOf(f).some((v) => v >= budget.lo && v <= budget.hi);
  const onBudget = (e) => {
    let lo = +pLo.value, hi = +pHi.value;
    if (lo > hi) { if (e.target === pLo) lo = hi; else hi = lo; pLo.value = lo; pHi.value = hi; }
    budget = lo <= +pLo.min && hi >= +pHi.max ? null : { lo, hi };
    budgetOut.textContent = `${won(lo)} ~ ${won(hi)}원`;
    clearTimeout(budgetTimer); budgetTimer = setTimeout(renderLib, 120); // 끄는 동안은 숫자만, 손을 멈추면 목록
  };
  let budgetTimer = 0;
  pLo.oninput = onBudget; pHi.oninput = onBudget;
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
    const pre = scope.filter((f) => f.variants.some((v) => left.has(v.sku)) && (!q || (CATEGORY[f.category] || "").includes(q) || f.name.toLowerCase().includes(q)
      || f.variants.some((v) => v.sku.toLowerCase().includes(q) || (v.color || "").toLowerCase().includes(q)))
      && inRange(f.product_dims_mm?.w, fW) && inRange(f.product_dims_mm?.h, fH));
    setupBudget(pre);
    const items = pre.filter(inBudget);
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
      const dots = colorDots(f), many = dots.length > 1;
      return `<li class="prod ${f.variants.some((x) => x.sku === armed) ? "armed" : ""} ${sized ? "" : "nosize"}" draggable="${sized ? "true" : "false"}" data-sku="${esc(sku)}">
        <i class="dot tile thumb" style="--tint:${esc(v.hex || "#fff")}${v.thumb ? "" : `;background:${esc(v.hex || "#fff")}`}">${v.thumb ? `<img src="${esc(v.thumb)}" alt="${esc(f.name)} ${esc(finishLabel(v))}" loading="lazy" decoding="async" draggable="false">` : ""}<span>${esc(CATEGORY[f.category] || f.category)}</span></i>
        <div class="body"><div class="name">${esc(f.name)}</div>
          ${sized ? "" : `<div class="cat">치수 정보 없음</div>`}
          ${typeof v.price_krw === "number" ? `<div class="price">${v.price_krw.toLocaleString("ko-KR")}원</div>` : ""}
          ${v.color ? `<div class="color-row"><span class="vk">색상</span>${many ? `<span class="variants" role="radiogroup" aria-label="색상 고르기">${dots.map((x) => { const on = x.color === v.color && x.hex === v.hex; return `<button class="vsw ${on ? "on" : ""}" data-fam="${esc(f.family_id)}" data-pick="${esc(on ? sku : x.sku)}" title="${esc(finishLabel(x))}" aria-label="${esc(finishLabel(x))}" role="radio" aria-checked="${on}"><i style="background:${esc(x.hex || "#fff")}"></i></button>`; }).join("")}</span>` : ""}</div>` : ""}
          ${sized && !f.demo_only ? `<button class="primary small place-btn" data-place="${esc(sku)}">공간에 배치하기</button>` : ""}
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
    document.querySelectorAll("#lib [data-place]").forEach((b) => (b.onclick = (e) => { e.stopPropagation(); openLib(false); autoPlace(b.dataset.place); }));
    document.querySelectorAll("#lib [data-sku]").forEach((li) => {
      li.onclick = () => {
        if (armed && armed === li.dataset.sku) { armed = null; ghost(null); setHint(); renderLib(); return; }
        openDetail(li.dataset.sku);
      };
      li.ondragstart = (e) => e.dataTransfer.setData("text/sku", li.dataset.sku);
    });
  };
  // ---- 제품 상세 창: 사진·모델명·크기·색상 ----
  // 카탈로그 spec_notes(근거)·필요 공간 같은 숫자는 판정에만 쓰고 화면에는 내지 않는다
  const pdModal = document.getElementById("pdModal");
  const closeDetail = () => { pdModal.hidden = true; pdModal.innerHTML = ""; };
  // 지예: 들어가는지는 넣고 나서 3D에서 판단한다 (초록/빨강). 상세 창에는 판정 줄을 두지 않는다
  const openDetail = (sku) => {
    const p = prodOf(sku), f = familyOf(sku);
    if (!p || !f) return;
    pick[f.family_id] = sku;
    const v = f.variants.find((x) => x.sku === sku) || {};
    const d = p.product_dims_mm || {}, sized = d.w && d.h && d.d;
    // 지예: 상세 창이 조잡하다 → 크기·색만 짧게 (설치 방식·옵션·모델명 표는 뺀다, 모델명은 제목 아래에)
    const rows = [
      ["크기", sized ? `${mm(d.w)} × ${mm(d.h)} × ${mm(d.d)} mm <span class="muted">(폭 × 높이 × 깊이)</span>` : ""],
      ["색상", esc(finishLabel(v))],
    ].filter(([, val]) => val);
    pdModal.innerHTML = `
      <div class="pd-top">
        <div class="pd-photo${v.thumb ? " has-photo" : ""}" style="background-color:${esc(v.hex || "#fff")}${v.thumb ? `;background-image:url('${esc(v.thumb)}')` : ""}" role="img" aria-label="${esc(f.name)} ${esc(finishLabel(v))}"><span>${esc(CATEGORY[p.category] || p.category)}</span></div>
        <div class="pd-title">
          <h2>${esc(f.name)}</h2>
          <p class="muted">${esc(CATEGORY[p.category] || p.category)} · ${esc(sku)}</p>
          ${f.demo_only ? `<span class="badge demo">가상 데이터 · 실제 제품 아님</span>` : ""}
          <div class="pd-variants" role="radiogroup" aria-label="색상 옵션">${f.variants.filter((x) => f.demo_only || sellable(x) || x.sku === sku).map((x) => `<button class="swatch ${x.sku === sku ? "on" : ""}" data-pd-variant="${esc(x.sku)}" role="radio" aria-checked="${x.sku === sku}">${x.color ? `<i style="background:${esc(x.hex || "#fff")}"></i>` : ""}${esc(optLabel(f, x))}</button>`).join("")}</div>
        </div>
        <button class="ghost small pd-close" id="pdClose" aria-label="상세 창 닫기">닫기</button>
      </div>
      <table class="pd-spec"><tbody>${rows.map(([k, val]) => `<tr><th>${k}</th><td>${val}</td></tr>`).join("")}</tbody></table>
      <div class="pd-actions">
        <button class="primary" id="pdPlace" ${sized ? "" : "disabled"}>${sized ? "넣어 보기" : "치수가 없어 놓을 수 없어요"}</button>
        ${p.source_url ? `<a class="btn ghost" href="${esc(p.source_url)}" target="_blank" rel="noopener">LGE.COM에서 보기</a>` : ""}
      </div>`;
    pdModal.hidden = false;
    pdModal.querySelectorAll("[data-pd-variant]").forEach((b) => (b.onclick = () => { openDetail(b.dataset.pdVariant); renderLib(); }));
    document.getElementById("pdClose").onclick = closeDetail;
    const place = document.getElementById("pdPlace");
    if (sized) place.onclick = () => {
      closeDetail();
      if (walking) setWalking(false);
      arm(sku);
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
  // ---- 손에 든 물건이 마우스를 따라온다 (심즈 건축 모드처럼) ----
  // 자리는 서버를 기다리지 않고 바로 옮기고, 들어가는지 색만 서버 판정이 오면 바꾼다. 누르면 그 자리에 놓인다
  let armedYaw = Math.PI / 2, armedVerdict = "unknown", lastHover = null;
  const armedSize = (sku) => {
    const d = isDecor(sku) ? decorOf(sku)?.size_mm : prodOf(sku)?.product_dims_mm;
    return d?.w && d?.h && d?.d ? [d.w / 1000, d.h / 1000, d.d / 1000] : null;
  };
  const showFollow = (center_xz, yaw_rad, size_m, verdict, sku) => {
    const res = { pose: { center_xz, yaw_rad }, size_m, verdict };
    const g = document.getElementById("ghost");
    if (g && pv) g.innerHTML = placedSvg({ center_xz, yaw_rad, size_m, verdict }, pv.sw, false, true);
    viewer.setGhost({ ...res, sku, hex: prodOf(sku)?.cmf_options[0]?.hex_approx });
  };
  const follow = (p) => {
    lastHover = p;
    if (armedRouter) { viewer.routerFollow(p); return; }
    if (mode !== "move" || wallPicking) return;
    if (wallDraw) { // 가벽: 시작점 전에는 기둥 하나, 시작점을 찍은 뒤에는 시작점부터 마우스까지 벽
      const a = wallDraw.start;
      if (!a) { showFollow(p, Math.PI / 2, [WALL_T, WALL_H, WALL_T], "fit", "decor:wall"); return; }
      const len = Math.hypot(p[0] - a[0], p[1] - a[1]), ang = Math.atan2(p[1] - a[1], p[0] - a[0]);
      showFollow([(a[0] + p[0]) / 2, (a[1] + p[1]) / 2], ang + Math.PI / 2, [Math.max(len, WALL_T), WALL_H, WALL_T], len < WALL_MIN ? "no_fit" : "fit", "decor:wall");
      return;
    }
    if (!armed) return;
    const size = armedSize(armed);
    if (size) showFollow(p, armedYaw, size, armedVerdict, armed);
    preview({ sku: armed, center_xz: p, yaw_rad: armedYaw }, (r) => { // 판정 색만 (자리는 마우스 그대로)
      if (!armed || !hovering) return;
      armedVerdict = r.verdict;
      if (lastHover) showFollow(lastHover, armedYaw, size || r.size_m, armedVerdict, armed);
    });
  };
  const arm = (sku) => {
    if (wallPicking) setWallPick(false);
    if (wallDraw) setWallDraw(false);
    armed = sku; armedYaw = Math.PI / 2; armedVerdict = "unknown"; mode = "move";
    selPl = null; selObj = null;
    syncMode(); setHint(); renderLib(); renderDecorLib(); renderInspector();
    if (lastHover && hovering) follow(lastHover);
  };
  let busy = false, queued = null, lastPreview = null;
  const preview = async (args, onRes) => {
    if (busy) { queued = [args, onRes]; return; }
    busy = true;
    try {
      lastPreview = await post(`/api/projects/${pid}/pose-check`, args);
      if (onRes) onRes(lastPreview);
      else if (lastPreview.size_m && ((armed && hovering) || drag)) ghost(lastPreview);
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
    if (x && !x.zone_id) remember({ kind: "pose", id: plid, body: { center_xz: [...x.center_xz], yaw_rad: x.yaw_rad, ...(isDecor(x.sku) ? sizeArgs(x) : { sku: x.sku }), snap: false } });
  };
  const rememberRemoval = (plid) => {
    const x = project.scene_state.placements.find((q) => q.placement_id === plid);
    if (x && !x.zone_id) remember({ kind: "add", id: plid, body: { sku: x.sku, center_xz: [...x.center_xz], yaw_rad: x.yaw_rad, snap: false, ...sizeArgs(x), ...(x.color ? { color: x.color } : {}) } });
  };
  // 단계 하나를 되돌리고, 그 반대 단계를 돌려준다 (되돌리기 ↔ 다시 실행)
  const applyStep = async (step) => {
    const id = liveId(step.id);
    if (step.kind === "remove") {
      const x = project.scene_state.placements.find((q) => q.placement_id === id);
      await api(`/api/projects/${pid}/placements/${id}`, { method: "DELETE" });
      if (selPl === id) selPl = null;
      return x && { kind: "add", id, body: { sku: x.sku, center_xz: [...x.center_xz], yaw_rad: x.yaw_rad, snap: false, ...sizeArgs(x), ...(x.color ? { color: x.color } : {}) } };
    }
    if (step.kind === "pose") {
      const x = project.scene_state.placements.find((q) => q.placement_id === id);
      await api(`/api/projects/${pid}/placements/${id}`, { method: "PATCH", body: JSON.stringify(step.body) });
      return x && { kind: "pose", id, body: { center_xz: [...x.center_xz], yaw_rad: x.yaw_rad, ...(isDecor(x.sku) ? sizeArgs(x) : { sku: x.sku }), snap: false } };
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
    if (step.kind === "wallHide" || step.kind === "wallShow") {
      const on = step.kind === "wallHide";
      await put(`/api/projects/${pid}/walls/${step.id}/hidden`, { hidden: on });
      return { kind: on ? "wallShow" : "wallHide", id: step.id };
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
    const r = await post(`/api/projects/${pid}/placements`, { sku, center_xz: p, yaw_rad: armed === sku ? armedYaw : Math.PI / 2 });
    remember({ kind: "remove", id: r.placement.placement_id });
    selPl = r.placement.placement_id; selObj = null; armed = null; ghost(null); setTab("sel");
    toast(`${nameOf(sku)}: ${LABEL[r.placement.verdict]}`);
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
      viewer.routerFollow(null); // 서버가 높이까지 정해 돌려주면 그 자리로 (실패하면 원래 자리)
      guard(async () => { project = await put(`/api/projects/${pid}/router`, { center_xz: p, band }); if (sim === "wifi") await wifiCtl(); })();
      return true;
    }
    if (wallDraw) { wallPoint(p); return true; }
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
    if (armed && mode === "move") { hovering = true; preview({ sku: armed, center_xz: p, yaw_rad: Math.PI / 2 }); return; }
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
  svg.onpointerleave = () => { hovering = false; if (armed) ghost(null); };
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
    if (k === "Escape") { if (armedRouter) { armedRouter = false; viewer.routerFollow(null); wifiCtl(); } viewer.cancelHold(); armed = null; ghost(null); if (wallPicking) setWallPick(false); if (wallDraw) setWallDraw(false); setHint(); renderLib(); return; }
    const in3d = studio.dataset.view !== "plan";
    // 카메라: WASD 이동, Q/E 돌기 (3D가 보일 때)
    const PAN = 0.3;
    if (in3d && !e.ctrlKey && !e.metaKey) {
      const cam = { w: [0, PAN], s: [0, -PAN], a: [-PAN, 0], d: [PAN, 0] }[k];
      if (cam) { viewer.panCamera(...cam); e.preventDefault(); return; }
      if (k === "q" || k === "e") { viewer.orbitCamera(k === "q" ? -15 : 15); e.preventDefault(); return; }
    }
    if (armed && (k === "r" || k === "." || k === ",")) { // 들고 있는 물건 돌리기
      armedYaw += (k === "," || e.shiftKey ? -1 : 1) * (e.altKey ? ROT_FINE : ROT_STEP);
      if (lastHover && hovering) follow(lastHover);
      e.preventDefault(); return;
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
  const autoPlace = guard(async (sku, size_m = null) => {
    const r = await post(`/api/projects/${pid}/auto-place`, { sku, ...(size_m ? { size_m } : {}) });
    remember({ kind: "remove", id: r.placement.placement_id });
    selPl = r.placement.placement_id; selObj = null; armed = null; ghost(null);
    toast(`${nameOf(sku)}${eul(nameOf(sku))} 공간에 놓았어요. 위에 뜬 메뉴로 옮기거나 돌릴 수 있어요`);
    setHint(); renderLib();
    await refresh(true);
    viewer.lookAt(r.placement.center_xz); // 놓인 자리로 시점을 옮겨서 어디 놓였는지 바로 보이게
  });
  const copyPlacement = guard(async (plid) => {
    const r = await post(`/api/projects/${pid}/placements/${plid}/copy`, {});
    remember({ kind: "remove", id: r.placement.placement_id });
    selPl = r.placement.placement_id; selObj = null;
    toast(`${nameOf(r.placement.sku)}${eul(nameOf(r.placement.sku))} 하나 더 놓았어요`);
    await refresh(true);
  });
  // 크기 조절 (꾸미기 가구만): 슬라이더를 놓으면 저장
  const resizePlacement = guard(async (plid, size_m) => {
    rememberPlacement(plid);
    await api(`/api/projects/${pid}/placements/${plid}`, { method: "PATCH", body: JSON.stringify({ size_m, snap: false }) });
    await refresh(true);
  });
  const setWallPick = (on) => {
    wallPicking = on;
    viewer.setWallPick(on);
    if (on) { selPl = null; selObj = null; armed = null; ghost(null); renderInspector(); setHint("철거할 벽을 3D에서 누르세요 · Esc 취소"); }
    else setHint();
    renderDecorLib();
  };
  removeWall = guard(async (wid) => {
    await put(`/api/projects/${pid}/walls/${wid}/hidden`, { hidden: true });
    remember({ kind: "wallShow", id: wid }); // 성공한 뒤에만 되돌리기에 쌓는다
    setWallPick(false);
    // 구조벽인지는 스캔으로 알 수 없다: 화면에서만 바꿔 보는 것이고, 실제 철거는 현장 확인이 필요하다
    toast("벽을 철거해 봤어요 (가상 체험). 실제 철거 가능 여부는 현장에서 확인해요");
    await refresh(true);
  });
  // 벽 추가: 바닥에서 시작점과 끝점을 차례로 누르면 그 사이에 가벽을 세운다
  const WALL_H = 2.4, WALL_T = 0.1, WALL_MIN = 0.3;
  const setWallDraw = (on) => {
    wallDraw = on ? {} : null;
    if (on) { selPl = null; selObj = null; armed = null; ghost(null); renderInspector(); setHint("벽을 세울 시작점을 바닥에서 누르세요 · Esc 취소"); }
    else setHint();
    renderDecorLib();
  };
  wallPoint = guard(async (p) => {
    if (!wallDraw.start) { wallDraw.start = p; setHint("끝점을 누르세요 · Esc 취소"); return; }
    const [a, b] = [wallDraw.start, p], len = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (len < WALL_MIN) { toast("벽이 너무 짧아요. 30 cm 넘게 떨어진 곳을 눌러 주세요", true); return; }
    const ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
    setWallDraw(false);
    const r = await post(`/api/projects/${pid}/placements`, {
      sku: "decor:wall", center_xz: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], yaw_rad: ang + Math.PI / 2, snap: false, size_m: [len, WALL_H, WALL_T] });
    remember({ kind: "remove", id: r.placement.placement_id });
    selPl = r.placement.placement_id; selObj = null;
    toast(`벽을 세웠어요 (길이 ${mm(len * 1000)} mm). 오른쪽에서 길이를 바꿀 수 있어요`);
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
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5h.01"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
    size: '<path d="M4 9V4h5M20 15v5h-5M4 4l7 7M20 20l-7-7"/>',
  };
  // 조작 메뉴는 고른 제품 바로 위에 따라붙는다 (큰 화면). 앱 배치는 아래 고정
  let actRaf = 0;
  // 도면 위에 지금 3D에서 보고 있는 방향을 부채꼴로
  let camSeen = "";
  const trackCam = () => {
    const m = document.getElementById("camMark"), d = document.getElementById("camDot");
    if (!m || !viewer || studio.dataset.view !== "3d") return;
    const c = viewer.camera(), key = `${c.pos}|${c.target}`;
    if (key === camSeen && m.getAttribute("points") !== "0,0 0,0 0,0") return;
    camSeen = key;
    // 궤도 시점은 카메라가 방 밖에 있으니, 보는 곳 바로 앞에 꼭짓점을 두고 보는 쪽으로 부채꼴을 편다
    const [cx, , cz] = c.pos, [tx, , tz] = c.target;
    const a = Math.atan2(tz - cz, tx - cx), L = 1.6, half = 0.5;
    const px = tx - Math.cos(a) * L * 0.7, pz = tz - Math.sin(a) * L * 0.7;
    m.setAttribute("points", `${px},${pz} ${px + L * Math.cos(a - half)},${pz + L * Math.sin(a - half)} ${px + L * Math.cos(a + half)},${pz + L * Math.sin(a + half)}`);
    d.setAttribute("cx", px); d.setAttribute("cy", pz);
  };
  const trackAct = () => {
    actRaf = requestAnimationFrame(trackAct);
    trackCam();
    if (actBar.hidden || armed || studio.classList.contains("app") || studio.dataset.view !== "3d") { actBar.classList.remove("near"); return; }
    const x = selPl && project?.scene_state.placements.find((q) => q.placement_id === selPl);
    const o = !x && selObj && room?.objects.find((q) => q.object_id === selObj);
    const held = viewer.held?.();
    const xz = held ? held.xz : x ? x.center_xz : o ? [o.position[0], o.position[2]] : null;
    if (!xz) { actBar.classList.remove("near"); return; }
    const top = x ? (x.size_m?.[1] ?? 1) : o ? o.bbox_m.h : 1;
    const [sx, sy] = viewer.toScreen(xz, top), r = canvasEl.getBoundingClientRect();
    const w = actBar.offsetWidth, h = actBar.offsetHeight;
    const left = Math.min(Math.max(sx - r.left, w / 2 + 8), r.width - w / 2 - 8);
    const topPx = Math.min(Math.max(sy - r.top - h - 14, 8), r.height - h - 8);
    actBar.classList.add("near");
    actBar.style.left = `${left}px`; actBar.style.top = `${topPx}px`;
  };
  actRaf = requestAnimationFrame(trackAct);
  cleanup.push(() => cancelAnimationFrame(actRaf));
  const actBtn = (id, icon, label, cls = "") => `<button class="act ${cls}" id="${id}"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true">${ICON[icon]}</svg><span>${label}</span></button>`;
  // 크기 조절: 3D 메뉴가 슬라이더로 바뀐다. 가벽·파티션은 길이(mm), 나머지는 기본 크기의 %
  let sizing = null;
  const TALL = new Set(["decor:shelf", "decor:storage", "decor:plant", "decor:lamp"]); // 키도 같이 바뀌는 것
  const sizeBar = (x) => {
    const d = decorOf(x.sku), long = LONG.has(x.sku), b = d?.size_mm || { w: 1000, h: 1000, d: 1000 };
    const val = long ? Math.round(x.size_m[0] * 1000) : Math.round((x.size_m[0] * 1000 / b.w) * 100);
    const show = (v) => (long ? `${mm(v)} mm` : `${v}%`);
    actBar.innerHTML = `<label class="act-size">${long ? "길이" : "크기"}<input type="range" id="szRange" ${long ? 'min="300" max="6000" step="50"' : 'min="50" max="200" step="5"'} value="${val}" aria-label="${long ? "길이 (mm)" : "크기 (%)"}"><output id="szOut">${show(val)}</output></label><button class="ghost small" id="szDone">완료</button>`;
    const range = document.getElementById("szRange"), out = document.getElementById("szOut");
    const sizeFor = (v) => (long ? [v / 1000, x.size_m[1], x.size_m[2]] : [(b.w * v) / 1e5, (TALL.has(x.sku) ? b.h * v : b.h * 100) / 1e5, (b.d * v) / 1e5]);
    range.oninput = () => { out.textContent = show(+range.value); };
    range.onchange = () => resizePlacement(x.placement_id, sizeFor(+range.value));
    document.getElementById("szDone").onclick = () => { sizing = null; renderAct(); };
  };
  renderAct = () => {
    if (!project) return;
    const x = selPl && project?.scene_state.placements.find((q) => q.placement_id === selPl);
    fitBadge.hidden = !x || walking;
    if (x) {
      // 안 들어가면 왜 안 되는지와 고치는 방법까지 한 줄로 (벽·가구·다른 제품과 겹칠 때 등)
      const r = x.verdict === "no_fit" ? badReasons(x)[0] : null;
      fitBadge.className = `fit-badge v-${shownVerdict(x.verdict)}`;
      fitBadge.innerHTML = `<b>${esc(BADGE[x.verdict] || BADGE.unknown)}</b>${r ? `<span>${esc(r.label)} · ${esc(FIX[r.code] || "다른 자리로 옮겨 보세요")}</span>` : ""}`;
    }
    if (walking) { actBar.hidden = true; return; }
    if (armed) {
      actBar.hidden = false;
      actBar.innerHTML = `<span class="act-tag">${esc(nameOf(armed))}</span>
        <button class="primary small" id="actAuto">알맞은 자리에 놓기</button><button class="ghost small" id="actCancel">취소</button>`;
      document.getElementById("actAuto").onclick = () => autoPlace(armed);
      document.getElementById("actCancel").onclick = () => { armed = null; ghost(null); setHint(); renderLib(); };
      return;
    }
    const target = x ? { type: "placement", id: x.placement_id } : selObj ? { type: "object", id: selObj } : null;
    actBar.hidden = !target;
    if (!target) { sizing = null; return; }
    if (x && isDecor(x.sku) && sizing === x.placement_id) { sizeBar(x); return; }
    const deco = x && isDecor(x.sku);
    actBar.innerHTML = actBtn("actMove", "move", "이동") + actBtn("actRot", "rotate", "회전")
      + (deco ? actBtn("actSize", "size", "크기 조절") : x ? actBtn("actAlign", "align", "벽에 붙이기") : "")
      + (x ? actBtn("actCopy", "copy", "복사") : "") + (x && !deco ? actBtn("actInfo", "info", "상세") : "") + actBtn("actDel", "del", "삭제", "danger");
    document.getElementById("actInfo")?.addEventListener("click", () => openDetail(x.sku));
    document.getElementById("actCopy")?.addEventListener("click", () => copyPlacement(x.placement_id));
    document.getElementById("actSize")?.addEventListener("click", () => { sizing = x.placement_id; renderAct(); document.getElementById("szRange")?.focus(); });
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
    const sel0 = selPl && project.scene_state.placements.find((q) => q.placement_id === selPl);
    // 지예: 가구·가벽을 골라도 오른쪽은 그대로. 조절은 3D 위 메뉴에서만 (이동·회전·크기·복사·삭제)
    const x = sel0 && !isDecor(sel0.sku) ? sel0 : null;
    document.getElementById("plBox").hidden = !!(x || selObj);
    document.getElementById("chkBox").hidden = !!(x || selObj);
    studio.classList.toggle("has-sel", !!(x || selObj));
    if (sel0 && !x) { box.innerHTML = ""; return; }
    if (x) {
      const p = prodOf(x.sku) || { name: x.sku, cmf_options: [] };
      const fv = familyOf(x.sku)?.variants.find((q) => q.sku === x.sku);
      box.innerHTML = `
        <div class="insp-photo" style="background-color:${esc(x.hex || fv?.hex || "#fff")}">${fv?.thumb ? `<img src="${esc(fv.thumb)}" alt="${esc(p.name)}">` : ""}
          <button class="ghost small insp-close" id="inspClose" aria-label="선택 풀기">닫기</button></div>
        <h2 class="insp-name">${esc(p.name)}</h2>
        ${p.demo_only ? `<p class="insp-meta"><span class="badge demo">가상 데이터 · 실제 제품 아님</span></p>` : ""}
        ${typeof fv?.price_krw === "number" ? `<p class="insp-price">${fv.price_krw.toLocaleString("ko-KR")}원 <span class="muted">LGE.COM 판매가</span></p>` : ""}
        ${fitCardHtml(x)}
        <p class="insp-links"><button class="linklike" id="inspDetail">제품 상세</button>${p.source_url && !p.demo_only ? `<a href="${esc(p.source_url)}" target="_blank" rel="noopener">LGE.COM에서 보기 ↗</a>` : ""}</p>`;
      box.querySelector("#inspDetail").onclick = () => openDetail(x.sku);
      box.querySelector("#inspClose").onclick = () => { selPl = null; draw(); renderInspector(); renderPlacements(); };
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
    const pls = lgOnly(project.scene_state.placements); // 가구·소품은 꾸미기용이라 신청에 넣지 않는다
    const bad = pls.filter((x) => x.verdict === "no_fit").length;
    if (pls.length && !bad && !flow.order) setTimeout(() => setFlow({ order: true }), 0);
    orderSheet.innerHTML = `
      <div class="order-head"><h2>구매 및 설치 신청</h2><button class="ghost small" id="orderClose">닫기</button></div>
      ${pls.length ? `<p class="order-sum">놓은 제품 <b>${pls.length}개</b>${bad ? ` · <b class="bad">${bad}개는 지금 자리에 설치하기 어려워요</b>` : " · 모두 설치할 수 있는 자리예요"}</p>
      <p class="hint-sm">${INSTALL_NOTE}</p>
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

  // 놓은 제품 하나를 골라 3D 시점을 그 자리로 (목록·체크리스트·도면에서 누를 때)
  const focusPlacement = (id) => {
    const x = project.scene_state.placements.find((q) => q.placement_id === id);
    if (!x) return;
    selPl = id; selObj = null; setTab("sel"); draw(); renderInspector(); renderPlacements();
    viewer.lookAt(x.center_xz);
  };
  // 설치 체크: 안 되는 것만, 왜 안 되는지와 어떻게 하면 되는지를 같이. 누르면 그 제품으로 간다
  const FIX = {
    hits_wall: "벽에서 조금 떼거나 '자동 정렬'을 눌러 보세요", outside_room: "방 안쪽으로 옮겨 주세요",
    overlaps_object: "가구를 옮기거나 '가구 치우기'로 치워 보세요", overlaps_placement: "다른 제품과 겹쳐요. 한쪽을 옮겨 주세요",
    front_blocked: "문을 열 앞 공간이 막혀요. 앞을 비우거나 돌려 보세요", passage_narrow: "지나갈 길이 좁아져요. 벽 쪽으로 붙여 보세요",
    door_blocked: "방문이 열릴 자리를 막아요. 옆으로 옮겨 주세요", entry_narrow: "방문보다 제품이 커서 들여오기 어려워요",
    covers_window: "창을 가려요. 창이 없는 벽으로 옮겨 보세요", ceiling_low: "천장보다 높아요. 더 낮은 제품을 골라 보세요",
    clearance_blocked: "옆·뒤 여유가 모자라요. 조금 떼어 주세요", tight: "딱 맞아서 여유가 없어요. 조금 옮겨 보세요",
    dims_unknown: "치수 정보가 없어서 판정을 못 해요",
  };
  const badReasons = (x) => (x.reasons || []).filter((r) => r.verdict === "no_fit");
  const renderCheck = (pls) => {
    const box = document.getElementById("chkBox");
    if (!pls.length) { box.innerHTML = ""; return; }
    const bad = pls.filter((x) => x.verdict === "no_fit");
    box.innerHTML = !bad.length
      ? `<p class="chk-ok"><span class="mk" aria-hidden="true">✓</span><span><b>모두 설치할 수 있는 자리예요</b><small>전원·배관은 설치 기사가 방문해서 확인해요</small></span></p>`
      : `<p class="chk-head"><span class="mk bad" aria-hidden="true">✕</span><b>설치하기 어려운 제품 ${bad.length}개</b></p>
        <ul class="chk-list">${bad.map((x) => { const r = badReasons(x)[0]; return `<li><button data-chk="${esc(x.placement_id)}">
          <b>${esc(prodOf(x.sku)?.name || x.sku)}</b><span>${esc(r?.label || "이 자리에는 안 들어가요")}</span>
          <em>${esc(FIX[r?.code] || "다른 자리로 옮겨 보세요")}</em><i aria-hidden="true">찾아가기 ›</i></button></li>`; }).join("")}</ul>`;
    box.querySelectorAll("[data-chk]").forEach((b) => (b.onclick = () => focusPlacement(b.dataset.chk)));
  };
  const renderPlacements = () => {
    renderProgress();
    const every = project.scene_state.placements, pls = lgOnly(every);
    document.getElementById("plCount").textContent = every.length;
    document.getElementById("orderMini").hidden = !pls.length;
    renderCheck(pls);
    // 신청 버튼 위에 합계를 같이: 놓은 제품이 있어야 버튼이 강조된다
    const price = (x) => familyOf(x.sku)?.variants.find((q) => q.sku === x.sku)?.price_krw;
    const known = pls.map(price).filter((v) => typeof v === "number"), tot = document.getElementById("orderTotal");
    tot.hidden = !pls.length;
    tot.innerHTML = pls.length ? `<span>LG 가전 ${pls.length}개</span><b>${known.length ? `${known.reduce((a, b) => a + b, 0).toLocaleString("ko-KR")}원` : "가격 정보 없음"}</b>${known.length < pls.length ? `<small>가격 정보가 없는 ${pls.length - known.length}개는 빼고 더했어요</small>` : ""}` : "";
    const ob = document.getElementById("orderBtn");
    ob.classList.toggle("primary", pls.length > 0); ob.classList.toggle("ghost", !pls.length);
    document.getElementById("pls").innerHTML = every.length ? every.map((x) => `
      <li data-sel="${esc(x.placement_id || "")}" class="${x.placement_id === selPl ? "on" : ""}">
        <i class="dot" style="background:${esc(x.hex || "#fff")}"></i><span style="flex:1">${esc(nameOf(x.sku))}</span>${shownVerdict(x.verdict) === "fit" ? "" : `<span class="badge ${shownVerdict(x.verdict)}">${LABEL[x.verdict]}</span>`}</li>`).join("")
      : `<li class="muted">아직 없어요. 왼쪽에서 가전이나 가구를 골라 3D에 놓아 보세요.</li>`;
    document.querySelectorAll("#pls [data-sel]").forEach((li) => (li.onclick = () => focusPlacement(li.dataset.sel)));
    const gone = project.scene_state.hidden_objects || [];
    if (gone.length) document.getElementById("pls").insertAdjacentHTML("beforeend", `<li class="muted" style="font-size:12px">치운 기존 가구 ${gone.length}개 <span class="spacer"></span><button class="small ghost" id="restore">모두 되돌리기</button></li>`);
    const walls = project.scene_state.hidden_walls || [];
    if (walls.length) document.getElementById("pls").insertAdjacentHTML("beforeend", `<li class="muted" style="font-size:12px">철거한 벽 ${walls.length}개 <span class="spacer"></span><button class="small ghost" id="wallBack">모두 다시 세우기</button></li>`);
    const wb = document.getElementById("wallBack");
    if (wb) wb.onclick = guard(async () => { for (const w of walls) await put(`/api/projects/${pid}/walls/${w}/hidden`, { hidden: false }); await refresh(true); });
    const rb = document.getElementById("restore");
    if (rb) rb.onclick = guard(async () => { await put(`/api/projects/${pid}/objects/hidden`, { hidden: false }); await refresh(true); });
    // 스캔 가구 한꺼번에 치우기 / 되돌리기
    const fb = document.getElementById("furn");
    const all = room.objects.length, allGone = all > 0 && gone.length >= all;
    fb.hidden = all === 0;
    // 지예: 버튼 하나로 켜고 끈다. 이름은 그대로, 켜져 있으면 레드
    fb.classList.toggle("on", allGone); fb.setAttribute("aria-pressed", allGone);
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
        arm(sku);
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
    svg.insertAdjacentHTML("beforeend", `<polygon class="cam-mark" id="camMark" points="0,0 0,0 0,0" style="stroke-width:${pv.sw(1.5)}px"/><circle class="cam-dot" id="camDot" r="${pv.sw(5)}"/>`);
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
      document.getElementById("needTag").hidden = true; // 점선 범례 글은 띄우지 않는다 (화면을 가볍게)
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
        <button class="small ghost" id="putRouter">${armedRouter ? "놓을 자리를 누르세요 · 책상·선반 위도 돼요" : "공유기 놓기"}</button>
        <button class="small ghost" id="bestRouter">추천 자리 찾기</button></div>
      <div id="simres" style="margin-top:8px"></div>`;
    document.querySelectorAll("[data-band]").forEach((b) => (b.onclick = () => { band = b.dataset.band; wifiCtl(); }));
    document.getElementById("putRouter").onclick = () => { armedRouter = !armedRouter; if (!armedRouter) viewer.routerFollow(null); armed = null; mode = "move"; syncMode(); wifiCtl(); };
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
    document.querySelectorAll("[data-sim]").forEach((x) => { x.classList.toggle("on", x.dataset.sim === sim); x.setAttribute("aria-checked", x.dataset.sim === sim); });
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
  const refresh = (force = false) => {
    if (force) document.dispatchEvent(new Event("lgb:changed")); // 저장 표시: 다음 자동 저장 전까지 '저장 안 된 변경'
    return (chain = chain.catch(() => {}).then(() => load(force)));
  };
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
    scheduleSuggest();
    floorplanBox(document.getElementById("fpBox"), pid, project, () => refresh(true));
    wallTable(document.getElementById("walls"), pid, room, { by: "customer", onChange: () => refresh(true) });
    // glb(벽·가구·색)는 바뀌었을 때만 다시 받는다. 놓은 제품은 화면에서 직접 그린다.
    const sceneKey = JSON.stringify([project.scene_state.materials, project.scene_state.finish, project.scene_state.finish_ids, FIN.length, project.scene_state.hidden_objects, project.scene_state.hidden_walls, project.scene_state.object_poses, room.walls.map((w) => w.measured)]);
    if (sceneKey !== lastSceneKey) { lastSceneKey = sceneKey; viewer.setObjects(room.objects); viewer.setFinishes(finishSet()); viewer.load(apiUrl(`/api/projects/${pid}/files/scene.glb`)); }
    document.getElementById("hud").textContent = `빈 곳 끌기 회전 · 휠 확대 · 휠 누르고 끌기 이동 · 누르면 집어 들기 · WASD 카메라 · ${project.scene.engine === "blender" ? "Blender 장면" : "스캔 치수 장면"}`;
  };
  setHint();
  setLibTab(libTab);
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
    const saveSum = document.getElementById("saveSum"), menuEl = document.getElementById("homeMenu");
    document.getElementById("savebar").addEventListener("savestate", (e) => {
      saveSum.textContent = e.detail.text;
      menuEl.dataset.save = e.detail.kind; // ok · busy · dirty · fail · off
    });
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
    setHint("놓은 제품 위 메뉴로 이동·회전·벽에 붙이기·삭제를 해 보세요. 오른쪽에서 설치 가능한지 바로 보여요");
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
    const outro = { title: "직접 체험해 볼까요?", text: "이 집에 들어가는 제품 하나를 알맞은 자리에 놓아 드릴게요. 놓은 뒤 제품 위 메뉴로 옮기거나 돌려 보세요.", cta: { label: "체험해 보기", run: tryIt } };
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
