"""빌트인 주방 맞춤장 API: 장 놓기 → 가전 넣기 → 부재 바꾸기 → 마감 → 저장·복원 (docs/specs/builtin-kitchen.md)."""
import pytest
from api import main
from core.service import Service
from fastapi.testclient import TestClient

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"


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
    c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True})  # 빈 방에서 본다
    return pid


def pls(c, pid):
    return c.get(f"/api/projects/{pid}").json()["scene_state"]["placements"]


def inside(c, pid, plid):
    return next(x for x in pls(c, pid) if x.get("in_cab") == plid)


def test_kinds_list_has_first_stage_and_next_stage(c):
    r = c.get("/api/cabinet/kinds").json()
    stages = {k["kind"]: k["stage"] for k in r["kinds"]}
    assert stages["fridge"] == 1 and stages["oven_tall"] == 1 and stages["tvwall"] == 1
    assert {f["id"] for f in r["finishes"]["top"]} == {"stone_white", "stone_warmbeige", "ceramic_dark"}
    assert any("G646GBB031" in x["skus"] for x in r["rules"])


def test_new_fridge_housing_suggests_inside_and_carries_the_fridge(c, pid):
    r = c.post(f"/api/projects/{pid}/cabinets", json={"kind": "fridge", "sku": "G646GBB031"})
    assert r.status_code == 200, r.text
    cab = r.json()["placement"]
    assert cab["sku"] == "decor:cab_fridge" and cab["kind"] == "decor"
    assert cab["cab"]["outer_mm"] == {"w": 958, "h": 2269, "d": 720}
    assert cab["size_m"] == pytest.approx([0.958, 2.269, 0.72])
    chk = cab["cab_check"]
    assert chk["verdict"] == "fit" and chk["axes"][0]["source"] == "designed"
    fr = inside(c, pid, cab["placement_id"])
    assert fr["sku"] == "G646GBB031" and fr["size_m"] == pytest.approx([0.914, 1.86, 0.709])  # 가전 크기는 그대로
    assert fr["verdict"] == "fit"
    # 장을 옮기면 냉장고도 같이 간다
    x, z = cab["center_xz"]
    r = c.patch(f"/api/projects/{pid}/placements/{cab['placement_id']}", json={"center_xz": [x + 0.3, z], "snap": False})
    assert r.status_code == 200, r.text
    moved = r.json()["placement"]
    fr2 = inside(c, pid, cab["placement_id"])
    assert fr2["center_xz"][0] - fr["center_xz"][0] == pytest.approx(moved["center_xz"][0] - x, abs=1e-6)


def test_thicker_side_panel_changes_verdict_and_short_mm(c, pid):
    cab = c.post(f"/api/projects/{pid}/cabinets", json={"kind": "fridge", "sku": "G646GBB031"}).json()["placement"]
    r = c.patch(f"/api/projects/{pid}/cabinets/{cab['placement_id']}", json={"parts": {"side_l": 25}})
    assert r.status_code == 200, r.text
    after = r.json()["placement"]
    assert after["cab"]["outer_mm"]["w"] == 958
    w = after["cab_check"]["axes"][0]
    assert after["cab_check"]["verdict"] == "no_fit" and w["short_mm"] == 7 and w["have_mm"] == 915
    assert inside(c, pid, cab["placement_id"])["verdict"] == "no_fit"
    back = c.patch(f"/api/projects/{pid}/cabinets/{cab['placement_id']}", json={"parts": {"side_l": 18}}).json()["placement"]
    assert back["cab_check"]["verdict"] == "fit"


