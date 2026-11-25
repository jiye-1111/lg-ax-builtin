"""인덕션 위 후드: 인덕션을 놓으면 후드가 같이 달리고, 옮기면 따라가고, 빼면 같이 빠진다.
아일랜드 식탁도 조리대·받침으로 쓴다."""
import json
import math

import pytest
from fastapi.testclient import TestClient

from api import main
from core.service import Service

APT = main.config.ROOT / "data" / "samples" / "apt_living_kitchen.usdz"
BARE = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"
CAT = json.loads((main.config.ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]
SELL = [p for p in CAT if p.get("sale_status") == "ACTIVE" and p.get("price_krw")]
COOKTOP = next(p["sku"] for p in SELL if p["category"] == "cooktop")
MICRO = next(p["sku"] for p in SELL if p["category"] == "microwave")
HOODS = ("decor:hood", "decor:islandhood")


@pytest.fixture
def c(tmp_path):
    svc = Service(storage=tmp_path / "st")
    main.app.dependency_overrides[main.get_service] = lambda: svc
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def home(c, path=BARE, clear=True):
    with open(path, "rb") as f:
        pid = c.post("/api/projects", files={"file": ("home.usdz", f)}, data={"scanned_by": "customer"}).json()["project_id"]
    if clear:
        c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True})
    return pid


def placements(c, pid):
    return c.get(f"/api/projects/{pid}").json()["scene_state"]["placements"]


def hoods(c, pid):
    return [x for x in placements(c, pid) if x["sku"] in HOODS]


def middle(c, pid):
    room = c.get(f"/api/projects/{pid}/room").json()
    xs = [v for w in room["walls"] for v in (w["start"][0], w["end"][0])]
    zs = [v for w in room["walls"] for v in (w["start"][1], w["end"][1])]
    return [(min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2]


def test_cooktop_by_the_wall_gets_a_wall_hood_above_it(c):
    pid = home(c)
    x = c.post(f"/api/projects/{pid}/auto-place", json={"sku": COOKTOP}).json()["placement"]
    hs = hoods(c, pid)
    assert len(hs) == 1
    h = hs[0]
    assert h["sku"] == "decor:hood" and h["over"] == x["placement_id"] and h["hung"] is True and h["kind"] == "decor"
    top = x["base_m"] + x["size_m"][1]
    assert h["base_m"] == pytest.approx(top + 0.7, abs=0.01)
    assert math.dist(h["center_xz"], x["center_xz"]) < 0.35   # 인덕션 바로 위
    assert h["size_m"][0] >= x["size_m"][0] - 0.05            # 인덕션보다 좁지 않게
    assert h["verdict"] != "no_fit"
    assert x["verdict"] != "no_fit"                           # 후드 때문에 인덕션이 겹침이 되지 않는다


def test_cooktop_on_an_island_in_the_middle_gets_a_ceiling_hood(c):
    pid = home(c)
    mid = middle(c, pid)
    isl = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:islandtable", "center_xz": mid, "yaw_rad": 0, "snap": False}).json()["placement"]
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": COOKTOP, "center_xz": mid, "yaw_rad": 0, "snap": False}).json()["placement"]
    assert x["on"] == isl["placement_id"] and x["verdict"] != "no_fit"
    assert not [y for y in placements(c, pid) if y["sku"] == "decor:basecab"]  # 아일랜드 식탁이 조리대라 하부장은 안 딸려 온다
    h = hoods(c, pid)[0]
    assert h["sku"] == "decor:islandhood" and h["center_xz"] == pytest.approx(x["center_xz"], abs=0.01)
    room = c.get(f"/api/projects/{pid}/room").json()
    tops = [(w.get("measured") or {}).get("height_m") or w["scanned"]["height_m"] for w in room["walls"]]
    assert min(t for t in tops if t) - 0.01 <= h["base_m"] + h["size_m"][1] <= max(t for t in tops if t) + 0.01  # 천장에서 내려온다
    assert h["verdict"] != "no_fit"


def test_hood_follows_the_cooktop_and_leaves_with_it(c):
    pid = home(c)
    mid = middle(c, pid)
    c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:islandtable", "center_xz": mid, "yaw_rad": 0, "snap": False})
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": COOKTOP, "center_xz": mid, "yaw_rad": 0, "snap": False}).json()["placement"]
    hid = hoods(c, pid)[0]["placement_id"]
    to = [mid[0] + 0.2, mid[1]]
    now = c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}", json={"center_xz": to, "yaw_rad": 0, "snap": False}).json()["placement"]
    assert math.dist(now["center_xz"], x["center_xz"]) > 0.05
    h = hoods(c, pid)
    assert len(h) == 1 and h[0]["placement_id"] == hid and h[0]["center_xz"] == pytest.approx(now["center_xz"], abs=0.01)
    c.delete(f"/api/projects/{pid}/placements/{x['placement_id']}")
    assert hoods(c, pid) == []


