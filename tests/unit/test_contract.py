"""전달받은 묶음의 설치 계약(data/lg-library/contracts): 설명서에 적힌 값만 쓰고, 적히지 않은 것은 현장 확인으로 남긴다."""
import json

from core import config
from recommender.contract import clearances, cutout, opening, site_lines

DIR = config.ROOT / "data" / "lg-library" / "contracts"


def load(sku: str) -> dict:
    return json.loads((DIR / f"{sku}.json").read_text(encoding="utf-8"))


def test_every_lineup_model_has_its_contract():
    models = json.loads((config.ROOT / "data/catalog/lineup.json").read_text(encoding="utf-8"))["models"]
    for sku, m in models.items():
        assert load(sku)["sku"] == m["handoff_sku"]


def test_fridge_ventilation_clearances_come_from_the_manual():
    assert clearances(load("B312W31")) == {"side": 100, "back": 100, "top": 100}
    assert clearances(load("MW23BDI")) == {"side": 100, "back": 100, "top": 200}


def test_no_clearance_is_invented_when_the_manual_has_none():
    assert clearances(load("DUE6BGE")) == {}
    assert clearances(load("BEI3ANHLE")) == {}  # 인덕션 벽 이격은 현장 값으로 보는 조건이라 줄로만 낸다


def test_cooktop_cutout_and_dishwasher_opening():
    assert cutout(load("BEI3ANHLE")) == {"w": 560, "d": 480}
    assert cutout(load("B312W31")) == {}
    assert opening(load("DUE6BGE")) == {"w": 600, "h": 815, "d": 600}
    assert opening(load("MW23BDI")) == {}


def test_site_lines_keep_unknown_as_site_check_never_ok():
    lines = site_lines(load("DUE6BG"))
    assert lines and all(x["status"] == "site" for x in lines)
    by = {x["code"]: x for x in lines}
    assert "개구 폭 600~605 mm" in by["manual"]["detail"]
    assert "급수 압력 0.05~1 MPa" in by["manual"]["detail"]
    assert "전원 220 V" in by["manual"]["detail"]
    # 설명서에 수치가 없는 것(문 열림 경로, 정비·사용·통행 공간)은 확인된 것으로 치지 않는다
    assert "정비" in by["unknown"]["detail"] and "통행" in by["unknown"]["detail"]


def test_false_conditions_read_as_not_allowed():
    d = {x["code"]: x for x in site_lines(load("MW23BDI"))}["manual"]["detail"]
    assert "사용자 눈높이 초과 안 됨" in {x["code"]: x for x in site_lines(load("MWJ25E"))}["manual"]["detail"]
    assert "전원 플러그 눌림 안 됨" in {x["code"]: x for x in site_lines(load("DUE6BG"))}["manual"]["detail"]
    assert "수납장 내부 설치 안 됨" in d and "지지면 높이 850 mm 이상" in d and "TV/오디오 거리 4,000 mm 이상" in d


def test_untrusted_rules_are_dropped():
    c = load("B312W31")
    for r in c["rules"]:
        r["source"] = {"status": "guess"}
    assert clearances(c) == {} and all(x["code"] != "manual" for x in site_lines(c))
