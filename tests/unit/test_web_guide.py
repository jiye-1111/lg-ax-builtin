"""리모델링 화면 안내 구성 (지예 정정 목업): 설치 확인 카드, 구매·설치 신청, 첫 안내.

없는 기능을 가짜로 채우지 않는다: 검사 항목은 판정 코드(recommender.pose.LABELS)에서만 만들고,
전원·배관처럼 데이터가 없는 것은 '기사 확인'으로 안내한다.
"""
import re
from pathlib import Path

from recommender.pose import LABELS

WEB = Path(__file__).resolve().parents[2] / "apps" / "web"
GUIDE = (WEB / "js" / "guide.js").read_text(encoding="utf-8")
REMODEL = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")


def test_no_step_indicator_and_familiar_file_buttons():
    """지예: 단계를 굳이 나눌 필요 없다 → 진행 단계 표시는 없고, 머리에는 새로 만들기 · 불러오기 · 저장만."""
    assert "stepState" not in GUIDE and 'id="progress"' not in REMODEL and "stepCard" not in REMODEL
    head = REMODEL.split('<header class="studio-head">', 1)[1].split("</header>", 1)[0]
    assert head.index("새로 만들기") < head.index("불러오기") < head.index(">저장<")
    for el in ('id="newBtn"', 'id="loadBtn"', 'id="saveBtn"', 'href="#/new"'):
        assert el in head, el
    account = (WEB / "js" / "account.js").read_text(encoding="utf-8")
    # '로그인 필요' 표시는 없고, 로그인 없이 저장·불러오기를 누르면 그때 안내한다
    assert "로그인 필요" not in account and "로그인 필요" not in REMODEL
    assert "저장하려면 로그인해 주세요." in account and "불러오려면 로그인해 주세요." in account
    assert "return { save: () => manual(), open: history };" in account


def test_live_panels_ask_for_as_little_as_possible():
    """지예: 채광은 주소만 넣고 어느 향인지, 동선은 '어디서 출발할까요?'.
    와이파이는 (2026-11-26 새 요청) 주파수 고르고 공유기를 놓으면 끊김 없는 색 + 등고선, 자세한 원인·설정은 접어 둔다."""
    sims = REMODEL.split("const runDaylight", 1)[1].split("const SIMS", 1)[0]
    wifi = sims.split("// ---- 살아 보기: 와이파이 ----", 1)[1].split("// ---- 가구 치우기", 1)[0]
    rest = sims.replace(wifi, "")
    for gone in ('id="north"', 'id="region"', 'id="sdate"', 'id="stime"', 'id="sheat"', "bestRouter", "가장 약한 곳",
                 "mkEnt", "mkSink", "현관 지정", "싱크 위치 지정", "작업 삼각형", "dBm"):
        assert gone not in rest, gone
    assert 'id="addr"' in sims and "집이에요" in sims
    assert 'data-band="${k}"' in wifi and '["6", "최신"]' in wifi and 'id="putRouter"' in wifi
    assert "viewer.setWifiHeat" in wifi and "probeWifi" in wifi and '<details class="wifi-more"' in wifi
    assert "어디서 출발할까요?" in sims and "viewer.personFollow" in REMODEL and "/marks/start" in REMODEL
    # 길이 막힌 제품에는 ✕, 누르면 뺀다
    assert 'class="flow-x"' in sims and 'method: "DELETE"' in sims.split("drawFlowX", 1)[1].split("trackFlowX", 1)[0]
    viewer = (WEB / "js" / "viewer.js").read_text(encoding="utf-8")
    assert "personFollow(xz)" in viewer and "doorExtras" in viewer
    for k in ("sink", "door"):
        assert (WEB / "models" / "furniture" / f"{k}.glb").exists() and (WEB / "img" / "decor" / f"{k}.webp").exists(), k


def test_fit_rows_cover_every_reason_code():
    # 판정 코드가 늘면 검사 카드의 어느 줄에 들어갈지도 정해야 한다
    block = GUIDE.split("const GROUPS", 1)[1].split("];", 1)[0]
    codes = set(re.findall(r'"([a-z_]+)"', block))
    notes = set(re.findall(r'"([a-z_]+)"', GUIDE.split("const NOTES", 1)[1].split("]", 1)[0]))
    assert set(LABELS) <= codes | notes, set(LABELS) - codes - notes


