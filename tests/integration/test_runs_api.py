"""벽면 맞춤가구 세트 API: 미리보기(저장 안 함) → 확정 → 장 고치기·지우기 → 다시 읽기 (docs/specs/wall-run.md)."""
import math

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
    c.put(f"/api/projects/{pid}/objects/hidden", json={"hidden": True})
    return pid


def long_wall(c, pid):
    room = c.get(f"/api/projects/{pid}/room").json()
    w = max(room["walls"], key=lambda w: math.dist(w["start"], w["end"]))
    return w, room


def pls(c, pid):
    return c.get(f"/api/projects/{pid}").json()["scene_state"]["placements"]


KITCHEN = {"base": [{"preset": "tall_pantry"}, {"preset": "bay_fridge", "app": {"sku": "G646GBB031"}}, {"preset": "sink_800"},
                    {"preset": "bay_dishwasher"}],
           "wall": [{"preset": "wall_glass", "gap_mm": 2200}]}


def test_presets_and_starters_are_listed_with_sources(c):
    r = c.get("/api/cabinet/presets").json()
    assert {s["id"] for s in r["starters"]} == {"empty", "kitchen", "tvwall", "storage"}
    assert r["sources"]["housetwin"]["url"] is None
    assert all(p["source"] in r["sources"] for p in r["presets"])


def test_preview_saves_nothing_and_confirm_saves(c, pid):
    w, _ = long_wall(c, pid)
    before = pls(c, pid)
    r = c.post(f"/api/projects/{pid}/runs/preview", json={"wall_id": w["wall_id"], "room": "kitchen", "rows": KITCHEN})
    assert r.status_code == 200, r.text
    pv = r.json()
    assert pv["preview"] is True and len(pv["modules"]) == 5
    assert pls(c, pid) == before  # 미리보기는 저장하지 않는다
    assert pv["usage"]["base"]["used_mm"] == 600 + 958 + 800 + 600 or pv["usage"]["base"]["used_mm"] > 2900
    # 결과는 셋으로 나눈다: 들어감 / 전기·급배수·방열 (문 열림은 화면에서)
    assert any(f["label"].startswith("냉장고") and f["verdict"] == "fit" for f in pv["fit"])
    dw = next(f for f in pv["fit"] if f["label"] == "식기세척기 자리")
    assert dw["verdict"] == "unknown" and "설치 기준 확인 필요" in dw["summary"]
    assert any("급수·배수" in u["label"] and u["status"] == "site" for u in pv["utilities"])
    assert pv["simulation"] in (True, False) and pv["wall"]["source"]

    r = c.post(f"/api/projects/{pid}/runs", json={"wall_id": w["wall_id"], "room": "kitchen", "rows": KITCHEN})
    assert r.status_code == 200, r.text
    rid = r.json()["run"]["run"]["run_id"]
    cabs = [x for x in pls(c, pid) if (x.get("cab") or {}).get("run", {}).get("id") == rid]
    assert len(cabs) == 5
    fr = next(x for x in pls(c, pid) if x["sku"] == "G646GBB031")
    assert fr.get("in_cab") and fr["cab_made"] is True
    again = c.get(f"/api/projects/{pid}/runs/{rid}").json()
    assert [m["label"] for m in again["modules"]][:3] == ["선반형 팬트리", "냉장고·김치냉장고장", "싱크 하부장 800"]


def test_existing_fridge_is_linked_not_duplicated(c, pid):
    w, _ = long_wall(c, pid)
    fr = c.post(f"/api/projects/{pid}/auto-place", json={"sku": "G646GBB031"})
    assert fr.status_code == 200, fr.text
    fid = fr.json()["placement"]["placement_id"]
    rows = {"base": [{"preset": "bay_fridge", "app": {"id": fid}}], "wall": []}
    r = c.post(f"/api/projects/{pid}/runs", json={"wall_id": w["wall_id"], "rows": rows})
    assert r.status_code == 200, r.text
    all_ = pls(c, pid)
    assert sum(1 for x in all_ if x["sku"] == "G646GBB031") == 1
    me = next(x for x in all_ if x["placement_id"] == fid)
    assert me["cab_made"] is False and me["in_cab"]
    # 장을 지워도 원래 놓은 냉장고는 남는다
    rid = r.json()["run"]["run"]["run_id"]
    r = c.delete(f"/api/projects/{pid}/runs/{rid}")
    assert r.status_code == 200, r.text
    left = [x for x in pls(c, pid) if x["placement_id"] == fid]
    assert left and not left[0].get("in_cab")


