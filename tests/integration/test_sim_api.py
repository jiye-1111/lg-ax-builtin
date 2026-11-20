"""살아 보기 시뮬레이션 API (S6~S8)."""
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
def pid(c):
    with open(REAL, "rb") as f:
        return c.post("/api/projects", files={"file": ("home.usdz", f)}, data={"scanned_by": "customer"}).json()["project_id"]


def test_daylight_needs_north_first(c, pid):
    r = c.get(f"/api/projects/{pid}/sim/daylight", params={"date": "2026-12-21"})
    assert r.status_code == 422 and "북쪽" in r.json()["detail"]


def test_site_and_daylight(c, pid):
    assert c.put(f"/api/projects/{pid}/site", json={"north_deg": 400, "region": "서울"}).status_code == 422
    assert c.put(f"/api/projects/{pid}/site", json={"north_deg": 0, "region": "화성시"}).status_code == 422
    r = c.put(f"/api/projects/{pid}/site", json={"north_deg": 180, "region": "부산"})
    assert r.status_code == 200 and r.json()["site"]["lat"] == pytest.approx(35.18, abs=0.01)
    r = c.get(f"/api/projects/{pid}/sim/daylight", params={"date": "2026-12-21", "time": "13:00"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["sun"]["altitude_deg"] > 20 and d["daily"]["values"] and d["assumptions"]
    assert isinstance(d["patches"], list)
    assert c.get(f"/api/projects/{pid}/sim/daylight", params={"date": "어제"}).status_code == 422


def test_daylight_gives_3d_sun_and_can_skip_heatmap(c, pid):
    c.put(f"/api/projects/{pid}/site", json={"north_deg": 0, "region": "서울"})
    d = c.get(f"/api/projects/{pid}/sim/daylight", params={"date": "2026-06-21", "time": "12:30"}).json()
    sun = d["sun"]
    assert len(sun["direction"]) == 3 and sun["direction"][1] > 0.8 and sun["color"].startswith("#")
    assert sun["intensity"] > 0 and sun["up"] is True
    fast = c.get(f"/api/projects/{pid}/sim/daylight",
                 params={"date": "2026-06-21", "time": "12:30", "heatmap": "false"}).json()
    assert fast["daily"] is None and fast["sun"]["direction"] == sun["direction"]  # 시간 슬라이더용: 히트맵 없이 빠르게


def test_render_uses_the_same_sun(c, pid, monkeypatch):
    from worker import runner

    seen = {}

    def fake(room, usdz, state, out_dir, render=False):
        seen.update(state=state, render=render)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "scene.glb").write_bytes(b"")
        return {"glb": out_dir / "scene.glb", "png": None, "engine": "fallback"}

    c.put(f"/api/projects/{pid}/site", json={"north_deg": 30, "region": "서울"})
    monkeypatch.setattr(runner, "build_scene", fake)
    r = c.post(f"/api/projects/{pid}/render", json={"date": "2026-12-21", "time": "15:00"})
    assert r.status_code == 200, r.text
    want = c.get(f"/api/projects/{pid}/sim/daylight",
                 params={"date": "2026-12-21", "time": "15:00", "heatmap": "false"}).json()["sun"]
    assert seen["render"] and seen["state"]["sun"]["direction"] == want["direction"]
    assert seen["state"]["sun"]["color"] == want["color"]


def test_regions_listed(c):
    rs = c.get("/api/regions").json()
    assert "서울" in rs and all({"lat", "lon"} <= set(v) for v in rs.values())


def test_wifi_flow(c, pid):
    assert c.get(f"/api/projects/{pid}/sim/wifi").status_code == 422  # 공유기 위치 먼저
    best = c.get(f"/api/projects/{pid}/sim/wifi/best", params={"band": "5"})
    assert best.status_code == 200, best.text
    spot = best.json()["center_xz"]
    r = c.put(f"/api/projects/{pid}/router", json={"center_xz": spot, "band": "5"})
    assert r.status_code == 200 and r.json()["scene_state"]["router"]["center_xz"] == spot
    assert c.put(f"/api/projects/{pid}/router", json={"center_xz": spot, "band": "6"}).status_code == 422
    c.post(f"/api/projects/{pid}/zones", json={"purpose": "kitchen", "polygon_m": [[-5.5, 1], [-4, 1], [-4, 4], [-5.5, 4]]})
    w = c.get(f"/api/projects/{pid}/sim/wifi").json()
    assert w["values"] and w["assumptions"] and w["zones"][0]["share"]
    assert w["min_dbm"] == pytest.approx(best.json()["min_dbm"], abs=3)


def test_flow_routes_to_placed_products(c, pid):
    pl = c.post(f"/api/projects/{pid}/placements", json={"sku": "G646GBB031", "center_xz": [0.5, -6.2], "yaw_rad": 1.57}).json()["placement"]
    assert c.put(f"/api/projects/{pid}/marks/sink", json={"center_xz": [-1.0, -6.3]}).status_code == 200
    assert c.put(f"/api/projects/{pid}/marks/../x", json={"center_xz": [0, 0]}).status_code in (404, 405, 422)
    assert c.put(f"/api/projects/{pid}/marks/bathroom", json={"center_xz": [0, 0]}).status_code == 404
    r = c.get(f"/api/projects/{pid}/sim/flow")
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["entrance"]["opening_id"] == "d1"
    route = f["routes"][pl["placement_id"]]
    assert set(route) >= {"reachable", "length_m", "min_width_m", "narrow", "path"}
    assert "sink" in f["routes"] and f["assumptions"]
    assert c.delete(f"/api/projects/{pid}/marks/sink").status_code == 200


def test_router_keeps_yaw_when_moved(c, pid):
    """3D에서 공유기를 돌려 놓으면 방향이 저장되고, 자리만 옮길 때(추천 자리 등)는 방향이 그대로 남는다."""
    r = c.put(f"/api/projects/{pid}/router", json={"center_xz": [-4.5, 2.0]})
    assert r.status_code == 200, r.text
    assert r.json()["scene_state"]["router"]["yaw_rad"] == 0  # 처음 놓을 때 방향을 안 주면 0
    r = c.put(f"/api/projects/{pid}/router", json={"center_xz": [-4.5, 2.0], "band": "5", "yaw_rad": 1.2})
    assert r.json()["scene_state"]["router"]["yaw_rad"] == pytest.approx(1.2)
    rt = c.put(f"/api/projects/{pid}/router", json={"center_xz": [-4.0, 2.5], "band": "5"}).json()["scene_state"]["router"]
    assert rt["center_xz"] == [-4.0, 2.5] and rt["yaw_rad"] == pytest.approx(1.2)
