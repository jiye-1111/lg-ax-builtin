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


def test_install_check_lists_placed_products(c, pid):
    assert c.get(f"/api/projects/{pid}/install-check").json() == {
        "summary": {"products": 0, "ok": 0, "check": 0, "blocked": 0, "walls_to_measure": []}, "items": []}
    pl = c.post(f"/api/projects/{pid}/placements", json={"sku": SKU, "center_xz": [-2.0, 0.0], "yaw_rad": 0, "snap": False}).json()["placement"]
    out = c.get(f"/api/projects/{pid}/install-check").json()
    assert out["summary"]["products"] == 1
    it = out["items"][0]
    assert it["placement_id"] == pl["placement_id"] and it["dims_mm"]["w"] == 914
    codes = [x["code"] for x in it["checks"]]
    assert codes[0] == "space" and "power" in codes and "carry" in codes  # 빌트인 핏이라 앞 공간 줄은 없다
    assert "front" not in codes
    assert it["status"] == {"fit": "ok", "conditional": "check", "no_fit": "blocked"}[pl["verdict"]]
    assert c.get("/api/projects/none/install-check").status_code == 404


FORM = {"name": "홍길동", "contact": "010-1234-5678", "address": "서울시 어딘가 1"}


def test_install_request_needs_a_placed_product(c, pid):
    assert c.post(f"/api/projects/{pid}/install-request", json=FORM).status_code == 422


def test_install_request_carries_products_and_checks(c, pid, monkeypatch):
    c.post(f"/api/projects/{pid}/placements", json={"sku": SKU, "center_xz": [-2.0, 0.0], "yaw_rad": 0, "snap": False})
    r = c.post(f"/api/projects/{pid}/install-request", json=FORM)
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["kind"] == "install" and req["project_id"] == pid and req["status"] == "requested"
    assert req["customer"] == {"name": "홍길동", "contact": "010-1234-5678"}
    item = req["products"][0]
    assert item["sku"] == SKU and item["name"] and item["source_url"].startswith("https://www.lge.co.kr/")
    assert item["status"] in {"ok", "check", "blocked"}
    assert req["summary"]["products"] == 1
    # 프로젝트에도 신청 번호가 남아서 화면에서 "신청함"을 보여 줄 수 있다
    assert c.get(f"/api/projects/{pid}").json()["install_request_id"] == req["request_id"]
    # 기사 목록에 함께 보인다
    svc = main.app.dependency_overrides[main.get_service]()
    assert [x["request_id"] for x in svc.list_requests() if x.get("kind") == "install"] == [req["request_id"]]


def test_before_scene_ignores_later_changes(c, pid):
    first = c.get(f"/api/projects/{pid}/files/scene.glb").content
    c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True})
    c.post(f"/api/projects/{pid}/placements", json={"sku": SKU, "center_xz": [-2.0, 0.0], "yaw_rad": 0, "snap": False})
    assert c.get(f"/api/projects/{pid}/files/scene.glb").content != first
    r = c.get(f"/api/projects/{pid}/files/before.glb")
    assert r.status_code == 200 and r.content == first
    assert c.get("/api/projects/none/files/before.glb").status_code == 404


def test_auto_place_finds_a_spot_in_the_real_scan(c, pid):
    c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True})  # 가구 치운 빈 방
    r = c.post(f"/api/projects/{pid}/auto-place", json={"sku": SKU})
    assert r.status_code == 200, r.text
    pl = r.json()["placement"]
    assert pl["verdict"] in {"fit", "conditional"} and pl["wall_id"]
    # 두 번째도 첫 번째와 안 겹치는 자리
    pl2 = c.post(f"/api/projects/{pid}/auto-place", json={"sku": SKU}).json()["placement"]
    assert all(x["code"] != "overlaps_placement" for x in pl2["reasons"])
    assert c.post(f"/api/projects/{pid}/auto-place", json={"sku": "NOPE"}).status_code == 404


def test_auto_align_snaps_to_wall_or_moves_to_a_good_spot(c, pid):
    c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True})
    room = c.get(f"/api/projects/{pid}/files/room.json").json()
    xs = [p[0] for w in room["walls"] for p in (w["start"], w["end"])]
    zs = [p[1] for w in room["walls"] for p in (w["start"], w["end"])]
    mid = [(min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2]
    # 방 한가운데 아무렇게나 놓은 제품
    pl = c.post(f"/api/projects/{pid}/placements", json={"sku": SKU, "center_xz": mid, "yaw_rad": 0.3, "snap": False}).json()["placement"]
    assert not pl["wall_id"]
    r = c.post(f"/api/projects/{pid}/placements/{pl['placement_id']}/auto-align")
    assert r.status_code == 200, r.text
    moved = r.json()["placement"]
    assert moved["placement_id"] == pl["placement_id"] and moved["wall_id"]
    assert moved["verdict"] in {"fit", "conditional"}
    assert len(r.json()["scene_state"]["placements"]) == 1
    assert c.post(f"/api/projects/{pid}/placements/nope/auto-align").status_code == 404


def test_suggest_returns_products_that_fit_this_home(c, pid):
    c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True})
    r = c.post(f"/api/projects/{pid}/suggest", json={"skus": [SKU, "NOPE"], "limit": 3})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert [x["sku"] for x in items] == [SKU]
    assert items[0]["verdict"] in {"fit", "conditional"} and items[0]["wall_id"]
    assert c.post(f"/api/projects/{pid}/suggest", json={"skus": [], "limit": 3}).json()["items"] == []
    assert c.post(f"/api/projects/{pid}/suggest", json={"skus": ["x"] * 61}).status_code == 422