def test_existing_cabinet_keeps_size_when_swapping_appliance(c, pid):
    r = c.post(f"/api/projects/{pid}/cabinets", json={"kind": "fridge", "mode": "existing", "sku": "G646GBB031",
                                                     "outer_mm": {"w": 760, "h": 2300, "d": 720}, "measured_mm": {"w": 708, "h": 1900, "d": 720}})
    assert r.status_code == 200, r.text
    cab = r.json()["placement"]
    assert cab["cab_check"]["verdict"] == "no_fit" and cab["cab_check"]["axes"][0]["source"] == "measured"
    r = c.put(f"/api/projects/{pid}/cabinets/{cab['placement_id']}/appliance", json={"sku": "Z386GBB281", "resize": True})
    swapped = r.json()["placement"]
    assert swapped["cab"]["outer_mm"] == {"w": 760, "h": 2300, "d": 720} and swapped["cab"]["measured_mm"]["w"] == 708
    assert swapped["cab_check"]["verdict"] == "fit" and swapped["cab_check"]["sku"] == "Z386GBB281"
    assert sum(1 for x in pls(c, pid) if x.get("in_cab") == cab["placement_id"]) == 1


def test_missing_measurement_or_rule_is_never_fit(c, pid):
    cab = c.post(f"/api/projects/{pid}/cabinets", json={"kind": "fridge", "mode": "existing", "sku": "G646GBB031",
                                                       "measured_mm": {"w": 930, "h": 1900}}).json()["placement"]
    assert cab["cab_check"]["verdict"] == "unknown"
    other = c.post(f"/api/projects/{pid}/cabinets", json={"kind": "fridge", "sku": "D646GBB021"}).json()["placement"]
    assert other["cab_check"]["verdict"] == "unknown" and other["cab"]["outer_mm"]["w"] == 958  # 권장 치수 없이 기본 크기


def test_dishwasher_bay_and_wrong_appliance(c, pid):
    r = c.post(f"/api/projects/{pid}/cabinets", json={"kind": "dishwasher", "sku": "DUE6BGE"})
    assert r.status_code == 200, r.text
    cab = r.json()["placement"]
    assert cab["cab_check"]["verdict"] == "fit"
    codes = {x["code"]: x["status"] for x in cab["cab_check"]["checks"]}
    assert codes["water"] == "site" and codes["side_fix"] == "ok"
    bad = c.put(f"/api/projects/{pid}/cabinets/{cab['placement_id']}/appliance", json={"sku": "G646GBB031"})
    assert bad.status_code == 422


def test_finish_many_cabinets_and_restore_after_reload(c, pid):
    a = c.post(f"/api/projects/{pid}/cabinets", json={"kind": "drawer"}).json()["placement"]
    b = c.post(f"/api/projects/{pid}/cabinets", json={"kind": "glass_wall", "glass": "bronze"}).json()["placement"]
    r = c.post(f"/api/projects/{pid}/cabinets/finish", json={"ids": [a["placement_id"], b["placement_id"]], "part": "front", "finish": "sage_matte"})
    assert r.status_code == 200, r.text
    bad = c.post(f"/api/projects/{pid}/cabinets/finish", json={"ids": [a["placement_id"]], "part": "front", "finish": "stone_white"})
    assert bad.status_code == 422
    got = {x["placement_id"]: x for x in pls(c, pid)}
    assert got[a["placement_id"]]["cab"]["finish"]["front"] == "sage_matte"
    assert got[b["placement_id"]]["cab"]["finish"]["front"] == "sage_matte" and got[b["placement_id"]]["cab"]["glass"] == "bronze"
    assert got[b["placement_id"]]["base_m"] == pytest.approx(1.45)


