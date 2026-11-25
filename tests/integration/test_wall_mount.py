"""벽걸이는 벽에 걸고, 월핏·빌트인은 벽이나 장에 붙인다: 놓기 → 높이 바꾸기 → 옮기기 → 복사."""
import math

import pytest
from fastapi.testclient import TestClient

from api import main
from core.service import Service

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"
TV, AC, WALLFIT, FITMAX, DISH = "OLED65C5ENA", "SW09GS1EES", "AS186LSAA", "G646GBB031", None
MID = [-2.0, -1.5]  # 강의실 가운데쯤


@pytest.fixture
def c(tmp_path):
    svc = Service(storage=tmp_path / "st")
    main.app.dependency_overrides[main.get_service] = lambda: svc
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def pid(c):
    with open(REAL, "rb") as f:
        pid = c.post("/api/projects", files={"file": ("home.usdz", f)}, data={"scanned_by": "customer"}).json()["project_id"]
    c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True})
    return pid


def wall_gap(c, pid, xz):
    """가장 가까운 벽면까지의 거리."""
    best = math.inf
    for w in c.get(f"/api/projects/{pid}/room").json()["walls"]:
        (ax, az), (bx, bz) = w["start"], w["end"]
        ex, ez = bx - ax, bz - az
        t = max(0.0, min(1.0, ((xz[0] - ax) * ex + (xz[1] - az) * ez) / (ex * ex + ez * ez)))
        best = min(best, math.hypot(xz[0] - ax - ex * t, xz[1] - az - ez * t) - (w.get("thickness_m") or 0.1) / 2)
    return best


def codes(x):
    return {r["code"] for r in x["reasons"]}


def test_catalog_tells_the_web_how_each_product_mounts(c):
    mounts = {v["sku"]: v["mount"] for f in c.get("/api/catalog/families").json() for v in f["variants"]}
    assert mounts[TV] == "wall" and mounts[AC] == "wall"
    assert mounts[WALLFIT] == "flush" and mounts[FITMAX] == "flush"
    assert mounts["FQ18GV3EK2"] is None  # 2in1 스탠드 에어컨


def test_wall_tv_hangs_on_a_wall_wherever_it_is_dropped(c, pid):
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": TV, "center_xz": MID}).json()["placement"]
    assert abs(wall_gap(c, pid, x["center_xz"]) - x["size_m"][2] / 2) < 0.01
    assert x["hung"] and 0.5 < x["base_m"] < 1.0
    assert x["verdict"] != "no_fit", x["reasons"]
    assert not x["tabletop"]


def test_height_can_be_changed_and_survives_other_edits(c, pid):
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": TV, "center_xz": MID}).json()["placement"]
    r = c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}", json={"base_m": 1.4}).json()["placement"]
    assert math.isclose(r["base_m"], 1.4, abs_tol=1e-3) and r["center_xz"] == x["center_xz"]
    # 다른 물건을 놓아 다시 판정해도 높이는 그대로
    c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:sofa"})
    again = next(q for q in c.get(f"/api/projects/{pid}").json()["scene_state"]["placements"] if q["placement_id"] == x["placement_id"])
    assert math.isclose(again["base_m"], 1.4, abs_tol=1e-3)
    # 천장을 넘는 높이는 천장 아래로 맞춘다
    top = c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}", json={"base_m": 9}).json()["placement"]
    assert top["base_m"] + top["size_m"][1] <= 2.9


def test_height_is_ignored_for_products_that_stand_on_the_floor(c, pid):
    x = c.post(f"/api/projects/{pid}/auto-place", json={"sku": FITMAX}).json()["placement"]
    r = c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}", json={"base_m": 1.0}).json()["placement"]
    assert r["base_m"] == 0


def test_wall_ac_is_auto_placed_under_the_ceiling(c, pid):
    x = c.post(f"/api/projects/{pid}/auto-place", json={"sku": AC}).json()["placement"]
    assert x["verdict"] != "no_fit", x["reasons"]
    assert x["base_m"] > 1.8 and abs(wall_gap(c, pid, x["center_xz"]) - x["size_m"][2] / 2) < 0.01


def test_copy_keeps_the_height(c, pid):
    x = c.post(f"/api/projects/{pid}/auto-place", json={"sku": AC}).json()["placement"]
    c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}", json={"base_m": 2.0})
    y = c.post(f"/api/projects/{pid}/placements/{x['placement_id']}/copy").json()["placement"]
    assert math.isclose(y["base_m"], 2.0, abs_tol=1e-3) and y["hung"]


def test_flush_products_need_a_wall_and_are_pulled_to_one(c, pid):
    far = c.post(f"/api/projects/{pid}/pose-check", json={"sku": WALLFIT, "center_xz": MID, "snap": False}).json()
    assert far["verdict"] == "no_fit"
    assert next(r["label"] for r in far["reasons"] if r["code"] == "needs_wall") == "뒷면을 벽에 붙여야 해요"
    tv = c.post(f"/api/projects/{pid}/placements", json={"sku": TV, "center_xz": MID}).json()["placement"]
    half = [tv["center_xz"][0] + math.cos(tv["yaw_rad"]) * 0.5, tv["center_xz"][1] + math.sin(tv["yaw_rad"]) * 0.5]
    near = c.post(f"/api/projects/{pid}/pose-check", json={"sku": WALLFIT, "center_xz": half}).json()
    assert "needs_wall" not in codes(near) and wall_gap(c, pid, near["pose"]["center_xz"]) < 0.2


def test_fit_and_max_fridge_in_the_middle_of_the_room_does_not_fit(c, pid):
    r = c.post(f"/api/projects/{pid}/pose-check", json={"sku": FITMAX, "center_xz": MID, "snap": False}).json()
    assert r["verdict"] == "no_fit" and "needs_wall" in codes(r)
    x = c.post(f"/api/projects/{pid}/auto-place", json={"sku": FITMAX}).json()["placement"]
    assert "needs_wall" not in codes(x)