def test_editing_one_cabinet_reflows_the_set_and_dragging_detaches(c, pid):
    w, _ = long_wall(c, pid)
    rows = {"base": [{"preset": "base_door"}, {"preset": "base_drawer3"}, {"preset": "base_door"}], "wall": []}
    r = c.post(f"/api/projects/{pid}/runs", json={"wall_id": w["wall_id"], "rows": rows}).json()["run"]
    rid = r["run"]["run_id"]
    a, b, d = [m["id"] for m in r["modules"]]
    third0 = next(m for m in r["modules"] if m["id"] == d)["s0"]
    # 가운데 장을 넓히면 오른쪽 장이 밀린다
    resp = c.patch(f"/api/projects/{pid}/cabinets/{b}", json={"outer_mm": {"w": 800}})
    assert resp.status_code == 200, resp.text
    rep = c.get(f"/api/projects/{pid}/runs/{rid}").json()
    assert next(m for m in rep["modules"] if m["id"] == d)["s0"] == third0 + 200
    assert rep["usage"]["base"]["used_mm"] == 2000
    # 지우면 붙는다
    c.delete(f"/api/projects/{pid}/placements/{b}")
    rep = c.get(f"/api/projects/{pid}/runs/{rid}").json()
    assert [m["id"] for m in rep["modules"]] == [a, d] and rep["modules"][1]["s0"] == rep["modules"][0]["s1"]
    # 끌어 옮기면 세트에서 빠지고 그 자리에 남는다
    x = next(y for y in pls(c, pid) if y["placement_id"] == d)
    c.patch(f"/api/projects/{pid}/placements/{d}", json={"center_xz": [x["center_xz"][0] + 0.01, x["center_xz"][1] + 0.5], "snap": False})
    rep = c.get(f"/api/projects/{pid}/runs/{rid}").json()
    assert [m["id"] for m in rep["modules"]] == [a]


def test_narrowing_reorders_and_reports_blocking_with_cancel_free(c, pid):
    w, room = long_wall(c, pid)
    L = math.dist(w["start"], w["end"]) * 1000
    rows = {"base": [{"preset": "base_door"}], "wall": []}
    pv = c.post(f"/api/projects/{pid}/runs/preview", json={"wall_id": w["wall_id"], "rows": rows, "start_mm": {"base": round(L) - 300}}).json()
    assert any(i["code"] == "past_wall" for i in pv["issues"])
    assert pv["modules"][0]["s1"] - pv["modules"][0]["s0"] == 600  # 줄이지 않음


def test_reload_keeps_order_dims_finish_and_links(c, pid):
    w, _ = long_wall(c, pid)
    rows = {"base": [{"preset": "living_bookshelf", "finish": {"front": "lightoak"}}, {"preset": "tv_base_1800", "outer_mm": {"w": 1600}, "dims_by": "user"},
                     {"preset": "living_glass"}], "wall": []}
    r = c.post(f"/api/projects/{pid}/runs", json={"wall_id": w["wall_id"], "room": "living", "rows": rows, "start_mm": {"base": 200}})
    assert r.status_code == 200, r.text
    rid = r.json()["run"]["run"]["run_id"]
    rep = c.get(f"/api/projects/{pid}/runs/{rid}").json()
    assert rep["run"]["start_mm"]["base"] == 200
    assert [m["label"] for m in rep["modules"]] == ["오픈 책장", "TV 하부장 1800", "투명 유리 진열장"]
    assert rep["modules"][1]["s1"] - rep["modules"][1]["s0"] == 1600 and rep["modules"][1]["dims_src"] == "입력값"
    cab = next(x for x in pls(c, pid) if x["placement_id"] == rep["modules"][0]["id"])
    assert cab["cab"]["finish"]["front"] == "lightoak"
    assert rep["simulation"] is False
    # 같은 세트를 다시 보내면 같은 장이 고쳐진다 (새로 생기지 않음)
    ids = [m["id"] for m in rep["modules"]]
    rows2 = {"base": [{"id": ids[2]}, {"id": ids[0]}, {"id": ids[1]}], "wall": []}
    r = c.post(f"/api/projects/{pid}/runs", json={"run_id": rid, "wall_id": w["wall_id"], "rows": rows2})
    assert r.status_code == 200, r.text
    rep = c.get(f"/api/projects/{pid}/runs/{rid}").json()
    assert [m["id"] for m in rep["modules"]] == [ids[2], ids[0], ids[1]]
    assert sum(1 for x in pls(c, pid) if (x.get("cab") or {}).get("run")) == 3


def test_unknown_preset_is_refused(c, pid):
    w, _ = long_wall(c, pid)
    r = c.post(f"/api/projects/{pid}/runs/preview", json={"wall_id": w["wall_id"], "rows": {"base": [{"preset": "spaceship"}]}})
    assert r.status_code in (400, 422)
