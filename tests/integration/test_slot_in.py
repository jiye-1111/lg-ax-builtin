"""빌트인을 장 칸에 끼워 넣기: 하부장 위에 놓으면 칸이 나고, 상판이 이어지고, 되돌릴 값이 온다."""
import math

import pytest
from fastapi.testclient import TestClient

from api import main
from core.service import Service

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"
DISH, FITMAX, MICRO = "DUE6BGE", "M336DS123", None


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


def cabinet(c, pid, sku="decor:basecab", size=(1.8, 0.85, 0.6)):
    r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": sku, "size_m": list(size)})
    assert r.status_code == 200, r.text
    return r.json()["placement"]


def along(cab, u, v=0.0):
    a = cab["yaw_rad"] - math.pi / 2
    return [cab["center_xz"][0] + math.cos(a) * u + math.cos(cab["yaw_rad"]) * v,
            cab["center_xz"][1] + math.sin(a) * u + math.sin(cab["yaw_rad"]) * v]


def local(cab, xz):
    a = cab["yaw_rad"] - math.pi / 2
    dx, dz = xz[0] - cab["center_xz"][0], xz[1] - cab["center_xz"][1]
    return dx * math.cos(a) + dz * math.sin(a), dx * math.cos(cab["yaw_rad"]) + dz * math.sin(cab["yaw_rad"])


def placements(c, pid):
    return c.get(f"/api/projects/{pid}").json()["scene_state"]["placements"]


def codes(x):
    return {r["code"] for r in x["reasons"]}


def test_dishwasher_dropped_on_a_base_cabinet_gets_its_own_bay(c, pid):
    cab = cabinet(c, pid)
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": DISH, "center_xz": along(cab, 0.0, 0.1), "yaw_rad": 0.3}).json()
    x = r["placement"]
    assert x["verdict"] != "no_fit", x["reasons"]
    assert "overlaps_placement" not in codes(x) and "needs_wall" not in codes(x)
    assert abs(x["yaw_rad"] - cab["yaw_rad"]) < 1e-6
    u, v = local(cab, x["center_xz"])
    assert abs(u) < 2e-3 and abs(v - (0.3 - 0.02 - x["size_m"][2] / 2)) < 2e-3  # 문짝 앞면에 맞춘다
    cabs = [p for p in placements(c, pid) if p["sku"] == "decor:basecab"]
    assert len(cabs) == 2
    assert abs(sum(p["size_m"][0] for p in cabs) + x["size_m"][0] - 1.8) < 3e-3
    assert all(p["verdict"] != "no_fit" for p in cabs), [p["reasons"] for p in cabs]
    # 상판이 이어진다
    assert x["slot"]["look"] == "basecab" and x["slot"]["top_m"] == 0.85 and x["slot"]["depth_m"] == 0.6
    # 되돌릴 값
    ch = r["slot_changes"]
    assert [k["id"] for k in ch["resized"]] == [cab["placement_id"]]
    assert ch["resized"][0]["size_m"] == [1.8, 0.85, 0.6] and len(ch["added"]) == 1 and ch["removed"] == []


def test_preview_says_it_fits_before_anything_is_cut(c, pid):
    cab = cabinet(c, pid)
    r = c.post(f"/api/projects/{pid}/pose-check", json={"sku": DISH, "center_xz": along(cab, 0.3), "yaw_rad": cab["yaw_rad"], "snap": False}).json()
    assert r["verdict"] != "no_fit", r["reasons"]
    assert len(placements(c, pid)) == 1 and placements(c, pid)[0]["size_m"][0] == 1.8


def test_slot_false_leaves_the_cabinet_alone(c, pid):
    cab = cabinet(c, pid)
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": DISH, "center_xz": along(cab, 0.0), "yaw_rad": cab["yaw_rad"], "snap": False, "slot": False}).json()
    assert "overlaps_placement" in codes(r["placement"])
    assert "slot_changes" not in r
    assert [p["size_m"][0] for p in placements(c, pid) if p["sku"] == "decor:basecab"] == [1.8]


