"""리모델링 화면 안내 구성 (지예 목업): 5단계 진행, 설치 적합성 검사 카드, 구매·설치 신청.

없는 기능을 가짜로 채우지 않는다: 검사 항목은 판정 코드(recommender.pose.LABELS)에서만 만들고,
전원·배관처럼 데이터가 없는 것은 '기사 확인'으로 안내한다.
"""
import re
from pathlib import Path

from recommender.pose import LABELS

WEB = Path(__file__).resolve().parents[2] / "apps" / "web"
GUIDE = (WEB / "js" / "guide.js").read_text(encoding="utf-8")
REMODEL = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")


def test_five_steps_in_order():
    labels = re.findall(r'label: "([^"]+)"', GUIDE.split("export function stepState", 1)[1].split("export", 1)[0])
    assert labels == ["집 스캔", "제품 선택", "3D 배치", "설치 적합성", "결과 확인"]
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
    assert 'id="orderSheet"' in REMODEL and "#/r" in REMODEL  # 방문 신청 화면으로 이어진다
    assert "./js/guide.js" in (WEB / "sw.js").read_text(encoding="utf-8")
    assert "studio.css" in (WEB / "index.html").read_text(encoding="utf-8")
