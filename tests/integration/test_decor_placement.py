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
