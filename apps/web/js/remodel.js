// 화면: 우리 집 가상 리모델링 (제품 배치, 색·재질, 살아 보기)
import { $app, cleanup, LABEL, shownVerdict, PURPOSE, USE, CATEGORY, CATEGORY_GROUP, DIM, OBJ, NOTE, esc, mm, api, apiUrl, post, put, toast, guard,
  rememberHome, forgetHome, uiState, saveUiState, saveHomeThumb } from "./core.js";
import { makeViewer } from "./viewer.js";
import { gapNotes } from "./gapnote.js";
import { buildWorld } from "./walk.js";
import { tourStops, findPath, lookYaw, nearestStop, nearFree } from "./stops.js";
import { planView, placedSvg } from "./plan.js";
import { wallTable, WALL_HEAD, floorplanBox, installRequestBox } from "./pages.js";
import { swatchUrl, TEXTURE_KO } from "./finishes.js";
import { mountSaveBar } from "./account.js";
import { fitCardHtml, VERDICT_LABEL, INSTALL_NOTE } from "./guide.js";
import { optionSteps, priceScale } from "./options.js";
import { SIZE_W, SIZE_H, appliedFilters, clearFilter, detailCount, installCounts, matchesQuery, parseManwon, wonText } from "./filters.js";
import { startTour, tourSeen } from "./tour.js";
import { snapPose } from "./snap.js";
import { coloursFor, lookOf, runOf } from "./furncolors.js";
import { straighten, snapStart } from "./wallsnap.js";
import { comboPopHtml, comboCardsHtml, bindComboCards, mountComboPop } from "./combos.js";

// 이 폭 이하(폰·태블릿·작은 앱 창)는 앱 배치: 3D 꽉 차게, 제품은 아래 서랍
const APP_MAX_W = 1100;
const MAX_DOTS = 5; // 카드에 보이는 색 동그라미 수 (나머지는 상세 창에서)
const DOOR_SKU = "decor:door"; // 벽에 다는 문: 앞이 비어야 열린다 (서버 판정 front_blocked)
const CATS_CLIP_PX = 72; // 품목 칩 두 줄 높이 (studio.css .cat-chips.clip과 같은 값)