def test_hood_moves_with_the_island_under_the_cooktop(c):
    pid = home(c)
    mid = middle(c, pid)
    isl = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:islandtable", "center_xz": mid, "yaw_rad": 0, "snap": False}).json()["placement"]
    c.post(f"/api/projects/{pid}/placements", json={"sku": COOKTOP, "center_xz": mid, "yaw_rad": 0, "snap": False})
    to = [mid[0] + 0.5, mid[1] + 0.3]
    c.patch(f"/api/projects/{pid}/placements/{isl['placement_id']}", json={"center_xz": to, "yaw_rad": 0, "snap": False})
    assert hoods(c, pid)[0]["center_xz"] == pytest.approx(to, abs=0.01)


def test_a_hood_taken_off_stays_off_until_it_is_asked_for_again(c):
    pid = home(c)
    x = c.post(f"/api/projects/{pid}/auto-place", json={"sku": COOKTOP}).json()["placement"]
    c.delete(f"/api/projects/{pid}/placements/{hoods(c, pid)[0]['placement_id']}")
    assert hoods(c, pid) == []
    cx, cz = x["center_xz"]
    u = x["yaw_rad"] - math.pi / 2
    c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}",
            json={"center_xz": [cx + 0.05 * math.cos(u), cz + 0.05 * math.sin(u)], "yaw_rad": x["yaw_rad"], "snap": False})
    assert hoods(c, pid) == []                       # 옮겨도 다시 생기지 않는다
    r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:hood"})
    assert r.status_code == 200, r.text
    assert r.json()["placement"]["over"] == x["placement_id"]   # 목록에서 후드를 누르면 인덕션 위에 다시 달린다
    assert len(hoods(c, pid)) == 1


def test_hood_put_on_a_wall_by_hand_hangs_at_cooking_height(c):
    pid = home(c)
    room = c.get(f"/api/projects/{pid}/room").json()
    w = max(room["walls"], key=lambda q: math.dist(q["start"], q["end"]))
    at = [(w["start"][0] + w["end"][0]) / 2, (w["start"][1] + w["end"][1]) / 2]
    x = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:hood", "center_xz": at, "yaw_rad": 0}).json()["placement"]
    assert x["hung"] is True and x["base_m"] > 1.4 and x["verdict"] != "no_fit" and not x.get("over")
    x2 = c.patch(f"/api/projects/{pid}/placements/{x['placement_id']}", json={"base_m": 1.8}).json()["placement"]
    assert x2["base_m"] == pytest.approx(1.8, abs=0.3)


def test_island_table_holds_small_appliances_like_a_table(c):
    pid = home(c)
    mid = middle(c, pid)
    isl = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:islandtable", "center_xz": mid, "yaw_rad": 0, "snap": False}).json()["placement"]
    m = c.post(f"/api/projects/{pid}/placements", json={"sku": MICRO, "center_xz": mid, "yaw_rad": 0, "snap": False}).json()["placement"]
    assert m["on"] == isl["placement_id"] and m["base_m"] == pytest.approx(isl["size_m"][1], abs=0.001)
