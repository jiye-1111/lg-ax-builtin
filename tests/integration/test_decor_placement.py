"""가구·가벽 놓기: LG 제품과 같은 판정(겹침·벽)을 쓰고, 주문·설치 신청에는 들어가지 않는다."""
import pytest
from api import main
from core.service import Service
from fastapi.testclient import TestClient

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"
SKU = "G646GBB031"


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


def test_decor_list_endpoint(c):
    items = c.get("/api/decor").json()["items"]
    assert any(i["sku"] == "decor:sofa" for i in items)
    assert all("price_krw" not in i for i in items)


def test_auto_place_sofa_and_copy(c, pid):
    r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:sofa"})
    assert r.status_code == 200, r.text
    pl = r.json()["placement"]
    assert pl["sku"] == "decor:sofa" and pl["kind"] == "decor" and pl["verdict"] in {"fit", "conditional"}
    # 복사: 같은 크기로 옆 빈자리에
    r2 = c.post(f"/api/projects/{pid}/placements/{pl['placement_id']}/copy")
    assert r2.status_code == 200, r2.text
    cp = r2.json()["placement"]
    assert cp["placement_id"] != pl["placement_id"] and cp["size_m"] == pl["size_m"]
    assert len(c.get(f"/api/projects/{pid}").json()["scene_state"]["placements"]) == 2


def test_partition_wall_length_can_change(c, pid):
    r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:wall", "size_m": [1.5, 2.4, 0.1]})
    assert r.status_code == 200, r.text
    pl = r.json()["placement"]
    assert pl["size_m"][0] == pytest.approx(1.5)
    r = c.patch(f"/api/projects/{pid}/placements/{pl['placement_id']}", json={"size_m": [2.5, 2.4, 0.1]})
    assert r.status_code == 200, r.text
    assert r.json()["placement"]["size_m"][0] == pytest.approx(2.5)


def test_resize_only_for_decor(c, pid):
    pl = c.post(f"/api/projects/{pid}/auto-place", json={"sku": SKU}).json()["placement"]
    r = c.patch(f"/api/projects/{pid}/placements/{pl['placement_id']}", json={"size_m": [1, 1, 1]})
    assert r.status_code == 422


def test_furniture_blocks_lg_product_overlap(c, pid):
    sofa = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:sofa"}).json()["placement"]
    r = c.post(f"/api/projects/{pid}/pose-check",
               json={"sku": SKU, "center_xz": sofa["center_xz"], "yaw_rad": sofa["yaw_rad"], "snap": False})
    assert any(x["code"] == "overlaps_placement" for x in r.json()["reasons"])


def test_rug_never_collides(c, pid):
    # 러그는 방 가운데 쪽에 깔리고, 그 위에 다른 것을 놓아도 겹침이 아니다
    r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:rug"})
    assert r.status_code == 200, r.text
    rug = r.json()["placement"]
    assert rug["verdict"] != "no_fit"
    chk = c.post(f"/api/projects/{pid}/pose-check",
                 json={"sku": "decor:coffee", "center_xz": rug["center_xz"], "yaw_rad": 0, "snap": False}).json()
    assert not any(x["code"] == "overlaps_placement" for x in chk["reasons"])


def test_decor_not_in_install_check(c, pid):
    c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:sofa"})
    chk = c.get(f"/api/projects/{pid}/install-check").json()
    assert chk["summary"]["products"] == 0


def test_remove_and_restore_scanned_wall(c, pid):
    room = c.get(f"/api/projects/{pid}/room").json()
    wid = room["walls"][0]["wall_id"]
    r = c.put(f"/api/projects/{pid}/walls/{wid}/hidden", json={"hidden": True})
    assert r.status_code == 200, r.text
    assert wid in r.json()["scene_state"]["hidden_walls"]
    r = c.put(f"/api/projects/{pid}/walls/{wid}/hidden", json={"hidden": False})
    assert wid not in r.json()["scene_state"]["hidden_walls"]
    assert c.put(f"/api/projects/{pid}/walls/nope/hidden", json={"hidden": True}).status_code == 404


