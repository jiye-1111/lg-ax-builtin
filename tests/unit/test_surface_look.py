"""제품 겉면 규칙. 웹(apps/web/js/surface.js, tests/web/surface.test.mjs)과 같은 답이 나와야 한다."""
import json
import re

from core import config
from core.models import Product
from core.surface import LOOKS, surface_for, surface_kind

REAL = {p["sku"]: Product.model_validate(p) for p in json.loads((config.ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]}


def test_kind_from_material_and_colour():
    assert surface_kind("스테인리스", "오브제컬렉션 실버") == "stainless"
    assert surface_kind("스톤 (스테인리스)", "오브제컬렉션 실버") == "stone"
    assert surface_kind("글라스 (크리스탈)", "오브제컬렉션 핑크") == "glass"
    assert surface_kind("미스트 (글라스)", "오브제컬렉션 베이지") == "mist"
    assert surface_kind("네이처 (메탈)", "퓨어") == "brushed"
    assert surface_kind("메탈", "화이트") == "coated"
    assert surface_kind(None, "화이트") is None
    assert surface_kind("인조가죽", "블랙") is None


def test_catalog_products_get_a_look_only_when_material_is_known():
    assert surface_for(REAL["B332S34"])["kind"] == "brushed" and surface_for(REAL["B332S34"])["case"] is True
    assert surface_for(REAL["B332W34"])["kind"] == "coated"
    glass = surface_for(REAL["W0082GLE"])
    assert glass["kind"] == "glass" and glass["case"] is False and glass["coat"] == 1.0
    assert surface_for(REAL["DUE6BGE"]) is None  # 식기세척기는 스펙 표에 재질이 없다


def test_same_numbers_as_the_web_rules():
    js = (config.ROOT / "apps/web/js/surface.js").read_text(encoding="utf-8")
    for kind, look in LOOKS.items():
        m = re.search(rf"{kind}: \{{ metalness: ([\d.]+), roughness: ([\d.]+), clearcoat: ([\d.]+), clearcoatRoughness: ([\d.]+)", js)
        assert m, kind
        assert [float(x) for x in m.groups()] == [look["metallic"], look["roughness"], look["coat"], look["coat_roughness"]], kind


def test_scene_state_carries_surface_to_the_renderer(tmp_path):
    from core.service import Service
    put = Service.surface_placements
    out = put(None, [{"sku": "B332S34", "placement_id": "a"}, {"sku": "DUE6BGE", "placement_id": "b"}, {"sku": "decor:sofa", "placement_id": "c"}], REAL.get)
    assert out[0]["surface"]["kind"] == "brushed" and "surface" not in out[1] and "surface" not in out[2]
