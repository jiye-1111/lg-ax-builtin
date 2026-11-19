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