def test_removed_wall_does_not_attract_snap(c, pid):
    room = c.get(f"/api/projects/{pid}/room").json()
    w = max(room["walls"], key=lambda w: w["scanned"]["length_m"])
    mid = [(w["start"][0] + w["end"][0]) / 2, (w["start"][1] + w["end"][1]) / 2]
    body = {"sku": "decor:plant", "center_xz": mid, "yaw_rad": 0, "snap": True}
    assert c.post(f"/api/projects/{pid}/pose-check", json=body).json()["pose"]["wall_id"] == w["wall_id"]
    c.put(f"/api/projects/{pid}/walls/{w['wall_id']}/hidden", json={"hidden": True})
    assert c.post(f"/api/projects/{pid}/pose-check", json=body).json()["pose"]["wall_id"] != w["wall_id"]


def test_nan_size_is_rejected(c, pid):
    r = c.post(f"/api/projects/{pid}/auto-place", content='{"sku": "decor:wall", "size_m": [NaN, 2.4, 0.1]}',
               headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_router_sits_on_desk_or_shelf_top(c, pid):
    """지예: 공유기를 책상·선반 위에 놓을 수 있게 → 놓은 자리 아래 가구 윗면 높이를 저장한다."""
    desk = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:desk"}).json()["placement"]
    r = c.put(f"/api/projects/{pid}/router", json={"center_xz": desk["center_xz"]})
    assert r.status_code == 200, r.text
    assert r.json()["scene_state"]["router"]["height_m"] == pytest.approx(desk["size_m"][1])
    shelf = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:shelf"}).json()["placement"]
    rt = c.put(f"/api/projects/{pid}/router", json={"center_xz": shelf["center_xz"]}).json()["scene_state"]["router"]
    assert rt["height_m"] == pytest.approx(shelf["size_m"][1])
    # 가구가 없는 바닥이면 0, 러그 위도 바닥
    rug = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:rug"}).json()["placement"]
    rt = c.put(f"/api/projects/{pid}/router", json={"center_xz": rug["center_xz"]}).json()["scene_state"]["router"]
    assert rt["height_m"] == 0


def test_router_comes_down_when_desk_is_removed(c, pid):
    desk = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:desk"}).json()["placement"]
    c.put(f"/api/projects/{pid}/router", json={"center_xz": desk["center_xz"]})
    assert c.delete(f"/api/projects/{pid}/placements/{desk['placement_id']}").status_code in (200, 204)
    assert c.get(f"/api/projects/{pid}").json()["scene_state"]["router"]["height_m"] == 0


def test_flow_walks_to_lg_products_not_furniture(c, pid):
    sofa = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:sofa"}).json()["placement"]
    lg = c.post(f"/api/projects/{pid}/auto-place", json={"sku": SKU}).json()["placement"]
    routes = c.get(f"/api/projects/{pid}/sim/flow").json()["routes"]
    assert lg["placement_id"] in routes and sofa["placement_id"] not in routes


def test_router_on_desk_edge_uses_desk_width(c, pid):
    """책상 가운데가 아니라 폭 끝쪽에 놓아도 책상 위 (폭 방향 = yaw - 90°)."""
    desk = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:desk"}).json()["placement"]
    import math
    w = desk["size_m"][0]
    yaw = desk["yaw_rad"] - math.pi / 2
    x, z = desk["center_xz"]
    edge = [x + math.cos(yaw) * w * 0.4, z + math.sin(yaw) * w * 0.4]
    rt = c.put(f"/api/projects/{pid}/router", json={"center_xz": edge}).json()["scene_state"]["router"]
    assert rt["height_m"] == pytest.approx(desk["size_m"][1])


def test_built_in_water_purifier_comes_with_sink_cabinet(c, pid):
    """빌트인 정수기는 싱크대 하부장 안에 들어간다. 하부장 없이 놓으면 하부장을 같이 놓고, 빼면 같이 빠진다."""
    r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "WU923AS"})
    assert r.status_code == 200, r.text
    pls = r.json()["scene_state"]["placements"]
    wp = next(x for x in pls if x["sku"] == "WU923AS")
    cab = [x for x in pls if x.get("host_of") == wp["placement_id"]]
    assert len(cab) == 1 and cab[0]["sku"] == "decor:basecab" and cab[0]["verdict"] != "no_fit"
    assert wp["verdict"] != "no_fit"   # 하부장 안이라 겹침이 아니다
    left = c.delete(f"/api/projects/{pid}/placements/{wp['placement_id']}").json()["scene_state"]["placements"]
    assert not left


