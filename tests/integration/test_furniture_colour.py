"""가구 색 고르기: 놓은 가구도, 스캔한 가구도 색을 바꿀 수 있다. LG 제품 색은 카탈로그 색만."""
import pytest
from fastapi.testclient import TestClient

from api import main
from core.service import Service

APT = main.config.ROOT / "data" / "samples" / "apt_living_kitchen.usdz"


@pytest.fixture
def c(tmp_path):
    svc = Service(storage=tmp_path / "st")
    main.app.dependency_overrides[main.get_service] = lambda: svc
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def pid(c):
    with open(APT, "rb") as f:
        return c.post("/api/projects", files={"file": ("home.usdz", f)}, data={"scanned_by": "customer"}).json()["project_id"]


def state(c, pid):
    return c.get(f"/api/projects/{pid}").json()["scene_state"]


def test_placed_furniture_takes_a_colour(c, pid):
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:dresser", "center_xz": [4.0, 2.4], "yaw_rad": 0}).json()["placement"]
    r = c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}", json={"hex": "#3A4660"})
    assert r.status_code == 200, r.text
    assert r.json()["placement"]["hex"] == "#3A4660"
    assert state(c, pid)["placements"][0]["hex"] == "#3A4660"
    assert r.json()["placement"]["center_xz"] == x["center_xz"]  # 자리는 그대로
    r = c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}", json={"hex": ""})  # 원래 색으로
    assert r.status_code == 200 and r.json()["placement"]["hex"] is None


def test_lg_product_colour_stays_with_the_catalog(c, pid):
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": "G646GBB031", "center_xz": [4.2, 0.45], "yaw_rad": 1.5708}).json()["placement"]
    r = c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}", json={"hex": "#3A4660"})
    assert r.status_code in (400, 422)
    assert state(c, pid)["placements"][0]["hex"] == x["hex"]


def test_colour_must_be_a_hex_code(c, pid):
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:dresser", "center_xz": [4.0, 2.4], "yaw_rad": 0}).json()["placement"]
    assert c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}", json={"hex": "navy"}).status_code == 422
    assert c.put(f"/api/projects/{pid}/objects/o1/color", json={"hex": "red"}).status_code == 422


def test_scanned_furniture_takes_a_colour_and_gives_it_back(c, pid):
    sofa = next(o["object_id"] for o in c.get(f"/api/projects/{pid}/room").json()["objects"] if o["category"] == "sofa")
    r = c.put(f"/api/projects/{pid}/objects/{sofa}/color", json={"hex": "#93A088"})
    assert r.status_code == 200, r.text
    assert state(c, pid)["object_colors"] == {sofa: "#93A088"}
    r = c.put(f"/api/projects/{pid}/objects/{sofa}/color", json={"hex": None})
    assert r.status_code == 200 and state(c, pid)["object_colors"] == {}


def test_colour_for_furniture_that_is_not_there(c, pid):
    assert c.put(f"/api/projects/{pid}/objects/nope/color", json={"hex": "#93A088"}).status_code == 404
