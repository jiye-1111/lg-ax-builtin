"""설치 전 확인 목록 — 테스트 먼저.

놓은 제품마다 자리 판정, 앞 사용 공간, 줄자로 재야 할 벽, 들여오는 길, 현장에서만 알 수 있는 설비를 한 줄씩 정리한다.
스캔으로 알 수 없는 것(콘센트, 급수·배수, 현관·복도)은 '현장 확인'으로 남기고 지어내지 않는다.
"""
from core.models import Clearance, Dims, MeasuredDims, Opening, Product, Room, ScannedDims, Wall
from recommender.install import install_checklist


def room(measured=False, door=None):
    m = MeasuredDims(length_m=4.0, by="technician") if measured else None
    walls = [
        Wall(wall_id="w1", start=(0, 0), end=(4, 0), thickness_m=0.1, scanned=ScannedDims(length_m=4.0, height_m=2.4), measured=m),
        Wall(wall_id="w2", start=(4, 0), end=(4, 3), thickness_m=0.1, scanned=ScannedDims(length_m=3.0, height_m=2.4)),
    ]
    ops = [Opening(opening_id="d1", type="door", wall_id="w2", offset_m=1.0, width_m=door, height_m=2.0)] if door else []
    return Room(walls=walls, openings=ops)


def prod(category="refrigerator", w=900, d=700, install="freestanding", door=600):
    return Product(sku="T-1", name="테스트 제품", category=category, zone_fit=["kitchen"], install_type=install, door_swing_mm=door,
                   product_dims_mm=Dims(w=w, h=1800, d=d), clearance_mm=Clearance(side=5, top=10, back=50),
                   source_url=None, source_checked_at=None, demo_only=True)


def placement(verdict="fit", reasons=(), wall_id="w1"):
    return {"placement_id": "pl_001", "sku": "T-1", "verdict": verdict, "wall_id": wall_id, "reasons": list(reasons)}


def reason(code, ref=None, verdict="conditional"):
    return {"code": code, "label": code, "ref": ref, "verdict": verdict}


def check(item, code):
    return next(c for c in item["checks"] if c["code"] == code)


def run(pl, r=None, p=None):
    p = p or prod()
    return install_checklist(r or room(), [pl], lambda sku: p)


def test_fit_placement_is_ok_and_site_items_stay_open():
    out = run(placement())
    it = out["items"][0]
    assert it["name"] == "테스트 제품" and it["dims_mm"] == {"w": 900, "h": 1800, "d": 700}
    assert check(it, "space")["status"] == "ok" and check(it, "front")["status"] == "ok"
    assert check(it, "power")["status"] == "site"
    assert check(it, "carry")["status"] == "site" and "700" in check(it, "carry")["detail"]
    assert out["summary"] == {"products": 1, "ok": 1, "check": 0, "blocked": 0, "walls_to_measure": []}


def test_tight_scanned_wall_asks_for_tape_measure():
    out = run(placement("conditional", [reason("tight", "w1")]))
    it = out["items"][0]
    assert check(it, "space")["status"] == "check"
    assert check(it, "measure")["status"] == "check" and "w1" in check(it, "measure")["detail"]
    assert out["summary"]["walls_to_measure"] == ["w1"] and out["summary"]["check"] == 1


def test_measured_wall_does_not_ask_again():
    out = run(placement("conditional", [reason("tight", "w1")]), room(measured=True))
    assert all(c["code"] != "measure" for c in out["items"][0]["checks"])
    assert out["summary"]["walls_to_measure"] == []


def test_no_fit_is_blocked():
    out = run(placement("no_fit", [reason("hits_wall", "w1", "no_fit")]))
    assert check(out["items"][0], "space")["status"] == "blocked" and out["summary"]["blocked"] == 1


def test_front_and_entry_reasons_get_their_own_lines():
    out = run(placement("no_fit", [reason("front_blocked", "chair1", "no_fit"), reason("entry_narrow", "d1")]), room(door=0.65))
    it = out["items"][0]
    assert check(it, "front")["status"] == "blocked" and it["status"] == "blocked"
    assert check(it, "entry")["status"] == "check" and "650" in check(it, "entry")["detail"]
    # 자리 자체에는 걸리는 것이 없다
    assert check(it, "space")["status"] == "ok"


def test_scanned_door_wide_enough_is_ok():
    it = run(placement(), room(door=0.9))["items"][0]
    assert check(it, "entry")["status"] == "ok"


def test_no_scanned_door_has_no_entry_line():
    it = run(placement())["items"][0]
    assert all(c["code"] != "entry" for c in it["checks"])


def test_water_line_only_for_products_that_need_it():
    assert all(c["code"] != "water" for c in run(placement())["items"][0]["checks"])
    it = run(placement(), p=prod("dishwasher", 600, 570))["items"][0]
    assert check(it, "water")["status"] == "site"


def test_products_used_from_the_front_only_get_front_line():
    it = run(placement(), p=prod("tv", 900, 200, door=None))["items"][0]
    assert all(c["code"] != "front" for c in it["checks"])


def test_built_in_has_no_front_line():
    it = run(placement(), p=prod(install="built_in"))["items"][0]
    assert all(c["code"] != "front" for c in it["checks"])


def test_assumed_door_space_asks_to_check():
    it = run(placement("conditional", [reason("front_space_assumed")]), p=prod(door=None))["items"][0]
    assert check(it, "front")["status"] == "check" and check(it, "space")["status"] == "ok"


def test_unknown_sku_is_skipped():
    def get(sku):
        raise KeyError(sku)
    assert install_checklist(room(), [placement()], get)["items"] == []


def test_narrow_passage_gets_its_own_line():
    it = run(placement("conditional", [reason("passage_narrow", "t1")]))["items"][0]
    assert check(it, "passage")["status"] == "check" and check(it, "space")["status"] == "ok"
