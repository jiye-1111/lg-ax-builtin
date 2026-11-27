"""맞춤장 안 가전의 LG 공식 설치 기준 판정 — 테스트 먼저. 규칙은 docs/specs/builtin-kitchen.md."""
import json
from pathlib import Path

from core.models import Product
from recommender.cabinet import normalize, suggest
from recommender.cabinet_fit import judge, load_rules

ROOT = Path(__file__).resolve().parents[2]
RULES = load_rules()
CATALOG = {p["sku"]: p for p in json.loads((ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]}


def prod(sku):
    return Product.model_validate(CATALOG[sku])


def axis(r, a):
    return next(x for x in r["axes"] if x["axis"] == a)


def check(r, code):
    return next(x for x in r["checks"] if x["code"] == code)


# ---------- 냉장고 Fit & Max ----------
def test_suggested_housing_fits_and_says_values_are_design_not_measured():
    r = judge(prod("G646GBB031"), suggest("fridge", RULES.get("G646GBB031")), RULES.get("G646GBB031"))
    assert r["verdict"] == "fit"
    w = axis(r, "w")
    assert (w["need_mm"], w["have_mm"], w["short_mm"], w["source"]) == (922, 922, 0, "designed")
    assert "검사한 범위" in r["scope"] and "설계값" in r["scope"]
    assert r["source_url"].startswith("https://www.lge.co.kr/")


def test_same_outside_thicker_side_panel_makes_width_short_by_mm():
    rule = RULES.get("G646GBB031")
    c = suggest("fridge", rule)
    c["parts"]["side_l"] = 25  # 외경 958 그대로, 내부 폭 915
    r = judge(prod("G646GBB031"), normalize(c), rule)
    assert r["verdict"] == "no_fit"
    assert axis(r, "w")["short_mm"] == 7 and axis(r, "w")["verdict"] == "no_fit"
    assert "7 mm" in r["summary"]


def test_existing_cabinet_keeps_its_size_when_appliance_changes():
    c = normalize({"kind": "fridge", "mode": "existing", "outer_mm": {"w": 760, "h": 2300, "d": 720},
                   "measured_mm": {"w": 705, "h": 1900, "d": 720}})
    kimchi = judge(prod("Z386GBB281"), c, RULES.get("Z386GBB281"))
    big = judge(prod("G646GBB031"), c, RULES.get("G646GBB031"))
    assert kimchi["verdict"] == "fit"
    assert big["verdict"] == "no_fit" and axis(big, "w")["short_mm"] == 922 - 705
    assert axis(big, "w")["source"] == "measured" and c["outer_mm"]["w"] == 760


def test_missing_measurement_is_never_fit():
    c = normalize({"kind": "fridge", "mode": "existing", "outer_mm": {"w": 958, "h": 2300, "d": 720},
                   "measured_mm": {"w": 930, "h": 1900, "d": None}})
    r = judge(prod("G646GBB031"), c, RULES.get("G646GBB031"))
    assert r["verdict"] == "unknown"
    assert axis(r, "d")["verdict"] == "unknown" and axis(r, "d")["have_mm"] is None


def test_model_without_official_rule_shows_outline_only_and_unknown():
    c = normalize({"kind": "fridge", "mode": "new", "outer_mm": {"w": 958, "h": 2300, "d": 720}})
    r = judge(prod("D646GBB021"), c, RULES.get("D646GBB021"))
    assert r["verdict"] == "unknown" and r["rule_id"] is None
    assert r["outline"]["w"]["fits"] is True  # 외형만 견주면 들어간다
    assert "판정 불가" in r["summary"]


def test_front_offset_in_mm_protrudes_flush_or_recessed():
    rule = RULES.get("G646GBB031")
    c = suggest("fridge", rule)
    assert judge(prod("G646GBB031"), c, rule)["front"] == {"offset_mm": -11, "state": "recessed"}  # 709 vs 720
    c["outer_mm"]["d"] = 709
    assert judge(prod("G646GBB031"), normalize(c), rule)["front"]["state"] == "flush"
    c["outer_mm"]["d"] = 700
    f = judge(prod("G646GBB031"), normalize(c), rule)["front"]
    assert f == {"offset_mm": 9, "state": "protrudes"}


def test_fridge_side_back_and_kit_items_are_listed_as_not_confirmed():
    r = judge(prod("G646GBB031"), suggest("fridge", RULES.get("G646GBB031")), RULES.get("G646GBB031"))
    assert check(r, "back_gap")["status"] == "none"
    assert check(r, "front_swing")["status"] == "none"
    assert check(r, "side_gap")["status"] == "ok"


# ---------- 식기세척기 빌트인 전용 (DU) ----------
def dw_cab(inner_w=600, h=850, d=600, **parts):
    return normalize({"kind": "dishwasher", "mode": "existing", "outer_mm": {"w": inner_w + 36, "h": h, "d": d},
                      "measured_mm": {"w": inner_w, "h": h - 30, "d": d}, "parts": parts})


def test_dishwasher_width_bands_follow_the_guide():
    rule = RULES.get("DUE6BGE")
    assert judge(prod("DUE6BGE"), dw_cab(602), rule)["verdict"] == "fit"
    narrow = judge(prod("DUE6BGE"), dw_cab(599), rule)
    assert axis(narrow, "w")["verdict"] == "conditional" and narrow["verdict"] == "conditional"
    tiny = judge(prod("DUE6BGE"), dw_cab(596), rule)
    assert tiny["verdict"] == "no_fit" and axis(tiny, "w")["short_mm"] == 2
    wide = judge(prod("DUE6BGE"), dw_cab(610), rule)
    assert wide["verdict"] == "no_fit" and axis(wide, "w")["over_mm"] == 5


def test_dishwasher_depth_and_height_bands():
    rule = RULES.get("DUE6BGE")
    shallow = judge(prod("DUE6BGE"), dw_cab(600, d=550), rule)
    assert axis(shallow, "d")["verdict"] == "conditional" and "동의" in axis(shallow, "d")["note"]
    assert judge(prod("DUE6BGE"), dw_cab(600, d=520), rule)["verdict"] == "no_fit"
    tall = judge(prod("DUE6BGE"), dw_cab(600, h=900), rule)  # 내부 870: 다리 조정
    assert axis(tall, "h")["verdict"] == "conditional"


def test_dishwasher_needs_fixed_faces_on_both_sides():
    rule = RULES.get("DUE6BGE")
    open_side = judge(prod("DUE6BGE"), dw_cab(600, side_r=0), rule)
    assert check(open_side, "side_fix")["status"] == "blocked" and open_side["verdict"] == "no_fit"
    beside = judge(prod("DUE6BGE"), dw_cab(600, side_r=0), rule, neighbours={"right": True})
    assert check(beside, "side_fix")["status"] == "ok"


def test_low_toe_kick_needs_the_other_model_line():
    r = judge(prod("DUE6BGE"), dw_cab(600, toe_kick=100), RULES.get("DUE6BGE"))
    assert check(r, "toe_kick")["status"] == "check" and r["verdict"] == "conditional"


def test_water_and_power_stay_site_checks_even_next_to_a_sink():
    r = judge(prod("DUE6BGE"), dw_cab(600), RULES.get("DUE6BGE"), neighbours={"sink": True})
    assert check(r, "water")["status"] == "site" and check(r, "power")["status"] == "site"
    assert "현장" in check(r, "water")["detail"]


def test_rules_point_only_at_the_models_the_guide_names():
    assert RULES.get("DEE6BGE") is None  # 낮은 걸레받이용(DE)은 이 표가 아니다
    assert RULES.get("DFE6BGE") is None
    assert RULES.get("G646GBB021") is None  # 같은 G646이라도 카탈로그에 공식 값이 없는 모델에는 복사하지 않는다


def test_fridge_rules_match_catalog_values_from_lgecom():
    for rule in RULES.all():
        if rule["install"] != "built_in_look":
            continue
        for sku in rule["applies_to"]:
            p = CATALOG[sku]
            side = p["clearance_mm"]["side"]
            assert rule["axes"]["w"]["recommend"] == p["product_dims_mm"]["w"] + 2 * side
            assert rule["axes"]["h"]["recommend"] == p["required_space_mm"]["h"]
            assert rule["axes"]["d"]["bands"][-1]["lo"] == p["required_space_mm"]["d"]
