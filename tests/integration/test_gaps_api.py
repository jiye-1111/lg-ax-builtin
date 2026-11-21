"""남는 틈 표시와 빈틈에 맞추기: 빌트인 옆에 장을 짜 넣을 때 쓰는 API."""
import math

import pytest
from api import main
from core.service import Service
from fastapi.testclient import TestClient

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"
FRIDGE = "G646GBB031"  # 핏 앤 맥스: 옆 4 mm, 위 9 mm (LGE.COM)


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


def beside(pl, dist, w):
    """pl 오른쪽(폭 축 +)으로 틈 dist(m)를 두고 폭 w인 것을 놓을 가운데 자리."""
    ux, uz = math.cos(pl["yaw_rad"] - math.pi / 2), math.sin(pl["yaw_rad"] - math.pi / 2)
    step = pl["size_m"][0] / 2 + dist + w / 2
    return [pl["center_xz"][0] + ux * step, pl["center_xz"][1] + uz * step]


def check(c, pid, pl):
    r = c.post(f"/api/projects/{pid}/pose-check", json={"sku": pl["sku"], "center_xz": pl["center_xz"], "yaw_rad": pl["yaw_rad"],
                                                        "snap": False, "placement_id": pl["placement_id"],
                                                        **({"size_m": pl["size_m"]} if pl["sku"].startswith("decor:") else {})})
    assert r.status_code == 200, r.text
    return r.json()


def test_pose_check_reports_gaps_with_lge_clearance(c, pid):
    pl = c.post(f"/api/projects/{pid}/auto-place", json={"sku": FRIDGE}).json()["placement"]
    g = check(c, pid, pl)["gaps"]
    assert set(g) == {"left", "right", "back", "top"}
    assert g["left"]["need_mm"] == 4 and g["right"]["need_mm"] == 4 and g["top"]["need_mm"] == 9
    assert g["back"]["need_mm"] is None
    assert g["top"]["mm"] > 0


def test_cabinet_too_close_shows_short_gap_on_both(c, pid):
    fr = c.post(f"/api/projects/{pid}/auto-place", json={"sku": FRIDGE}).json()["placement"]
    size = [0.6, 2.0, 0.6]
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:tallcab", "center_xz": beside(fr, 0.002, 0.6),
                                                         "yaw_rad": fr["yaw_rad"], "snap": False, "size_m": size})
    assert r.status_code == 200, r.text
    cab = r.json()["placement"]
    g = check(c, pid, fr)["gaps"]["right"]
    assert g["ref"] == cab["placement_id"] and g["mm"] == pytest.approx(2, abs=0.6) and g["ok"] is False
    g2 = check(c, pid, cab)["gaps"]["left"]
    assert g2["ref"] == fr["placement_id"] and g2["need_mm"] == 4 and g2["ok"] is False
    # 판정도 같이 안 들어감으로 바뀐다 (이격 부족)
    state = c.get(f"/api/projects/{pid}").json()["scene_state"]["placements"]
    assert next(x for x in state if x["placement_id"] == fr["placement_id"])["verdict"] == "no_fit"


def test_fit_gap_stretches_cabinet_and_keeps_required_clearance(c, pid):
    fr = c.post(f"/api/projects/{pid}/auto-place", json={"sku": FRIDGE}).json()["placement"]
    cab = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:tallcab", "center_xz": beside(fr, 0.15, 0.4),
                                                           "yaw_rad": fr["yaw_rad"], "snap": False, "size_m": [0.4, 2.0, 0.6]}).json()["placement"]
    before = check(c, pid, cab)["gaps"]
    r = c.post(f"/api/projects/{pid}/placements/{cab['placement_id']}/fit-gap")
    assert r.status_code == 200, r.text
    after_pl = r.json()["placement"]
    assert after_pl["size_m"][0] == pytest.approx(0.4 + (before["left"]["mm"] - 4 + before["right"]["mm"] - (before["right"]["need_mm"] or 0)) / 1000, abs=2e-3)
    g = check(c, pid, after_pl)["gaps"]
    assert g["left"]["mm"] == pytest.approx(4, abs=0.6) and g["left"]["ok"] is True
    assert g["right"]["mm"] == pytest.approx(g["right"]["need_mm"] or 0, abs=0.6)
    state = c.get(f"/api/projects/{pid}").json()["scene_state"]["placements"]
    assert next(x for x in state if x["placement_id"] == fr["placement_id"])["verdict"] != "no_fit"


def test_fit_gap_only_for_furniture(c, pid):
    fr = c.post(f"/api/projects/{pid}/auto-place", json={"sku": FRIDGE}).json()["placement"]
    assert c.post(f"/api/projects/{pid}/placements/{fr['placement_id']}/fit-gap").status_code == 422
