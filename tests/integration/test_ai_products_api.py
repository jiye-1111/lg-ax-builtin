"""말로 꾸미기 대화에서 제품 조건을 말하면 카탈로그에서 맞는 제품을 돌려준다."""
import pytest
from fastapi.testclient import TestClient

from api import main
from core.ai_products import rule_based_products
from core.ai_style import rule_based_style
from core.service import Service

SAMPLE = main.config.ROOT / "data" / "samples" / "synthetic_room.usdz"


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_BLENDER", "0")
    calls = []

    def stylist(prompt, catalog_brief=""):
        calls.append(prompt)
        return rule_based_style(prompt)
    svc = Service(storage=tmp_path, stylist=stylist, product_reader=rule_based_products)
    main.app.dependency_overrides[main.get_service] = lambda: svc
    c = TestClient(main.app)
    with open(SAMPLE, "rb") as f:
        pid = c.post("/api/projects", files={"file": ("room.usdz", f, "model/vnd.usdz+zip")}).json()["project_id"]
    yield c, pid, calls
    main.app.dependency_overrides.clear()


def ask(c, pid, prompt):
    r = c.post(f"/api/projects/{pid}/style/ai", json={"prompt": prompt})
    assert r.status_code == 200, r.text
    return r.json()


def test_product_question_returns_matching_products_and_keeps_room_style(ctx):
    c, pid, _ = ctx
    before = c.get(f"/api/projects/{pid}").json()
    d = ask(c, pid, "600L 이상 베이지 냉장고, 폭 950 안에 들어가는 걸로, 300만 원 이하")
    ps = d["products"]
    assert ps["conditions"] == {"category": "refrigerator", "capacity_min": 600, "color": "베이지",
                                "space_w": 950, "price_max": 3_000_000}
    assert ps["total"] >= 1 and 1 <= len(ps["items"]) <= 5
    for it in ps["items"]:
        p = it["product"]
        assert p["category"] == "refrigerator"
        assert p["options"]["capacity_l"] >= 600
        assert p["price_krw"] <= 3_000_000
        assert it["color_group"] == "베이지"
        assert it["fit"]["verdict"] in ("fit", "conditional")
        assert it["reasons"]
    assert "냉장고" in ps["message"] and str(ps["total"]) in ps["message"]
    assert d["summary"] == ps["message"]
    # 제품만 물었으면 벽지·바닥재는 건드리지 않는다
    assert d["applied"] == {} and d["finishes"] == {"wall": [], "floor": []}
    after = c.get(f"/api/projects/{pid}").json()
    assert after["scene_state"]["materials"] == before["scene_state"]["materials"]
    assert after["style"]["palette"] == before["style"]["palette"]


def test_style_sentence_works_as_before(ctx):
    c, pid, _ = ctx
    d = ask(c, pid, "따뜻한 우드톤에 대리석 포인트 주고 싶어")
    assert d["products"] is None
    assert d["applied"] and d["style"]["palette"]


def test_style_and_products_in_one_sentence(ctx):
    c, pid, _ = ctx
    d = ask(c, pid, "화이트 우드 분위기로 꾸미고 어울리는 냉장고도 골라 줘")
    assert d["applied"] and d["products"]["items"]
    assert d["products"]["message"] in d["summary"]


def test_nothing_matches_says_so(ctx):
    c, pid, _ = ctx
    d = ask(c, pid, "냉장고 폭 200mm 안에 들어가는 걸로")
    assert d["products"]["total"] == 0 and d["products"]["items"] == []
    assert "없" in d["products"]["message"]
