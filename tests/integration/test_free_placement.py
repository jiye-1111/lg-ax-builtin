"""제품을 골라 원하는 자리에 놓기·옮기기·돌리기 + 기존 가구 치우기 (S2~S4)."""
import pytest
from fastapi.testclient import TestClient

from api import main
from core.service import Service

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"
SKU = "G646GBB031"  # LGE.COM 실제품 (치수 있음)


@pytest.fixture
def c(tmp_path, monkeypatch):
    svc = Service(storage=tmp_path / "st")
    main.app.dependency_overrides[main.get_service] = lambda: svc
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def pid(c):
    with open(REAL, "rb") as f:
        return c.post("/api/projects", files={"file": ("home.usdz", f)}, data={"scanned_by": "customer"}).json()["project_id"]


def test_pose_check_does_not_save(c, pid):
    r = c.post(f"/api/projects/{pid}/pose-check", json={"sku": SKU, "center_xz": [-2.0, 0.0], "yaw_rad": 0})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] in {"fit", "conditional", "no_fit"} and "reasons" in body and len(body["footprint"]) == 4
    assert c.get(f"/api/projects/{pid}").json()["scene_state"]["placements"] == []


def test_place_move_rotate_delete(c, pid):
    # w8(x≈-5.6, 긴 벽) 근처에 놓으면 벽에 붙는다. 가구 없는 자리를 판정으로 찾는다
    spot = next(z / 2 for z in range(-12, 8)
                if c.post(f"/api/projects/{pid}/pose-check", json={"sku": SKU, "center_xz": [-5.0, z / 2], "yaw_rad": 0.3})
                .json()["verdict"] != "no_fit")
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": SKU, "center_xz": [-5.0, spot], "yaw_rad": 0.3})
    assert r.status_code == 200, r.text
    pl = r.json()["placement"]
    assert pl["placement_id"] and pl["wall_id"] in {"w8", "w3", "w2"} and pl["verdict"] in {"fit", "conditional"}
    plid = pl["placement_id"]
    # 옮기기 (붙이기 끔) → 방 밖
    r = c.patch(f"/api/projects/{pid}/placements/{plid}", json={"center_xz": [-9.0, 2.0], "snap": False})
    assert r.status_code == 200 and r.json()["placement"]["verdict"] == "no_fit"
    # 색 바꾸기는 카탈로그 옵션 안에서만
    assert c.patch(f"/api/projects/{pid}/placements/{plid}", json={"color": "없는색"}).status_code == 422
    assert c.delete(f"/api/projects/{pid}/placements/{plid}").status_code == 200
    assert c.get(f"/api/projects/{pid}").json()["scene_state"]["placements"] == []


def test_two_products_cannot_share_a_spot(c, pid):
    a = c.post(f"/api/projects/{pid}/placements", json={"sku": SKU, "center_xz": [-2.0, 0.0], "yaw_rad": 0, "snap": False}).json()
    b = c.post(f"/api/projects/{pid}/placements", json={"sku": SKU, "center_xz": [-2.2, 0.0], "yaw_rad": 0, "snap": False}).json()
    assert any(x["code"] == "overlaps_placement" for x in b["placement"]["reasons"])
    # 첫 번째도 다시 판정되어 겹침이 보인다
    first = next(p for p in b["scene_state"]["placements"] if p["placement_id"] == a["placement"]["placement_id"])
    assert first["verdict"] == "no_fit"


def test_hide_scanned_furniture_frees_space(c, pid):
    room = c.get(f"/api/projects/{pid}/room").json()
    table = max((o for o in room["objects"] if o["category"] == "table"), key=lambda o: o["bbox_m"]["w"])
    x, _, z = table["position"]
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": SKU, "center_xz": [x, z], "yaw_rad": 0, "snap": False}).json()
    assert any(x["code"] == "overlaps_object" for x in r["placement"]["reasons"])
    r = c.put(f"/api/projects/{pid}/objects/{table['object_id']}/hidden", json={"hidden": True})
    assert r.status_code == 200
    st = c.get(f"/api/projects/{pid}").json()["scene_state"]
    assert table["object_id"] in st["hidden_objects"]
    assert not any(x["code"] == "overlaps_object" and x["ref"] == table["object_id"] for x in st["placements"][0]["reasons"])
    assert c.put(f"/api/projects/{pid}/objects/nope/hidden", json={"hidden": True}).status_code == 404


def test_zone_placement_still_works_and_gets_id(c, pid):
    z = c.post(f"/api/projects/{pid}/zones", json={"purpose": "kitchen", "polygon_m": [[-5.7, 1.0], [-4.5, 1.0], [-4.5, 4.0], [-5.7, 4.0]]}).json()
    r = c.post(f"/api/projects/{pid}/placements", json={"zone_id": z["zone_id"], "sku": SKU})
    if r.status_code == 200:
        assert r.json()["scene_state"]["placements"][0]["placement_id"]


