"""꾸며 놓은 집을 보고 하우니가 '여기에 이걸 더하면 좋아요'를 골라 주고, 한 번에 더한다."""
import math

import pytest
from api import main
from core.service import Service
from fastapi.testclient import TestClient

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = Service(storage=tmp_path / "st")
    main.app.dependency_overrides[main.get_service] = lambda: s
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def pid(c):
    with open(REAL, "rb") as f:
        pid = c.post("/api/projects", files={"file": ("home.usdz", f)}, data={"scanned_by": "customer"}).json()["project_id"]
    c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True})  # 스캔 가구를 치운 빈 집
    return pid


def addons(c, pid):
    r = c.get(f"/api/projects/{pid}/addons")
    assert r.status_code == 200, r.text
    return r.json()["items"]


def put(c, pid, sku):
    r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": sku})
    assert r.status_code == 200, r.text
    return r.json()["placement"]


def test_untouched_home_gets_no_nagging(c, pid):
    assert addons(c, pid) == []


def test_bed_gets_nightstand_right_beside_it_and_one_tap_adds_it(c, pid):
    bed = put(c, pid, "decor:bed")
    items = addons(c, pid)
    assert 1 <= len(items) <= 3
    ns = next(i for i in items if i["id"] == "nightstand")
    assert ns["name"] == "협탁" and ns["text"] and ns["kind"] == "decor"
    r = c.post(f"/api/projects/{pid}/addons/nightstand/apply")
    assert r.status_code == 200, r.text
    out = r.json()
    new = [x for x in out["scene_state"]["placements"] if x["placement_id"] in out["added"]]
    assert 1 <= len(new) <= 2
    for x in new:
        assert x["verdict"] != "no_fit"
        assert math.dist(x["center_xz"], bed["center_xz"]) < bed["size_m"][0] / 2 + 0.6   # 침대 바로 옆
    assert "nightstand" not in [i["id"] for i in addons(c, pid)]


def test_lg_addon_is_a_real_product_on_sale_with_price(c, pid):
    s = main.app.dependency_overrides[main.get_service]()
    washer = next(p for p in s.catalog.products if p.category == "washer" and p.listed and p.price_krw and p.sale_status in (None, "ACTIVE"))
    put(c, pid, washer.sku)
    items = addons(c, pid)
    lg = next(i for i in items if i["id"] == "dryer")
    prod = s.catalog.get(lg["sku"])
    assert prod.category == "dryer" and prod.listed and lg["price"] == prod.price_krw
    r = c.post(f"/api/projects/{pid}/addons/dryer/apply")
    assert r.status_code == 200, r.text
    assert any(x["sku"] == lg["sku"] for x in r.json()["scene_state"]["placements"])


def test_unknown_or_stale_addon_is_refused(c, pid):
    put(c, pid, "decor:bed")
    assert c.post(f"/api/projects/{pid}/addons/dryer/apply").status_code in (404, 422)