def test_no_fake_checks_and_clear_cta():
    assert "전원" in GUIDE and "기사" in GUIDE and "INSTALL_NOTE" in REMODEL  # 전원·배관은 검사한 척하지 않고 신청할 때 기사 확인으로 안내
    assert 'id="orderBtn"' in REMODEL and "구매 및 설치 신청" in REMODEL
    assert 'id="orderSheet"' in REMODEL and "installRequestBox(irBox" in REMODEL  # 놓은 제품 그대로 방문 설치 신청으로 이어진다
    assert "./js/guide.js" in (WEB / "sw.js").read_text(encoding="utf-8")
    assert "studio.css" in (WEB / "index.html").read_text(encoding="utf-8")


def test_selected_product_shows_needed_space_without_size_labels():
    viewer = (WEB / "js" / "viewer.js").read_text(encoding="utf-8")
    # 놓을 때 3D에 치수 글자는 띄우지 않는다 (치수는 제품 카드·상세에서). 바닥에는 판정과 같은 계산으로 얻은 필요 공간
    assert "dimLines" not in viewer and "dimLabel" not in viewer and "setNeed(pts" in viewer
    assert "viewer.setNeed(r.required" in REMODEL and "pose-check" in REMODEL
    assert 'id="needTag"' in REMODEL


def test_simple_layout_from_corrected_mockup():
    """지예: 탭·토글이 많아 지저분하다 → 오른쪽 탭 없음, 3D 위·아래 조작 버튼, 살아 보기는 버튼 하나."""
    # 탭은 왼쪽 라이브러리(전체/LG 가전/가구/수납/소품/벽지·바닥) 하나뿐, 오른쪽은 탭 없음
    assert "side-tabs" not in REMODEL and REMODEL.count('data-tab="') == 6
    assert 'id="guideBar"' not in REMODEL and 'data-view="split"' not in REMODEL
    for el in ('id="undo"', 'id="redo"', 'id="fullBtn"', 'id="actBar"', 'id="fitBadge"', 'id="liveBtn"',
               'data-tab="finish"', 'id="extraBtn"', 'id="saveBtn"', 'id="sugg"', 'id="moreFilter"', 'id="resetFilter"'):
        assert el in REMODEL, el
    # 조작은 서버 계산을 그대로: 자동 정렬, 알맞은 자리, 이 집에 들어가는 제품
    for path in ("/auto-align", "/auto-place", "/suggest"):
        assert path in REMODEL, path
    # 지예: 들어가는 건 굳이 표시하지 않고, 안 되는 것만 알린다 ('확인 필요'·'들어가요' 표시 없음)
    assert 'badge rec' not in REMODEL and "확인 필요" not in REMODEL and "확인 필요" not in GUIDE
    assert "채광" in GUIDE and "와이파이" in GUIDE and "설치 가능합니다!" in GUIDE


def test_first_visit_tour_with_haunie():
    tour = (WEB / "js" / "tour.js").read_text(encoding="utf-8")
    assert "startTour(" in REMODEL and "tourSeen()" in REMODEL and 'id="tourBtn"' in REMODEL
    assert "집 스캔이 끝났어요!" in REMODEL and "직접 체험해 볼까요?" in REMODEL
    assert "localStorage" in tour and "tour-hole" in tour
    assert "./js/tour.js" in (WEB / "sw.js").read_text(encoding="utf-8")


def test_app_layout_for_phone_and_small_window():
    """지예: 앱으로 열면 읽기 어렵고 안내가 안 맞는다 → 좁은 화면은 3D 꽉 차게, 제품은 서랍, 안내는 보이는 메뉴만."""
    css = (WEB / "studio.css").read_text(encoding="utf-8")
    tour = (WEB / "js" / "tour.js").read_text(encoding="utf-8")
    assert "APP_MAX_W" in REMODEL and 'classList.toggle("app"' in REMODEL
    assert 'id="libMore"' in REMODEL and 'id="orderMini"' in REMODEL and 'id="extraBtn2"' in REMODEL
    assert ".studio.app" in css and ".studio.app.has-sel .side" in css and ".studio.app.lib-open .lib" in css
    assert "NARROW_W" in tour  # 좁은 화면은 말풍선을 화면 폭에 맞춰 밝힌 곳 위·아래에
    assert '{ sel: "#libMore"' in REMODEL  # 앱 안내는 앱 화면에 있는 메뉴를 짚는다


