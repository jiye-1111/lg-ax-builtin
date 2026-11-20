"""공간 꾸미기 가구 (제품 정보 없는 일반 모양): 목록·크기·판정용 Product."""
import json

import pytest
from core import config
from core.decor import DECOR, decor_items, decor_product, is_decor


def test_library_groups_and_models_exist():
    groups = {d["group"] for d in DECOR.values()}
    assert groups == {"furniture", "storage", "decor", "structure"}
    idx = json.loads((config.ROOT / "apps" / "web" / "models" / "furniture" / "index.json").read_text(encoding="utf-8"))
    for key, d in DECOR.items():
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