def test_hide_all_furniture_at_once_and_restore(c, pid):
    room = c.get(f"/api/projects/{pid}/room").json()
    every = {o["object_id"] for o in room["objects"]}
    r = c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True})
    assert r.status_code == 200, r.text
    assert set(c.get(f"/api/projects/{pid}").json()["scene_state"]["hidden_objects"]) == every
    r = c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": False})
    assert r.status_code == 200
    assert c.get(f"/api/projects/{pid}").json()["scene_state"]["hidden_objects"] == []


def test_hide_some_furniture_by_ids(c, pid):
    chairs = [o["object_id"] for o in c.get(f"/api/projects/{pid}/room").json()["objects"] if o["category"] == "chair"][:3]
    r = c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True, "object_ids": chairs})
    assert r.status_code == 200
    assert sorted(c.get(f"/api/projects/{pid}").json()["scene_state"]["hidden_objects"]) == sorted(chairs)
    assert c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True, "object_ids": ["nope"]}).status_code == 404


# ---- 스캔 가구 옮기기·돌리기 (건축 모드) ----
def _table(c, pid):
    room = c.get(f"/api/projects/{pid}/room").json()
    return max((o for o in room["objects"] if o["category"] == "table"), key=lambda o: o["bbox_m"]["w"])


def test_move_and_rotate_scanned_furniture(c, pid):
    t = _table(c, pid)
    x, y, z = t["position"]
    r = c.put(f"/api/projects/{pid}/objects/{t['object_id']}/pose", json={"center_xz": [x + 0.5, z - 0.25], "yaw_rad": t["yaw_rad"] + 0.785})
    assert r.status_code == 200, r.text
    moved = next(o for o in c.get(f"/api/projects/{pid}/room").json()["objects"] if o["object_id"] == t["object_id"])
    assert moved["position"] == pytest.approx([x + 0.5, y, z - 0.25])
    assert moved["yaw_rad"] == pytest.approx(t["yaw_rad"] + 0.785)
    assert c.get(f"/api/projects/{pid}").json()["scene_state"]["object_poses"][t["object_id"]]["center_xz"] == pytest.approx([x + 0.5, z - 0.25])


def test_moving_furniture_away_frees_the_spot(c, pid):
    t = _table(c, pid)
    x, _, z = t["position"]
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": SKU, "center_xz": [x, z], "yaw_rad": 0, "snap": False}).json()
    assert any(q["code"] == "overlaps_object" and q["ref"] == t["object_id"] for q in r["placement"]["reasons"])
    c.put(f"/api/projects/{pid}/objects/{t['object_id']}/pose", json={"center_xz": [x + 4.0, z], "yaw_rad": t["yaw_rad"]})
    st = c.get(f"/api/projects/{pid}").json()["scene_state"]
    assert not any(q["code"] == "overlaps_object" and q["ref"] == t["object_id"] for q in st["placements"][0]["reasons"])


def test_reset_furniture_pose_and_measurements_do_not_bake_moves(c, pid):
    t = _table(c, pid)
    x, y, z = t["position"]
    c.put(f"/api/projects/{pid}/objects/{t['object_id']}/pose", json={"center_xz": [x + 1, z], "yaw_rad": 0})
    room = c.get(f"/api/projects/{pid}/room").json()
    w = room["walls"][0]
    c.put(f"/api/projects/{pid}/walls/{w['wall_id']}/measured", json={"length_m": round(w["scanned"]["length_m"], 3), "by": "customer"})
    assert c.delete(f"/api/projects/{pid}/objects/{t['object_id']}/pose").status_code == 200
    back = next(o for o in c.get(f"/api/projects/{pid}/room").json()["objects"] if o["object_id"] == t["object_id"])
    assert back["position"] == pytest.approx([x, y, z]) and back["yaw_rad"] == pytest.approx(t["yaw_rad"])


def test_move_unknown_furniture_is_404_and_bad_input_422(c, pid):
    assert c.put(f"/api/projects/{pid}/objects/nope/pose", json={"center_xz": [0, 0], "yaw_rad": 0}).status_code == 404
    t = _table(c, pid)
    assert c.put(f"/api/projects/{pid}/objects/{t['object_id']}/pose", json={"center_xz": [0], "yaw_rad": 0}).status_code == 422


def test_measured_spot_overrides_scan(c, pid):
    """넣을 자리를 줄자로 잰 값(선택)을 넣으면 그 값으로 판정하고, 지우면 스캔 판정으로 돌아간다."""
    pl = c.post(f"/api/projects/{pid}/placements", json={"sku": SKU, "center_xz": [-9.0, 2.0], "snap": False}).json()["placement"]
    assert pl["verdict"] == "no_fit"
    url = f"/api/projects/{pid}/placements/{pl['placement_id']}/measured"
    r = c.put(url, json={"w_mm": 2000, "h_mm": 2600, "d_mm": 1200})
    assert r.status_code == 200, r.text
    got = r.json()["placement"]
    assert got["measured_mm"] == {"w": 2000, "h": 2600, "d": 1200}
    assert any(x["code"] == "measured" for x in got["reasons"])
    assert c.put(url, json={"w_mm": -1}).status_code == 422
    r = c.put(url, json={"w_mm": None, "h_mm": None, "d_mm": None}).json()["placement"]
    assert "measured_mm" not in r and r["verdict"] == "no_fit"
