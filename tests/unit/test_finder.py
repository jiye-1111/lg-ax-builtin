"""조건으로 제품 찾기: 종류·용량·색상·가격·설치 공간으로 좁히고 추천순으로 줄 세운다."""
from core.models import CmfOption, Clearance, Dims, Product
from recommender.finder import Conditions, color_group, find_products, space_fit
from recommender.fit import FitConfig


def _p(sku, w=900, cap=600, color="베이지", hex_="#E8DFD0", price=3000000, cat="refrigerator", status="ACTIVE", side=4, **kw):
    return Product(sku=sku, name=sku, category=cat, zone_fit=["kitchen"], install_type="freestanding",
                   product_dims_mm=Dims(w=w, h=1800, d=700), clearance_mm=Clearance(side=side, top=10, back=20),
                   options=({"capacity_l": cap} if cap else {}), cmf_options=[CmfOption(color=color, hex_approx=hex_)],
                   source_url=None, source_checked_at=None, sale_status=status, price_krw=price, **kw)


def skus(res):
    return [it["product"]["sku"] for it in res["items"]]


def test_color_group_from_name_then_hex():
    assert color_group("오브제컬렉션 베이지 / 베이지", "#EEE") == "베이지"
    assert color_group("에센스 화이트", None) == "화이트"
    assert color_group("스페이스 블랙", None) == "블랙"
    assert color_group("모던 스테인리스", None) == "실버·그레이"
    assert color_group("네이처 그린", None) == "그린"
    assert color_group(None, "#101010") == "블랙"      # 이름이 없으면 색 값으로
    assert color_group(None, "#F7F7F5") == "화이트"
    assert color_group(None, None) is None


def test_space_fit_uses_required_width_with_side_clearance():
    cfg = FitConfig()
    ok = space_fit(_p("a", w=914), {"width": 950}, cfg)
    assert ok["verdict"] == "fit" and ok["dims"]["width"]["required_mm"] == 922 and ok["dims"]["width"]["slack_mm"] == 28
    tight = space_fit(_p("a", w=914), {"width": 924}, cfg)     # 여유 2mm < 실측 마진 5mm
    assert tight["verdict"] == "conditional"
    assert space_fit(_p("a", w=960), {"width": 950}, cfg)["verdict"] == "no_fit"
    unknown = space_fit(_p("a", w=900, side=None), {"width": 950}, cfg)
    assert unknown["verdict"] == "conditional" and "clearance_unknown" in unknown["notes"]   # 이격을 모르면 조건부까지만
    assert space_fit(_p("a"), {}, cfg) is None


def test_filters_by_category_capacity_color_price():
    ps = [_p("small", cap=350), _p("mid", cap=500), _p("big", cap=650), _p("white", cap=650, color="화이트", hex_="#FFFFFF"),
          _p("pricey", cap=650, price=5000000), _p("noprice", cap=650, price=None), _p("tv", cat="tv", cap=None)]
    assert skus(find_products(ps, Conditions(category="refrigerator", capacity_min=600))) == ["big", "white", "pricey", "noprice"]
    assert skus(find_products(ps, Conditions(category="refrigerator", capacity_max=400))) == ["small"]
    assert skus(find_products(ps, Conditions(color="화이트"))) == ["white"]
    # 가격 조건을 걸면 가격을 모르는 제품은 뺀다 (지어내지 않는다)
    assert skus(find_products(ps, Conditions(category="refrigerator", capacity_min=600, price_max=3000000))) == ["big", "white"]


def test_only_products_on_sale():
    ps = [_p("on"), _p("out", status="SOLD_OUT"), _p("gone", status="NOT_FOR_SALE"), _p("unknown", status=None),
          _p("demo", status=None, demo_only=True)]
    assert skus(find_products(ps, Conditions())) == ["on", "out", "demo"]


def test_space_width_ranks_fitting_first_and_fits_only_drops_the_rest():
    ps = [_p("wide", w=1000), _p("snug", w=930), _p("loose", w=700), _p("tight", w=940)]
    res = find_products(ps, Conditions(space_w=950))
    # 들어가는 것(딱 맞는 순) → 빠듯한 것 → 안 들어가는 것
    assert skus(res) == ["snug", "loose", "tight", "wide"]
    assert [it["fit"]["verdict"] for it in res["items"]] == ["fit", "fit", "conditional", "no_fit"]
    assert skus(find_products(ps, Conditions(space_w=950, fits_only=True))) == ["snug", "loose", "tight"]
    assert "폭 950 mm 공간에 들어가요 (여유 12 mm)" in res["items"][0]["reasons"]


def test_zone_fit_callback_wins_over_typed_width():
    ps = [_p("a"), _p("b")]
    verdicts = {"a": {"verdict": "no_fit", "dims": {}, "notes": []}, "b": {"verdict": "fit", "dims": {}, "notes": []}}
    res = find_products(ps, Conditions(), zone_fit=lambda p: verdicts[p.sku])
    assert skus(res) == ["b", "a"] and res["items"][0]["fit"]["source"] == "zone"


def test_sort_by_size_and_price():
    ps = [_p("a", w=900, price=3000000), _p("b", w=600, price=None), _p("c", w=700, price=1000000)]
    assert skus(find_products(ps, Conditions(sort="size"))) == ["b", "c", "a"]
    assert skus(find_products(ps, Conditions(sort="price"))) == ["c", "a", "b"]   # 가격을 모르면 맨 뒤


def test_facets_count_within_category_and_hide_price_when_unknown():
    ps = [_p("s", cap=350), _p("m", cap=500, color="화이트"), _p("l", cap=650), _p("x", cap=820, price=None)]
    f = find_products(ps, Conditions(category="refrigerator", capacity_min=600))["facets"]
    # 필터 값은 고른 용량과 상관없이 그 종류 전체에서 센다
    assert f["capacity"] == [{"label": "400L 이하", "max": 400, "count": 1}, {"label": "400~600L", "min": 400, "max": 600, "count": 1},
                             {"label": "600L 이상", "min": 600, "count": 2}]
    assert {"label": "베이지", "count": 3} in f["color"] and {"label": "화이트", "count": 1} in f["color"]
    assert f["price"]["min"] == 3000000 and f["price"]["known"] == 3
    none = find_products([_p("a", price=None)], Conditions())["facets"]
    assert none["price"] is None and none["capacity"][2]["count"] == 1


def test_limit_and_total():
    res = find_products([_p(f"p{i}") for i in range(10)], Conditions(limit=3))
    assert len(res["items"]) == 3 and res["total"] == 10
