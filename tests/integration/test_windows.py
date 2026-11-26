"""창문: 스캔한 창은 없앨 수 있고, 창문·베란다 유리문은 벽에 새로 달 수 있다."""
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


def test_scanned_window_can_be_removed_and_put_back(c, pid):
    r = c.put(f"/api/projects/{pid}/openings/win1/hidden", json={"hidden": True})
    assert r.status_code == 200, r.text
    assert state(c, pid)["hidden_openings"] == ["win1"]
    r = c.put(f"/api/projects/{pid}/openings/win1/hidden", json={"hidden": False})
    assert r.status_code == 200 and state(c, pid)["hidden_openings"] == []


def test_removed_window_is_left_out_of_the_3d_room(c, pid):
    from worker.glb import boxes_for_room
    svc = main.app.dependency_overrides[main.get_service]()
    c.put(f"/api/projects/{pid}/openings/win1/hidden", json={"hidden": True})
    room = svc._standing(svc.get_room(pid), svc.get_project(pid))
    names = [b["name"] for b in boxes_for_room(room)]
    assert "win1" not in names and "win2" in names and "d1" in names


def test_only_windows_can_be_removed(c, pid):
    assert c.put(f"/api/projects/{pid}/openings/d1/hidden", json={"hidden": True}).status_code in (400, 422)
    assert c.put(f"/api/projects/{pid}/openings/nope/hidden", json={"hidden": True}).status_code == 404


@pytest.mark.parametrize("sku,sill", [("decor:window", 0.9), ("decor:glassdoor", 0.0)])
def test_new_window_snaps_onto_the_wall_at_its_height(c, pid, sku, sill):
    # 아래쪽 벽(w3 근처가 아닌 긴 벽 z=0) 안쪽을 누른다
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": sku, "center_xz": [3.6, 0.3], "yaw_rad": 0})
    assert r.status_code == 200, r.text
    x = r.json()["placement"]
    assert x["center_xz"][1] == pytest.approx(0.0, abs=0.01)
    assert x["base_m"] == pytest.approx(sill, abs=0.001)
    assert x["verdict"] != "no_fit", x["reasons"]


def test_window_away_from_any_wall_is_not_installable(c, pid):
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:window", "center_xz": [4.0, 2.4], "yaw_rad": 0}).json()["placement"]
    assert x["verdict"] == "no_fit"
    assert [z["label"] for z in x["reasons"] if z["code"] == "not_on_wall"] == ["창은 벽이나 가벽에 달아 주세요"]


def test_furniture_can_stand_under_a_new_window(c, pid):
    win = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:window", "center_xz": [5.0, 0.3], "yaw_rad": 0}).json()["placement"]
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:dresser", "center_xz": [5.0, 0.4], "yaw_rad": 1.5708})
    x = r.json()["placement"]
    assert not any(z.get("ref") == win["placement_id"] for z in x["reasons"]), x["reasons"]


def test_fridge_in_front_of_a_removed_window_is_not_told_it_covers_one(c, pid):
    def covers():
        x = c.post(f"/api/projects/{pid}/placements", json={"sku": "G646GBB031", "center_xz": [7.3, 2.3], "yaw_rad": 3.1416}).json()["placement"]
        c.delete(f"/api/projects/{pid}/placements/{x['placement_id']}")
        return any(z["code"] == "covers_window" for z in x["reasons"])
    assert covers()
    c.put(f"/api/projects/{pid}/openings/win1/hidden", json={"hidden": True})
    assert not covers()


def test_scanned_door_and_window_width_can_be_typed_in(c, pid):
    room = c.get(f"/api/projects/{pid}/room").json()
    win = next(o for o in room["openings"] if o["opening_id"] == "win1")
    mid = win["offset_m"] + win["width_m"] / 2
    r = c.put(f"/api/projects/{pid}/openings/win1/size", json={"width_m": round(win["width_m"] - 0.3, 3)})
    assert r.status_code == 200, r.text
    after = next(o for o in c.get(f"/api/projects/{pid}/room").json()["openings"] if o["opening_id"] == "win1")
    assert after["width_m"] == pytest.approx(win["width_m"] - 0.3, abs=1e-3)
    assert after["offset_m"] + after["width_m"] / 2 == pytest.approx(mid, abs=2e-3)
    r = c.put(f"/api/projects/{pid}/openings/d1/size", json={"width_m": 1.0})
    assert r.status_code == 200, r.text


def test_opening_size_that_cannot_fit_is_refused_with_a_plain_sentence(c, pid):
    r = c.put(f"/api/projects/{pid}/openings/win1/size", json={"width_m": 0.1})
    assert r.status_code in (400, 422) and "mm" in r.text
    r = c.put(f"/api/projects/{pid}/openings/win1/size", json={"width_m": 6.0})
    assert r.status_code in (400, 422) and "자리" in r.text
    assert c.put(f"/api/projects/{pid}/openings/nope/size", json={"width_m": 1.0}).status_code == 404


def test_placed_window_and_door_keep_working_after_a_new_width(c, pid):
    for sku, w in (("decor:window", 1.8), ("decor:door", 0.8)):
        pl = c.post(f"/api/projects/{pid}/auto-place", json={"sku": sku}).json()["placement"]
        assert pl["verdict"] != "no_fit", (sku, pl["reasons"])
        size = [w, *pl["size_m"][1:]]
        r = c.patch(f"/api/projects/{pid}/placements/{pl['placement_id']}", json={"size_m": size, "snap": False})
        assert r.status_code == 200, r.text
        after = r.json()["placement"]
        assert after["size_m"][0] == pytest.approx(w) and after["verdict"] != "no_fit", (sku, after["reasons"])
        c.delete(f"/api/projects/{pid}/placements/{pl['placement_id']}")


def test_furniture_in_front_of_a_scanned_door_is_refused(c, pid):
    room = c.get(f"/api/projects/{pid}/room").json()
    d = next(o for o in room["openings"] if o["type"] == "door")
    w = next(x for x in room["walls"] if x["wall_id"] == d["wall_id"])
    length = ((w["end"][0] - w["start"][0]) ** 2 + (w["end"][1] - w["start"][1]) ** 2) ** 0.5
    u = (d["offset_m"] + d["width_m"] / 2) / length
    at = [w["start"][0] + (w["end"][0] - w["start"][0]) * u, w["start"][1] + (w["end"][1] - w["start"][1]) * u]
    mid = [sum(x["start"][0] for x in room["walls"]) / len(room["walls"]), sum(x["start"][1] for x in room["walls"]) / len(room["walls"])]
    n = ((mid[0] - at[0]) ** 2 + (mid[1] - at[1]) ** 2) ** 0.5
    front = [at[0] + (mid[0] - at[0]) / n * 0.5, at[1] + (mid[1] - at[1]) / n * 0.5]
    r = c.post(f"/api/projects/{pid}/pose-check", json={"sku": "decor:chair", "center_xz": front, "yaw_rad": 0, "snap": False}).json()
    why = [x for x in r["reasons"] if x["code"] == "door_blocked"]
    assert r["verdict"] == "no_fit" and why and why[0]["label"] == "여기 두면 문을 열 수 없어요"
