from core.models import CmfOption, Clearance, Dims, MeasuredDims, Product, StyleTags
from recommender.fit import FitConfig
from recommender.recommend import recommend_zone
from test_fit import KITCHEN, make_room


def _p(sku, w, purpose="kitchen", hex_="#FFFFFF"):
    return Product(sku=sku, name=sku, category="refrigerator", zone_fit=[purpose], install_type="built_in",
                   product_dims_mm=Dims(w=w, h=1800, d=600), clearance_mm=Clearance(side=5, top=10, back=20),
                   cmf_options=[CmfOption(color="c", hex_approx=hex_)], source_url=None, source_checked_at=None,
                   demo_only=True)


def test_filters_by_zone_purpose_and_sorts_by_verdict():
    room = make_room(measured=MeasuredDims(length_m=4.0, height_m=2.4, depth_m=1.5))
    zone = KITCHEN.model_copy(update={"style_tags": StyleTags(palette=["#FFFFFF"])})
    res = recommend_zone(room, zone, [_p("big", 5000), _p("ok", 900), _p("tv", 900, purpose="living")],
                         FitConfig())
    assert [r["product"]["sku"] for r in res] == ["ok", "big"]
    assert res[0]["fit"]["verdict"] == "fit" and res[1]["fit"]["verdict"] == "no_fit"
    assert res[0]["cmf"][0]["score"] > 0.9


def test_products_not_for_sale_are_not_recommended():
    room = make_room(measured=MeasuredDims(length_m=4.0, height_m=2.4, depth_m=1.5))
    gone = _p("gone", 900).model_copy(update={"sale_status": "NOT_FOR_SALE"})
    out = _p("out", 900).model_copy(update={"sale_status": "SOLD_OUT"})
    res = recommend_zone(room, KITCHEN, [gone, out, _p("unknown", 900)], FitConfig())
    assert [r["product"]["sku"] for r in res] == ["out", "unknown"]  # 일시품절·확인 안 된 제품은 남긴다
