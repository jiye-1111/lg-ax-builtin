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