def test_save_and_restore_keeps_cabinet_and_appliance(c, tmp_path):
    tok = c.post("/api/auth/signup", json={"email": "kim@example.com", "password": "pass-word-1", "name": "김", "role": "customer"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    with open(REAL, "rb") as f:
        pid = c.post("/api/projects", files={"file": ("home.usdz", f)}, data={"scanned_by": "customer"}, headers=h).json()["project_id"]
    cab = c.post(f"/api/projects/{pid}/cabinets", json={"kind": "fridge", "sku": "G646GBB031",
                                                       "finish": {"front": "walnut"}}).json()["placement"]
    save = c.post(f"/api/projects/{pid}/saves", json={"kind": "manual", "label": "주방"}, headers=h)
    assert save.status_code == 201, save.text
    c.patch(f"/api/projects/{pid}/cabinets/{cab['placement_id']}", json={"parts": {"side_l": 30}})
    c.put(f"/api/projects/{pid}/cabinets/{cab['placement_id']}/appliance", json={"sku": None})
    assert not any(x.get("in_cab") for x in pls(c, pid))
    r = c.post(f"/api/projects/{pid}/saves/{save.json()['save_id']}/restore", headers=h)
    assert r.status_code == 200, r.text
    back = next(x for x in pls(c, pid) if x["placement_id"] == cab["placement_id"])
    assert back["cab"]["parts"]["side_l"] == 18 and back["cab"]["finish"]["front"] == "walnut"
    assert inside(c, pid, cab["placement_id"])["sku"] == "G646GBB031"
    assert back["cab_check"]["verdict"] == "fit"
    # 새로 열어도 (서버를 다시 띄워도) 그대로
    again = Service(storage=tmp_path / "st").get_project(pid)["scene_state"]["placements"]
    assert next(x for x in again if x["placement_id"] == cab["placement_id"])["cab"]["finish"]["front"] == "walnut"


def test_unknown_kind_is_refused(c, pid):
    assert c.post(f"/api/projects/{pid}/cabinets", json={"kind": "spaceship"}).status_code == 422


def test_removing_cabinet_takes_out_its_appliance(c, pid):
    r = c.post(f"/api/projects/{pid}/cabinets", json={"kind": "fridge", "sku": "G646GBB031", "center_xz": [1.0, 1.0], "yaw_rad": 1.5708})
    cab = r.json()["placement"]["placement_id"]
    fr = next(x["placement_id"] for x in pls(c, pid) if x.get("in_cab") == cab)
    assert c.delete(f"/api/projects/{pid}/placements/{cab}").status_code == 200
    assert not {cab, fr} & {x["placement_id"] for x in pls(c, pid)}  # 장과 같이 놓은 가전도 같이 빠진다


def test_plain_placement_and_copy_keep_cabinet_parts(c, pid):
    # 목록에서 그냥 놓아도(되돌리기·MCP) 기본 부재가 붙은 장이 된다
    r = c.post(f"/api/projects/{pid}/placements", json={"sku": "decor:cab_drawer", "center_xz": [1.0, 1.0], "yaw_rad": 1.5708, "snap": False})
    assert r.status_code == 200, r.text
    x = next(q for q in pls(c, pid) if q["placement_id"] == r.json()["placement"]["placement_id"])
    assert x["cab"]["kind"] == "drawer" and x["cab"]["outer_mm"]["w"] == pytest.approx(x["size_m"][0] * 1000)
    # 복사하면 고친 부재·마감도 그대로
    c.patch(f"/api/projects/{pid}/cabinets/{x['placement_id']}", json={"parts": {"drawers": 4}, "finish": {"front": "sage_matte"}})
    r = c.post(f"/api/projects/{pid}/placements/{x['placement_id']}/copy", json={})
    assert r.status_code == 200, r.text
    twin = next(q for q in pls(c, pid) if q["placement_id"] == r.json()["placement"]["placement_id"])
    assert twin["cab"]["parts"]["drawers"] == 4 and twin["cab"]["finish"]["front"] == "sage_matte"


def test_switch_to_existing_with_partly_measured_inside(c, pid):
    cab = c.post(f"/api/projects/{pid}/cabinets", json={"kind": "fridge", "sku": "G646GBB031"}).json()["placement"]
    r = c.patch(f"/api/projects/{pid}/cabinets/{cab['placement_id']}", json={"mode": "existing", "measured_mm": {"w": 922, "h": 1869, "d": None}})
    assert r.status_code == 200, r.text
    x = r.json()["placement"]
    assert x["cab"]["mode"] == "existing" and x["cab_check"]["verdict"] == "unknown"  # 깊이를 안 쟀으면 판정 불가
