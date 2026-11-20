"""같은 모델(모양·크기 같음)의 색·재질 다른 제품을 하나로 묶기."""
import json
from pathlib import Path

from recommender.variants import families, family_name, shape_key

ROOT = Path(__file__).resolve().parents[2]
CAT = json.loads((ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]


def shapes() -> dict:
    out = {}
    for p in CAT:
        f = ROOT / "data/drawings" / f"{p['sku']}.json"
        out[p["sku"]] = shape_key(json.loads(f.read_text(encoding="utf-8"))) if f.exists() else None
    return out


def by_sku(fams):
    return {v["sku"]: f for f in fams for v in f["variants"]}


def test_lineup_products_group_into_models():
    fams = families(CAT, shapes())
    assert len(fams) == 267
    assert sum(len(f["variants"]) for f in fams) == 1150


def test_same_body_different_finish_is_one_model():
    m = by_sku(families(CAT, shapes()))
    assert m["G646GBB031"] is m["G646MEE021"] is m["G646SVV031"]
    assert m["Z386GBB281"] is m["Z386MEE221"] is m["Z386SLL281"]
    assert m["DUE6BGE"] is m["DUE6EWL2E"]
    assert m["BEF3AMB4E"] is m["BEF3ASMLE"]
    assert m["WU523AWB"] is m["WU523ACB"]
    assert m["W1213GG"] is m["W1212GB"]
    assert m["WL21WDU"] is m["WL21EGZU"]
    assert m["FX24KNTR"] is m["FX24ENER"]
    assert m["RD20KNTR"] is m["RD21ESER"]
    assert m["SC5GMR80S"] is m["SC5MBR80S"] is m["SC5MSR82A"]
    assert m["SS4RHS60E"] is m["SS4RWS60E"]
    # LGE.COM 전체를 넣은 뒤에도 같은 몸통의 새 SKU는 원래 모델에 붙는다
    assert m["G646GBB021"] is m["G646GBB031"]
    assert m["D646GBB021"] is m["D646GBB041"]
    assert m["Z386GBB221"] is m["Z386GBB281"]
    assert m["FQ18GV3BK2"] is m["FQ18GV3EK2"]       # 뷰I 3시리즈 베이지·화이트


def test_different_size_or_shape_stays_separate():
    m = by_sku(families(CAT, shapes()))
    assert m["M616GBB0M1"] is not m["G646GBB031"]   # 깊이 698 vs 709
    assert m["X323MEF"] is not m["Y323MEF"]           # 같은 크기라도 냉장·냉동은 다른 제품
    assert m["FQ18GV3EK2"] is not m["FQ17GU1ED2"]     # 뷰I · 뷰II는 앞모양이 다르다
    assert m["D646GBB041"] is not m["G646GBB031"]   # 컨버터블: 같은 크기, 다른 문 나눔
    assert m["BEI3QKBLOE"] is not m["BEF3AMB4E"]    # 화구 배치 다름


def test_variants_carry_color_material_and_keep_catalog_order():
    f = by_sku(families(CAT, shapes()))["G646GBB031"]
    assert [v["sku"] for v in f["variants"]][:3] == ["G646GBB031", "G646MEE021", "G646SVV031"]
    assert [v["material"] for v in f["variants"]][:3] == ["글라스", "메탈", "스톤 (스테인리스)"]
    assert all(v["hex"] and v["color"] for v in f["variants"])
    assert f["family_id"] == "G646GBB031" and f["category"] == "refrigerator"


def test_family_name_drops_finish_words():
    assert family_name(["LG 디오스 AI 오브제컬렉션 냉장고 Fit & Max (650L)",
                        "LG 디오스 AI 오브제컬렉션 냉장고 Fit & Max (650L, 메탈)",
                        "LG 디오스 AI 오브제컬렉션 냉장고 Fit & Max (650L, 실버)"]) == "LG 디오스 AI 오브제컬렉션 냉장고 Fit & Max (650L)"
    assert family_name(["LG 디오스 인덕션 3구 (와이드존)", "LG 디오스 인덕션 3구 (와이드존, 무광블랙)"]) == "LG 디오스 인덕션 3구 (와이드존)"
    assert family_name(["X (빌트인, 냉온정)", "X (빌트인, 냉온정, 베이지)"]) == "X (빌트인, 냉온정)"
    assert family_name(["하나뿐인 제품"]) == "하나뿐인 제품"


def test_no_drawing_falls_back_to_size():
    a = {**CAT[0], "sku": "A1"}
    b = {**CAT[0], "sku": "B1", "cmf_options": [{"color": "블랙", "hex_approx": "#000000"}]}
    assert len(families([a, b], {})) == 1


def test_variants_carry_install_type_and_lgecom_options():
    m = by_sku(families(CAT, shapes()))
    v = next(x for x in m["S834MEE111"]["variants"] if x["sku"] == "S834MEE111")
    assert v["install_type"] == "freestanding"
    assert v["options"] == {"kind": "양문형", "doors": "2도어", "door_material": "메탈", "capacity_l": 832}
    v = next(x for x in m["FX24KNTR"]["variants"] if x["sku"] == "FX24KNTR")
    assert v["options"]["kind"] == "드럼세탁기" and v["options"]["wash_kg"] == 24


def test_washer_door_space_comes_from_lgecom_open_size():
    p = next(x for x in CAT if x["sku"] == "FX24KNTR")  # 도어 열림 시 700 x 990 x 1,410, 제품 깊이 830
    assert p["door_swing_mm"] == 1410 - p["product_dims_mm"]["d"]