def test_moving_a_dishwasher_onto_the_cabinet_cuts_a_bay_and_turning_it_does_not_recut(c, pid):
    cab = cabinet(c, pid)
    x = c.post(f"/api/projects/{pid}/auto-place", json={"sku": DISH}).json()["placement"]
    r = c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}", json={"center_xz": along(cab, 0.6 + 0.02), "yaw_rad": cab["yaw_rad"], "snap": False}).json()
    x2 = r["placement"]
    assert x2["verdict"] != "no_fit" and x2.get("slot")
    u, _ = local(cab, x2["center_xz"])
    assert abs(u + x2["size_m"][0] / 2 - 0.9) < 2e-3  # 장 끝에 맞춰 들어간다
    assert len(r["slot_changes"]["resized"]) == 1 and r["slot_changes"]["added"] == []
    # 제자리에서 돌리면 줄에 다시 끌려가지 않는다
    r = c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}", json={"yaw_rad": cab["yaw_rad"] + math.pi / 2, "snap": False}).json()
    assert abs(r["placement"]["yaw_rad"] - (cab["yaw_rad"] + math.pi / 2)) < 1e-6
    assert "slot_changes" not in r


def test_auto_place_puts_a_dishwasher_into_the_cabinet_run(c, pid):
    cab = cabinet(c, pid)
    x = c.post(f"/api/projects/{pid}/auto-place", json={"sku": DISH}).json()["placement"]
    assert x["verdict"] != "no_fit", x["reasons"]
    assert abs(x["yaw_rad"] - cab["yaw_rad"]) < 1e-6
    assert x.get("slot"), "하부장 줄에 붙어 상판이 이어져야 한다"
    _, v = local(cab, x["center_xz"])
    assert abs(v - (0.3 - 0.02 - x["size_m"][2] / 2)) < 2e-3


def test_things_can_stand_on_the_countertop_over_the_dishwasher(c, pid):
    cab = cabinet(c, pid)
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": DISH, "center_xz": along(cab, 0.0)}).json()["placement"]
    oven = next(v["sku"] for f in c.get("/api/catalog/families").json() if f["category"] in ("microwave", "oven") for v in f["variants"])
    m = c.post(f"/api/projects/{pid}/placements", json={"sku": oven, "center_xz": x["center_xz"], "yaw_rad": cab["yaw_rad"], "snap": False}).json()["placement"]
    assert m["base_m"] == 0.85 and m["on"] == x["placement_id"]
    assert m["verdict"] != "no_fit", m["reasons"]


def test_a_locked_cabinet_is_not_cut(c, pid):
    cab = cabinet(c, pid)
    c.put(f"/api/projects/{pid}/locked", json={"id": cab["placement_id"], "locked": True})
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": DISH, "center_xz": along(cab, 0.0), "yaw_rad": cab["yaw_rad"], "snap": False}).json()
    assert "overlaps_placement" in codes(x["placement"])
    assert [p["size_m"][0] for p in placements(c, pid) if p["sku"] == "decor:basecab"] == [1.8]


def test_fit_and_max_fridge_slots_between_tall_cabinets_with_a_filler_above(c, pid):
    t1 = cabinet(c, pid, "decor:tallcab", (0.6, 2.0, 0.6))
    # 냉장고 폭 + 옆 여유만큼 띄워 두 번째 키큰장
    c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:tallcab", "center_xz": along(t1, 0.6 + 0.62), "yaw_rad": t1["yaw_rad"], "snap": False, "size_m": [0.6, 2.0, 0.6]})
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": FITMAX, "center_xz": along(t1, 0.62, 0.15), "yaw_rad": t1["yaw_rad"], "snap": False}).json()["placement"]
    assert x["verdict"] != "no_fit", x["reasons"]
    assert x["slot"]["look"] == "tallcab" and x["slot"]["top_m"] == 2.0
    assert len([p for p in placements(c, pid) if p["sku"] == "decor:tallcab"]) == 2


