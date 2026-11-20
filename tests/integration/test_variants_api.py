"""모델 묶음 API + 놓은 제품의 색·재질(같은 모델 다른 SKU) 바꾸기."""
import pytest
from fastapi.testclient import TestClient

from api import main
from core.service import Service

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"


@pytest.fixture
def c(tmp_path):
    svc = Service(storage=tmp_path / "st")
    main.app.dependency_overrides[main.get_service] = lambda: svc
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def placed(c):
    with open(REAL, "rb") as f:
        pid = c.post("/api/projects", files={"file": ("home.usdz", f)}, data={"scanned_by": "customer"}).json()["project_id"]
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": "G646GBB031", "center_xz": [-5.0, 0.0], "yaw_rad": 0.0})
    assert r.status_code == 200, r.text
    return pid, r.json()["placement"]["placement_id"]


def test_families_endpoint_groups_real_products(c):
    fams = c.get("/api/catalog/families").json()
    real = [f for f in fams if not f["demo_only"]]
    assert len(real) == 268  # 1,150개 제품 → 268개 모델
    fr = next(f for f in real if f["family_id"] == "G646GBB031")
    assert [v["sku"] for v in fr["variants"]][:3] == ["G646GBB031", "G646MEE021", "G646SVV031"]
    # 색마다 그 색으로 렌더한 제품 사진이 있다 (카드에서 사진을 눌러 고른다)
    assert all(v["thumb"] == f"img/products/{v['sku']}.webp" for f in real for v in f["variants"])


def test_switch_to_sibling_variant_changes_sku_and_color(c, placed):
    pid, plid = placed
    r = c.patch(f"/api/projects/{pid}/placements/{plid}", json={"sku": "G646SVV031"})
    assert r.status_code == 200, r.text
    x = r.json()["placement"]
    assert x["sku"] == "G646SVV031" and x["color"] == "오브제컬렉션 실버" and x["hex"] == "#D7D7D7"


def test_switch_to_other_model_is_rejected(c, placed):
    pid, plid = placed
    r = c.patch(f"/api/projects/{pid}/placements/{plid}", json={"sku": "DUE6BGE"})
    assert r.status_code == 422
