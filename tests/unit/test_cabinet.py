"""맞춤장(빌트인 주방) 부재와 내부 빈 공간 — 테스트 먼저. 규칙은 docs/specs/builtin-kitchen.md."""
import pytest

from recommender.cabinet import KINDS, interior, normalize, suggest
from recommender.cabinet_fit import load_rules

RULES = load_rules()


def fridge_cab(**parts):
    return normalize({"kind": "fridge", "mode": "new", "outer_mm": {"w": 958, "h": 2300, "d": 720}, "parts": parts})


def test_fridge_housing_interior_is_outer_minus_its_parts():
    c = fridge_cab()  # 측판 18 + 18, 위 수납장 400, 뒷판 없음
    assert interior(c) == {"w": 922, "h": 1900, "d": 720, "source": "designed"}


def test_thicker_side_panel_shrinks_the_inside_but_not_the_outside():
    c = fridge_cab(side_l=25)
    assert c["outer_mm"]["w"] == 958
    assert interior(c)["w"] == 915


def test_fillers_end_panels_and_back_take_room_from_the_inside():
    c = fridge_cab(filler_l=20, end_r=16, back=9, upper_h=350)
    i = interior(c)
    assert (i["w"], i["h"], i["d"]) == (958 - 18 - 18 - 20 - 16, 2300 - 350, 711)


def test_dishwasher_bay_is_the_space_under_the_counter_between_fixed_faces():
    c = normalize({"kind": "dishwasher", "mode": "new", "outer_mm": {"w": 636, "h": 850, "d": 600}})
    assert interior(c) == {"w": 600, "h": 820, "d": 600, "source": "designed"}  # 상판 30, 측판 18 + 18


def test_existing_cabinet_uses_measured_inside_as_typed():
    c = normalize({"kind": "fridge", "mode": "existing", "outer_mm": {"w": 958, "h": 2300, "d": 720},
                   "measured_mm": {"w": 925, "h": 1880, "d": None}, "parts": {"side_l": 40}})
    assert interior(c) == {"w": 925, "h": 1880, "d": None, "source": "measured"}


def test_suggest_new_housing_from_official_rule_only():
    c = suggest("fridge", RULES.get("G646GBB031"))
    assert interior(c) == {"w": 922, "h": 1869, "d": 720, "source": "designed"}
    assert c["outer_mm"] == {"w": 958, "h": 2269, "d": 720}
    dw = suggest("dishwasher", RULES.get("DUE6BGE"))
    assert interior(dw)["w"] == 600 and interior(dw)["h"] == 820 and interior(dw)["d"] == 600
    assert suggest("fridge", RULES.get("D646GBB021")) is None  # 공식 기준이 없는 모델은 권장 치수를 내지 않는다


def test_parts_are_checked():
    with pytest.raises(ValueError):
        fridge_cab(side_l=-1)
    with pytest.raises(ValueError):
        fridge_cab(side_l=80)
    with pytest.raises(ValueError):
        normalize({"kind": "fridge", "mode": "new", "outer_mm": {"w": 900, "h": 2300, "d": 720}, "parts": {"side_l": 500}})
    with pytest.raises(ValueError):
        normalize({"kind": "fridge", "mode": "new", "outer_mm": {"w": 958, "h": 2300, "d": 720}, "parts": {"nope": 1}})
    with pytest.raises(ValueError):
        normalize({"kind": "fridge", "mode": "guess", "outer_mm": {"w": 958, "h": 2300, "d": 720}})


def test_next_stage_modules_are_registered_but_not_open_yet():
    assert KINDS["oven_tall"]["stage"] == 2 and KINDS["corner"]["stage"] == 2
    with pytest.raises(ValueError):
        normalize({"kind": "oven_tall", "mode": "new", "outer_mm": {"w": 600, "h": 2100, "d": 600}})
    first = {k for k, v in KINDS.items() if v["stage"] == 1}
    assert {"fridge", "dishwasher", "sink", "drawer", "wall", "pantry", "glass_wall", "counter", "filler", "end_panel"} <= first


def test_glass_wall_cabinet_has_glass_doors_and_opaque_body():
    c = normalize({"kind": "glass_wall", "mode": "new", "outer_mm": {"w": 800, "h": 700, "d": 370}})
    assert c["glass"] == "clear" and c["parts"]["shelves"] >= 1
    tinted = normalize({**c, "glass": "bronze"})
    assert tinted["glass"] == "bronze"
    with pytest.raises(ValueError):
        normalize({**c, "glass": "mirror"})


def test_finishes_are_per_part_and_only_from_the_palette():
    c = normalize({"kind": "drawer", "mode": "new", "outer_mm": {"w": 600, "h": 850, "d": 600},
                   "finish": {"front": "sage_matte", "top": "stone_white"}})
    assert c["finish"]["front"] == "sage_matte" and c["finish"]["top"] == "stone_white"
    assert c["finish"]["body"]  # 몸통은 기본 마감
    with pytest.raises(ValueError):
        normalize({**c, "finish": {"front": "stone_white"}})  # 상판 돌을 문짝에 쓰지 않는다
    with pytest.raises(ValueError):
        normalize({**c, "finish": {"front": "#ff0000"}})
