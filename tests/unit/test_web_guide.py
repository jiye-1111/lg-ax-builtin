"""리모델링 화면 안내 구성 (지예 정정 목업): 3단계 진행, 설치 확인 카드, 구매·설치 신청, 첫 안내.

없는 기능을 가짜로 채우지 않는다: 검사 항목은 판정 코드(recommender.pose.LABELS)에서만 만들고,
전원·배관처럼 데이터가 없는 것은 '기사 확인'으로 안내한다.
"""
import re
from pathlib import Path

from recommender.pose import LABELS

WEB = Path(__file__).resolve().parents[2] / "apps" / "web"
GUIDE = (WEB / "js" / "guide.js").read_text(encoding="utf-8")
REMODEL = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")


def test_three_steps_in_order():
    labels = re.findall(r'label: "([^"]+)"', GUIDE.split("export function stepState", 1)[1].split("export", 1)[0])
    assert labels == ["공간 확인", "제품 고르기", "설치 확인"]
    assert 'id="progress"' in REMODEL


def test_fit_rows_cover_every_reason_code():
    # 판정 코드가 늘면 검사 카드의 어느 줄에 들어갈지도 정해야 한다
    block = GUIDE.split("const GROUPS", 1)[1].split("];", 1)[0]
    codes = set(re.findall(r'"([a-z_]+)"', block))
    notes = set(re.findall(r'"([a-z_]+)"', GUIDE.split("const NOTES", 1)[1].split("]", 1)[0]))
    assert set(LABELS) <= codes | notes, set(LABELS) - codes - notes


def test_no_fake_checks_and_clear_cta():
    assert "전원" in GUIDE and "기사" in GUIDE  # 전원·배관은 검사한 척하지 않고 기사 확인으로
    assert 'id="orderBtn"' in REMODEL and "구매 및 설치 신청" in REMODEL
    assert 'id="orderSheet"' in REMODEL and "installRequestBox(irBox" in REMODEL  # 놓은 제품 그대로 방문 설치 신청으로 이어진다
    assert "./js/guide.js" in (WEB / "sw.js").read_text(encoding="utf-8")
    assert "studio.css" in (WEB / "index.html").read_text(encoding="utf-8")


def test_selected_product_shows_dimensions_and_needed_space():
    viewer = (WEB / "js" / "viewer.js").read_text(encoding="utf-8")
    # 고른 제품에는 치수선(mm), 바닥에는 판정과 같은 계산으로 얻은 필요 공간
    assert "dimLines(w, h, d)" in viewer and "setNeed(pts)" in viewer
    assert "viewer.setNeed(r.required)" in REMODEL and "pose-check" in REMODEL
    assert 'id="needTag"' in REMODEL


def test_simple_layout_from_corrected_mockup():
    """지예: 탭·토글이 많아 지저분하다 → 오른쪽 탭 없음, 3D 위·아래 조작 버튼, 살아 보기는 버튼 하나."""
    assert "side-tabs" not in REMODEL and 'data-tab="' not in REMODEL
    assert 'id="guideBar"' not in REMODEL and 'data-view="split"' not in REMODEL
    for el in ('id="undo"', 'id="redo"', 'id="fullBtn"', 'id="actBar"', 'id="fitBadge"', 'id="liveBtn"',
               'id="finBtn"', 'id="extraBtn"', 'id="homeMenu"', 'id="sugg"', 'id="moreFilter"', 'id="resetFilter"'):
        assert el in REMODEL, el
    # 조작은 서버 계산을 그대로: 자동 정렬, 알맞은 자리, 이 집에 들어가는 제품, 제품 자리 채광·와이파이
    for path in ("/auto-align", "/auto-place", "/suggest", "/life-check"):
        assert path in REMODEL, path
    assert 'badge rec' in REMODEL
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
