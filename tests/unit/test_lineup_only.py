"""내놓는 모델 목록(data/catalog/lineup.json): 전달받은 묶음에 3D 모델이 있는 제품만 목록·추천에 나온다."""
import json

from core import config
from core.service import Catalog
from recommender.finder import Conditions, find_products

LINEUP = config.ROOT / "data" / "catalog" / "lineup.json"
MODELS = json.loads(LINEUP.read_text(encoding="utf-8"))["models"]


def catalog(lineup=LINEUP) -> Catalog:
    return Catalog([config.ROOT / "data" / "catalog" / "products.json"], lineup)


def test_lineup_is_the_56_handed_over_models_and_all_are_in_the_catalog():
    cat = catalog()
    assert len(MODELS) == 56
    assert set(MODELS) <= {p.sku for p in cat.products}
    assert {p.sku for p in cat.products if p.listed} == set(MODELS)


def test_every_lineup_row_has_lgecom_source_and_checked_sale_status():
    for p in catalog().products:
        if not p.listed:
            continue
        assert p.source_url.startswith("https://www.lge.co.kr/"), p.sku
        assert p.source_checked_at and p.sale_checked_at in ("2026-11-25", None), p.sku
        d = p.product_dims_mm
        assert None not in (d.w, d.h, d.d), p.sku
        if p.sale_status in ("ACTIVE", "SOLD_OUT"):
            assert p.price_krw, p.sku


def test_only_lineup_models_on_sale_can_be_found():
    cat = catalog()
    on_sale = {p.sku for p in cat.products if p.on_sale}
    assert on_sale and on_sale <= set(MODELS)
    assert "G646GBB031" not in on_sale  # 직접 만든 모델만 있던 제품은 목록에서 빠진다
    assert "DUE6GL" not in on_sale and "BEI3GQK" not in on_sale  # 묶음에 있어도 단종·출시 전이면 안 나온다
    found = find_products(cat.products, Conditions(limit=None), None, None)
    assert {it["product"]["sku"] for it in found["items"]} <= on_sale


def test_products_outside_lineup_stay_readable_for_homes_saved_earlier():
    p = catalog().get("G646GBB031")
    assert p.listed is False and p.on_sale is False


def test_without_lineup_file_everything_is_listed():
    assert all(p.listed for p in catalog(None).products)


def test_families_follow_the_handed_over_grouping():
    fams = [f for f in catalog().families() if any(v["listed"] for v in f["variants"])]
    by_first = {}
    for f in fams:
        groups = {MODELS[v["sku"]]["family_id"] for v in f["variants"]}
        assert len(groups) == 1, f["family_id"]  # 치수가 같아도 다른 제품군은 섞이지 않는다
        by_first[groups.pop()] = f
    assert len(by_first) == 28
    due5 = {v["sku"]: v for v in by_first["DUE5-batch10"]["variants"]}
    assert due5["DUE5BGE"]["note"] == "상단 글라이드 레일 없음" and due5["DUE5BGHE"]["note"] == "상단 글라이드 레일 있음"