@pytest.mark.parametrize("cleared", [False, True])
def test_every_decor_item_can_be_placed_in_the_real_scan(c, pid, cleared):
    """지예: 모든 물건이 놓이는지 확인. 스캔 가구가 있을 때와 다 치웠을 때 모두, 가구·소품마다 들어가는 자리가 있어야 한다."""
    if cleared:
        assert c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True}).status_code == 200
    kinds = [i["sku"] for i in c.get("/api/decor").json()["items"]]
    for sku in kinds:
        r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": sku})
        assert r.status_code == 200, (sku, r.text)
        pl = r.json()["placement"]
        assert pl["verdict"] != "no_fit", (sku, pl["reasons"])
        c.delete(f"/api/projects/{pid}/placements/{pl['placement_id']}")


def test_plant_in_open_floor_is_fit_after_clearing(c, pid):
    c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True})
    room = c.get(f"/api/projects/{pid}/room").json()
    xs = [v for w in room["walls"] for v in (w["start"][0], w["end"][0])]
    zs = [v for w in room["walls"] for v in (w["start"][1], w["end"][1])]
    mid = [(min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2]
    r = c.post(f"/api/projects/{pid}/pose-check", json={"sku": "decor:plant", "center_xz": mid, "yaw_rad": 0, "snap": False}).json()
    assert r["verdict"] == "fit", r["reasons"]


def test_placed_sink_is_the_sink_of_the_work_triangle(c, pid):
    sink = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:sink"}).json()["placement"]
    f = c.get(f"/api/projects/{pid}/sim/flow").json()
    assert sink["placement_id"] not in f["routes"]
    assert "sink" in f["routes"] and f["names"]["sink"] == "싱크대"


def test_start_mark_is_where_the_walk_begins(c, pid):
    lg = c.post(f"/api/projects/{pid}/auto-place", json={"sku": SKU}).json()["placement"]
    x, z = lg["center_xz"]
    import math
    spot = [x + math.cos(lg["yaw_rad"]) * 1.5, z + math.sin(lg["yaw_rad"]) * 1.5]
    assert c.put(f"/api/projects/{pid}/marks/start", json={"center_xz": spot}).status_code == 200
    f = c.get(f"/api/projects/{pid}/sim/flow").json()
    assert f["start"] == pytest.approx(spot, abs=0.3)
    assert f["routes"][lg["placement_id"]]["length_m"] < 2.0


def test_door_snaps_into_a_partition_wall_and_tells_if_it_opens(c, pid):
    wall = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "decor:wall", "size_m": [2.4, 2.4, 0.1]}).json()["placement"]
    import math
    mid = wall["center_xz"]
    # 벽 옆 20 cm를 눌러도 벽 한가운데 줄에 달린다
    near = [mid[0] + math.cos(wall["yaw_rad"]) * 0.2, mid[1] + math.sin(wall["yaw_rad"]) * 0.2]
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:door", "center_xz": near, "yaw_rad": 0.0})
    assert r.status_code in (200, 201), r.text
    door = r.json()["placement"]
    assert door["center_xz"] == pytest.approx(mid, abs=0.01)
    assert "hits_wall" not in {x["code"] for x in door["reasons"]} and "overlaps_placement" not in {x["code"] for x in door["reasons"]}
    assert abs(math.cos(door["yaw_rad"] - wall["yaw_rad"])) == pytest.approx(1, abs=1e-6)
