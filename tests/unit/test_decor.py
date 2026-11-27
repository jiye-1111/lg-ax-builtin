"""공간 꾸미기 가구 (제품 정보 없는 일반 모양): 목록·크기·판정용 Product."""
import json

import pytest
from core import config
from core.decor import DECOR, decor_items, decor_product, is_decor


def test_library_groups_and_models_exist():
    groups = {d["group"] for d in DECOR.values()}
    assert groups == {"furniture", "storage", "decor", "structure", "kitchen"}
    idx = json.loads((config.ROOT / "apps" / "web" / "models" / "furniture" / "index.json").read_text(encoding="utf-8"))
    for key, d in DECOR.items():
        if d["group"] == "kitchen":  # 맞춤장은 모델 파일 없이 부재로 만든다 (apps/web/js/cabinet3d.js)
            assert d["model"] == "cab" and d["cab"], key
            continue
        assert d["model"] in idx["models"], key
    for need in ("sofa", "table", "chair", "bed", "desk", "shelf", "storage", "rug", "lamp", "plant", "wall", "partition", "coffee", "island", "tvstand"):
        assert need in DECOR


def test_items_have_no_product_info():
    for it in decor_items():
        assert it["sku"].startswith("decor:")
        assert not {"price_krw", "source_url", "brand"} & set(it)
        assert all(v > 0 for v in it["size_mm"].values())


def test_decor_product_uses_given_size_and_has_no_door_rules():
    p = decor_product("decor:wall", [3.0, 2.4, 0.1])
    assert p.product_dims_mm.w == 3000 and p.product_dims_mm.d == 100
    assert p.clearance_mm.side == 0 and p.clearance_mm.back == 0 and p.clearance_mm.top == 0
    assert p.source_url is None and p.price_krw is None
    assert is_decor("decor:sofa") and not is_decor("G646GBB031")


def test_size_is_clamped_to_sane_range():
    p = decor_product("decor:wall", [50.0, 0.0, 0.1])
    assert p.product_dims_mm.w <= 8000 and p.product_dims_mm.h >= 10


def test_unknown_decor_raises():
    with pytest.raises(KeyError):
        decor_product("decor:spaceship")


def test_cabinet_kinds_for_builtin_planning():
    for need in ("wardrobe", "tallcab", "basecab", "dresser", "storage"):
        assert need in DECOR and DECOR[need]["group"] == "storage"


def test_presets_are_real_products_with_source():
    """크기 프리셋은 실제 판매 제품의 공개 치수만. 출처 주소가 있어야 한다."""
    by = {i["sku"]: i for i in decor_items()}
    for sku in ("decor:wardrobe", "decor:tallcab", "decor:basecab", "decor:dresser"):
        ps = by[sku]["presets"]
        assert ps, sku
        for p in ps:
            assert p["source_url"].startswith("https://www.ikea.com/") and p["label"]
            assert set(p["size_mm"]) == {"w", "h", "d"} and all(v > 0 for v in p["size_mm"].values())
    assert by["decor:sofa"]["presets"] == []


def test_sink_and_door_are_in_the_library():
    assert DECOR["sink"]["group"] == "storage" and DECOR["sink"]["label"] == "싱크대"
    assert DECOR["door"]["group"] == "structure" and DECOR["door"]["label"] == "문"


def test_island_table_and_hood_are_in_the_library_with_real_size_chips():
    items = {it["sku"]: it for it in decor_items()}
    isl = items["decor:islandtable"]
    assert isl["label"] == "아일랜드 식탁" and isl["group"] == "furniture"
    assert isl["size_mm"] == {"w": 1200, "h": 890, "d": 750}          # 한샘 모디 아일랜드식탁 120cm
    assert {p["label"] for p in isl["presets"]} >= {"한샘 모디 120", "IKEA TORNVIKEN", "IKEA VADHOLMA"}
    assert all(p["source_url"].startswith("https://") for p in isl["presets"])
    hood = items["decor:hood"]
    assert hood["label"] == "후드" and hood["hang"] is True and hood["size_mm"]["w"] == 600
    assert items["decor:islandhood"]["listed"] is False             # 인덕션을 아일랜드에 놓을 때만 달린다
    assert isl["listed"] is True