def test_start_view_is_never_stuck_on_the_floor():
    """지예: 시작 화면이 바닥에 붙은 시점, 반쪽만 그려짐 → 저장된 시점이 이상하면 방 전체 보기, 화면 배율이 바뀌면 다시 맞춤."""
    viewer = (WEB / "js" / "viewer.js").read_text(encoding="utf-8")
    assert "sensibleCam(" in viewer and "ctl.minDistance" in viewer
    assert "renderer.getPixelRatio() !== Math.min(devicePixelRatio" in viewer  # 브라우저 확대·축소(화면 배율)가 바뀌면 다시 잡는다


def test_three_areas_layout_and_feedback():
    css = (WEB / "studio.css").read_text(encoding="utf-8")
    account = (WEB / "js" / "account.js").read_text(encoding="utf-8")
    guide = (WEB / "js" / "guide.js").read_text(encoding="utf-8")
    # 왼쪽: 카드는 사진·이름·모델명·가격 / 색과 '공간에 배치하기' (지예: 폭·높이·깊이는 카드에서 빼고 상세에만)
    assert 'class="dims"' not in REMODEL and "공간에 배치하기" in REMODEL and 'class="model"' in REMODEL and 'class="card-foot"' in REMODEL
    assert 'id="pLo"' in REMODEL and 'id="pHi"' in REMODEL and "setupBudget(pre)" in REMODEL
    # 가운데: 놓으면 그 자리로 시점 이동, 조작 메뉴는 고른 제품 위에 (상세 포함), 안 되면 이유와 고칠 방법
    assert "viewer.lookAt(r.placement.center_xz)" in REMODEL and 'actBtn("actInfo"' in REMODEL
    assert "const FIX = {" in REMODEL and ".act-bar.near" in css
    # 오른쪽: 설치 체크(누르면 그 제품으로) · 합계와 신청 (지예: 이것만). 도면은 3D 구석 작은 지도로
    assert '.studio .side #mapSlot, .studio .side #suggSlot, .studio .side #plBox { display: none; }' in css
    for frag in ('id="chkBox"', 'id="mapSlot"', 'id="suggSlot"', 'id="orderTotal"', "focusPlacement", 'id="camMark"', "data-scat", "data-splace"):
        assert frag in REMODEL, frag
    # 저장 상태 다섯 가지
    for word in ("저장 중…", "저장 실패", "저장 안 된 변경", "저장됨 · "):
        assert word in account, word


def test_space_library_tabs_decor_and_wall_edit():
    """왼쪽 라이브러리: 전체/LG 가전/가구/수납/소품 + 벽 추가·제거·파티션, 가구는 정보 없이 모양만, 신청은 LG만."""
    js = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    for tab in ('data-tab="all"', 'data-tab="lg"', 'data-tab="furniture"', 'data-tab="storage"', 'data-tab="decor"'):
        assert tab in js
    assert "/api/decor" in js and "벽체 & 구조 변경" in js and 'id="wallRm"' in js
    assert "/walls/${wid}/hidden" in js and "setWallPick" in js
    # 벽 추가는 바닥에서 시작점 → 끝점, 철거·가벽은 가상 체험이라고 알린다
    assert "setWallDraw" in js and "시작점" in js and "가상 체험" in js
    # 3D 메뉴: 크기 조절(메뉴 안 슬라이더)·복사. 가구를 골라도 오른쪽은 그대로 (지예)
    assert '"actCopy"' in js and '"actSize"' in js and "sizeBar(x)" in js and "/copy`" in js
    # 신청·합계는 LG 가전만
    assert "lgOnly(project.scene_state.placements)" in js
    viewer = (WEB / "js" / "viewer.js").read_text(encoding="utf-8")
    assert 'startsWith("decor:")' in viewer and "fitFurniture" in viewer and "setWallPick" in viewer
    for k in ("sofa", "table", "chair", "desk", "shelf", "storage", "rug", "lamp", "plant", "wall", "partition", "wall-remove", "dresser", "basecab"):
        assert (WEB / "img" / "decor" / f"{k}.webp").exists(), k


