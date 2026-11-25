"""상판 색: 아일랜드 식탁·하부장처럼 상판이 있는 가구는 몸통과 따로 상판 색을 고른다."""
import pytest
from fastapi.testclient import TestClient

from api import main
from core.service import Service

BARE = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"


@pytest.fixture
def c(tmp_path):
    svc = Service(storage=tmp_path / "st")
    main.app.dependency_overrides[main.get_service] = lambda: svc
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def placed(c, sku):
    with open(BARE, "rb") as f:
        pid = c.post("/api/projects", files={"file": ("a.usdz", f, "model/vnd.usdz+zip")}).json()["project_id"]
    room = c.get(f"/api/projects/{pid}/room").json()
    n = len(room["walls"])
    mid = [sum((w["start"][i] + w["end"][i]) / 2 for w in room["walls"]) / n for i in (0, 1)]
    pl = c.post(f"/api/projects/{pid}/placements", json={"sku": sku, "center_xz": mid, "yaw_rad": 0, "snap": False}).json()["placement"]
    return pid, pl["placement_id"]


def saved(c, pid, plid):
    return next(x for x in c.get(f"/api/projects/{pid}").json()["scene_state"]["placements"] if x["placement_id"] == plid)


def test_top_colour_is_saved_apart_from_the_body_colour(c):
    pid, plid = placed(c, "decor:islandtable")
    assert c.patch(f"/api/projects/{pid}/placements/{plid}", json={"hex": "#7a5638"}).status_code == 200
    assert c.patch(f"/api/projects/{pid}/placements/{plid}", json={"top_hex": "#3a3b3d"}).status_code == 200
    x = saved(c, pid, plid)
    assert (x["hex"], x["top_hex"]) == ("#7A5638", "#3A3B3D")


def test_empty_top_colour_goes_back_to_the_original_top(c):
    pid, plid = placed(c, "decor:islandtable")
    c.patch(f"/api/projects/{pid}/placements/{plid}", json={"top_hex": "#3A3B3D"})
    c.patch(f"/api/projects/{pid}/placements/{plid}", json={"top_hex": ""})
    assert saved(c, pid, plid).get("top_hex") is None


def test_furniture_without_a_top_refuses_a_top_colour(c):
    pid, plid = placed(c, "decor:sofa")
    r = c.patch(f"/api/projects/{pid}/placements/{plid}", json={"top_hex": "#3A3B3D"})
    assert r.status_code in (400, 422)


def test_top_colour_must_be_a_hex_colour(c):
    pid, plid = placed(c, "decor:islandtable")
    assert c.patch(f"/api/projects/{pid}/placements/{plid}", json={"top_hex": "black"}).status_code == 422
