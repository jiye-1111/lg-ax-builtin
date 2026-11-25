"""식탁·아일랜드 위에 작은 가전 올리기: 놓기 → 같이 옮기기 → 받침을 빼면 바닥으로."""
import json
import math

import pytest
from fastapi.testclient import TestClient

from api import main
from core.service import Service

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"
CAT = json.loads((main.config.ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]
MICRO = next(p["sku"] for p in CAT if p["category"] == "microwave" and p.get("sale_status") == "ACTIVE")
FRIDGE = "G646GBB031"


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
    c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True})  # 스캔 가구를 다 치우고 빈방에서
    return pid


def island(c, pid):
    r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:island"})
    assert r.status_code == 200, r.text
    return r.json()["placement"]


def test_microwave_sits_on_the_island(c, pid):
    isl = island(c, pid)
    body = {"sku": MICRO, "center_xz": isl["center_xz"], "yaw_rad": isl["yaw_rad"], "snap": False}
    chk = c.post(f"/api/projects/{pid}/pose-check", json=body).json()
    assert chk["on"] == isl["placement_id"] and chk["base_m"] == pytest.approx(0.9)
    assert "overlaps_placement" not in {x["code"] for x in chk["reasons"]} and chk["verdict"] != "no_fit"
    pl = c.post(f"/api/projects/{pid}/placements", json=body).json()["placement"]
    assert pl["base_m"] == pytest.approx(0.9) and pl["on"] == isl["placement_id"] and pl["tabletop"] is True
    # 아일랜드는 그 위 물건 때문에 '겹침'이 되지 않는다
    state = c.get(f"/api/projects/{pid}").json()["scene_state"]["placements"]
    assert next(x for x in state if x["placement_id"] == isl["placement_id"])["verdict"] != "no_fit"


def test_big_appliance_does_not_climb(c, pid):
    isl = island(c, pid)
    chk = c.post(f"/api/projects/{pid}/pose-check", json={"sku": FRIDGE, "center_xz": isl["center_xz"], "yaw_rad": 0, "snap": False}).json()
    assert chk["base_m"] == 0 and chk["on"] is None and chk["verdict"] == "no_fit"


def test_things_on_top_follow_the_island_and_drop_when_it_is_removed(c, pid):
    isl = island(c, pid)
    at = [isl["center_xz"][0] + 0.2 * math.cos(isl["yaw_rad"] - math.pi / 2), isl["center_xz"][1] + 0.2 * math.sin(isl["yaw_rad"] - math.pi / 2)]
    pl = c.post(f"/api/projects/{pid}/placements", json={"sku": MICRO, "center_xz": at, "yaw_rad": isl["yaw_rad"], "snap": False}).json()["placement"]
    assert pl["on"] == isl["placement_id"]
    to = [isl["center_xz"][0] + 0.3, isl["center_xz"][1] + 0.2]
    r = c.patch(f"/api/projects/{pid}/placements/{isl['placement_id']}", json={"center_xz": to, "snap": False})
    assert r.status_code == 200, r.text
    moved = next(x for x in r.json()["scene_state"]["placements"] if x["placement_id"] == pl["placement_id"])
    assert moved["center_xz"] == pytest.approx([at[0] + 0.3, at[1] + 0.2], abs=1e-6)
    assert moved["on"] == isl["placement_id"] and moved["base_m"] == pytest.approx(0.9)
    r = c.delete(f"/api/projects/{pid}/placements/{isl['placement_id']}")
    left = r.json()["scene_state"]["placements"]
    assert len(left) == 1 and left[0]["base_m"] == 0 and left[0]["on"] is None


def test_auto_place_prefers_a_top_when_there_is_one(c, pid):
    isl = island(c, pid)
    pl = c.post(f"/api/projects/{pid}/auto-place", json={"sku": MICRO}).json()["placement"]
    assert pl["on"] == isl["placement_id"] and pl["base_m"] == pytest.approx(0.9) and pl["verdict"] != "no_fit"


def test_catalog_marks_tabletop_products(c):
    fams = c.get("/api/catalog/families").json()
    fams = fams["families"] if isinstance(fams, dict) else fams
    flag = {v["sku"]: v.get("tabletop") for f in fams for v in f["variants"]}
    assert flag[MICRO] is True and flag[FRIDGE] is False


def test_mini_wine_cellar_sits_on_a_desk_but_auto_place_keeps_it_on_the_floor(c, pid):
    desk = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:desk"}).json()["placement"]
    body = {"sku": "W0082GLE", "center_xz": desk["center_xz"], "yaw_rad": desk["yaw_rad"], "snap": False}
    pl = c.post(f"/api/projects/{pid}/placements", json=body).json()["placement"]
    assert pl["on"] == desk["placement_id"] and pl["base_m"] == pytest.approx(desk["size_m"][1]) and pl["tabletop"] is True
    assert pl["verdict"] != "no_fit", pl["reasons"]
    auto = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "W0082GLE"}).json()["placement"]
    assert auto["base_m"] == 0 and auto["verdict"] != "no_fit"


def test_moving_from_the_floor_onto_a_desk_does_not_mark_the_desk_as_overlapped(c, pid):
    import math
    desk = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:desk"}).json()["placement"]
    out = [desk["center_xz"][0] + math.cos(desk["yaw_rad"]) * 1.3, desk["center_xz"][1] + math.sin(desk["yaw_rad"]) * 1.3]
    pl = c.post(f"/api/projects/{pid}/placements", json={"sku": "W0082GLE", "center_xz": out, "yaw_rad": desk["yaw_rad"], "snap": False}).json()["placement"]
    assert pl["base_m"] == 0
    r = c.patch(f"/api/projects/{pid}/placements/{pl['placement_id']}", json={"center_xz": desk["center_xz"], "snap": False}).json()
    assert r["placement"]["on"] == desk["placement_id"]
    host = next(x for x in r["scene_state"]["placements"] if x["placement_id"] == desk["placement_id"])
    assert "overlaps_placement" not in [q["code"] for q in host["reasons"]], host["reasons"]