def test_toolbar_switches_and_one_button_toggles():
    """지예: 살아 보기는 오른쪽 위 밀어서 켜는 스위치(채광·와이파이·동선), 처음과 비교·가구 모두 지우기는 버튼 하나, 도면·실측은 뺀다."""
    css = (WEB / "studio.css").read_text(encoding="utf-8")
    for k in ("daylight", "wifi", "flow"):
        assert f'class="simsw" data-sim="{k}" role="switch"' in REMODEL, k
    assert 'class="icon-btn" id="furn"' in REMODEL and 'class="icon-btn" id="beforeBtn"' in REMODEL
    assert "가구 모두 지우기" not in REMODEL and "처음과 비교" not in REMODEL
    assert "#liveBtn, #liveBar, .studio #extraBtn { display: none !important; }" in css
    # 손에 든 물건은 마우스를 따라오고 누르면 놓인다 (가구·가전·가벽·공유기 모두)
    assert "const follow = (p) =>" in REMODEL and "arm(b.dataset.decor)" in REMODEL and "viewer.routerFollow(p)" in REMODEL


def test_combo_panel_and_haeuni_use_server_combos():
    """지예: 가전 종류와 목표 가격을 고르면 조합 2~3개를 3D에 한 번에. 하우니는 나열 대신 조합·한 개 추천."""
    js = (WEB / "js" / "combos.js").read_text(encoding="utf-8")
    assert 'id="comboBudget"' in js and 'id="comboCats"' in js and "/combos" in js and "/apply" in js
    assert 'id="comboBtn"' in REMODEL and "comboPopHtml()" in REMODEL
    assert "/assist" in REMODEL and "/style/ai`, { prompt })" not in REMODEL.split("botForm.onsubmit", 1)[1]
    css = (WEB / "studio.css").read_text(encoding="utf-8")
    assert ".canvas > .sim-switches" in css


def test_color_dots_only_for_products_with_a_color_name():
    js = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    assert "x.color && a.findIndex" in js


def test_action_bar_drops_its_follow_position_when_holding_something():
    # 들고 있을 때 메뉴가 예전 자리에서 길게 늘어나 바닥 클릭을 막던 문제
    js = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    assert 'actBar.style.left = ""' in js and 'actBar.style.top = ""' in js


def test_haeuni_takes_a_photo_and_sends_it_small():
    js = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    assert 'id="botPhoto"' in js and "PHOTO_MAX = 1024" in js and 'toDataURL("image/jpeg"' in js
    assert "(image ? { image } : {})" in js and 'd.type === "message"' in js


def test_photoreal_button_sends_view_and_product_mask():
    js = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    vw = (WEB / "js" / "viewer.js").read_text(encoding="utf-8")
    assert 'id="render"' in js and "<span>실사</span>" in js and "/photoreal" in js and "viewer.snapshot()" in js
    assert "snapshot(W = 1536, H = 1024)" in vw and 'startsWith("decor:")' in vw


def test_detail_color_chips_have_no_model_numbers():
    # 같은 색 모델이 여럿이면 칩에 모델 번호를 붙여 20개 넘게 늘어지던 것: 칩은 색마다 하나, 모델은 작은 목록
    js = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    assert "optLabel" not in js and 'id="pdModel"' in js and "${esc(g.k)}</button>" in js


def test_haeuni_shows_life_picks_with_guide_link_and_combo_follow_up():
    js = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    assert 'd.type === "life"' in js and "LGE.COM 기준" in js and "categories: d.categories, life: d.life" in js