def test_auto_place_cuts_into_the_run_when_there_is_no_room_beside_it(c, pid):
    cab = cabinet(c, pid)
    for sgn in (-1, 1):  # 양 끝을 키큰장으로 막는다
        t = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:tallcab", "center_xz": along(cab, sgn * 1.2), "yaw_rad": cab["yaw_rad"],
                                                            "snap": False, "size_m": [0.6, 2.0, 0.6]}).json()["placement"]
        assert t["verdict"] != "no_fit", t["reasons"]
    r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": DISH}).json()
    x = r["placement"]
    assert x["verdict"] != "no_fit" and x.get("slot")
    u, _ = local(cab, x["center_xz"])
    assert abs(u) < 0.9
    assert abs(sum(p["size_m"][0] for p in placements(c, pid) if p["sku"] == "decor:basecab") + x["size_m"][0] - 1.8) < 3e-3
    assert r["slot_changes"]["resized"]


# ---------- 싱크대·아일랜드·스캔한 장 ----------
def test_a_sink_shrinks_from_its_end_and_is_never_split(c, pid):
    s = cabinet(c, pid, "decor:sink", (1.6, 0.88, 0.6))
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": DISH, "center_xz": along(s, 0.0, 0.1), "yaw_rad": s["yaw_rad"]}).json()
    x = r["placement"]
    assert x["verdict"] != "no_fit", x["reasons"]
    sinks = [p for p in placements(c, pid) if p["sku"] == "decor:sink"]
    assert len(sinks) == 1 and abs(sinks[0]["size_m"][0] + x["size_m"][0] - 1.6) < 3e-3
    assert x["slot"]["look"] == "sink" and x["slot"]["top_m"] == 0.88


def test_an_island_takes_a_dishwasher_and_the_counter_runs_over_it(c, pid):
    isl = cabinet(c, pid, "decor:island", (1.8, 0.9, 0.9))
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": DISH, "center_xz": along(isl, 0.0, 0.2), "yaw_rad": 0.0, "snap": False}).json()["placement"]
    assert x["verdict"] != "no_fit", x["reasons"]
    assert x["slot"]["look"] == "island" and x["slot"]["depth_m"] == 0.9
    assert len([p for p in placements(c, pid) if p["sku"] == "decor:island"]) == 2


def scanned_counter(c, pid):
    hosts = c.get(f"/api/projects/{pid}").json()["scene_state"]["scan_hosts"]
    return max(hosts, key=lambda h: h["size_m"][0]) if hosts else None


def test_a_scanned_low_cabinet_gives_way_and_comes_back_as_base_cabinets(c):
    with open(REAL.with_name("synthetic_room.usdz"), "rb") as f:
        pid = c.post("/api/projects", files={"file": ("home.usdz", f)}, data={"scanned_by": "customer"}).json()["project_id"]
    h = scanned_counter(c, pid)
    assert h and h["size_m"][0] >= 0.9
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": DISH, "center_xz": h["center_xz"], "yaw_rad": h["yaw_rad"], "snap": False}).json()
    x, ss = r["placement"], c.get(f"/api/projects/{pid}").json()["scene_state"]
    assert "overlaps_object" not in codes(x) and "overlaps_placement" not in codes(x), x["reasons"]
    assert h["placement_id"] in ss["hidden_objects"] and r["slot_changes"]["hidden"] == [h["placement_id"]]
    cabs = [p for p in ss["placements"] if p["sku"] == "decor:basecab"]
    assert cabs and abs(sum(p["size_m"][0] for p in cabs) + x["size_m"][0] - h["size_m"][0]) < 3e-3
    assert sorted(r["slot_changes"]["added"]) == sorted(p["placement_id"] for p in cabs)
    assert x["slot"]["top_m"] == h["size_m"][1]
