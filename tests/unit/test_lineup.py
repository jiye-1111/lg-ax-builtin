"""LG 가전 전체 라인업: LGE.COM 가전 카테고리마다 실제 제품이 하나 이상 있고, 화면에서 사진으로 고를 수 있어야 한다."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAT = json.loads((ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]
WEB = ROOT / "apps/web"

# LGE.COM 제품 메뉴의 생활가전 카테고리 (2026-11-20 확인, docs/catalog-sources.md)
LINEUP = {
    "refrigerator", "freezer", "kimchi_refrigerator", "wine_cellar", "dishwasher", "cooktop", "oven", "microwave",
    "water_purifier", "washer", "dryer", "wash_tower", "washer_dryer", "styler", "shoe_care", "tv", "portable_tv",
    "air_conditioner", "air_purifier", "humidifier", "dehumidifier", "vacuum", "massage_chair", "plant_grower",
}


def test_every_lineup_category_has_a_real_product():
    have = {p["category"] for p in CAT if not p["demo_only"]}
    assert LINEUP <= have, sorted(LINEUP - have)


def test_every_category_has_a_korean_label():
    core = (WEB / "js/core.js").read_text(encoding="utf-8")
    block = re.search(r"export const CATEGORY = {(.*?)};", core, re.S).group(1)
    labels = set(re.findall(r"(\w+):", block))
    assert {p["category"] for p in CAT} <= labels


def test_every_product_has_a_photo_rendered_from_its_model():
    """제품 사진은 우리 3D 모델을 Blender로 렌더한 것 (LG 사진을 가져다 쓰지 않는다)."""
    missing = [p["sku"] for p in CAT if not (WEB / "img/products" / f"{p['sku']}.webp").exists()]
    assert not missing, missing


def test_product_drawer_picks_by_photo():
    js = (WEB / "js/remodel.js").read_text(encoding="utf-8")
    assert 'class="dot tile thumb"' in js and "v.thumb" in js   # 사진은 카드 위 타일 자리
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    assert "img/products/" in sw


def test_whole_lgecom_lineup_is_in_the_catalog():
    """LGE.COM 생활가전 단품 전체 (세트·패키지·부속품 제외, docs/catalog-sources.md)."""
    real = [p for p in CAT if not p["demo_only"]]
    assert len(real) >= 1150
    assert all(p["source_url"].startswith("https://www.lge.co.kr/") and p["source_checked_at"] for p in real)


def test_card_shows_one_dot_per_color():
    """같은 색 SKU가 여럿인 모델은 카드에 색 동그라미 하나, 상세 창에서 모델명으로 구분한다."""
    js = (WEB / "js/remodel.js").read_text(encoding="utf-8")
    assert "colorDots(f)" in js and "optLabel(f, x)" in js