def test_left_filter_order_and_wide_3d():
    """지예: 왼쪽 필터를 카테고리 → 설치 방식 → 품목 → 가격 범위 → 상세 필터 순서로, 3D는 넓게."""
    css = (WEB / "studio.css").read_text(encoding="utf-8")
    order = ['id="libTabs"', 'id="installSeg"', 'id="cats"', 'id="budget"', 'id="moreFilter"', 'id="resetFilter"', 'id="applyFilter"', 'id="applied"', 'id="lib"']
    at = [REMODEL.index(x) for x in order]
    assert at == sorted(at), order
    # 가격은 최소·최대 금액을 보고 직접 넣을 수 있다. 눈금은 실제 가격에서 나온다
    assert 'id="pLoIn"' in REMODEL and 'id="pHiIn"' in REMODEL and "priceScale(ps)" in REMODEL
    # 적용된 조건은 칩으로 보이고 하나씩 뺄 수 있다
    assert "appliedFilters(" in REMODEL and "clearFilter(" in REMODEL and "적용하기 (${n})" in REMODEL
    # 3D 약 79% · 제품 탐색 약 21%, 패널과 아래 정보 칸은 접을 수 있다
    assert "clamp(288px, 20vw, 340px)" in css and ".lib-folded" in css and 'id="libFold"' in REMODEL
    assert 'id="simFold"' in REMODEL and ".sim-folded" in css


def test_finish_tab_shows_only_color_chips():
    """지예: 벽지 파는 곳이 아니다 → 벽지·바닥은 왼쪽 탭에서 색깔만 고른다. 상표·품명·출처·말로 꾸미기 상자는 없다."""
    assert 'data-tab="finish">벽지·바닥</button>' in REMODEL
    for gone in ('id="finBtn"', 'id="finishPop"', "aiBoxHtml", "f.brand", "f.trend", "f.source_url", "2026 트렌드", "말로 꾸미기 <span"):
        assert gone not in REMODEL, gone
    assert 'class="fin-sw' in REMODEL and "/finishes`" in REMODEL


def test_furniture_x_and_hold_to_compare():
    """지예: 가구마다 ✕가 떠 있으면 징그럽다 → 마우스를 올린 가구·창문에만 ✕. 처음 모습은 누르고 있는 동안만 보인다."""
    assert 'id="furnX"' in REMODEL and 'id="furnAll"' in REMODEL
    assert "wantHoverHit: () => furnPick" in REMODEL and 'class="flow-x soft"' in REMODEL
    assert "furnShown = HOVERS ? (furnHot ? [furnHot] : []) : all" in REMODEL  # 터치 화면만 전부 띄운다
    assert "/openings/" in REMODEL  # 창문도 같은 ✕로 없앤다
    assert "beforeBtn.onpointerdown" in REMODEL and '"pointerup"' in REMODEL


def test_view_stack_on_the_3d_view():
    """지예: 떠 있는 걷기 버튼이 뭔지 모르겠다 → 3D 오른쪽 위에 지도 앱처럼 보기 버튼을 세로로 (위에서 / 걸어 보기 / 실사)."""
    for el in ('class="view-stack"', 'class="vbtn on" id="viewTop"', 'class="vbtn" id="walk"', 'class="vbtn" id="render"'):
        assert el in REMODEL, el
    assert "walk-btn" not in REMODEL and "render-btn" not in REMODEL
    # 위 도구 아이콘에는 이름이 붙는다. 되돌리기·다시는 화살표만 (글자가 지저분해 보인다고 해서 뺐다)
    for label in ("가구 치우기", "처음 모습", "전체 화면"):
        assert f'data-l="{label}"' in REMODEL, label
    assert 'data-l="되돌리기"' not in REMODEL and 'data-l="다시"' not in REMODEL
    assert 'id="undo" disabled aria-label="되돌리기"' in REMODEL


def test_live_modes_stack_and_time_bar():
    """지예: 채광·와이파이·동선을 같이 켜고 싶다. 하루 재생 대신 향 아래에 시간 바."""
    assert "const sims = new Set()" in REMODEL and 'class="sim-sec"' not in REMODEL.split("const showSim")[0]
    assert 'id="sunTime"' in REMODEL and "하루 재생" not in REMODEL and 'id="splay"' not in REMODEL
    # 고르지 않아도 누른 채 끌면 잡힌다. 조금만 움직인 건 누르기로 본다 (실수로 밀리지 않게)
    viewer = (WEB / "js" / "viewer.js").read_text(encoding="utf-8")
    assert "canGrab" in REMODEL and "onGrab" in REMODEL and "GRAB_PX" in viewer
    assert "누른 채 끌기" in REMODEL


