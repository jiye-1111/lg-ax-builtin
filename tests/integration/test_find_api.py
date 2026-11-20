"""조건으로 제품 찾기 API: 화면의 추천 카드와 상세 필터(용량·색상·가격대)가 쓴다."""
import pytest
from fastapi.testclient import TestClient

from api import main
from core.service import Service

SYNTH = main.config.ROOT / "data" / "samples" / "synthetic_room.usdz"
KITCHEN = [[0, 0], [3.0, 0], [3.0, 1.6], [0, 1.6]]


@pytest.fixture
def c(tmp_path):
    svc = Service(storage=tmp_path / "st")
    main.app.dependency_overrides[main.get_service] = lambda: svc
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_find_refrigerators_that_fit_typed_width(c):
    r = c.get("/api/catalog/find", params={"category": "refrigerator", "capacity_min": 600, "space_w": 950, "limit": 3})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == 3 and body["total"] > 3
    for it in body["items"]:
        p = it["product"]
        assert p["category"] == "refrigerator" and p["options"]["capacity_l"] >= 600
        assert it["fit"]["verdict"] in ("fit", "conditional") and it["fit"]["source"] == "typed"
        assert it["family_id"] and it["thumb"] and it["reasons"]
    # 같은 모델의 색만 다른 제품은 한 줄로
    assert len({it["family_id"] for it in body["items"]}) == 3
    labels = [b["label"] for b in body["facets"]["capacity"]]
    assert labels == ["400L 이하", "400~600L", "600L 이상"]
    assert {"화이트", "베이지"} <= {x["label"] for x in body["facets"]["color"]}


def test_fits_only_and_color_and_sort(c):
    all_ = c.get("/api/catalog/find", params={"category": "refrigerator", "space_w": 700}).json()
    only = c.get("/api/catalog/find", params={"category": "refrigerator", "space_w": 700, "fits_only": True}).json()
    assert 0 < only["total"] < all_["total"]
    assert all(it["fit"]["verdict"] != "no_fit" for it in only["items"])
    beige = c.get("/api/catalog/find", params={"category": "refrigerator", "color": "베이지"}).json()
    assert beige["total"] and all(it["color_group"] == "베이지" for it in beige["items"])
    by_size = c.get("/api/catalog/find", params={"category": "refrigerator", "sort": "size"}).json()["items"]
    ws = [it["product"]["product_dims_mm"]["w"] for it in by_size]
    assert ws == sorted(ws)


def test_bad_values_are_rejected(c):
    assert c.get("/api/catalog/find", params={"sort": "random"}).status_code == 422
    assert c.get("/api/catalog/find", params={"color": "무지개"}).status_code == 422
    assert c.get("/api/catalog/find", params={"space_w": -5}).status_code == 422


def test_project_find_uses_drawn_zone(c):
    with open(SYNTH, "rb") as f:
        pid = c.post("/api/projects", files={"file": ("home.usdz", f)}).json()["project_id"]
    # 영역을 안 그렸으면 공간 판정 없이 조건만
    none = c.get(f"/api/projects/{pid}/find", params={"category": "refrigerator", "limit": 3}).json()
    assert all(it["fit"] is None for it in none["items"])
    z = c.post(f"/api/projects/{pid}/zones", json={"purpose": "kitchen", "polygon_m": KITCHEN, "name": "주방"}).json()
    res = c.get(f"/api/projects/{pid}/find", params={"category": "refrigerator", "limit": 3}).json()
    assert res["zone_id"] == z["zone_id"]
    assert all(it["fit"]["source"] == "zone" for it in res["items"])
    assert res["items"][0]["fit"]["verdict"] in ("fit", "conditional")
    # 영역 판정은 영역 추천 API와 같은 값이다 (같은 코드가 계산)
    rec = c.get(f"/api/projects/{pid}/zones/{z['zone_id']}/recommendations", params={"category": "refrigerator"}).json()
    by_sku = {it["product"]["sku"]: it["fit"]["verdict"] for it in rec["items"]}
    assert all(by_sku[it["product"]["sku"]] == it["fit"]["verdict"] for it in res["items"])
    # 폭을 직접 넣으면 그 값이 먼저다
    typed = c.get(f"/api/projects/{pid}/find", params={"category": "refrigerator", "space_w": 950, "limit": 3}).json()
    assert all(it["fit"]["source"] == "typed" for it in typed["items"])
