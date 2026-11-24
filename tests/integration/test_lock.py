"""고정: 다 꾸민 물건은 고정해 두면 화면에서 실수로 끌려가지 않는다. 고정 목록은 scene_state.locked에 저장된다."""
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


def locked(c, pid):
    return c.get(f"/api/projects/{pid}").json()["scene_state"].get("locked", [])


def test_placement_locks_and_unlocks(c, pid):
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:dresser", "center_xz": [4.0, 2.4], "yaw_rad": 0}).json()["placement"]
    r = c.put(f"/api/projects/{pid}/locked", json={"id": x["placement_id"], "locked": True})
    assert r.status_code == 200, r.text
    assert locked(c, pid) == [x["placement_id"]]
    c.put(f"/api/projects/{pid}/locked", json={"id": x["placement_id"], "locked": True})  # 두 번 눌러도 하나
    assert locked(c, pid) == [x["placement_id"]]
    c.put(f"/api/projects/{pid}/locked", json={"id": x["placement_id"], "locked": False})
    assert locked(c, pid) == []


def test_scanned_furniture_locks(c, pid):
    sofa = next(o["object_id"] for o in c.get(f"/api/projects/{pid}/room").json()["objects"] if o["category"] == "sofa")
    assert c.put(f"/api/projects/{pid}/locked", json={"id": sofa, "locked": True}).status_code == 200
    assert locked(c, pid) == [sofa]


def test_unknown_item_cannot_lock(c, pid):
    assert c.put(f"/api/projects/{pid}/locked", json={"id": "nope", "locked": True}).status_code == 404


def test_deleted_placement_leaves_the_lock_list(c, pid):
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:dresser", "center_xz": [4.0, 2.4], "yaw_rad": 0}).json()["placement"]
    c.put(f"/api/projects/{pid}/locked", json={"id": x["placement_id"], "locked": True})
    c.delete(f"/api/projects/{pid}/placements/{x['placement_id']}")
    assert locked(c, pid) == []