export async function customer(pid) {
  const token = new URLSearchParams(location.hash.split("?")[1] || "").get("t");
  const saved = uiState(pid); // 다른 화면에 다녀와도 보던 그대로
  $app.innerHTML = `
    <div class="studio" data-view="3d">
      <header class="studio-head">
        <div class="studio-title"><h1>우리 집 가상 리모델링</h1><p class="sub" id="sub">불러오는 중…</p></div>
        <div class="file-bar" role="toolbar" aria-label="파일">
          <span class="save-note" id="savebar" aria-live="polite"></span>
          <button class="fbtn app-only" id="extraBtn2">도면·실측</button>
          <a class="fbtn" id="newBtn" href="#/new" title="지금 집은 그대로 두고, 다른 집을 새로 스캔해 올려요"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M12 11v6M9 14h6"/></svg>새로 만들기</a>
          <button class="fbtn" id="loadBtn" title="저장해 둔 집을 불러와요"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>불러오기</button>
          <button class="fbtn primary" id="saveBtn" title="지금 꾸민 집을 저장해요 (Ctrl+S)"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h11l3 3v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M7 3v6h8V3M7 21v-7h10v7"/></svg>저장</button>
        </div>
      </header>

      <aside class="lib" data-panel="lib" aria-label="공간 꾸미기 라이브러리">
        <div class="lib-side">
          <!-- 카테고리 → 설치 방식 → 품목 → 가격 범위 → 상세 필터 순서 -->
          <nav class="lib-tabs" id="libTabs" role="tablist" aria-label="카테고리">
            <button role="tab" data-tab="all">전체</button><button role="tab" data-tab="lg">LG 가전</button><button role="tab" data-tab="furniture">가구</button><button role="tab" data-tab="storage">수납</button><button role="tab" data-tab="decor">소품</button><button role="tab" data-tab="finish">벽지·바닥</button></nav>
          <section class="decor-lib" id="decorLib" aria-label="벽체·가구·수납·소품·벽지·바닥"></section>
          <div class="lib-head lg-part"><h2>LG 가전</h2>
            <button class="primary small app-only" id="orderMini" hidden>구매·설치 신청</button>
            <button class="ghost small app-only" id="libMore" aria-expanded="false">전체 보기</button></div>
          <input id="q" class="lg-part" type="search" placeholder="이름·모델명 검색" aria-label="제품 검색">
          <details class="fbox lg-part" id="filterBox">
            <summary><span class="fbox-t"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg>필터</span><span class="fbox-n" id="filterN" hidden></span><span class="fbox-arrow" aria-hidden="true"></span></summary>
            <section class="fsec" aria-labelledby="fInstall"><h3 id="fInstall">설치 방식</h3>
              <div class="seg2" id="installSeg" role="group" aria-label="설치 방식"></div></section>
            <section class="fsec" aria-labelledby="fCat"><h3 id="fCat">품목</h3>
              <div class="ask" id="ask" aria-label="공간 용도"></div>
              <div class="chips cat-chips" id="cats" aria-label="가전 종류"></div>
              <button class="linklike cats-more" id="catsMore" aria-expanded="false" hidden>품목 더 보기</button></section>
            <section class="fsec budget" id="budget" hidden aria-labelledby="fPrice"><h3 id="fPrice">가격 범위</h3>
              <div class="budget-io">
                <label><span>최소 가격</span><span class="won-in"><input id="pLoIn" type="text" inputmode="numeric" autocomplete="off" aria-label="최소 가격 (만 원)"><i>만원</i></span></label>
                <label><span>최대 가격</span><span class="won-in"><input id="pHiIn" type="text" inputmode="numeric" autocomplete="off" aria-label="최대 가격 (만 원)"><i id="pHiUnit">만원</i></span></label>
              </div>
              <div class="budget-rail" id="budgetRail"><input type="range" id="pLo" aria-label="최저 가격"><input type="range" id="pHi" aria-label="최고 가격"></div>
            </section>
            <details class="more-filter fsec" id="moreFilter"><summary><h3>상세 필터</h3><span class="fbox-n ok" id="filterOn" hidden></span><span class="fbox-arrow" aria-hidden="true"></span></summary>
              <div class="fsub"><h4>크기</h4>
                <div class="filters" aria-label="크기 필터">
                  <select id="fW" aria-label="폭"><option value="">폭 전체</option>${SIZE_W.map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select>
                  <select id="fH" aria-label="높이"><option value="">높이 전체</option>${SIZE_H.map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select>
                </div></div>
              <ol class="opt-steps" id="steps" aria-label="옵션을 차례로 골라 좁히기"></ol>
              <p class="hint-sm steps-hint" id="stepsHint" hidden>품목을 고르면 색상·용량·도어 같은 조건을 더 고를 수 있어요.</p>
            </details>
            <div class="fact"><button class="linklike" id="resetFilter">필터 초기화</button><button class="primary" id="applyFilter">적용하기</button></div>
          </details>
          <div class="applied lg-part" id="applied" aria-label="적용된 필터" hidden></div>
          <section class="sugg" id="sugg" aria-label="이 집에 들어가는 제품" hidden></section>
          <div class="list-head lg-part"><span id="libCount"></span>
            <select id="sortBy" aria-label="정렬"><option value="">추천순</option><option value="price">낮은 가격순</option><option value="size">작은 크기순</option></select></div>
        </div>
        <ul class="list lg-part" id="lib" aria-label="LG 제품 목록. 누른 뒤 3D 바닥을 누르면 놓여요"></ul>
      </aside>
      <button class="lib-fold" id="libFold" aria-expanded="true" aria-label="제품 패널 접기" title="제품 패널 접기"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="m14 6-6 6 6 6"/></svg></button>

      <section class="stage" aria-label="우리 집">
        <section class="pd-modal" id="pdModal" role="dialog" aria-label="제품 상세" hidden></section>
        <section class="order-sheet" id="orderSheet" role="dialog" aria-label="구매 및 설치 신청" hidden></section>
        <div class="toolbar">
          <button class="furn-btn combo-btn" id="comboBtn" aria-expanded="false" aria-controls="comboPop" title="가전과 목표 가격을 고르면 이 집에 맞춘 조합을 놓아 봐요">추천 배치</button>
          <button class="furn-btn live-btn" id="liveBtn" aria-pressed="false" title="실제로 살아 보듯 둘러보고, 볕·와이파이·동선을 봐요"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11 12 4l9 7v9H3z"/><path d="M9 20v-6h6v6"/></svg>살아 보기</button>
          <button class="furn-btn" id="extraBtn" aria-expanded="false" aria-controls="extraPop" title="도면을 올리거나 줄자로 잰 벽 길이를 넣어요">도면·실측</button>
          <span class="spacer"></span>
          <div class="icon-row" role="group" aria-label="되돌리기">
            <button class="icon-btn" id="undo" disabled aria-label="되돌리기" title="되돌리기 (Ctrl+Z)"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/></svg></button>
            <button class="icon-btn" id="redo" disabled aria-label="다시 실행" title="다시 실행 (Ctrl+Shift+Z)"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="m15 14 5-5-5-5"/><path d="M20 9H10a6 6 0 0 0 0 12h3"/></svg></button>
            <button class="icon-btn" id="furn" data-l="가구 치우기" aria-pressed="false" aria-label="가구 치우기" title="가구 치우기: 가구나 창문에 마우스를 올리면 뜨는 ✕를 눌러요"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12V8a2 2 0 0 1 2-2h4M4 12h9a2 2 0 0 1 2 2v3H4zM5 17v2M14 17v2"/><path d="m16 4 5 5M21 4l-5 5"/></svg></button>
            <button class="icon-btn" id="beforeBtn" data-l="처음 모습" aria-pressed="false" aria-label="처음 모습 보기" title="누르고 있는 동안 처음 모습을 보여 줘요"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M12 3v18"/><path d="m7.5 10-2 2 2 2M16.5 10l2 2-2 2"/></svg></button>
            <button class="icon-btn" id="fullBtn" data-l="전체 화면" aria-label="전체 화면" title="전체 화면"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg></button>
            <button class="icon-btn" id="tourBtn" data-l="안내" aria-label="화면 안내 다시 보기" title="화면 안내 다시 보기"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6M12 17h.01"/></svg></button>
            <button class="icon-btn" id="keysBtn" data-l="조작키" aria-expanded="false" aria-controls="keysPop" aria-label="조작키" title="마우스·키보드 조작 방법"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/></svg></button>
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
          <div class="pane view-pane"><div class="viewer" id="viewer"><span class="hud" id="hud"></span></div><img class="tour-photo" id="tourPhoto" alt="지금 선 곳의 실사 이미지" hidden>
            <button class="pip-swap" data-swap="3d" title="3D를 크게 보기">3D 보기</button>
            <div class="view-stack" role="group" aria-label="보기 바꾸기">
              <button class="vbtn on" id="viewTop" aria-pressed="true" title="위에서 내려다봐요"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 3 8l9 5 9-5zM3 12l9 5 9-5M3 16l9 5 9-5"/></svg><span>위에서</span></button>
              <button class="vbtn" id="walk" aria-pressed="false" title="집 안에 들어가 눈높이로 걸어 봐요 (W A S D)"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="5" r="2.5"/><path d="M8.5 21l1.5-6-2-2.5V10a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2.5L14 15l1.5 6"/></svg><span>걸어 보기</span></button>
              <button class="vbtn" id="render" title="지금 보는 장면을 사진처럼 만들어요"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="6" width="18" height="13" rx="2"/><circle cx="12" cy="12.5" r="3.5"/><path d="M8 6l1.5-2h5L16 6"/></svg><span>실사</span></button>
            </div>
            <div class="before-pane" id="beforePane" hidden><div class="viewer" id="beforeViewer"></div><span class="before-tag">스캔했을 때 모습</span></div></div>
          <div class="keys-pop" id="keysPop" role="dialog" aria-label="조작키" hidden>
            <div class="keys-head"><b>조작키</b><button class="ghost small" id="keysClose">닫기</button></div>
            <h4>제품</h4>
            <p class="hint-sm">제품이나 가구를 누른 채 끌면 바로 옮겨져요. 누르기만 하면 위에 메뉴가 떠요.</p>
            <ul class="keys"><li><kbd>누른 채 끌기</kbd> 잡아서 옮기기 · 놓으면 내려놓기</li><li>잡은 채 <kbd>휠</kbd> 또는 <kbd>E</kbd> 누르고 마우스 돌리기 (<kbd>Shift</kbd> 45°)</li><li><kbd>R</kbd> 45° 돌리기 (<kbd>Shift</kbd> 반대, <kbd>Alt</kbd> 15°)</li>
              <li><kbd>←↑↓→</kbd> 10 cm 옮기기 (<kbd>Shift</kbd> 1 cm)</li><li><kbd>Delete</kbd> 지우기</li><li><kbd>Ctrl</kbd><kbd>Z</kbd> 되돌리기 · <kbd>Ctrl</kbd><kbd>Shift</kbd><kbd>Z</kbd> 다시 실행</li><li><kbd>Esc</kbd> 취소</li></ul>
            <h4>화면</h4>
            <ul class="keys"><li><kbd>빈 곳 끌기</kbd> 시점 돌리기</li><li><kbd>휠</kbd> 확대·축소</li><li><kbd>휠 누르고 끌기</kbd> 화면 옮기기</li><li><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> 카메라 이동 · <kbd>Q</kbd><kbd>E</kbd> 돌기</li></ul>
            <h4>둘러보기</h4>
            <ul class="keys"><li><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> 걷기 · <kbd>Shift</kbd> 빠르게</li><li><kbd>←</kbd><kbd>→</kbd><kbd>↑</kbd><kbd>↓</kbd> 둘러보기 (화면을 끌어도 돼요)</li></ul>
            <h4>저장 (로그인하면)</h4>
            <ul class="keys"><li><kbd>Ctrl</kbd><kbd>S</kbd> 지금 상태 저장 (맥 <kbd>⌘</kbd><kbd>S</kbd>) · 10초마다 자동 저장</li></ul>
          </div>
          ${comboPopHtml()}
          <section class="extra-pop" id="extraPop" role="dialog" aria-label="도면·실측" hidden>
            <div class="keys-head"><b>도면·실측 <span class="muted">선택</span></b><button class="ghost small" id="extraClose">닫기</button></div>
            <p class="hint-sm">스캔만으로도 판정해요. 도면이나 줄자로 잰 값이 있으면 넣어 주세요. 더 촘촘하게 판정해요.</p>
            <h3>도면</h3><div id="fpBox"></div>
            <h3 class="gap">벽 실측값 (m)</h3>
            <p class="hint-sm">평면의 벽 번호를 보고, 잰 값만 넣으면 됩니다.</p>
            <div class="table-scroll"><table>${WALL_HEAD}<tbody id="walls"></tbody></table></div>
          </section>
          <p class="render-wait" id="renderWait" role="status" hidden><i aria-hidden="true"></i>실사 사진을 만들고 있어요. 30초쯤 걸려요.</p>
          <nav class="walk-tour" id="walkTour" aria-label="둘러보기" hidden>
            <div class="wt-head"><b id="wtName" aria-live="polite"></b>
              <button type="button" class="wt-play" id="wtPlay" aria-pressed="false"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path class="wt-go" d="M8 5.5v13l10.5-6.500z"/><path class="wt-halt" d="M8 6v12M16 6v12"/></svg><span>한 번에 둘러보기</span></button></div>
            <ol class="wt-line" id="wtLine"></ol>
          </nav>
          <figure class="render-shot" id="renderBox" hidden><img id="renderImg" alt="실사 이미지">
            <figcaption id="renderCap" class="hint-sm"></figcaption>
            <span class="render-act"><a class="ghost small btn" id="renderSave" download="우리집-실사.png">저장</a><button class="ghost small" id="renderClose">닫기</button></span></figure>
          <div class="sim-switches" role="group" aria-label="살아 보기"><button class="simsw" data-sim="daylight" role="switch" aria-checked="false"><span class="sw-track" aria-hidden="true"><i></i></span>채광</button><button class="simsw" data-sim="wifi" role="switch" aria-checked="false"><span class="sw-track" aria-hidden="true"><i></i></span>와이파이</button><button class="simsw" data-sim="flow" role="switch" aria-checked="false"><span class="sw-track" aria-hidden="true"><i></i></span>동선</button></div>
          <section class="minimap" id="minimap" aria-label="도면" hidden></section>
          <p class="hint" id="hint" aria-live="polite"></p>
          <p class="fit-badge" id="fitBadge" aria-live="polite" hidden></p>
          <div class="act-bar" id="actBar" role="toolbar" aria-label="고른 제품 조작" hidden></div>
          <div class="gap-tags" id="gapTags" aria-live="off"></div>
          <p class="need-tag" id="needTag" hidden><i aria-hidden="true"></i>점선 안은 제품과 문을 여는 데 필요한 공간이에요</p>
          <div class="flow-xs" id="flowX"></div>
          <div class="flow-xs" id="furnX"></div>
          <button class="furn-all" id="furnAll" hidden></button>
          <div class="sheet" id="simctl"></div>
          <button class="sheet-fold" id="simFold" aria-expanded="true" aria-controls="simctl">정보 접기</button>
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
    if (app) { studio.querySelector(".list-head").before(sugg); studio.querySelector(".canvas").append(mini); }
    else { document.getElementById("suggSlot").append(sugg); studio.querySelector(".canvas").append(mini); } // 지예: 평면도는 3D 화면 구석에 작은 지도처럼
  }
  appMq.addEventListener("change", syncApp);
  cleanup.push(() => appMq.removeEventListener("change", syncApp));
  libMore.onclick = () => openLib(!studio.classList.contains("lib-open"));
  // 제품 패널 접기: 3D를 화면 가득 넓게 쓰고 싶을 때 (접은 상태는 기억해 둔다)
  const libFold = document.getElementById("libFold");
  const foldLib = (on) => {
    studio.classList.toggle("lib-folded", on);
    const label = on ? "제품 패널 펼치기" : "제품 패널 접기";
    libFold.setAttribute("aria-expanded", !on); libFold.setAttribute("aria-label", label); libFold.title = label;
    saveUiState(pid, { libFolded: on });
  };
  libFold.onclick = () => foldLib(!studio.classList.contains("lib-folded"));
  // 3D 아래 채광·와이파이·동선 정보 칸도 접어 둘 수 있다
  const simFold = document.getElementById("simFold");
  simFold.onclick = () => {
    const on = !studio.classList.contains("sim-folded");
    studio.classList.toggle("sim-folded", on);
    simFold.textContent = on ? "정보 펼치기" : "정보 접기";
    simFold.setAttribute("aria-expanded", !on);
  };
  if (saved.libFolded) foldLib(true);
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
  // 오른쪽은 탭 없이: 고른 제품 카드, 안 골랐으면 놓은 제품 목록. 벽지·바닥은 왼쪽 탭
  const setTab = (t) => {
    if (t === "list" && selPl) { selPl = null; selObj = null; draw(); renderInspector(); renderPlacements(); }
  };
  // 처음 모습: 스캔 그대로의 집을 같은 시점으로 3D 위에 겹쳐 보여 준다 (지금 꾸민 것은 건드리지 않는다)
  const beforeBtn = document.getElementById("beforeBtn"), beforePane = document.getElementById("beforePane");
  let beforeViewer = null;
  const showBefore = async (on) => {
    beforeBtn.setAttribute("aria-pressed", on);
    beforeBtn.classList.toggle("on", on);
    beforePane.hidden = !on;
    if (!on) { if (beforeViewer) viewer.setCamera(beforeViewer.camera()); beforeViewer?.dispose(); beforeViewer = null; return; }
    beforeViewer = makeViewer(document.getElementById("beforeViewer"));
    beforeViewer.setCamera(viewer.camera());
    const scan = await api(`/api/projects/${pid}/files/room.json`);
    if (!beforeViewer) return;
    beforeViewer.setObjects(scan.objects);
    beforeViewer.load(apiUrl(`/api/projects/${pid}/files/before.glb`));
  };
  // 사진 앱처럼: 누르고 있는 동안만 처음 모습, 떼면 지금 모습
  const holdBefore = (on) => { if (on === beforePane.hidden) showBefore(on).catch(() => {}); };
  beforeBtn.onpointerdown = (e) => { beforeBtn.setPointerCapture?.(e.pointerId); holdBefore(true); };
  ["pointerup", "pointercancel", "lostpointercapture", "blur"].forEach((ev) => beforeBtn.addEventListener(ev, () => holdBefore(false)));
  beforeBtn.onkeydown = (e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); holdBefore(true); } };
  beforeBtn.onkeyup = (e) => { if (e.key === " " || e.key === "Enter") holdBefore(false); };
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
  document.getElementById("extraBtn2").onclick = () => showExtra(true);
  document.getElementById("extraClose").onclick = () => showExtra(false);
  extraPop.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); showExtra(false); extraBtn.focus(); } });
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
  // 둘러보기 줄: 현관·창 앞·가구 앞·놓은 가전 앞을 차례로. 누르면 걸어서 가고, '한 번에 둘러보기'는 끝까지 이어서 간다
  const TOUR_STAY_MS = 2200; // 한 곳에서 머무는 시간
  const TOUR_DECOR = new Set(["decor:sofa", "decor:bed", "decor:sink", "decor:island"]);
  const tourBar = document.getElementById("walkTour"), wtLine = document.getElementById("wtLine"), wtPlay = document.getElementById("wtPlay");
  let stops = [], stopAt = -1, touring = false, tourTimer = 0;
  const stopNames = { objects: OBJ, placement: (x) => (isDecor(x.sku) ? (TOUR_DECOR.has(x.sku) ? decorOf(x.sku)?.name : null) : CATEGORY[prodOf(x.sku)?.category]) || null };
  const markStop = (i) => {
    stopAt = i;
    wtLine.querySelectorAll("button").forEach((b, j) => {
      b.classList.toggle("on", j === i); b.classList.toggle("done", i >= 0 && j < i);
      if (j === i) { b.setAttribute("aria-current", "step"); b.scrollIntoView?.({ block: "nearest", inline: "nearest" }); } else b.removeAttribute("aria-current");
    });
    wtLine.style.setProperty("--p", i > 0 && stops.length > 1 ? i / (stops.length - 1) : 0);
    document.getElementById("wtName").textContent = i >= 0 ? stops[i].name : "걸어 보는 중";
  };
  const drawStopDots = () => {
    const g = document.getElementById("stopDots");
    if (g && pv) g.innerHTML = walking ? stops.map((x) => `<circle class="stop-dot" cx="${x.pos[0]}" cy="${x.pos[1]}" r="${pv.sw(4)}"/>`).join("") : "";
  };
  const loadStops = () => {
    const was = stops[stopAt]?.id;
    stops = tourStops(room, project.scene_state.placements, project.scene_state.hidden_objects, walkWorld(), stopNames);
    wtLine.innerHTML = stops.map((x, i) => `<li><button type="button" data-stop="${i}"><i aria-hidden="true"></i><span>${esc(x.name)}</span></button></li>`).join("");
    markStop(stops.findIndex((x) => x.id === was));
    drawStopDots();
  };
  const setTouring = (on) => {
    touring = !!on;
    clearTimeout(tourTimer);
    wtPlay.classList.toggle("on", touring); wtPlay.setAttribute("aria-pressed", touring);
    wtPlay.querySelector("span").textContent = touring ? "멈추기" : "한 번에 둘러보기";
  };
  const herePos = () => { const w = viewer.walkInfo(); return [w.pos[0], w.pos[2]]; };
  const goStop = (i, then) => {
    const x = stops[i];
    if (!x || !walking) return;
    const path = findPath(herePos(), x.pos, walkWorld());
    const arrive = () => { markStop(i); then?.(); };
    if (path) viewer.walkTo(path, x.yaw, arrive, x.pitch);
    else { viewer.walkPlace(x.pos, x.yaw, x.pitch); arrive(); } // 걸어서 갈 길이 없으면 바로 그 자리로
  };
  const tourNext = (i) => {
    if (!touring || !walking) return;
    if (i >= stops.length) { setTouring(false); return; }
    goStop(i, async () => {
      if (photoOn) await showPhoto(stops[i]).catch(() => {}); // 실사는 다 뜬 뒤부터 머문다
      if (touring) tourTimer = setTimeout(() => tourNext(i + 1), TOUR_STAY_MS * (photoOn ? 1.6 : 1));
    });
  };
  wtLine.onclick = (e) => { const b = e.target.closest("[data-stop]"); if (!b) return; setTouring(false); goStop(+b.dataset.stop); };
  wtPlay.onclick = () => {
    if (touring) { viewer.walkStop(); setTouring(false); return; }
    setTouring(true);
    // 실사를 켠 채 시작하면 지금 선 곳부터 실사로 보고 넘어간다
    tourNext(stopAt < 0 || stopAt >= stops.length - 1 ? 0 : photoOn ? stopAt : stopAt + 1);
  };
  // 실사로 둘러보기: 걸어 보는 중에 실사를 켜면, 들르는 곳에 설 때마다 그 장면을 실사 사진으로 바꿔 보여 준다.
  // 한 번 만든 곳은 서버에 남아서(장면이 그대로면) 다시 갈 때 바로 뜬다.
  const tourPhoto = document.getElementById("tourPhoto");
  let photoOn = false, photoAt = null, spotPhotos = {}; // photoAt: 지금 사진을 보여 주는(만드는) 곳 id
  const photoJobs = new Map(); // 곳 id → 만드는 중인 약속 (같은 곳을 두 번 만들지 않게)
  const hidePhoto = () => { photoAt = null; tourPhoto.classList.remove("on"); document.getElementById("renderWait").hidden = true; };
  const setPhotoOn = (on) => {
    photoOn = !!on;
    const b = document.getElementById("render");
    b.classList.toggle("on", photoOn); b.setAttribute("aria-pressed", photoOn);
    if (!photoOn) hidePhoto();
  };
  const spotPhoto = (x) => {
    const had = spotPhotos[x.id];
    if (had && had.version === project.version) return Promise.resolve(apiUrl(had.url));
    const key = `${x.id}@${project.version}`;
    if (!photoJobs.has(key)) {
      const version = project.version;
      photoJobs.set(key, post(`/api/projects/${pid}/photoreal`, { ...takeShot(), spot: x.id })
        .then((r) => { spotPhotos = { ...spotPhotos, [x.id]: { url: r.url, version } }; return apiUrl(r.url); })
        .finally(() => photoJobs.delete(key)));
    }
    return photoJobs.get(key);
  };
  /** 그 곳에 서 있을 때 실사를 띄운다. 만드는 동안 자리를 뜨면 버린다. 끝나면(띄웠든 아니든) 돌아온다 */
  let photoRun = null; // 지금 띄우는 중인 일 (같은 곳을 또 부르면 그 일이 끝나기를 같이 기다린다)
  const showPhoto = (x) => {
    if (photoAt === x.id && photoRun) return photoRun;
    photoRun = runPhoto(x);
    return photoRun;
  };
  const runPhoto = async (x) => {
    photoAt = x.id;
    const waitEl = document.getElementById("renderWait");
    waitEl.hidden = !!(spotPhotos[x.id]?.version === project.version);
    try {
      const url = await spotPhoto(x);
      if (photoAt !== x.id || !photoOn) return;
      await new Promise((ok) => { tourPhoto.onload = tourPhoto.onerror = ok; tourPhoto.src = url; });
      if (photoAt !== x.id || !photoOn) return;
      tourPhoto.hidden = false;
      requestAnimationFrame(() => tourPhoto.classList.add("on"));
    } catch (err) {
      setPhotoOn(false); setTouring(false);
      if (err.status !== 503 && err.status !== 429) throw err;
      toast(err.message, true);
    } finally { if (photoAt === x.id || !photoAt) waitEl.hidden = true; }
  };
  const setWalking = (on) => {
    walking = !!(on && room && viewer);
    setTouring(false);
    setPhotoOn(false);
    if (walking) {
      if (studio.dataset.view === "plan") setView("3d");
      armed = null; ghost(null); renderLib();
      viewer.setWalk(walkWorld());
      loadStops();
      if (stops[0]) { viewer.walkPlace(stops[0].pos, stops[0].yaw, stops[0].pitch); markStop(0); } // 현관에서 시작
      api(`/api/projects/${pid}/photoreal/spots`).then((r) => { spotPhotos = r.spots || {}; }).catch(() => { /* 없으면 새로 만든다 */ });
    } else { viewer?.setWalk(null); stops = []; stopAt = -1; }
    tourBar.hidden = !walking;
    drawStopDots();
    setTimeout(() => { if (project) draw(); }, 320); // 도면 칸 크기가 바뀌니 글자·선 굵기를 다시 맞춘다
    const b = document.getElementById("walk");
    b.classList.toggle("on", walking);
    studio.classList.toggle("walking", walking);
    b.setAttribute("aria-pressed", walking);
    const top = document.getElementById("viewTop"); top.classList.toggle("on", !walking); top.setAttribute("aria-pressed", !walking);
    setHint();
    if (walking) document.getElementById("hint").textContent = "둘러보기: 아래에서 가고 싶은 곳을 누르면 걸어가요 · 직접 걸으려면 W A S D · 둘러보려면 방향키나 화면 끌기";
  };
  // 작은 도면을 누르면 그 자리로 걸어간다
  minimap.addEventListener("pointerdown", (e) => {
    if (!walking || !pv || e.target.closest("#miniGrow")) return;
    e.stopPropagation(); e.preventDefault();
    const world = walkWorld(), from = herePos(), to = nearFree(pv.toWorld(e), world); // 가구 위를 눌렀으면 그 옆으로
    if (!to) return;
    const path = findPath(from, to, world);
    if (!path) return;
    setTouring(false);
    viewer.walkTo(path, lookYaw(from, to));
  }, true);
  document.getElementById("walk").onclick = () => setWalking(true);
  document.getElementById("viewTop").onclick = () => setWalking(false);
  // 살아 보기: 버튼 하나로 들어가서 둘러보기·채광·와이파이·동선을 고른다 (켜고 끄는 토글 줄은 이 안에만)
  const liveBtn = document.getElementById("liveBtn"), liveBar = document.getElementById("liveBar");
  const setLive = (on) => {
    liveBar.hidden = !on; liveBtn.classList.toggle("on", on); liveBtn.setAttribute("aria-pressed", on);
    studio.classList.toggle("living", on);
  };
  liveBtn.onclick = () => (liveBar.hidden ? setLive(true) : endLive());
  const endLive = () => { if (walking) setWalking(false); if (sims.size) { sims.clear(); saveSims(); showSim(); } setLive(false); };
  document.getElementById("liveEnd").onclick = endLive;
  studio.querySelectorAll(".toolbar [data-view]").forEach((b) => (b.onclick = () => setView(b.dataset.view)));
  studio.querySelectorAll("[data-swap]").forEach((b) => (b.onclick = () => setView(b.dataset.swap)));
  // 3D 안에서 바로 놓기·옮기기·고르기 (plans/virtual-remodel.md S10)
  let drag3d = null, hovering = false; // hovering: 마우스가 3D 위에 있는지 (버튼 위로 나가면 늦게 온 미리 보기를 버린다)
  let wallPicking = false, removeWall = () => {}; // 벽 철거: 3D에서 벽을 눌러 고르는 중 (아래에서 채운다)
  let furnPick = false, furnHover = () => {}; // 가구 치우기: 마우스가 올라간 가구·창에만 ✕ (아래에서 채운다)
  let wallDraw = null, wallPoint = () => {}; // 벽 추가: 바닥에서 시작점 → 끝점 ({start} 또는 {})
  const viewer = makeViewer(document.getElementById("viewer"), {
    onWalkStop: () => setTouring(false), // 직접 걷거나 화면을 누르면 이어 보기를 멈춘다
    canDrag: (id) => mode === "move" && !armed && !armedRouter && !armedStart && id === selPl,
    // 물건을 누른 채 끌면 바로 잡힌다. 놓으면 내려놓는다. 잡은 채 휠이나 E+마우스로 돌린다
    canGrab: () => mode === "move" && !armed && !armedRouter && !armedStart && !wallDraw && !wallPicking && !furnPick,
    onGrab: (hit, point) => {
      if (hit.type === "placement") { selPl = hit.id; selObj = null; } else { selObj = hit.id; selPl = null; }
      pickUp(hit, point);
      if (viewer.held()) setHint("놓으면 그 자리에 내려놓아요 · 휠을 굴리거나 E를 누른 채 마우스를 움직이면 돌아가요 (Shift 45°) · Esc 취소");
      renderAct();
    },
    // 공유기는 책상·선반 윗면에도, 전자레인지·정수기 같은 작은 가전은 식탁·아일랜드·하부장 윗면에도 놓인다
    onSurface: () => (armedRouter ? "router" : armed && tabletop(armed) ? "product" : false),
    onHover: (p) => { hovering = true; follow(p); },
    wantHoverHit: () => furnPick,
    onHoverHit: (h) => furnHover(h),
    onLeave: () => { hovering = false; if (armed) ghost(null); if (armedRouter) viewer.routerFollow(null); if (armedStart) viewer.personFollow(null); },
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
      if (x) preview({ sku: x.sku, center_xz: xz, yaw_rad: h.yaw, snap: false, placement_id: h.id, ...sizeArgs(x) }, (r) => { viewer.holdVerdict(r.verdict); showGaps(r); });
    },
    // 들고 옮기거나 끌 때 벽·가전 옆에 착 붙는 자리 (없으면 null)
    snap: (h, xz, yaw) => {
      if (h.kind !== "placement") return null;
      const x = project?.scene_state.placements.find((q) => q.placement_id === h.id);
      return x ? snapAt(x.sku, x.size_m, xz, yaw ?? x.yaw_rad, x.placement_id, !!h.turned) : null;
    },
    onHoldClick: () => putDown(),
    onDragMove: (id, c, yaw) => {
      const x = project.scene_state.placements.find((q) => q.placement_id === id);
      if (!x) return;
      drag3d = id; selPl = id; selObj = null;
      preview({ sku: x.sku, center_xz: c, yaw_rad: yaw ?? x.yaw_rad, snap: false, placement_id: id, ...sizeArgs(x) }, (r) => { viewer.setDragVerdict(id, r.verdict); showGaps(r); });
    },
    onDragEnd: (id, c, baseY, yaw) => {
      const x = project.scene_state.placements.find((q) => q.placement_id === id);
      drag3d = null;
      setTab("sel");
      if (x && baseY !== undefined) x.base_m = baseY; // 저장 응답이 오기 전에도 올려 둔 높이 그대로
      // 붙는 물건은 화면에서 본 자리 그대로 저장한다 (서버가 다시 벽에 맞추면 본 것과 달라진다)
      if (x) patch(id, { center_xz: c, yaw_rad: yaw ?? x.yaw_rad, ...(snappable(x.sku) ? { snap: false } : {}) });
    },
    onDropSku: (sku, p) => placeAt(sku, p),
  });
  const saveCamera = () => { try { saveUiState(pid, { cam: viewer.camera() }); } catch { /* 이미 닫힌 화면 */ } };
  // 첫 화면 ‘최근에 만든 집’ 카드에 쓸 미리보기. 3D가 다 뜬 뒤와 화면을 떠날 때 찍는다
  let thumbT = 0;
  const saveThumb = () => { try { if (project && room && !viewer.walking()) saveHomeThumb(pid, viewer.thumb()); } catch { /* 미리보기는 없어도 된다 */ } };
  const thumbSoon = () => { clearTimeout(thumbT); thumbT = setTimeout(saveThumb, 4000); };
  cleanup.push(() => clearTimeout(thumbT), saveThumb, saveCamera, () => viewer.dispose()); // 화면을 떠나기 전에 미리보기와 카메라부터 적어 둔다
  window.addEventListener("pagehide", saveCamera);
  cleanup.push(() => window.removeEventListener("pagehide", saveCamera));
  const restoredCam = viewer.setCamera(saved.cam);
  if (VIEWS.includes(saved.view) && saved.view !== "3d") setView(saved.view, restoredCam);
  const svg = document.getElementById("plan");
  let mode = "move", draft = [], dragging = null, version = -1, zoneSel = null, project, room, zones, pv;
  let tabletop = () => false; // 카탈로그를 받은 뒤 채운다
  let armed = null, selPl = null, selObj = null, drag = null, cat = typeof saved.cat === "string" ? saved.cat : "", catalog = [];
  const sims = new Set(); // 켜 둔 살아 보기 (채광·와이파이·동선을 같이 켤 수 있다)
  const SIM_ORDER = ["daylight", "wifi", "flow"], SIM_KO = { daylight: "채광", wifi: "와이파이", flow: "동선" };
  const simOn = (k) => sims.has(k);
  const saveSims = () => saveUiState(pid, { sims: [...sims] });
  const secOf = (k) => document.querySelector(`#simctl [data-sec="${k}"]`);
  const ctlOf = (k) => secOf(k)?.querySelector(".sim-ctl"), resOf = (k) => secOf(k)?.querySelector(".sim-res");
  let overlay = "", simState = { date: new Date().toISOString().slice(0, 10), time: "12:00" };
  const prodOf = (sku) => catalog.find((p) => p.sku === sku);
  // 공간 꾸미기 가구 (제품 정보 없이 모양만, sku = "decor:종류"). 주문·설치 신청에는 넣지 않는다
  let decorList = [];
  const isDecor = (sku) => typeof sku === "string" && sku.startsWith("decor:");
  const decorOf = (sku) => decorList.find((d) => d.sku === sku);
  const nameOf = (sku) => prodOf(sku)?.name || decorOf(sku)?.name || sku;
  // 받침 있으면 "을", 없으면 "를" (한글이 아니면 "을(를)")
  const eul = (w) => { const c = w.charCodeAt(w.length - 1) - 0xac00; return c < 0 || c > 11171 ? "을(를)" : c % 28 ? "을" : "를"; };
  // ---- 벽·가전 옆에 착 붙기 (js/snap.js). 장·소파·침대·책상과 바닥에 세우는 LG 가전만 붙는다 ----
  const SNAP_MORE = new Set(["decor:sofa", "decor:bed", "decor:desk"]);
  const SNAP_MARGIN_M = 0.03; // 가전은 벽에서 뒤 여유 + 이만큼 띄운다 (서버 '벽에 붙이기'와 같은 값)
  const isPurifier = (sku) => prodOf(sku)?.category === "water_purifier";
  const snappable = (sku) => (isDecor(sku)
    ? (decorOf(sku)?.group === "storage" && sku !== "decor:island") || SNAP_MORE.has(sku)
    : !!prodOf(sku) && !tabletop(sku) && !isPurifier(sku));
  const sideNeed = (sku) => (isDecor(sku) ? 0 : (prodOf(sku)?.clearance_mm?.side || 0) / 1000);
  const snapAt = (sku, size, xz, yaw, skipId = null, keepYaw = false) => {
    if (!size || !room || !project || !snappable(sku)) return null;
    const gone = new Set(project.scene_state.hidden_walls || []);
    const walls = room.walls.filter((w) => !gone.has(w.wall_id)).map((w) => ({ start: w.start, end: w.end, t: w.thickness_m || 0.1 }));
    const others = project.scene_state.placements
      .filter((q) => q.placement_id !== skipId && q.size_m && !(q.base_m > 0) && q.sku !== "decor:rug" && !isPurifier(q.sku))
      .map((q) => ({ xz: q.center_xz, yaw: q.yaw_rad, w: q.size_m[0], d: q.size_m[2], side: sideNeed(q.sku) }));
    const mid = walls.reduce((a, w) => [a[0] + (w.start[0] + w.end[0]) / 2 / walls.length, a[1] + (w.start[1] + w.end[1]) / 2 / walls.length], [0, 0]);
    const back = isDecor(sku) ? 0 : (prodOf(sku)?.clearance_mm?.back || 0) / 1000 + SNAP_MARGIN_M;
    const r = snapPose({ xz, yaw, w: size[0], d: size[2], side: sideNeed(sku), backOff: back, keepYaw }, walls, others, mid);
    return r.wall || r.side || r.yaw !== yaw ? r : null;
  };
  const sizeArgs = (x) => (isDecor(x?.sku) && x.size_m ? { size_m: [...x.size_m] } : {});
  const lgOnly = (pls) => pls.filter((x) => !isDecor(x.sku));
  const HINT = {
    move: "제품이나 가구를 누르면 고를 수 있어요. 제품 위에 뜨는 메뉴로 옮기고 돌려 보세요",
    rect: "평면도에서 드래그해 영역을 그리세요 (5cm 단위).",
    poly: "꼭짓점을 차례로 누르고, 첫 점을 다시 누르거나 더블클릭하면 완성됩니다.",
  };
  let renderAct = () => {}; // 3D 아래 조작 버튼 (아래에서 채운다)
  let trackFurnX = () => {}; // 가구 치우기에서 가구마다 뜨는 ✕ 자리
  let trackFlowX = () => {}; // 동선에서 길이 막힌 제품의 ✕ 자리 (아래에서 채운다)
  const setHint = (msg) => {
    renderAct();
    if (msg) { document.getElementById("hint").textContent = msg; return; }
    document.getElementById("hint").innerHTML = armed ? (tabletop(armed)
      ? `바닥이나 <b>식탁·아일랜드·하부장 위</b>를 누르면 그 자리에 놓여요. 아래 <b>알맞은 자리에 놓기</b>도 돼요`
      : `3D 바닥에서 놓을 자리를 누르거나, 아래 <b>알맞은 자리에 놓기</b>를 눌러 보세요`) : HINT[mode];
    const u = document.getElementById("unarm");
    if (u) u.onclick = (e) => { e.preventDefault(); armed = null; ghost(null); setHint(); renderLib(); };
  };

  // ---- 제품 서랍 ----
  catalog = await api("/api/catalog");
  decorList = (await api("/api/decor").catch(() => ({ items: [] }))).items;
  // ---- 공간 꾸미기 라이브러리: 전체 / LG 가전 / 가구 / 수납 / 소품. 벽체·구조 변경은 전체 맨 위 ----
  // 벽지·바닥 색 (탭을 집이 다 열리기 전에 눌러도 되게 탭보다 먼저 둔다)
  let FIN = [];
  const finById = (id) => FIN.find((f) => f.id === id);
  const curFinish = (kind) => project?.scene_state.finish_ids?.[kind] || null;
  const finishSet = () => Object.fromEntries(["wall", "floor"].map((k) => [k, finById(curFinish(k)?.id)]).filter(([, f]) => f));
  const FIN_KIND = [["wall", "벽지"], ["floor", "바닥"]];
  const toneLabel = (f, t) => `${TEXTURE_KO[f.texture]} ${t.name.replace(/ 톤$/, "")}`;
  const finChip = (f, t) => {
    const cur = curFinish(f.kind), on = cur?.id === f.id && cur.tone === t.hex, label = toneLabel(f, t);
    return `<button class="fin-sw${on ? " on" : ""}" data-fin="${esc(f.id)}" data-tone="${esc(t.hex)}" role="radio" aria-checked="${on}" aria-label="${esc(label)}" title="${esc(label)}"><img src="${swatchUrl(f, t.hex, 96)}" alt="" width="48" height="48" draggable="false"></button>`;
  };
  const libAside = studio.querySelector(".lib");
  const TABS = ["all", "lg", "furniture", "storage", "decor", "finish"];
  let libTab = TABS.includes(saved.libTab) ? saved.libTab : "lg"; // 가전을 사러 온 사람이 먼저 보는 것은 가전
  const SECTION = [["structure", "벽체 & 구조 변경"], ["furniture", "가구"], ["storage", "수납 & 선반"], ["decor", "인테리어 소품"]];
  const tileHtml = (d) => `<button class="dtile" data-decor="${esc(d.sku)}" draggable="true" title="${esc(d.label)} 놓기">
      <span class="dimg"><img src="img/decor/${esc(d.model)}.webp" alt="" loading="lazy" decoding="async" draggable="false" onerror="this.remove()"></span><span>${esc(d.label)}</span></button>`;
  const wallTile = () => `<button class="dtile ${wallPicking ? "on" : ""}" id="wallRm" aria-pressed="${wallPicking}" title="3D에서 철거할 벽을 눌러요">
      <span class="dimg"><img src="img/decor/wall-remove.webp" alt="" loading="lazy" decoding="async" draggable="false" onerror="this.remove()"></span><span>${wallPicking ? "벽 고르는 중" : "벽 제거"}</span></button>`;
  function renderDecorLib() {
    const box = document.getElementById("decorLib");
    if (libTab === "finish") { renderFinishes(); return; }
    const groups = libTab === "all" ? SECTION : SECTION.filter(([g]) => g === libTab);
    box.innerHTML = libTab === "lg" ? "" : (libTab === "all" ? `<button class="dsec-lg" data-go="lg">LG 가전 고르러 가기 <span aria-hidden="true">›</span></button>` : "") + groups.map(([g, title]) => {
      const items = decorList.filter((d) => d.group === g);
      const tiles = (g === "structure" ? [items.find((d) => d.sku === "decor:wall")].filter(Boolean).map(tileHtml).join("") + wallTile() + items.filter((d) => d.sku !== "decor:wall").map(tileHtml).join("") : items.map(tileHtml).join(""));
      return `<section class="dsec"><h3>${esc(title)}</h3><div class="dgrid">${tiles}</div></section>`;
    }).join("");
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
    if (t === "lg") syncCatsMore(); // 탭이 가려져 있을 때는 칩 높이를 잴 수 없다
  };
  document.querySelectorAll("#libTabs [data-tab]").forEach((b) => (b.onclick = () => setLibTab(b.dataset.tab)));
  // 고른 꾸미기 가구: 위치·회전·크기 조절·주변 간격만 (가격·출처 같은 제품 정보는 없다)
  const LONG = new Set(["decor:wall", "decor:partition"]); // 길이만 바꾸는 것
  // 먼저 이 공간을 어떤 용도로 쓸지 묻고, 그 용도에 맞는 가전 종류부터 보여 준다 (카탈로그 zone_fit 기준)
  const ORDER = CATEGORY_GROUP.flatMap(([, , cs]) => cs);
  const rank = (c) => (ORDER.indexOf(c) < 0 ? 999 : ORDER.indexOf(c));
  const catsFor = (pu) => [...new Set(catalog.filter((p) => (p.demo_only || !catalog.some((x) => x.sale_status) || p.sale_status === "ACTIVE" || p.sale_status === "SOLD_OUT") && (!pu || (p.zone_fit || []).includes(pu))).map((p) => p.category))].sort((a, b) => rank(a) - rank(b));
  const USES = Object.keys(USE).filter((k) => catsFor(k).length);
  let use = USES.includes(saved.use) ? saved.use : ""; // "": 용도를 안 골랐으면 전체
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
    // 용도를 고르면 그 공간에 어울리는 품목만 남는다. 다시 누르면 전체로
    const ask = document.getElementById("ask");
    ask.innerHTML = `<p class="ask-q">이 공간을 어떤 용도로 쓰실 건가요?</p><div class="chips use-chips">${USES.map((k) => `<button class="chip ${use === k ? "on" : ""}" data-use="${esc(k)}" aria-pressed="${use === k}">${esc(USE[k])}</button>`).join("")}</div>`;
    ask.querySelectorAll("[data-use]").forEach((b) => (b.onclick = () => setScope({ use: use === b.dataset.use ? "" : b.dataset.use })));
    document.getElementById("cats").innerHTML = catsFor(use || "").map((c) => `<button class="chip ${cat === c ? "on" : ""}" data-cat="${esc(c)}" aria-pressed="${cat === c}">${esc(CATEGORY[c] || c)}</button>`).join("");
    document.querySelectorAll("[data-cat]").forEach((b) => (b.onclick = () => setScope({ cat: cat === b.dataset.cat ? "" : b.dataset.cat })));
    syncCatsMore();
  };
  // 품목이 많으면 두 줄만 보이고 나머지는 '품목 더 보기'로 (고른 품목이 가려져 있으면 펼쳐 둔다)
  let catsOpen = false;
  const syncCatsMore = () => {
    const box = document.getElementById("cats"), more = document.getElementById("catsMore");
    const on = box.querySelector(".chip.on");
    box.classList.remove("clip");
    const tall = box.scrollHeight > CATS_CLIP_PX + 8;
    if (on && on.offsetTop - box.offsetTop > CATS_CLIP_PX - 8) catsOpen = true;
    box.classList.toggle("clip", tall && !catsOpen);
    more.hidden = !tall;
    more.textContent = catsOpen ? "품목 접기" : "품목 더 보기";
    more.setAttribute("aria-expanded", catsOpen);
  };
  document.getElementById("catsMore").onclick = () => { catsOpen = !catsOpen; syncCatsMore(); };
  // 같은 모델의 색·재질 다른 SKU는 한 줄로 묶고, 색·재질은 동그라미로 고른다
  const families = await api("/api/catalog/families");
  const familyOf = (sku) => families.find((f) => f.variants.some((v) => v.sku === sku));
  const onTops = new Set(families.flatMap((f) => f.variants.filter((v) => v.tabletop).map((v) => v.sku)));
  tabletop = (sku) => onTops.has(sku); // 가구 위에 올려 둘 수 있는 가전 (서버가 정한다)
  const pick = {}; // family_id → 고른 SKU
  const finishLabel = (v) => [v.color, v.material].filter(Boolean).join(" · ");
  // 목록 카드의 색 동그라미는 색마다 하나만
  // 색 점은 LGE.COM에 색 이름이 있는 것만 (hex_approx는 3D 근사색이라 색상 표시로 쓰지 않는다)
  const colorDots = (f) => f.variants.filter((x, i, a) => x.color && a.findIndex((y) => y.color === x.color && y.hex === x.hex) === i);
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
  const pickStep = (key, val) => {
    if (sel[key] === val) delete sel[key]; else sel[key] = val;
    saveUiState(pid, { sel });
    renderLib();
  };
  // 설치 방식(빌트인·일반)은 둘 중 하나를 고르는 버튼으로 늘 보이게, 나머지 옵션은 상세 필터 안에
  const renderInstall = (variants) => {
    const n = installCounts(variants), box = document.getElementById("installSeg");
    box.innerHTML = ["빌트인", "일반"].map((k) => `<button data-install="${k}" aria-pressed="${sel.install === k}" class="${sel.install === k ? "on" : ""}" ${n[k] || sel.install === k ? "" : "disabled"}>${k} <span class="n">(${n[k].toLocaleString("ko-KR")})</span></button>`).join("");
    box.querySelectorAll("[data-install]").forEach((b) => (b.onclick = () => pickStep("install", b.dataset.install)));
  };
  const renderSteps = (steps) => {
    const rest = steps.filter((st) => st.key !== "install");
    document.getElementById("steps").innerHTML = stepsHtml(rest);
    document.getElementById("stepsHint").hidden = !!cat || rest.length > 0;
    document.querySelectorAll("#steps [data-step]").forEach((b) => (b.onclick = () => pickStep(b.dataset.step, b.dataset.val)));
  };
  // 이 집에 들어가는 제품: 지금 목록 앞쪽 후보를 서버가 벽을 따라 놓아 보고(find_spot) 들어가는 것만 3개
  let recSkus = new Set(), suggItems = [], suggKey = "", suggTimer = 0, suggPool = [], suggReady = false;
  const isRec = (f) => f.variants.some((v) => recSkus.has(v.sku));
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
    box.querySelectorAll("[data-scat]").forEach((b) => (b.onclick = () => setScope({ cat: b.dataset.scat })));
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
  // ---- 필터 상태: 적용된 조건은 목록 위 칩으로 보여 주고, ×로 하나씩 뺀다 ----
  const qEl = document.getElementById("q"), fWEl = document.getElementById("fW"), fHEl = document.getElementById("fH");
  const filterBox = document.getElementById("filterBox");
  const filterState = () => ({ cat, sel, budget, fW: fWEl.value, fH: fHEl.value, q: qEl.value.trim() });
  const setFilterState = (st) => {
    const catChanged = st.cat !== cat;
    cat = st.cat; sel = st.sel; budget = st.budget; fWEl.value = st.fW; fHEl.value = st.fH; qEl.value = st.q;
    saveUiState(pid, { cat, sel });
    if (catChanged) renderCats();
    renderLib();
  };
  const renderApplied = () => {
    const chips = appliedFilters(filterState(), { cat: CATEGORY }), box = document.getElementById("applied");
    box.hidden = !chips.length;
    box.innerHTML = chips.map((c) => `<button class="fchip" data-clear="${esc(c.key)}" aria-label="${esc(c.label)} 조건 빼기"><span>${esc(c.label)}</span><i aria-hidden="true">×</i></button>`).join("");
    box.querySelectorAll("[data-clear]").forEach((b) => (b.onclick = () => setFilterState(clearFilter(filterState(), b.dataset.clear))));
    const n = chips.length, fn = document.getElementById("filterN"), dn = detailCount(filterState()), fo = document.getElementById("filterOn");
    fn.hidden = !n; fn.textContent = n;
    fo.hidden = !dn; fo.textContent = `${dn}개 적용`;
    document.getElementById("applyFilter").textContent = n ? `적용하기 (${n})` : "적용하기";
    document.getElementById("resetFilter").disabled = !n;
  };
  document.getElementById("resetFilter").onclick = () => setFilterState({ cat: "", sel: {}, budget: null, fW: "", fH: "", q: "" });
  // 적용하기: 필터 칸을 접고 고른 조건의 제품 목록을 바로 보여 준다 (조건은 고르는 대로 이미 반영돼 있다)
  const openFilter = (on) => { filterBox.open = on; saveUiState(pid, { filterOpen: on }); };
  document.getElementById("applyFilter").onclick = () => {
    openFilter(false);
    libAside.scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  };
  filterBox.addEventListener("toggle", () => { saveUiState(pid, { filterOpen: filterBox.open }); if (filterBox.open) syncCatsMore(); });
  if (saved.filterOpen === true) filterBox.open = true; // 처음에는 접어 둔다: 제품이 먼저 보이게
  // ---- 가격 범위: 지금 보이는 종류(예: 냉장고)의 실제 가격 범위 안에서 손잡이 두 개나 금액 입력으로 예산을 맞춘다 ----
  let budget = null, budgetScope = "", scale = null; // budget: {lo, hi} (원), 범위 전체면 null. scale: 눈금 {lo, hi, step, open}
  const pLo = document.getElementById("pLo"), pHi = document.getElementById("pHi"), pLoIn = document.getElementById("pLoIn"), pHiIn = document.getElementById("pHiIn");
  const rail = document.getElementById("budgetRail");
  const man = (v) => Math.round(v / 1e4).toLocaleString("ko-KR");
  const pricesOf = (f) => f.variants.filter((v) => typeof v.price_krw === "number" && (f.demo_only || sellable(v))).map((v) => v.price_krw);
  const paintBudget = () => {
    const lo = +pLo.value, hi = +pHi.value, span = scale.hi - scale.lo || 1;
    rail.style.setProperty("--a", (lo - scale.lo) / span);
    rail.style.setProperty("--b", (hi - scale.lo) / span);
    if (document.activeElement !== pLoIn) pLoIn.value = man(lo);
    if (document.activeElement !== pHiIn) pHiIn.value = man(hi);
    document.getElementById("pHiUnit").textContent = scale.open && hi >= scale.hi ? "만원 이상" : "만원";
    pLo.setAttribute("aria-valuetext", wonText(lo)); pHi.setAttribute("aria-valuetext", wonText(hi));
  };
  const setupBudget = (list) => {
    const ps = list.flatMap(pricesOf), box = document.getElementById("budget");
    box.hidden = ps.length < 2;
    if (box.hidden) { budget = null; return; }
    scale = priceScale(ps);
    const key = `${cat}|${use}`;
    if (key !== budgetScope) { budgetScope = key; budget = null; } // 종류가 바뀌면 그 종류의 전체 범위로
    for (const r of [pLo, pHi]) Object.assign(r, { min: scale.lo, max: scale.hi, step: scale.step });
    // 끝에 닿아 있던 손잡이는 범위가 바뀌어도 끝에 둔다 (그쪽은 제한이 없다는 뜻이니까)
    pLo.value = budget && !budget.atMin ? Math.min(scale.hi, Math.max(scale.lo, budget.lo)) : scale.lo;
    pHi.value = budget && !budget.atMax ? Math.max(scale.lo, Math.min(scale.hi, budget.hi)) : scale.hi;
    paintBudget();
  };
  const inBudget = (f) => !budget || pricesOf(f).some((v) => (budget.atMin || v >= budget.lo) && (budget.atMax || v <= budget.hi));
  let budgetTimer = 0;
  const commitBudget = (lo, hi) => {
    pLo.value = lo; pHi.value = hi;
    budget = lo <= scale.lo && hi >= scale.hi ? null : { lo, hi, atMin: lo <= scale.lo, atMax: hi >= scale.hi };
    paintBudget();
    clearTimeout(budgetTimer); budgetTimer = setTimeout(renderLib, 120); // 끄는 동안은 숫자만, 손을 멈추면 목록
  };
  const onBudget = (e) => {
    let lo = +pLo.value, hi = +pHi.value;
    if (lo > hi) { if (e.target === pLo) lo = hi; else hi = lo; }
    commitBudget(lo, hi);
  };
  pLo.oninput = onBudget; pHi.oninput = onBudget;
  // 금액을 직접 넣기 (만 원). 범위를 벗어나면 가장 가까운 값으로 맞춘다
  const onBudgetType = (e) => {
    if (!scale) return;
    const v = parseManwon(e.target.value, scale);
    let lo = +pLo.value, hi = +pHi.value;
    if (v != null) { if (e.target === pLoIn) lo = Math.min(v, hi); else hi = Math.max(v, lo); }
    e.target.blur();
    commitBudget(lo, hi);
  };
  for (const el of [pLoIn, pHiIn]) {
    el.onchange = onBudgetType;
    el.onfocus = () => el.select();
  }
  const renderLib = () => {
    const q = qEl.value.trim();
    const fW = fWEl.value, fH = fHEl.value;
    const scope = shop.filter((f) => inScope(f.category));
    const all = scope.flatMap((f) => f.variants.map((v) => ({ ...v, fam: f.family_id }))); // 칩의 숫자를 모델 수로 세려고 모델을 달아 둔다
    const found = (f) => matchesQuery(q, { words: [CATEGORY[f.category], f.name, ...f.variants.flatMap((v) => [v.sku, v.color, v.options?.kind, v.options?.door_type])],
      liters: f.variants.map((v) => v.options?.capacity_l).filter(Boolean) });
    // 종류를 아직 안 골랐으면 설치 방식(빌트인/일반)만, 골랐으면 그 종류의 옵션을 차례로
    const narrowed = optionSteps(all, sel, cat ? null : ["install"]);
    sel = narrowed.sel;
    renderInstall(optionSteps(all, { ...sel, install: undefined }, cat ? null : ["install"]).remaining);
    renderSteps(narrowed.steps);
    const left = new Set(narrowed.remaining.map((v) => v.sku));
    scope.forEach((f) => { // 고른 옵션에 맞는 SKU를 그 모델의 대표로
      if (!left.has(pick[f.family_id] || f.variants[0].sku)) { const v = f.variants.find((x) => left.has(x.sku)); if (v) pick[f.family_id] = v.sku; }
    });
    const pre = scope.filter((f) => f.variants.some((v) => left.has(v.sku)) && found(f)
      && inRange(f.product_dims_mm?.w, fW) && inRange(f.product_dims_mm?.h, fH));
    setupBudget(pre);
    const items = pre.filter(inBudget);
    if (budget) items.forEach((f) => { // 카드에 보이는 대표 모델도 고른 가격 범위 안의 것으로
      const ok = (v) => typeof v?.price_krw === "number" && (budget.atMin || v.price_krw >= budget.lo) && (budget.atMax || v.price_krw <= budget.hi);
      const cur = f.variants.find((v) => v.sku === pick[f.family_id]) || f.variants[0];
      if (!ok(cur)) { const v = f.variants.find((x) => left.has(x.sku) && ok(x)); if (v) pick[f.family_id] = v.sku; }
    });
    suggPool = items.filter((f) => !f.demo_only && f.product_dims_mm?.w && f.product_dims_mm?.h && f.product_dims_mm?.d)
      .slice(0, SUGG_POOL).map((f) => pick[f.family_id] || f.variants[0].sku);
    scheduleSuggest();
    const sortBy = document.getElementById("sortBy").value;
    const priceOf = (f) => (f.variants.find((v) => v.sku === pick[f.family_id]) || f.variants[0]).price_krw ?? Infinity;
    const sizeOf = (f) => { const d = f.product_dims_mm || {}; return d.w && d.d ? d.w * d.d : Infinity; };
    items.sort((a, b) => a.demo_only - b.demo_only || (sortBy === "price" ? priceOf(a) - priceOf(b) : sortBy === "size" ? sizeOf(a) - sizeOf(b) : 0)
      || isRec(b) - isRec(a)); // 기본: 이 집에 들어가는 제품을 위로
    renderApplied();
    document.getElementById("libCount").innerHTML = `<b>${items.length.toLocaleString("ko-KR")}</b>개 모델`;
    document.getElementById("lib").innerHTML = items.map((f) => {
      const d = f.product_dims_mm || {}, sized = d.w && d.h && d.d;
      const sku = pick[f.family_id] || f.variants[0].sku, v = f.variants.find((x) => x.sku === sku);
      const dots = colorDots(f), many = dots.length > 1;
      return `<li class="prod ${f.variants.some((x) => x.sku === armed) ? "armed" : ""} ${sized ? "" : "nosize"}" draggable="${sized ? "true" : "false"}" data-sku="${esc(sku)}">
        <i class="dot tile thumb" style="--tint:${esc(v.hex || "#fff")}${v.thumb ? "" : `;background:${esc(v.hex || "#fff")}`}">${v.thumb ? `<img src="${esc(v.thumb)}" alt="${esc(f.name)} ${esc(finishLabel(v))}" loading="lazy" decoding="async" draggable="false">` : ""}<span>${esc(CATEGORY[f.category] || f.category)}</span></i>
        <div class="body"><div class="name">${esc(f.name)}</div>
          ${f.demo_only ? "" : `<div class="model">${esc(sku)}</div>`}
          ${sized ? "" : `<div class="cat">치수 정보 없음</div>`}
          ${typeof v.price_krw === "number" ? `<div class="price">${v.price_krw.toLocaleString("ko-KR")}원</div>` : ""}
          ${f.demo_only ? `<span class="badge demo">가상 데이터 · 실제 제품 아님</span>` : ""}</div>
        <div class="card-foot">
          ${v.color ? `<div class="color-row"><span class="vk">색상</span>${many ? `<span class="variants" role="radiogroup" aria-label="색상 고르기">${dots.slice(0, MAX_DOTS).map((x) => { const on = x.color === v.color && x.hex === v.hex; return `<button class="vsw ${on ? "on" : ""}" data-fam="${esc(f.family_id)}" data-pick="${esc(on ? sku : x.sku)}" title="${esc(finishLabel(x))}" aria-label="${esc(finishLabel(x))}" role="radio" aria-checked="${on}"><i style="background:${esc(x.hex || "#fff")}"></i></button>`; }).join("")}${dots.length > MAX_DOTS ? `<span class="more-dots" title="상세에서 색상 ${dots.length}가지를 모두 볼 수 있어요">+${dots.length - MAX_DOTS}</span>` : ""}</span>` : `<span class="one-color">${esc(v.color)}</span>`}</div>` : `<span></span>`}
          ${sized && !f.demo_only ? `<button class="small place-btn" data-place="${esc(sku)}" aria-label="${esc(f.name)} 공간에 배치하기" title="공간에 배치하기">배치하기</button>` : ""}</div></li>`;
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
  // 지예: 색 칩에 모델 번호가 붙어 20개 넘게 늘어지면 보기 싫다 → 칩은 색마다 하나, 같은 색 안의 모델은 작은 목록에서 고른다
  const pdOptions = (f, sku) => {
    const opts = f.variants.filter((x) => f.demo_only || sellable(x) || x.sku === sku);
    const cur = opts.find((x) => x.sku === sku) || f.variants.find((x) => x.sku === sku) || {};
    const groups = [];
    opts.forEach((x) => { const k = finishLabel(x); const g = groups.find((y) => y.k === k); if (g) g.items.push(x); else groups.push({ k, items: [x] }); });
    const mine = groups.find((g) => g.k === finishLabel(cur)) || { items: [cur] };
    const chips = groups.length > 1 || groups[0]?.k
      ? `<div class="pd-variants" role="radiogroup" aria-label="색상 옵션">${groups.filter((g) => g.k).map((g) => { const on = g === mine, to = on ? sku : g.items[0].sku, x = g.items[0];
        return `<button class="swatch ${on ? "on" : ""}" data-pd-variant="${esc(to)}" role="radio" aria-checked="${on}"><i style="background:${esc(x.hex || "#fff")}"></i>${esc(g.k)}</button>`; }).join("")}</div>`
      : "";
    const models = mine.items.length > 1
      ? `<label class="pd-model"><span>모델</span><select id="pdModel" aria-label="모델 고르기">${mine.items.map((x) => `<option value="${esc(x.sku)}" ${x.sku === sku ? "selected" : ""}>${esc(x.sku)}</option>`).join("")}</select></label>`
      : "";
    return chips + models;
  };
  const closeDetail = () => { pdModal.hidden = true; pdModal.innerHTML = ""; };
  // 지예: 들어가는지는 넣고 나서 3D에서 판단한다 (초록/빨강). 상세 창에는 판정 줄을 두지 않는다
  const openDetail = (sku) => {
    const p = prodOf(sku), f = familyOf(sku);
    if (!p || !f) return;
    pick[f.family_id] = sku;
    const v = f.variants.find((x) => x.sku === sku) || {};
    const d = p.product_dims_mm || {}, sized = d.w && d.h && d.d;
    // 지예: 상세 창이 조잡하다 → 크기·색만 짧게 (설치 방식·옵션·모델명 표는 뺀다, 모델명은 제목 아래에)
    const o = p.options || {};
    const cap = o.capacity_l ? `${mm(o.capacity_l)} L` : o.capacity || [o.wash_kg && `세탁 ${o.wash_kg} kg`, o.dry_kg && `건조 ${o.dry_kg} kg`].filter(Boolean).join(" · ");
    const price = typeof v.price_krw === "number" ? v.price_krw : p.price_krw;
    // 살지 말지 정하려면 가격과 용량은 있어야 한다. 그 밖의 표는 넣지 않는다
    const rows = [
      ["용량", cap ? esc(String(cap)) : ""],
      ["크기", sized ? `${mm(d.w)} × ${mm(d.h)} × ${mm(d.d)} mm <span class="muted">(폭 × 높이 × 깊이)</span>` : ""],
      ["색상", esc(finishLabel(v))],
    ].filter(([, val]) => val);
    pdModal.innerHTML = `
      <div class="pd-top">
        <div class="pd-photo${v.thumb ? " has-photo" : ""}" style="background-color:${esc(v.hex || "#fff")}${v.thumb ? `;background-image:url('${esc(v.thumb)}')` : ""}" role="img" aria-label="${esc(f.name)} ${esc(finishLabel(v))}"><span>${esc(CATEGORY[p.category] || p.category)}</span></div>
        <div class="pd-title">
          <h2>${esc(f.name)}</h2>
          <p class="muted">${esc(CATEGORY[p.category] || p.category)} · ${esc(sku)}</p>
          ${typeof price === "number" ? `<p class="pd-price">${price.toLocaleString("ko-KR")}원</p>` : ""}
          ${f.demo_only ? `<span class="badge demo">가상 데이터 · 실제 제품 아님</span>` : ""}
          ${pdOptions(f, sku)}
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
    const pdModel = document.getElementById("pdModel");
    if (pdModel) pdModel.onchange = () => { openDetail(pdModel.value); renderLib(); };
    document.getElementById("pdClose").onclick = closeDetail;
    const place = document.getElementById("pdPlace");
    if (sized) place.onclick = () => {
      closeDetail();
      if (walking) setWalking(false);
      openLib(false); // 앱에서는 서랍을 내려 3D 바닥이 보이게
      autoPlace(sku); // 목록의 배치하기와 똑같이: 알맞은 자리에 바로 놓고, 옮기는 건 그다음에
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
  let armedYaw = Math.PI / 2, armedVerdict = "unknown", lastHover = null, armedTurned = false;
  const armedSize = (sku) => {
    const d = isDecor(sku) ? decorOf(sku)?.size_mm : prodOf(sku)?.product_dims_mm;
    return d?.w && d?.h && d?.d ? [d.w / 1000, d.h / 1000, d.d / 1000] : null;
  };
  const showFollow = (center_xz, yaw_rad, size_m, verdict, sku) => {
    const res = { pose: { center_xz, yaw_rad }, size_m, verdict };
    const g = document.getElementById("ghost");
    if (g && pv) g.innerHTML = placedSvg({ center_xz, yaw_rad, size_m, verdict }, pv.sw, false, true);
    viewer.setGhost({ ...res, sku, hex: prodOf(sku)?.cmf_options[0]?.hex_approx, surface: tabletop(sku) ? "product" : null });
  };
  // 벽을 그리는 동안 Shift를 누르고 있으면 기존 벽과 나란하거나 직각으로, 가까운 벽에 딱 붙게 맞춘다
  let shiftDown = false;
  const standingWalls = () => { const gone = new Set(project.scene_state.hidden_walls || []); return room.walls.filter((w) => !gone.has(w.wall_id)); };
  const wallAt = (p) => (!shiftDown || !wallDraw ? p : wallDraw.start ? straighten(wallDraw.start, p, standingWalls()) : snapStart(p, standingWalls()));
  const onShift = (e) => { if (e.key !== "Shift" || shiftDown === (e.type === "keydown")) return; shiftDown = e.type === "keydown"; if (wallDraw && lastHover) follow(lastHover); };
  document.addEventListener("keydown", onShift); document.addEventListener("keyup", onShift);
  cleanup.push(() => { document.removeEventListener("keydown", onShift); document.removeEventListener("keyup", onShift); });
  const follow = (p) => {
    lastHover = p;
    if (armedRouter && !armed) { viewer.routerFollow(p); return; }
    if (armedStart && !armed) { viewer.personFollow(p); return; }
    if (mode !== "move" || wallPicking) return;
    if (wallDraw) { // 가벽: 시작점 전에는 기둥 하나, 시작점을 찍은 뒤에는 시작점부터 마우스까지 벽
      const a = wallDraw.start;
      p = wallAt(p);
      if (!a) { showFollow(p, Math.PI / 2, [WALL_T, WALL_H, WALL_T], "fit", "decor:wall"); return; }
      const len = Math.hypot(p[0] - a[0], p[1] - a[1]), ang = Math.atan2(p[1] - a[1], p[0] - a[0]);
      showFollow([(a[0] + p[0]) / 2, (a[1] + p[1]) / 2], ang + Math.PI / 2, [Math.max(len, WALL_T), WALL_H, WALL_T], len < WALL_MIN ? "no_fit" : "fit", "decor:wall");
      return;
    }
    if (!armed) return;
    const size = armedSize(armed);
    const at = () => { // 벽·가전 옆에 가까우면 붙은 자리, 아니면 마우스 그대로
      const sn = lastHover && snapAt(armed, size, lastHover, armedYaw, null, armedTurned);
      return sn ? { xz: sn.xz, yaw: sn.yaw, snap: false } : { xz: lastHover, yaw: armedYaw };
    };
    const a = at();
    if (size) showFollow(a.xz, a.yaw, size, armedVerdict, armed);
    preview({ sku: armed, center_xz: a.xz, yaw_rad: a.yaw, ...(a.snap === false ? { snap: false } : {}) }, (r) => { // 판정 색과 남는 틈
      if (!armed || !hovering) return;
      armedVerdict = r.verdict;
      const b = lastHover && at();
      if (b) showFollow(b.xz, b.yaw, size || r.size_m, armedVerdict, armed);
      if (a.snap === false) showGaps(r); else showGaps(null);
    });
  };
  const arm = (sku) => {
    if (wallPicking) setWallPick(false);
    if (wallDraw) setWallDraw(false);
    armed = sku; armedYaw = Math.PI / 2; armedVerdict = "unknown"; armedTurned = false; mode = "move";
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
    if (step.kind === "winHide" || step.kind === "winShow") {
      const on = step.kind === "winHide";
      await put(`/api/projects/${pid}/openings/${step.id}/hidden`, { hidden: on });
      return { kind: on ? "winShow" : "winHide", id: step.id };
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
    const yaw0 = armed === sku ? armedYaw : Math.PI / 2;
    const sn = snapAt(sku, armedSize(sku), p, yaw0, null, armed === sku && armedTurned); // 미리 보기에서 붙어 있던 그 자리에 놓는다
    showGaps(null);
    const r = await post(`/api/projects/${pid}/placements`, sn ? { sku, center_xz: sn.xz, yaw_rad: sn.yaw, snap: false } : { sku, center_xz: p, yaw_rad: yaw0 });
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
  // 바닥을 눌렀을 때 할 일 (평면·3D 공통): 동선 출발 자리, 공유기 놓기, 제품 놓기
  const floorAction = (p) => {
    if (mode !== "move") return false;
    if (armedStart && !armed) { // "어디서 출발할까요?" (제품을 들고 있으면 제품 놓기가 먼저): 누른 자리에 사람을 세우고 거기서 걷기 시작
      armedStart = false;
      viewer.personFollow(null);
      guard(async () => {
        try { project = await put(`/api/projects/${pid}/marks/start`, { center_xz: p }); }
        finally { if (simOn("flow")) await flowCtl(); } // 저장이 안 됐으면 flowCtl이 다시 묻는다
      })();
      return true;
    }
    if (armedRouter && !armed) {
      armedRouter = false;
      viewer.routerFollow(null); // 서버가 높이까지 정해 돌려주면 그 자리로 (실패하면 원래 자리)
      guard(async () => { project = await put(`/api/projects/${pid}/router`, { center_xz: p, band }); if (simOn("wifi")) await wifiCtl(); })();
      return true;
    }
    if (wallDraw) { wallPoint(wallAt(p)); return true; }
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
      return rt && { kind: "router", id: "router", xz: [...rt.center_xz], yaw: rt.yaw_rad ?? 0, surface: "router" };
    }
    if (hit.type === "placement") {
      const x = project.scene_state.placements.find((q) => q.placement_id === hit.id);
      return x && { kind: "placement", id: x.placement_id, xz: [...x.center_xz], yaw: x.yaw_rad, surface: x.tabletop ? "product" : null };
    }
    const o = objOf(hit.id);
    return o && { kind: "object", id: o.object_id, xz: [o.position[0], o.position[2]], yaw: o.yaw_rad };
  };
  const pickUp = (hit, point) => {
    const item = poseOf(hit);
    if (item && viewer.hold(item, point)) setHint(item.surface === "product"
      ? "들고 있어요: 식탁·아일랜드·하부장 위를 가리키면 그 위로 올라가요 · 바닥을 누르면 내려놓기 · R 돌리기 · Esc 취소 · Delete 지우기"
      : "들고 있어요: 놓을 곳을 누르세요 · R 돌리기(Shift 반대, Alt 15°) · 방향키 살짝 옮기기 · Esc 취소 · Delete 지우기");
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
      if (x) { x.center_xz = [...it.xz]; x.yaw_rad = it.yaw; if (it.baseY !== undefined) x.base_m = it.baseY; }
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
      if (simOn("wifi")) await runWifi();
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
  const CAM_KEYS = ["w", "a", "s", "d", "q", "e"];
  const onKeyUp = (e) => { const k = e.key.length === 1 ? e.key.toLowerCase() : e.key; if (CAM_KEYS.includes(k)) viewer?.camKey(k, false); if (k === "e") viewer?.spinKey(false); };
  const camKeysOff = () => viewer?.camKeysOff();
  document.addEventListener("keyup", onKeyUp);
  window.addEventListener("blur", camKeysOff);
  cleanup.push(() => { document.removeEventListener("keyup", onKeyUp); window.removeEventListener("blur", camKeysOff); });
  const onKey = (e) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
    if (viewer.walking()) return; // 둘러보기 중에는 걷기 키만 (뷰어가 받는다)
    const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    if (k === "z" && (e.ctrlKey || e.metaKey) && !e.shiftKey && wallDraw?.start) { // 그리던 벽의 시작점만 되돌린다 (앞서 한 일까지 되돌리지 않게)
      e.preventDefault(); wallDraw = {}; setHint("벽을 세울 시작점을 바닥에서 누르세요 · Esc 취소"); if (lastHover) follow(lastHover); return;
    }
    if (k === "z" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); if (e.shiftKey) redo(); else undo(); return; }
    if (k === "y" && e.ctrlKey) { e.preventDefault(); redo(); return; }
    if (k === "Escape") { if (armedRouter && project.scene_state.router) { armedRouter = false; viewer.routerFollow(null); wifiCtl(); } if (armedStart && project.scene_state.marks?.start) { armedStart = false; viewer.personFollow(null); flowCtl(); } viewer.cancelHold(); armed = null; ghost(null); if (wallPicking) setWallPick(false); if (wallDraw) setWallDraw(false); setHint(); renderLib(); return; }
    const in3d = studio.dataset.view !== "plan";
    // 카메라: WASD 이동, Q/E 돌기 (3D가 보일 때)
    if (k === "e" && viewer.held()) { viewer.spinKey(true); e.preventDefault(); return; } // 잡은 물건 돌리기
    if (in3d && !e.ctrlKey && !e.metaKey && CAM_KEYS.includes(k)) { viewer.camKey(k, true); e.preventDefault(); return; } // 누르고 있는 동안 움직인다
    if (armed && (k === "r" || k === "." || k === ",")) { // 들고 있는 물건 돌리기
      armedYaw += (k === "," || e.shiftKey ? -1 : 1) * (e.altKey ? ROT_FINE : ROT_STEP);
      armedTurned = true; // 직접 돌린 방향은 벽이 다시 돌려놓지 않는다
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
    if (on) { selPl = null; selObj = null; armed = null; ghost(null); renderInspector(); setHint("벽을 세울 시작점을 바닥에서 누르세요 · Shift를 누르고 있으면 벽에 딱 붙어요 · Esc 취소"); }
    else setHint();
    renderDecorLib();
  };
  wallPoint = guard(async (p) => {
    if (!wallDraw.start) { wallDraw.start = p; setHint("끝점을 누르세요 · Shift를 누르고 있으면 반듯하게 맞춰져요 · Ctrl+Z 시작점 다시 · Esc 취소"); return; }
    const [a, b] = [wallDraw.start, p], len = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (len < WALL_MIN) { toast("벽이 너무 짧아요. 30 cm 넘게 떨어진 곳을 눌러 주세요", true); return; }
    const ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
    setWallDraw(false);
    const r = await post(`/api/projects/${pid}/placements`, {
      sku: "decor:wall", center_xz: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], yaw_rad: ang + Math.PI / 2, snap: false, size_m: [len, WALL_H, WALL_T] });
    remember({ kind: "remove", id: r.placement.placement_id });
    selPl = r.placement.placement_id; selObj = null;
    toast(`벽을 세웠어요 (길이 ${mm(len * 1000)} mm). '크기 조절'에서 mm로 바꿀 수 있어요`);
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
    color: '<path d="M12 3.5c3 3.6 5.5 6.4 5.5 9.6a5.5 5.5 0 0 1-11 0c0-3.2 2.5-6 5.5-9.6z"/>',
    fill: '<path d="M4 4v16M20 4v16M8 12h8M8 12l3-3M8 12l3 3M16 12l-3-3M16 12l-3 3"/>',
  };
  // 조작 메뉴는 고른 제품 바로 위에 따라붙는다 (큰 화면). 앱 배치는 아래 고정
  let actRaf = 0;
  // 도면 위에 지금 3D에서 보고 있는 방향을 부채꼴로
  let camSeen = "";
  // 보는 쪽으로 퍼지는 시야: 선 자리에서 진하고 멀어질수록 옅어진다 (테두리 선 없이)
  const FAN_M = 2.6, FAN_HALF = 0.55, FAN_STEPS = 8;
  const viewFan = (x, z, a) => {
    const g = document.getElementById("camFade");
    if (g) { g.setAttribute("cx", x); g.setAttribute("cy", z); g.setAttribute("r", FAN_M); }
    const arc = Array.from({ length: FAN_STEPS + 1 }, (_, i) => { const t = a - FAN_HALF + (2 * FAN_HALF * i) / FAN_STEPS; return `${x + FAN_M * Math.cos(t)},${z + FAN_M * Math.sin(t)}`; });
    return `${x},${z} ${arc.join(" ")}`;
  };
  const trackCam = () => {
    const m = document.getElementById("camMark"), d = document.getElementById("camDot");
    if (!m || !viewer || studio.dataset.view !== "3d") return;
    if (walking) { // 걸어 보기: 지금 선 자리에서 보는 쪽으로 부채꼴, 들를 곳 가까이 가면 줄에도 표시
      const w = viewer.walkInfo(), x = w.pos[0], z = w.pos[2], a = Math.atan2(-Math.cos(w.yaw), -Math.sin(w.yaw));
      camSeen = "";
      m.setAttribute("points", viewFan(x, z, a));
      d.setAttribute("cx", x); d.setAttribute("cy", z);
      if (!w.gliding) { const n = nearestStop(stops, [x, z]); if (n !== stopAt) markStop(n); }
      if (photoOn) { // 들르는 곳에 그 방향 그대로 서 있을 때만 실사. 움직이거나 고개를 돌리면 3D로 돌아간다
        const st = stops[stopAt], turn = st ? Math.abs(Math.atan2(Math.sin(w.yaw - st.yaw), Math.cos(w.yaw - st.yaw))) : 9;
        const still = st && !w.gliding && Math.hypot(st.pos[0] - x, st.pos[1] - z) < 0.06 && turn < 0.06;
        if (still) showPhoto(st).catch((e) => toast(e.message, true)); else if (photoAt) hidePhoto();
      }
      return;
    }
    const c = viewer.camera(), key = `${c.pos}|${c.target}`;
    if (key === camSeen && m.getAttribute("points") !== "0,0 0,0 0,0") return;
    camSeen = key;
    // 궤도 시점은 카메라가 방 밖에 있으니, 보는 곳 바로 앞에 꼭짓점을 두고 보는 쪽으로 부채꼴을 편다
    const [cx, , cz] = c.pos, [tx, , tz] = c.target;
    const a = Math.atan2(tz - cz, tx - cx);
    const px = tx - Math.cos(a) * 1.1, pz = tz - Math.sin(a) * 1.1;
    m.setAttribute("points", viewFan(px, pz, a));
    d.setAttribute("cx", px); d.setAttribute("cy", pz);
  };
  // 제품 옆에 붙어 있던 메뉴를 3D 아래 가운데로 되돌린다. 자리(left/top)를 남겨 두면 들고 있을 때
  // 메뉴가 그 자리부터 아래까지 길게 늘어나 바닥 클릭을 가로채서 물건이 안 놓였다.
  // ---- 남는 틈: 숫자는 띄우지 않는다. 설치 여유가 모자란 곳에만 그 자리에 한 문장 (gapnote.js). 잘 들어가면 초록 테두리뿐 ----
  const gapBox = document.getElementById("gapTags");
  let gapInfo = null;
  const showGaps = (r) => {
    const g = r?.gaps, size = r?.size_m;
    gapInfo = null;
    if (g && size) {
      const base = r.base_m || 0, c = r.pose.center_xz;
      const mid = (ln) => [(ln[0][0] + ln[1][0]) / 2, (ln[0][1] + ln[1][1]) / 2];
      const tags = gapNotes(g).map((n) => ({ text: n.text, xz: n.line ? mid(n.line) : c,
        y: base + (n.key === "top" ? size[1] + 0.1 : n.key === "back" ? size[1] : Math.min(size[1] * 0.55, 1.0)) }));
      if (tags.length) gapInfo = tags;
    }
    gapBox.innerHTML = (gapInfo || []).map((t) => `<span class="gap-tag bad">${esc(t.text)}</span>`).join("");
  };
  const trackGaps = () => {
    const off = !gapInfo || walking || studio.dataset.view !== "3d";
    gapBox.hidden = off;
    if (off) return;
    const r = canvasEl.getBoundingClientRect();
    [...gapBox.children].forEach((el, i) => {
      const [sx, sy] = viewer.toScreen(gapInfo[i].xz, gapInfo[i].y);
      el.style.transform = `translate(${Math.round(sx - r.left)}px, ${Math.round(sy - r.top)}px) translate(-50%, -50%)`;
    });
  };
  const unNear = () => { if (actBar.classList.contains("near")) { actBar.classList.remove("near", "under"); actBar.style.left = ""; actBar.style.top = ""; } };
  const trackAct = () => {
    actRaf = requestAnimationFrame(trackAct);
    trackCam();
    trackGaps();
    trackFlowX();
    trackFurnX();
    if (actBar.hidden || armed || studio.classList.contains("app") || studio.dataset.view !== "3d") { unNear(); return; }
    const x = selPl && project?.scene_state.placements.find((q) => q.placement_id === selPl);
    const o = !x && selObj && room?.objects.find((q) => q.object_id === selObj);
    const held = viewer.held?.();
    const xz = held ? held.xz : x ? x.center_xz : o ? [o.position[0], o.position[2]] : null;
    if (!xz) { unNear(); return; }
    const top = x ? (x.size_m?.[1] ?? 1) : o ? o.bbox_m.h : 1;
    // 가구 위에 올려 둔 것은 그 높이만큼 위에 (안 그러면 메뉴가 물건을 가려 놓을 자리를 못 누른다)
    const base = held ? (held.kind === "placement" ? held.y : 0) : x ? x.base_m || 0 : 0;
    const [sx, sy] = viewer.toScreen(xz, top + base), r = canvasEl.getBoundingClientRect();
    const w = actBar.offsetWidth, h = actBar.offsetHeight;
    const left = Math.min(Math.max(sx - r.left, w / 2 + 8), r.width - w / 2 - 8);
    // 위에 자리가 없으면(물건이 화면 위쪽에 있을 때) 물건을 덮지 않게 발밑으로 내린다
    const above = sy - r.top - h - 14, below = viewer.toScreen(xz, base)[1] - r.top + 14;
    const under = above < 8 && below + h <= r.height - 8;
    const topPx = under ? below : Math.min(Math.max(above, 8), r.height - h - 8);
    actBar.classList.add("near");
    actBar.classList.toggle("under", under);
    actBar.style.left = `${left}px`; actBar.style.top = `${topPx}px`;
  };
  actRaf = requestAnimationFrame(trackAct);
  cleanup.push(() => cancelAnimationFrame(actRaf));
  const actBtn = (id, icon, label, cls = "") => `<button class="act ${cls}" id="${id}"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true">${ICON[icon]}</svg><span>${label}</span></button>`;
  // 크기 조절: 3D 메뉴가 치수 입력으로 바뀐다. 폭·높이·깊이를 mm로 바로 적거나, 실제 제품 치수(프리셋)를 누른다
  let sizing = null;
  const SIZE_MIN = { w: 100, h: 100, d: 20 }, SIZE_MAX = { w: 8000, h: 3000, d: 3000 };
  const sizeBar = (x) => {
    const d = decorOf(x.sku), long = LONG.has(x.sku);
    const cur = { w: Math.round(x.size_m[0] * 1000), h: Math.round(x.size_m[1] * 1000), d: Math.round(x.size_m[2] * 1000) };
    const names = long ? { w: "길이", h: "높이", d: "두께" } : { w: "폭", h: "높이", d: "깊이" };
    const same = (p) => p.size_mm.w === cur.w && p.size_mm.h === cur.h && p.size_mm.d === cur.d;
    const presets = d?.presets || [];
    actBar.classList.add("sizing");
    actBar.innerHTML = `${presets.length ? `<div class="sz-presets" role="group" aria-label="실제 제품 치수">${presets.map((p, i) =>
      `<button class="chip${same(p) ? " on" : ""}" data-preset="${i}" title="${mm(p.size_mm.w)} × ${mm(p.size_mm.h)} × ${mm(p.size_mm.d)} mm (폭 × 높이 × 깊이)">${esc(p.label)}</button>`).join("")}</div>` : ""}
      <div class="sz-row">${["w", "h", "d"].map((k) => `<label class="sz-f">${names[k]}<input type="number" inputmode="numeric" data-dim="${k}" min="${SIZE_MIN[k]}" max="${SIZE_MAX[k]}" step="10" value="${cur[k]}" aria-label="${names[k]} (mm)"></label>`).join("")}
        <span class="sz-unit">mm</span><button class="primary small" id="szDone">완료</button></div>`;
    const apply = (v) => resizePlacement(x.placement_id, [v.w / 1000, v.h / 1000, v.d / 1000]);
    actBar.querySelectorAll("[data-dim]").forEach((inp) => {
      inp.onchange = () => {
        const k = inp.dataset.dim, n = Math.round(+inp.value);
        if (!Number.isFinite(n) || !inp.value) { inp.value = cur[k]; return; }
        const v = Math.min(Math.max(n, SIZE_MIN[k]), SIZE_MAX[k]);
        inp.value = v;
        if (v !== cur[k]) apply({ ...cur, [k]: v });
      };
      inp.onkeydown = (e) => { e.stopPropagation(); if (e.key === "Enter") inp.blur(); };
    });
    actBar.querySelectorAll("[data-preset]").forEach((b) => (b.onclick = () => apply(presets[+b.dataset.preset].size_mm)));
    document.getElementById("szDone").onclick = () => { sizing = null; renderAct(); };
  };
  // 색 고르기: 3D 메뉴가 색 점 줄로 바뀐다. 누르면 바로 입혀진다 (놓은 가구도, 스캔한 가구도)
  let colouring = null;
  const paintOf = (x, o) => (x ? x.sku.slice(x.sku.indexOf(":") + 1) : o ? lookOf(o.category, o.bbox_m.h) : null);
  // 설치한 LG 가전의 색: 그 모델에 실제로 있는 색만 (같은 사양에서 색만 다른 모델로 바꾼다)
  const lgColours = (x) => {
    const f = x && !isDecor(x.sku) && familyOf(x.sku);
    if (!f) return [];
    const mine = f.variants.find((v) => v.sku === x.sku), same = (v) => JSON.stringify(v.options || {}) === JSON.stringify(mine?.options || {});
    const pool = f.variants.filter((v) => v.color && v.hex && (v.sku === x.sku || f.demo_only || sellable(v)));
    const names = [...new Set(pool.map((v) => v.color))];
    const list = names.map((n) => { const v = pool.find((q) => q.color === n && q.sku === x.sku) || pool.find((q) => q.color === n && same(q)) || pool.find((q) => q.color === n); return { name: n, hex: v.hex, sku: v.sku }; });
    return list.length > 1 ? list : [];
  };
  const colourBar = (x, o) => {
    const lg = lgColours(x);
    const list = lg.length ? lg : coloursFor(paintOf(x, o));
    const cur = lg.length ? lg.find((c) => c.sku === x.sku)?.hex || null : (x ? x.hex : (project.scene_state.object_colors || {})[o.object_id]) || null;
    actBar.classList.add("colouring");
    actBar.innerHTML = `<div class="cl-row" role="radiogroup" aria-label="가구 색">${list.map((c) =>
      `<button class="cl-dot${cur === c.hex ? " on" : ""}" data-hex="${c.hex}" role="radio" aria-checked="${cur === c.hex}" aria-label="${esc(c.name)}" title="${esc(c.name)}" style="--c:${c.hex}"></button>`).join("")}</div>
      <div class="cl-foot"><span class="cl-name">${esc(list.find((c) => c.hex === cur)?.name || "원래 색")}</span><span class="spacer"></span>
        ${cur && !lg.length ? `<button class="ghost small" id="clReset">원래 색으로</button>` : ""}<button class="primary small" id="clDone">완료</button></div>`;
    const apply = guard(async (hex) => {
      if (lg.length) { // 색이 다른 같은 모델로 바꾼다 (가격이 다르면 합계도 바뀐다)
        const to = lg.find((c) => c.hex === hex);
        if (!to || to.sku === x.sku) return;
        rememberPlacement(x.placement_id);
        await api(`/api/projects/${pid}/placements/${x.placement_id}`, { method: "PATCH", body: JSON.stringify({ sku: to.sku }) });
        const vs = familyOf(x.sku).variants, was = vs.find((v) => v.sku === x.sku)?.price_krw, now = vs.find((v) => v.sku === to.sku)?.price_krw;
        if (typeof now === "number" && now !== was) toast(`${to.name}은 ${now.toLocaleString("ko-KR")}원이에요`); // 색에 따라 값이 다르면 알려 준다
      } else if (x) await api(`/api/projects/${pid}/placements/${x.placement_id}`, { method: "PATCH", body: JSON.stringify({ hex: hex || "" }) });
      else for (const oid of runOf(room.objects, o.object_id)) await put(`/api/projects/${pid}/objects/${oid}/color`, { hex: hex || null }); // 붙어 있는 한 줄은 같이
      await refresh(true);
    });
    actBar.querySelectorAll("[data-hex]").forEach((b) => (b.onclick = () => apply(b.dataset.hex)));
    document.getElementById("clReset")?.addEventListener("click", () => apply(null));
    document.getElementById("clDone").onclick = () => { colouring = null; renderAct(); };
  };
  // 빈틈에 맞추기: 장·가벽을 양옆 벽·가전 사이에 꽉 차게 (가전이 요구하는 옆 여유는 남긴다)
  const fitGap = guard(async (plid) => {
    rememberPlacement(plid);
    const r = await post(`/api/projects/${pid}/placements/${plid}/fit-gap`, {});
    toast(`빈틈에 맞췄어요 (폭 ${mm(Math.round(r.placement.size_m[0] * 1000))} mm)`);
    await refresh(true);
  });
  const canFill = (sku) => ["storage", "structure"].includes(decorOf(sku)?.group) && sku !== "decor:island" && sku !== "decor:door";
  renderAct = () => {
    if (!project) return;
    const x = selPl && project?.scene_state.placements.find((q) => q.placement_id === selPl);
    fitBadge.hidden = !x || walking;
    if (x) {
      // 안 들어가면 왜 안 되는지와 고치는 방법까지 한 줄로 (벽·가구·다른 제품과 겹칠 때 등)
      const r = x.verdict === "no_fit" ? badReasons(x)[0] : null;
      fitBadge.className = `fit-badge v-${shownVerdict(x.verdict)}`;
      const doorShut = x.sku === DOOR_SKU && r?.code === "front_blocked"; // 문은 열리는지부터 말해 준다
      const head = x.sku === DOOR_SKU && !r ? "문이 잘 열려요" : doorShut ? "문이 안 열려요" : BADGE[x.verdict] || BADGE.unknown;
      const why = doorShut ? "앞에 문짝만큼 비워 주세요. R로 돌리면 반대쪽으로 열려요" : r ? `${r.label} · ${FIX[r.code] || "다른 자리로 옮겨 보세요"}` : "";
      fitBadge.innerHTML = `<b>${esc(head)}</b>${why ? `<span>${esc(why)}</span>` : ""}`;
    }
    actBar.classList.remove("sizing", "colouring");
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
    if (!target) { sizing = null; colouring = null; return; }
    if (x && isDecor(x.sku) && sizing === x.placement_id) { sizeBar(x); return; }
    const deco = x && isDecor(x.sku);
    const obj = !x && room.objects.find((q) => q.object_id === selObj);
    const paintable = x && !deco ? lgColours(x).length > 0 : (deco || obj) && coloursFor(paintOf(deco ? x : null, obj)).length > 0;
    if (paintable && colouring === target.id) { colourBar(x || null, obj); return; }
    if (colouring !== target.id) colouring = null;
    actBar.innerHTML = actBtn("actMove", "move", "이동") + actBtn("actRot", "rotate", "회전")
      + (paintable ? actBtn("actColor", "color", "색") : "")
      + (deco ? actBtn("actSize", "size", "크기 조절") + (canFill(x.sku) ? actBtn("actFill", "fill", "빈틈 맞춤") : "") : x ? actBtn("actAlign", "align", "벽에 붙이기") : "")
      + (x ? actBtn("actCopy", "copy", "복사") : "") + (x && !deco ? actBtn("actInfo", "info", "상세") : "") + actBtn("actDel", "del", "삭제", "danger");
    document.getElementById("actInfo")?.addEventListener("click", () => openDetail(x.sku));
    document.getElementById("actCopy")?.addEventListener("click", () => copyPlacement(x.placement_id));
    document.getElementById("actSize")?.addEventListener("click", () => { sizing = x.placement_id; renderAct(); actBar.querySelector("[data-dim]")?.select(); });
    document.getElementById("actColor")?.addEventListener("click", () => { colouring = target.id; renderAct(); });
    document.getElementById("actFill")?.addEventListener("click", () => fitGap(x.placement_id));
    document.getElementById("actMove").onclick = () => { const it = poseOf(target); if (it && viewer.hold(it)) setHint(it.surface === "product" ? "옮길 자리를 누르세요 · 식탁·아일랜드·하부장 위를 가리키면 그 위로 올라가요 · Esc 취소" : "옮길 자리를 누르세요 · Esc 취소"); };
    document.getElementById("actRot").onclick = () => rotate(90); // 버튼은 직각으로. 조금씩 돌리는 건 키보드(R)로
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
  // ---- 구매 및 설치 신청: 놓은 제품과 판정을 모아 보여 주고, 구매는 LGE.COM, 설치는 방문 신청으로 잇는다 ----
  const orderSheet = document.getElementById("orderSheet");
  const closeOrder = () => { orderSheet.hidden = true; orderSheet.innerHTML = ""; };
  const openOrder = () => {
    const pls = lgOnly(project.scene_state.placements); // 가구·소품은 꾸미기용이라 신청에 넣지 않는다
    const bad = pls.filter((x) => x.verdict === "no_fit").length;
    const priceOf = (x) => (prodOf(x.sku) || {}).price_krw;
    const known = pls.map(priceOf).filter((n) => typeof n === "number");
    const sum = known.reduce((a, b) => a + b, 0);
    orderSheet.innerHTML = `
      <div class="order-head"><h2>구매 및 설치 신청</h2><button class="ghost small" id="orderClose">닫기</button></div>
      ${pls.length ? `<p class="order-sum">놓은 제품 <b>${pls.length}개</b>${bad ? ` · <b class="bad">${bad}개는 지금 자리에 설치하기 어려워요</b>` : " · 모두 설치할 수 있는 자리예요"}</p>
      <p class="hint-sm">${INSTALL_NOTE}</p>
      <ul class="order-list">${pls.map((x) => { const p = prodOf(x.sku) || { name: x.sku }; return `<li class="${x.verdict === "no_fit" ? "nofit" : ""}">
        <i class="dot" style="background:${esc(x.hex || "#fff")}"></i>
        <span class="nm">${esc(p.name)}<small>${esc(x.sku)}${x.color ? ` · ${esc(x.color)}` : ""}</small></span>
        ${typeof p.price_krw === "number" ? `<b class="order-price">${p.price_krw.toLocaleString("ko-KR")}원</b>` : ""}
        ${x.verdict === "no_fit" ? `<button class="btn small order-fix" data-fix="${esc(x.placement_id)}">자리 옮기기</button>` : ""}
        ${p.source_url && !p.demo_only ? `<a class="btn ghost small" href="${esc(p.source_url)}" target="_blank" rel="noopener">LGE.COM에서 구매</a>` : ""}</li>`; }).join("")}</ul>
      ${known.length ? `<p class="order-all"><span>합계</span><b>${sum.toLocaleString("ko-KR")}원</b></p>` : ""}
      <p class="order-note">구매는 LGE.COM 제품 페이지에서 하고, 설치는 방문 신청을 하면 기사가 실측한 뒤 진행해요. 전원·배관 위치도 그때 확인해요.</p>
      <div class="order-actions ir-box" id="irBox"></div>`
      : `<p class="order-sum">아직 놓은 제품이 없어요.</p><p class="order-note">왼쪽 목록에서 제품을 골라 3D에 놓으면, 설치할 수 있는 자리인지 검사한 결과와 함께 신청할 수 있어요.</p>`}`;
    orderSheet.hidden = false;
    // 방문 설치 신청: 놓은 제품과 설치 전 확인 목록을 그대로 기사에게 넘긴다
    const irBox = document.getElementById("irBox");
    if (irBox) installRequestBox(irBox, pid, project, () => refresh(true).then(() => { if (!orderSheet.hidden) openOrder(); }));
    document.getElementById("orderClose").onclick = closeOrder;
    orderSheet.querySelectorAll("[data-fix]").forEach((b) => (b.onclick = () => { closeOrder(); focusPlacement(b.dataset.fix); }));
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
    hits_wall: "벽에서 조금 떼거나 '벽에 붙이기'를 눌러 보세요", outside_room: "방 안쪽으로 옮겨 주세요",
    overlaps_object: "가구를 옮기거나 '가구 치우기'로 치워 보세요", overlaps_placement: "다른 제품과 겹쳐요. 한쪽을 옮겨 주세요",
    not_on_wall: "벽이나 가벽 가까이를 누르면 벽에 달려요",
    surface_overhang: "올려 둔 가구보다 커서 밖으로 나와요. 더 넓은 가구 위나 바닥에 놓아 보세요",
    needs_counter: "인덕션은 주방 하부장이나 아일랜드 위에 놓아야 해요",
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
    const wins = project.scene_state.hidden_openings || [];
    if (wins.length) document.getElementById("pls").insertAdjacentHTML("beforeend", `<li class="muted" style="font-size:12px">없앤 창문 ${wins.length}개 <span class="spacer"></span><button class="small ghost" id="winBack">모두 되돌리기</button></li>`);
    const nb = document.getElementById("winBack");
    if (nb) nb.onclick = guard(async () => { for (const w of wins) await put(`/api/projects/${pid}/openings/${w}/hidden`, { hidden: false }); await refresh(true); });
    const wb = document.getElementById("wallBack");
    if (wb) wb.onclick = guard(async () => { for (const w of walls) await put(`/api/projects/${pid}/walls/${w}/hidden`, { hidden: false }); await refresh(true); });
    const rb = document.getElementById("restore");
    if (rb) rb.onclick = guard(async () => { await put(`/api/projects/${pid}/objects/hidden`, { hidden: false }); await refresh(true); });
    const furnEl = document.getElementById("furn");
    if (!furnEl) return; // 화면을 떠난 뒤 늦게 온 응답
    furnEl.hidden = room.objects.length === 0;
    drawFurnX();
  };
  // 실사로 보기: 지금 3D 시점 + LG 제품 마스크 → 서버의 이미지 AI가 벽·바닥·빛만 사진처럼 (제품은 3D 그대로)
  const showShot = (url, cap) => {
    const img = document.getElementById("renderImg");
    img.src = url;
    document.getElementById("renderSave").href = url;
    document.getElementById("renderCap").textContent = cap;
    document.getElementById("renderBox").hidden = false;
  };
  const takeShot = () => {
    viewer.cancelHold(); armed = null; ghost(null);
    const keepSel = selPl; selPl = null; draw(); // 고른 표시 없이 찍는다
    const shot = { ...viewer.snapshot(), camera: viewer.cameraPose() };
    selPl = keepSel; draw();
    return shot;
  };
  document.getElementById("render").onclick = guard(async (e) => {
    const b = e.currentTarget;
    if (walking) { // 걸어 보는 중: 들르는 곳마다 실사로 바뀌는 둘러보기를 켜고 끈다
      setPhotoOn(!photoOn);
      if (photoOn && !viewer.walkInfo().gliding) { // 들르는 곳이 아니면 가장 가까운 곳으로 가서 보여 준다
        const here = herePos();
        let near = 0;
        stops.forEach((x, i) => { if (Math.hypot(x.pos[0] - here[0], x.pos[1] - here[1]) < Math.hypot(stops[near].pos[0] - here[0], stops[near].pos[1] - here[1])) near = i; });
        goStop(near);
      }
      return;
    }
    const shot = takeShot();
    const label = b.querySelector("span");
    b.disabled = true; b.classList.add("busy"); label.textContent = "만드는 중";
    const waitEl = document.getElementById("renderWait"); // 잠깐 뜨는 알림 대신 끝날 때까지 화면에 남긴다
    waitEl.hidden = false;
    try {
      const r = await post(`/api/projects/${pid}/photoreal`, shot);
      showShot(apiUrl(r.url), r.model === "blender" ? "지금 집과 놓은 제품을 치수 그대로 빛을 계산해 그린 이미지예요."
        : "AI가 만든 참고 이미지예요. LG 제품은 실제 치수·색 그대로 두고 벽·바닥·빛만 사진처럼 바꿨어요.");
    } catch (err) {
      if (err.status !== 503 && err.status !== 429) throw err;
      toast(err.message, true);
    } finally { waitEl.hidden = true; b.disabled = false; b.classList.remove("busy"); label.textContent = "실사"; }
  });
  document.getElementById("renderClose").onclick = () => (document.getElementById("renderBox").hidden = true);

  // ---- 벽지·바닥: 색깔만 고른다 (왼쪽 ‘벽지·바닥’ 탭). 상표·품명은 보여 주지 않는다 ----
  function renderFinishes() {
    if (libTab !== "finish") return;
    const box = document.getElementById("decorLib");
    box.innerHTML = FIN_KIND.map(([kind, title]) => `<section class="dsec"><h3>${title}</h3>
      <div class="fin-sws" role="radiogroup" aria-label="${title} 색깔">${FIN.filter((f) => f.kind === kind).flatMap((f) => f.tones.map((t) => finChip(f, t))).join("")}</div></section>`).join("");
    box.querySelectorAll("[data-fin]").forEach((b) => (b.onclick = guard(async () => {
      const f = finById(b.dataset.fin);
      await post(`/api/projects/${pid}/finishes`, { finish_id: f.id, tone: b.dataset.tone });
      toast(f.kind === "wall" ? "벽지 색을 바꿨어요" : "바닥 색을 바꿨어요");
      await refresh(true);
    })));
  }
  const AI_EX = ["따뜻한 오크 마루에 회벽 느낌", "대리석 바닥에 호텔처럼 차분하게", "밝은 화이트 미니멀", "린넨 느낌 벽에 그린 포인트", "어둡고 시크한 모던"];

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
  document.getElementById("botEx").innerHTML = [...AI_EX.slice(0, 2), "맞벌이 4인 가족, 장은 주말에 몰아서 봐요"].map((t) => `<button class="chip" data-say="${esc(t)}">${esc(t)}</button>`).join("");
  document.querySelectorAll("[data-say]").forEach((b) => (b.onclick = () => { botIn.value = b.dataset.say; botForm.requestSubmit(); }));
  // 사진 한 장으로 꾸미기: 긴 변 1024px JPEG로 줄여서 보낸다 (서버는 AI에 한 번 보내고 버린다)
  const PHOTO_MAX = 1024, PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
  let botPhoto = null; // data URL
  const photoPrev = document.getElementById("botPhotoPrev"), photoIn = document.getElementById("botPhoto");
  const setPhoto = (url) => {
    botPhoto = url;
    photoPrev.hidden = !url;
    photoPrev.innerHTML = url ? `<img src="${url}" alt="붙인 사진"><span>이 사진 느낌으로 꾸며 볼게요</span><button type="button" class="bot-x" id="botPhotoX" aria-label="사진 빼기">×</button>` : "";
    if (url) document.getElementById("botPhotoX").onclick = () => { setPhoto(null); botIn.focus(); };
    botIn.placeholder = url ? "더 하고 싶은 말 (없어도 돼요)" : "예) 호텔 같은 침실, 가전은 300만 원 안";
  };
  const shrinkPhoto = async (file) => {
    if (!PHOTO_TYPES.includes(file.type)) throw new Error("jpg, png, webp 사진만 붙일 수 있어요");
    if (file.size > 20 * 1024 * 1024) throw new Error("사진이 너무 커요 (20MB 안)");
    const bmp = await createImageBitmap(file);
    const k = Math.min(1, PHOTO_MAX / Math.max(bmp.width, bmp.height));
    const cv = document.createElement("canvas");
    cv.width = Math.round(bmp.width * k); cv.height = Math.round(bmp.height * k);
    cv.getContext("2d").drawImage(bmp, 0, 0, cv.width, cv.height);
    bmp.close?.();
    return cv.toDataURL("image/jpeg", 0.85);
  };
  const takePhoto = async (file) => {
    if (!file) return;
    try { setPhoto(await shrinkPhoto(file)); botIn.focus(); } catch (err) { toast(err.message || "사진을 못 읽었어요", true); }
  };
  photoIn.onchange = () => { takePhoto(photoIn.files[0]); photoIn.value = ""; };
  botIn.addEventListener("paste", (e) => { const f = [...(e.clipboardData?.files || [])].find((x) => x.type.startsWith("image/")); if (f) { e.preventDefault(); takePhoto(f); } });
  document.getElementById("botPanel").addEventListener("dragover", (e) => e.preventDefault());
  document.getElementById("botPanel").addEventListener("drop", (e) => { const f = e.dataTransfer?.files?.[0]; if (f) { e.preventDefault(); takePhoto(f); } });
  botForm.onsubmit = async (e) => {
    e.preventDefault();
    const prompt = botIn.value.trim(), image = botPhoto;
    if ((!prompt && !image) || botForm.dataset.busy) return;
    botIn.value = ""; setPhoto(null); botForm.dataset.busy = "1"; bot.classList.add("thinking");
    say("me", `${image ? `<img class="msg-photo" src="${image}" alt="붙인 사진">` : ""}${prompt ? esc(prompt) : ""}`);
    const wait = say("hb", `<span class="dots" aria-label="생각하는 중"><i></i><i></i><i></i></span>`);
    try {
      // 하우니: 꾸미기·분위기를 말하거나 사진을 붙이면 조합, 제품만 물으면 이 집에 맞는 하나 + 대안 (서버가 계산)
      const d = await post(`/api/projects/${pid}/assist`, image ? { prompt, image } : { prompt });
      if (d.type === "message") {
        wait.innerHTML = `<p>${esc(d.message)}</p>`;
      } else if (d.type === "combos") {
        wait.innerHTML = `<p>${esc(d.message)}</p>${comboCardsHtml(d)}`;
        bindComboCards(wait, pid, () => refresh(true));
      } else if (d.type === "life") {
        // 생활 이야기: 가전마다 하나 + 한 줄 이유(LGE.COM 구매 가이드 기준) → 넣어 보기, 이어서 배치 추천
        const row = (it) => `<li class="best"><span class="ph">${it.thumb ? `<img src="${esc(it.thumb)}" alt="" loading="lazy">` : ""}</span>
          <span class="nm"><b>${esc(it.family_name || it.product.name)}</b>${it.product.price_krw ? `<small>${it.product.price_krw.toLocaleString("ko-KR")}원</small>` : ""}
          <small>${esc(it.need.why)}${it.need.source_url ? ` · <a href="${esc(it.need.source_url)}" target="_blank" rel="noopener">LGE.COM 기준</a>` : ""}</small></span>
          <button class="small primary" data-try="${esc(it.product.sku)}">넣어 보기</button></li>`;
        wait.innerHTML = `<p>${esc(d.message)}</p>${d.items.length ? `<ul class="bot-prods">${d.items.map(row).join("")}</ul>
          <div class="chips"><button class="chip" id="lifeCombo">이 가전으로 배치 추천 받기</button></div>` : ""}`;
        wait.querySelectorAll("[data-try]").forEach((b) => (b.onclick = () => {
          const sku = b.dataset.try;
          if (!prodOf(sku)) return;
          openBot(false);
          if (walking) setWalking(false);
          arm(sku);
        }));
        const more = wait.querySelector("#lifeCombo");
        if (more) more.onclick = async () => {
          more.disabled = true;
          const w2 = say("hb", `<span class="dots" aria-label="생각하는 중"><i></i><i></i><i></i></span>`);
          try {
            const c = await post(`/api/projects/${pid}/assist`, { prompt, categories: d.categories, life: d.life });
            w2.innerHTML = `<p>${esc(c.message)}</p>${comboCardsHtml(c)}`;
            bindComboCards(w2, pid, () => refresh(true));
          } catch { w2.innerHTML = `<p>앗, 지금은 배치를 못 만들었어요. 잠시 뒤 다시 눌러 주세요.</p>`; more.disabled = false; }
          botLog.scrollTop = botLog.scrollHeight;
        };
      } else {
        const [best, ...alt] = d.items || [];
        const row = (it, big) => `<li class="${big ? "best" : ""}"><span class="ph">${it.thumb ? `<img src="${esc(it.thumb)}" alt="" loading="lazy">` : ""}</span>
          <span class="nm"><b>${esc(it.family_name || it.product.name)}</b>${it.product.price_krw ? `<small>${it.product.price_krw.toLocaleString("ko-KR")}원</small>` : ""}
          ${big && it.reasons?.length ? `<small>${esc(it.reasons.slice(0, 2).join(" · "))}</small>` : ""}</span>
          <button class="small ${big ? "primary" : "ghost"}" data-try="${esc(it.product.sku)}">넣어 보기</button></li>`;
        wait.innerHTML = `<p>${esc(d.message)}</p>${best ? `<ul class="bot-prods">${row(best, true)}${alt.map((it) => row(it, false)).join("")}</ul>` : ""}`;
        wait.querySelectorAll("[data-try]").forEach((b) => (b.onclick = () => {
          const sku = b.dataset.try;
          if (!prodOf(sku)) return;
          openBot(false);
          if (walking) setWalking(false);
          arm(sku);
        }));
      }
    } catch (err) {
      wait.innerHTML = `<p>앗, 지금은 해석이 안 됐어요. 잠시 뒤 다시 말해 주세요.</p>`;
    } finally { delete botForm.dataset.busy; bot.classList.remove("thinking"); botLog.scrollTop = botLog.scrollHeight; }
  };
  mountComboPop(pid, () => refresh(true));
  if (!saved.botSeen) { bot.classList.add("nudge"); saveUiState(pid, { botSeen: true }); }
  api("/api/finishes").then((r) => { FIN = r.finishes; renderFinishes(); lastSceneKey = null; refresh(true).catch(() => {}); }).catch(() => {});

  const draw = () => {
    pv = planView(svg, room, { zones, placements: project.scene_state.placements, hidden: project.scene_state.hidden_objects, hiddenOpenings: project.scene_state.hidden_openings,
      selectedPl: selPl, selectedObj: selObj, overlay, northDeg: simOn("daylight") ? project.site?.north_deg ?? 0 : null });
    drawDraft();
    svg.insertAdjacentHTML("beforeend", `<g id="stopDots"></g><defs><radialGradient id="camFade" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="1"><stop offset="0" stop-color="#a50034" stop-opacity=".5"/><stop offset=".55" stop-color="#a50034" stop-opacity=".2"/><stop offset="1" stop-color="#a50034" stop-opacity="0"/></radialGradient></defs><polygon class="cam-mark" id="camMark" points="0,0 0,0 0,0" style="fill:url(#camFade);stroke:none"/><circle class="cam-dot" id="camDot" r="${pv.sw(5)}"/>`);
    drawStopDots();
    if (!drag3d) viewer.setPlacements(project.scene_state.placements, selPl);
    syncNeed();
  };
  // 고른 제품이 차지하는 공간(본체 + 문 여는 공간)을 3D 바닥에 표시. 판정과 같은 계산(pose-check)을 그대로 쓴다
  let needKey = "";
  const syncNeed = async () => {
    const x = project.scene_state.placements.find((q) => q.placement_id === selPl);
    const key = x ? `${x.placement_id}|${x.sku}|${x.center_xz}|${x.yaw_rad}|${x.base_m || 0}|${x.size_m}|${project.scene_state.placements.length}` : "";
    if (key === needKey) return;
    needKey = key;
    document.getElementById("needTag").hidden = true;
    if (!x) { viewer.setNeed(null); showGaps(null); return; }
    try {
      const r = await post(`/api/projects/${pid}/pose-check`, { sku: x.sku, center_xz: x.center_xz, yaw_rad: x.yaw_rad, snap: false, placement_id: x.placement_id, size_m: x.size_m });
      if (needKey !== key) return;
      showGaps(r);
      // 가구·소품은 문 열 공간이 없으니 필요 공간 점선은 없다 (본체와 같아서 겹쳐 보이기만 한다)
      if (x.kind === "decor") { viewer.setNeed(null); return; }
      viewer.setNeed(r.required, r.base_m || 0);
      document.getElementById("needTag").hidden = true; // 점선 범례 글은 띄우지 않는다 (화면을 가볍게)
    } catch { viewer.setNeed(null); }
  };
  const overlays = { wifi: "", flow: "" };
  const setOverlay = (key, html) => {
    overlays[key] = html;
    html = overlays.wifi + overlays.flow;
    overlay = html;
    const g = document.getElementById("overlay");
    if (g) g.innerHTML = html;
    viewer.setOverlay(html, svg.getAttribute("viewBox")?.split(" ").map(Number));
  };

  // ---- 살아 보기: 채광 ----
  // 하루 해 경로(5분 간격)를 한 번 받아 두고 그 사이를 이어서 쓴다: 시간을 움직여도 서버를 기다리지 않고 바로, 끊김 없이
  let sunPath = { key: null, pts: null };
  const toMin = (t) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
  const hhmm = (v) => `${String(Math.floor(v / 60)).padStart(2, "0")}:${String(Math.floor(v % 60)).padStart(2, "0")}`;
  let simMin = toMin(simState.time);
  const timeKo = (v) => { const h = Math.floor(v / 60), m = Math.floor(v % 60); return `${h < 12 ? "오전" : "오후"} ${h % 12 || 12}:${String(m).padStart(2, "0")}`; };
  // 시간 바는 해가 떠 있는 동안만 (해 뜰 때 ~ 질 때). 경로를 아직 못 받았으면 6시 ~ 19시
  const dayRange = () => {
    const up = (sunPath.pts || []).filter((q) => q.altitude_deg > 0).map((q) => q.minute);
    return up.length ? [Math.ceil(Math.min(...up) / 10) * 10, Math.floor(Math.max(...up) / 10) * 10] : [360, 1140];
  };
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
  let addrTyped = null; // 주소 칸에는 적은 말을 그대로 둔다 (찾은 곳의 긴 지도 이름으로 바꾸지 않는다)
  const runDaylight = async () => {
    const box = resOf("daylight");
    if (!box) return;
    if (project.site?.north_deg == null) { viewer.setSun(null); box.innerHTML = `<p class="sim-line">창이 없는 방이라 방향을 알 수 없어요. 주소를 넣으면 건물 방향으로 알려 드려요.</p>`; return; }
    const pathKey = JSON.stringify([simState.date, project.site]);
    const needPath = sunPath.key !== pathKey;
    const d = await api(`/api/projects/${pid}/sim/daylight?date=${simState.date}&time=${simState.time}&heatmap=false&path=${needPath}`);
    if (!simOn("daylight") || !box.isConnected) return;
    if (needPath && d.path) sunPath = { key: pathKey, pts: d.path };
    // 3D: 그 시각 해 방향·색·세기로 비추고 창으로 볕이 든다
    const [lo, hi] = dayRange();
    simMin = Math.max(lo, Math.min(hi, simMin)); simState.time = hhmm(simMin);
    viewer.setSun(sunAt(simMin) || d.sun);
    const main = (d.facings || [])[0];
    // 적은 곳을 지도에서 못 찾아 동네까지만 찾았으면 어디 기준인지 한 줄로 알려 준다
    const near = project.site?.approx ? `<p class="sim-line">${esc(project.site.area || String(project.site.address || "").split(",")[0])} 근처 기준이에요</p>` : "";
    // 향 한 줄 아래에 시간 바: 끌면 그 시각의 볕으로 바로 바뀐다
    box.innerHTML = (!main ? "" : project.site?.address ? `<p class="facing"><b>${esc(main.label)}</b> 집이에요</p>`
      : `<p class="facing guess">주소를 넣으면 실제 방향으로 맞춰요. 지금은 큰 창이 남쪽이라고 봤어요.</p>`) + near + `
      <div class="time-bar"><span class="tb-end">${timeKo(lo)}</span>
        <input type="range" id="sunTime" min="${lo}" max="${hi}" step="10" value="${Math.round(simMin / 10) * 10}" aria-label="시각" aria-valuetext="${timeKo(simMin)}">
        <span class="tb-end">${timeKo(hi)}</span><b class="tb-now" id="sunNow">${timeKo(simMin)}</b></div>`;
    const bar = document.getElementById("sunTime");
    const paint = () => bar.style.setProperty("--p", `${((bar.value - lo) / Math.max(1, hi - lo)) * 100}%`);
    paint();
    bar.oninput = () => {
      simMin = +bar.value; simState.time = hhmm(simMin);
      const sun = sunAt(simMin); if (sun) viewer.setSun(sun);
      document.getElementById("sunNow").textContent = timeKo(simMin); bar.setAttribute("aria-valuetext", timeKo(simMin));
      paint();
    };
  };
  // 채광: 주소만 넣으면 어느 향인지 한 줄로 알려 주고, 그 아래 시간 바로 하루 볕을 본다
  const daylightCtl = async () => {
    // 스캔에는 나침반이 없다 → 북쪽을 안 정했으면 가장 큰 창이 남쪽을 본다고 보고 먼저 잡아 준다 (주소를 넣으면 건물 방향으로 바뀐다)
    if (project.site?.north_deg == null) { try { project = await put(`/api/projects/${pid}/site`, { auto_north: true }); draw(); } catch { /* 창이 없으면 안내문 */ } }
    const site = project.site || {}, ctl = ctlOf("daylight");
    if (!ctl) return;
    ctl.innerHTML = `
      <div class="sim-row">
        <input type="search" id="addr" placeholder="우리 집 주소 (예: 서울 중구 세종대로 110)" value="${esc(addrTyped ?? site.address ?? "")}" maxlength="200" autocomplete="street-address" aria-label="우리 집 주소">
        <button class="small primary" id="addrGo">찾기</button>
      </div>`;
    // 주소 → 위도·경도 (서버가 찾는다). 건물 방향을 알면 북쪽도 같이 잡힌다
    const findAddr = guard(async () => {
      const q = document.getElementById("addr").value.trim();
      if (!q) { document.getElementById("addr").focus(); return; }
      const b = document.getElementById("addrGo"); b.disabled = true; b.textContent = "찾는 중…";
      try {
        project = await put(`/api/projects/${pid}/site`, { address: q });
        addrTyped = q;
        sunPath = { key: null, pts: null };
        draw(); await daylightCtl();
      } catch (e) {
        // 못 찾았으면 예전 결과를 그대로 두지 않고 그 자리에 알려 준다 (잠깐 떴다 사라지는 알림만으로는 놓친다)
        const box = resOf("daylight");
        if (box) box.innerHTML = `<p class="sim-line warn" role="alert">${esc(e.message)}</p>`;
      } finally { const x = document.getElementById("addrGo"); if (x) { x.disabled = false; x.textContent = "찾기"; } }
    });
    document.getElementById("addrGo").onclick = findAddr;
    document.getElementById("addr").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); findAddr(); } };
    if (project.site?.north_deg == null) draw();
    await runDaylight();
  };
  // ---- 살아 보기: 와이파이 ----
  // 공유기 종류를 고르고 놓기만 한다. 결과는 방 바닥에 색으로만: 초록 잘 통함 · 노랑 보통 · 빨강 약함
  let armedRouter = false, band = "5";
  const WCOLOR = { good: "#1f7a4d", ok: "#e0a800", weak: "#b3261e" };
  const runWifi = async () => {
    const box = resOf("wifi");
    if (!box) return;
    const rt = project.scene_state.router;
    if (!rt) { setOverlay("wifi", ""); viewer.setRouter(null); box.innerHTML = ""; return; }
    const g = await api(`/api/projects/${pid}/sim/wifi?band=${band}`);
    if (!simOn("wifi") || !box.isConnected) return;
    const tint = simOn("daylight") ? 0.22 : 0.3; // 볕과 같이 볼 때는 색을 조금 옅게
    const gradeOf = (v) => (v >= -60 ? "good" : v >= -70 ? "ok" : "weak");
    const [x0, y0] = g.origin, c = g.cell_m, cells = [];
    g.values.forEach((row, j) => row.forEach((v, i) => { if (v != null) cells.push(`<rect x="${x0 + i * c}" y="${y0 + j * c}" width="${c}" height="${c}" fill="${WCOLOR[gradeOf(v)]}" fill-opacity="${tint}"/>`); }));
    const [rx, ry] = g.router;
    // 평면도에는 실제 크기 윗면 기호(본체 + 안테나 4개), 3D에는 실제 공유기 모델
    const yawDeg = ((rt.yaw_rad ?? 0) * 180) / Math.PI;
    const ants = [-0.1, -0.045, 0.045, 0.1].map((x) => `M${x} 0.06v0.05`).join("");
    setOverlay("wifi", cells.join("") + `<g class="router-sym" transform="translate(${rx} ${ry}) rotate(${-yawDeg})"><rect x="-0.1305" y="-0.0672" width="0.261" height="0.1345" rx="0.012"/><path d="${ants}" style="stroke-width:0.018px;stroke-linecap:round"/></g>`);
    viewer.setRouter(rt);
    box.innerHTML = `<p class="wifi-legend"><span><i style="background:${WCOLOR.good}"></i>잘 통해요</span><span><i style="background:${WCOLOR.ok}"></i>보통</span><span><i style="background:${WCOLOR.weak}"></i>약해요</span></p>`;
  };
  const wifiCtl = async () => {
    const ctl = ctlOf("wifi");
    if (!ctl) return;
    ctl.innerHTML = `
      <div class="sim-row">
        <div class="seg2 band" role="group" aria-label="공유기 종류">
          <button data-band="5" class="${band === "5" ? "on" : ""}" aria-pressed="${band === "5"}">5 GHz <span class="n">빠름</span></button>
          <button data-band="2.4" class="${band === "2.4" ? "on" : ""}" aria-pressed="${band === "2.4"}">2.4 GHz <span class="n">멀리</span></button></div>
        <button class="small ${armedRouter ? "primary" : "ghost"}" id="putRouter" aria-pressed="${armedRouter}">${armedRouter ? "놓을 자리를 눌러 주세요" : "공유기 놓기"}</button>
      </div>`;
    document.querySelectorAll("[data-band]").forEach((b) => (b.onclick = () => { band = b.dataset.band; wifiCtl(); }));
    document.getElementById("putRouter").onclick = () => {
      armedRouter = !armedRouter;
      if (!armedRouter) viewer.routerFollow(null);
      else if (armedStart) { armedStart = false; viewer.personFollow(null); if (simOn("flow")) flowCtl(); } // 손에는 하나만 든다
      armed = null; mode = "move"; syncMode(); wifiCtl();
    };
    if (armedRouter) { armed = null; mode = "move"; syncMode(); }
    await runWifi();
  };
  // ---- 가구 치우기: 버튼을 켜고 가구나 창문에 마우스를 올리면 그것에만 ✕가 뜬다. 누르면 치운다 ----
  // (터치 화면은 올려 둘 마우스가 없어서 전부 띄운다)
  const X_SVG = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>`;
  const furnBtn = document.getElementById("furn"), furnX = document.getElementById("furnX"), furnAll = document.getElementById("furnAll");
  const HOVERS = globalThis.matchMedia?.("(hover: hover)").matches ?? true, X_LINGER_MS = 700;
  let furnShown = [], furnHot = null, furnCool = 0;
  const winTop = (op) => {
    const w = room.walls.find((x) => x.wall_id === op.wall_id);
    if (!w) return null;
    const L = Math.hypot(w.end[0] - w.start[0], w.end[1] - w.start[1]) || 1, u = (op.offset_m + op.width_m / 2) / L;
    return [w.start[0] + (w.end[0] - w.start[0]) * u, op.sill_m + op.height_m, w.start[1] + (w.end[1] - w.start[1]) * u];
  };
  const clearables = () => {
    const gone = project.scene_state.hidden_objects || [], shut = project.scene_state.hidden_openings || [];
    return [...room.objects.filter((o) => !gone.includes(o.object_id)).map((o) => ({ type: "object", id: o.object_id, top: [o.position[0], o.position[1] * 2, o.position[2]] })),
      ...room.openings.filter((o) => o.type === "window" && !shut.includes(o.opening_id)).map((o) => ({ type: "window", id: o.opening_id, top: winTop(o) })).filter((x) => x.top)];
  };
  const coolDown = () => { clearTimeout(furnCool); furnCool = setTimeout(() => { furnHot = null; drawFurnX(); }, X_LINGER_MS); };
  function drawFurnX() {
    const all = furnPick ? clearables() : [];
    if (furnHot && !all.some((x) => x.id === furnHot.id)) furnHot = null;
    furnShown = HOVERS ? (furnHot ? [furnHot] : []) : all;
    furnX.innerHTML = furnShown.map((x) => { const t = x.type === "window" ? "창문 없애기" : "가구 치우기";
      return `<button class="flow-x soft" data-id="${esc(x.id)}" data-type="${x.type}" title="${t}" aria-label="${t}">${X_SVG}</button>`; }).join("");
    furnX.querySelectorAll("button").forEach((b) => {
      b.onmouseenter = () => clearTimeout(furnCool);
      b.onmouseleave = coolDown;
      b.onclick = guard(async (e) => {
        e.stopPropagation();
        b.disabled = true;
        const id = b.dataset.id, win = b.dataset.type === "window";
        remember({ kind: win ? "winShow" : "objShow", id });
        await put(`/api/projects/${pid}/${win ? "openings" : "objects"}/${id}/hidden`, { hidden: true });
        if (selObj === id) selObj = null;
        furnHot = null;
        await refresh(true);
        if (win) toast("창문을 없앴어요. 되돌리기로 다시 살릴 수 있어요");
      });
    });
    const allGone = room.objects.length > 0 && !all.some((x) => x.type === "object");
    furnAll.hidden = !furnPick || studio.dataset.view !== "3d";
    furnAll.textContent = allGone ? "모두 되돌리기" : "모두 치우기";
    furnAll.onclick = guard(async () => { await put(`/api/projects/${pid}/objects/hidden`, { hidden: !allGone }); await refresh(true); });
    trackFurnX();
  }
  furnHover = (h) => {
    if (!h) { if (furnHot) coolDown(); return; }
    clearTimeout(furnCool);
    if (furnHot?.id === h.id) return;
    furnHot = h;
    drawFurnX();
  };
  furnBtn.onclick = () => {
    furnPick = !furnPick; furnHot = null;
    furnBtn.classList.toggle("on", furnPick); furnBtn.setAttribute("aria-pressed", furnPick);
    if (furnPick && HOVERS) toast("치울 가구나 창문에 마우스를 올리면 ✕가 떠요");
    drawFurnX();
  };
  trackFurnX = () => {
    if (!furnShown.length) return;
    const r = canvasEl.getBoundingClientRect();
    furnShown.forEach((x, i) => {
      const b = furnX.children[i];
      if (!b) return;
      const [sx, sy] = viewer.toScreen([x.top[0], x.top[2]], x.top[1]);
      b.style.transform = `translate(${Math.round(sx - r.left)}px, ${Math.round(sy - r.top)}px)`;
    });
  };

  // ---- 살아 보기: 동선 ----
  // 처음에 "어디서 출발할까요?"를 묻고, 마우스를 따라오는 사람을 놓은 자리에서 가전 앞까지 걸어 본다.
  // 길이 막혀 못 가는 제품에는 3D에 ✕가 뜨고, 누르면 그 제품을 뺀다. 싱크대는 가구(수납)에서 놓는다.
  let armedStart = false, flowBlocked = [];
  const flowX = document.getElementById("flowX");
  const clearFlowX = () => { flowBlocked = []; flowX.innerHTML = ""; };
  const drawFlowX = (ids) => {
    flowBlocked = ids.map((id) => project.scene_state.placements.find((x) => x.placement_id === id)).filter(Boolean);
    flowX.innerHTML = flowBlocked.map((x) => `<button class="flow-x" data-id="${esc(x.placement_id)}" title="길이 막혀 못 가요. 누르면 빼요" aria-label="${esc(nameOf(x.sku))} 빼기"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>`).join("");
    flowX.querySelectorAll(".flow-x").forEach((b) => (b.onclick = guard(async (e) => {
      e.stopPropagation();
      const id = b.dataset.id;
      b.disabled = true;
      rememberRemoval(id);
      await api(`/api/projects/${pid}/placements/${id}`, { method: "DELETE" });
      if (selPl === id) selPl = null;
      toast("길을 막던 제품을 뺐어요 · 되돌리기로 다시 놓을 수 있어요");
      await refresh(true);
    })));
  };
  // ✕는 제품 오른쪽 위 모서리를 따라다닌다 (매 프레임, trackAct에서 부른다)
  trackFlowX = () => {
    if (!flowBlocked.length) return;
    const r = canvasEl.getBoundingClientRect();
    flowBlocked.forEach((x, i) => {
      const b = flowX.children[i];
      if (!b) return;
      const [w, h] = x.size_m, u = x.yaw_rad - Math.PI / 2, top = (x.base_m || 0) + h;
      const ends = [1, -1].map((k) => viewer.toScreen([x.center_xz[0] + Math.cos(u) * k * w / 2, x.center_xz[1] + Math.sin(u) * k * w / 2], top));
      const [sx, sy] = ends[0][0] >= ends[1][0] ? ends[0] : ends[1];
      b.style.transform = `translate(${Math.round(sx - r.left)}px, ${Math.round(sy - r.top)}px)`;
    });
  };
  const runFlow = async () => {
    const box = resOf("flow");
    if (!box) return;
    if (armedStart || !project.scene_state.marks?.start) { setOverlay("flow", ""); viewer.setWalkers([]); clearFlowX(); box.innerHTML = ""; return; }
    const f = await api(`/api/projects/${pid}/sim/flow`);
    if (!simOn("flow") || armedStart || !box.isConnected) return;
    const parts = [], paths = [], blocked = [];
    const lw = pv.sw(2);
    for (const [k, r] of Object.entries(f.routes)) {
      if (!r.reachable) { if (k !== "sink") blocked.push(k); continue; }
      paths.push(r.path);
      parts.push(`<polyline class="route" points="${r.path.map((p) => p.join(",")).join(" ")}" style="stroke-width:${lw}px;stroke-dasharray:${pv.sw(6)} ${pv.sw(5)}"/>`);
      // 좁은 곳: 바닥에 얇은 빨간 고리 (0.9 m보다 좁음)
      for (const n of r.narrow) parts.push(`<circle class="narrow" cx="${n[0]}" cy="${n[1]}" r="0.18" style="stroke-width:0.03px"/>`);
    }
    if (f.start) parts.push(`<circle class="start-dot" cx="${f.start[0]}" cy="${f.start[1]}" r="0.16"/>`);
    setOverlay("flow", parts.join(""));
    viewer.setWalkers(paths); // 실제 크기(170 cm) 사람이 출발 자리에서 제품 앞까지 걷는다
    drawFlowX(blocked);
    box.innerHTML = Object.keys(f.routes).length ? "" : `<p class="sim-line">가전을 놓으면 출발 자리에서 걸어가 볼게요.</p>`;
  };
  const flowCtl = async () => {
    const hasStart = !!project.scene_state.marks?.start, ctl = ctlOf("flow");
    if (!ctl) return;
    if (!hasStart && !armedRouter) armedStart = true; // 처음이면 바로 묻는다 (공유기를 들고 있으면 그것부터)
    ctl.innerHTML = `
      <div class="sim-row">
        ${armedStart ? `<p class="sim-ask"><b>어디서 출발할까요?</b><span>사람을 놓을 자리를 눌러 주세요</span></p>${hasStart ? `<button class="small ghost" id="reStart">취소</button>` : ""}`
          : `<p class="sim-ask"><span>${hasStart ? "출발 자리에서 가전 앞까지 걸어 봐요" : "사람이 출발할 자리를 정해 주세요"}</span></p><button class="small ghost" id="reStart">${hasStart ? "출발 자리 바꾸기" : "출발 자리 놓기"}</button>`}
      </div>`;
    const re = document.getElementById("reStart");
    if (re) re.onclick = () => {
      armedStart = !armedStart;
      if (!armedStart) viewer.personFollow(null);
      else if (armedRouter) { armedRouter = false; viewer.routerFollow(null); if (simOn("wifi")) wifiCtl(); } // 손에는 하나만 든다
      flowCtl();
    };
    if (armedStart) { armed = null; mode = "move"; syncMode(); if (lastHover) viewer.personFollow(lastHover); }
    await runFlow();
  };
  // 와이파이를 켰는데 공유기가 아직 없으면 바로 놓을 수 있게 마우스에 붙인다
  const SIMS = { daylight: daylightCtl, wifi: () => { if (!project.scene_state.router && !armedStart) armedRouter = true; return wifiCtl(); }, flow: flowCtl };
  const showSim = guard(async () => {
    document.querySelectorAll("[data-sim]").forEach((x) => { const on = simOn(x.dataset.sim); x.classList.toggle("on", on); x.setAttribute("aria-checked", on); });
    if (!simOn("daylight")) viewer.setSun(null); // 채광이 아니면 보기 좋은 기본 해
    if (!simOn("wifi")) { viewer.setRouter(null); setOverlay("wifi", ""); if (armedRouter) { armedRouter = false; viewer.routerFollow(null); } }
    if (!simOn("flow")) { viewer.setWalkers([]); viewer.personFollow(null); armedStart = false; clearFlowX(); setOverlay("flow", ""); }
    // 켠 것마다 한 칸씩, 늘 같은 순서로 쌓는다. 이미 있는 칸은 그대로 둔다 (적던 주소가 지워지지 않게)
    const box = document.getElementById("simctl");
    const active = SIM_ORDER.filter(simOn);
    [...box.children].forEach((el) => { if (!simOn(el.dataset.sec)) el.remove(); });
    const fresh = [];
    active.forEach((k, i) => {
      let el = secOf(k);
      if (!el) {
        el = document.createElement("section");
        el.className = "sim-sec"; el.dataset.sec = k;
        el.innerHTML = `<h4>${SIM_KO[k]}</h4><div class="sim-ctl"></div><div class="sim-res"></div>`;
        fresh.push(k);
      }
      if (box.children[i] !== el) box.insertBefore(el, box.children[i] || null);
    });
    box.classList.toggle("many", active.length > 1);
    draw();
    for (const k of fresh) await SIMS[k]();
    if (simOn("wifi") && !fresh.includes("wifi")) await runWifi(); // 채광을 켜고 끄면 색 농도가 달라진다
  });
  document.querySelectorAll("[data-sim]").forEach((b) => (b.onclick = () => { const k = b.dataset.sim; if (simOn(k)) sims.delete(k); else sims.add(k); saveSims(); showSim(); }));
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
    if (!studio.isConnected) return; // 화면을 떠난 뒤 늦게 온 응답은 그리지 않는다
    version = v;
    [project, room, zones] = got;
    if (selPl && !project.scene_state.placements.some((q) => q.placement_id === selPl)) selPl = null;
    const n = project.scene_state.placements.length;
    document.getElementById("sub").textContent = n ? `놓은 제품 ${n}개` : "제품을 골라 우리 집에 놓아 보세요";
    draw();
    if (walking) { viewer.setWalk(walkWorld()); loadStops(); } // 옮긴 제품·치운 가구로 충돌과 들를 곳을 다시
    if (simOn("daylight") && resOf("daylight")) guard(runDaylight)();
    if (simOn("wifi") && resOf("wifi")) guard(runWifi)();
    if (simOn("flow") && resOf("flow")) guard(runFlow)();
    renderInspector();
    renderPlacements();
    renderFinishes();
    scheduleSuggest();
    floorplanBox(document.getElementById("fpBox"), pid, project, () => refresh(true));
    wallTable(document.getElementById("walls"), pid, room, { by: "customer", onChange: () => refresh(true) });
    // glb(벽·가구·색)는 바뀌었을 때만 다시 받는다. 놓은 제품은 화면에서 직접 그린다.
    const sceneKey = JSON.stringify([project.scene_state.materials, project.scene_state.finish, project.scene_state.finish_ids, FIN.length, project.scene_state.hidden_objects, project.scene_state.hidden_walls, project.scene_state.hidden_openings, project.scene_state.object_colors, project.scene_state.object_poses, room.walls.map((w) => w.measured)]);
    thumbSoon();
    if (sceneKey !== lastSceneKey) { lastSceneKey = sceneKey; viewer.setObjects(room.objects, project.scene_state.object_colors); viewer.setFinishes(finishSet()); viewer.load(apiUrl(`/api/projects/${pid}/files/scene.glb`)); }
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
    // 저장 · 불러오기: 로그인을 안 했으면 누를 때 로그인을 안내한다
    const file = mountSaveBar(document.getElementById("savebar"), pid, () => token || project.share_token);
    document.getElementById("saveBtn").onclick = file.save;
    document.getElementById("loadBtn").onclick = file.open;
  }
  (Array.isArray(saved.sims) ? saved.sims : [saved.sim]).filter((k) => SIM_ORDER.includes(k)).forEach((k) => sims.add(k));
  if (sims.size) { setLive(true); showSim(); }
  // ---- 첫 안내: 하우니가 스캔 결과를 알려 주고, 메뉴를 하나씩 짚은 뒤, 직접 놓아 보게 한다 ----
  const tryIt = guard(async () => {
    const pool = suggItems.length ? suggItems.map((x) => x.sku) : suggPool;
    const sku = pool[0];
    if (!sku) { toast("왼쪽 목록에서 제품을 하나 골라 3D 바닥을 눌러 보세요"); return; }
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
      { sel: ".canvas", title: "우리 집 3D", text: "놓은 제품을 누르면 아래에 이동·회전·벽에 붙이기·삭제 버튼이 나와요. 두 손가락으로 확대하고, 끌면 시점이 돌아가요." },
      { sel: "#liveBtn", title: "살아 보기", text: "눈높이로 걸어 보고, 볕·와이파이·동선을 봐요." },
      { sel: "#orderMini", title: "구매 및 설치 신청", text: "마음에 들면 LGE.COM에서 구매하고, 설치 기사 방문을 바로 신청할 수 있어요." },
      { sel: "#botBtn", title: "하우니에게 물어보기", text: "\"600리터 넘는 냉장고\"처럼 말로 물어보면 제가 골라 드려요." },
      outro,
    ] : [
      intro,
      { sel: ".lib-side", title: "제품 찾기", text: "LG 가전, 가구, 벽지·바닥을 탭으로 골라요. '필터'를 열면 품목·가격·색상으로 좁힐 수 있어요." },
      { sel: "#lib", title: "제품 목록", text: "제품을 누르면 상세가 열리고, '넣어 보기'를 누르면 3D에 놓을 수 있어요." },
      { sel: ".canvas", title: "우리 집 3D", text: "바닥을 누르면 제품이 놓여요. 놓은 제품을 누르면 아래에 이동·회전·벽에 붙이기·삭제 버튼이 나와요. 빈 곳을 끌면 시점이 돌아가요." },
      { sel: "#liveBtn", title: "살아 보기", text: "눈높이로 집 안을 걸어 보고, 하루 동안 볕이 어떻게 드는지, 와이파이가 어디까지 닿는지, 동선이 어떤지 봐요." },
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
        <div class="msg hb"><p>안녕하세요, 하우니예요! 어떻게 살고 싶은지 말해 주면 이 집 구조에 맞춰 가구·LG 가전·벽지까지 조합으로 놓아 볼게요. 마음에 드는 방 사진을 붙여도 되고, 가족 이야기를 해 주면 맞는 용량의 가전을 골라 드려요.</p></div>
      </div>
      <div class="chips bot-ex" id="botEx"></div>
      <div class="bot-photo-prev" id="botPhotoPrev" hidden></div>
      <form class="bot-form" id="botForm"><label class="bot-photo" title="사진 붙이기"><input type="file" id="botPhoto" accept="image/jpeg,image/png,image/webp" hidden>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h3l2-2.5h6L17 8h3v11H4z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle cx="12" cy="13" r="3.5" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>
          <span class="sr">사진 붙이기</span></label><input id="botIn" maxlength="500" autocomplete="off" placeholder="예) 호텔 같은 침실, 가전은 300만 원 안" aria-label="하우니에게 말하기">
        <button class="primary" aria-label="보내기">보내기</button></form>
    </section>
    <button class="bot-btn" id="botBtn" aria-expanded="false" aria-controls="botPanel" title="하우니에게 말로 꾸미기">${BOT_SVG}<span class="bot-tip">말로 꾸며 볼까요?</span></button>
  </div>`;
}