def test_walk_tour_bar():
    """지예: 걸어 보기를 들를 곳을 따라 둘러보는 식으로. 줄에서 곳을 누르면 걸어가고 한 번에 둘러볼 수도 있다."""
    css = (WEB / "studio.css").read_text(encoding="utf-8")
    viewer = (WEB / "js" / "viewer.js").read_text(encoding="utf-8")
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    assert 'id="walkTour"' in REMODEL and 'id="wtLine"' in REMODEL and "한 번에 둘러보기" in REMODEL
    assert "tourStops(" in REMODEL and "findPath(" in REMODEL
    assert "walkTo(" in viewer and "onWalkStop" in viewer
    assert ".walk-tour" in css and "./js/stops.js" in sw


def test_walk_plan_is_calm():
    """지예: 걸어 보기 도면이 알록달록하면 안 된다. 문·창·제품 테두리는 베이지 계열, 빨강은 선 곳에만."""
    css = (WEB / "studio.css").read_text(encoding="utf-8")
    for sel in (".zone", ".placed:not(.v-no_fit) rect"):
        assert f".studio.walking .minimap .plan {sel}" in css, sel
    # 문·창은 어느 도면에서나 색 없이: 벽을 비운 자리 + 유리 선, 문 열리는 호
    base = (WEB / "style.css").read_text(encoding="utf-8")
    assert ".plan .door, .plan .window { stroke: #fdfbf8" in base
    assert "#c99a6b" not in base and "#86bde3" not in base


def test_plan_draws_furniture_as_symbols():
    """지예: 네모만 있는 도면은 성의 없어 보인다. 가구는 평면도 기호로, 들를 곳 점은 빨간 테두리 없이."""
    plan = (WEB / "js" / "plan.js").read_text(encoding="utf-8")
    assert "furnitureSymbol(" in plan and 'class="swing"' in plan and 'class="floor"' in plan
    css = (WEB / "studio.css").read_text(encoding="utf-8")
    dot = css.split(".plan .stop-dot {")[1].split("}")[0]
    assert "#a50034" not in dot
    assert "radialGradient" in REMODEL and "viewFan" in REMODEL


def test_minimap_buttons_match_the_other_buttons():
    """작은 도면 위 버튼만 어두워서 튀지 않게: 흰 바탕에 짙은 글씨."""
    css = (WEB / "studio.css").read_text(encoding="utf-8")
    rule = css.split("\n.minimap :is(.mini-grow, .pip-swap) {")[1].split("}")[0]
    assert "rgba(255, 255, 255" in rule and "var(--ink" in rule


def test_scene_reloads_when_a_window_is_removed_or_furniture_recoloured():
    """창을 없애거나 스캔 가구 색을 바꾸면 3D를 다시 읽어야 화면에 바로 보인다."""
    key = REMODEL.split("const sceneKey = ")[1].split("\n")[0]
    assert "hidden_openings" in key and "object_colors" in key


def test_furniture_colour_is_picked_from_the_3d_menu():
    assert 'actBtn("actColor", "color", "색")' in REMODEL and 'class="cl-dot' in REMODEL


def test_installed_lg_appliances_change_colour_only_to_real_colours():
    """지예: 가전도 설치한 뒤 색을 바꿀 수 있게. 단, 그 모델에 실제로 있는 색(같은 모델군)으로만 바꾼다."""
    fn = REMODEL.split("const lgColours = ")[1].split("const colourBar")[0]
    assert "familyOf(x.sku)" in fn and "v.color" in fn and "sellable(v)" in fn
    bar = REMODEL.split("const colourBar = ")[1].split("// 빈틈에 맞추기")[0]
    assert 'JSON.stringify({ sku: to.sku })' in bar


def test_haeuni_shows_numbered_layouts_with_a_picture_and_speaks_first():
    js = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    combos = (WEB / "js" / "combos.js").read_text(encoding="utf-8")
    viewer = (WEB / "js" / "viewer.js").read_text(encoding="utf-8")
    assert "previewShot(" in viewer and "viewer.previewShot(" in js      # 놓아 본 모습을 3D에서 찍는다
    assert "combo-no" in combos and "번으로 꾸미기" in combos               # 1·2·3번
    assert "/addons" in js and 'id="botHint"' in js                       # 꾸민 뒤 먼저 권한다
    assert "./js/hauni.js" in (WEB / "sw.js").read_text(encoding="utf-8")
