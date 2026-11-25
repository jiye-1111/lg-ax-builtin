"""카탈로그 규칙 (docs/specs/catalog.md): 실데이터는 출처 필수, 가상 데이터는 표시."""
import json

import pytest

from core import config
from core.models import MeasuredDims, Product, Room, ScannedDims, Wall, Zone
from recommender.fit import FitConfig, Verdict, check_fit

REAL = json.loads((config.ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]
DEMO = json.loads((config.ROOT / "data/catalog/demo_fixture.json").read_text(encoding="utf-8"))["products"]


@pytest.mark.parametrize("p", REAL, ids=lambda p: p["sku"])
def test_real_products_have_source(p):
    prod = Product.model_validate(p)
    assert not prod.demo_only
    assert prod.source_url and prod.source_url.startswith("https://www.lge.co.kr/")
    assert prod.source_checked_at
    assert prod.sku.lower() in prod.source_url


def test_demo_products_are_marked():
    assert all(p["demo_only"] and p["name"].startswith("[가상]") for p in DEMO)


def test_skus_unique():
    skus = [p["sku"] for p in REAL + DEMO]
    assert len(skus) == len(set(skus))


def test_fit_and_max_can_be_fit_with_measured_cabinet():
    """G646: 폭 914+2×4=922, 높이 1,869, 깊이 700 (설치가이드). 실측 가구장 930×1,880×720이면 적합."""
    p = Product.model_validate(next(x for x in REAL if x["sku"] == "G646GBB031"))
    room = Room(walls=[Wall(wall_id="w1", start=(0, 0), end=(0.93, 0), scanned=ScannedDims(length_m=0.93, height_m=1.88),
                            measured=MeasuredDims(length_m=0.93, height_m=1.88, depth_m=0.72))])
    z = Zone(zone_id="z", purpose="kitchen", polygon_m=[(0, 0), (0.93, 0), (0.93, 0.72), (0, 0.72)], wall_ids=["w1"])
    r = check_fit(room, z, p, FitConfig())
    assert r.dims["width"].required_mm == 922
    assert r.dims["height"].required_mm == 1869
    assert r.verdict == Verdict.FIT
    # 가구장 폭이 925면 여유 3mm < 5mm → 조건부
    room.walls[0].measured.length_m = 0.925
    assert check_fit(room, z, p, FitConfig()).verdict == Verdict.CONDITIONAL


def test_products_on_sale_have_lgecom_price():
    """파는 제품은 LGE.COM 판매가와 확인한 날이 있다. 가격을 모르면 null이고, 0이나 지어낸 값은 없다."""
    real = [Product.model_validate(p) for p in REAL]
    on_sale = [p for p in real if p.sale_status in ("ACTIVE", "SOLD_OUT")]
    assert on_sale and all(p.price_krw and p.price_checked_at for p in on_sale)
    assert all(p.price_krw is None or p.price_krw >= 1000 for p in real)
    assert all((p.price_krw is None) == (p.price_checked_at is None) for p in real)


def test_only_categories_without_lgecom_color_have_null_color():
    """색상 이름이 비어 있어도 되는 건 LGE.COM 스펙 표에 색상 항목이 없는 종류뿐이다."""
    no_color = {p["category"] for p in REAL if not p["cmf_options"][0]["color"]}
    assert no_color <= {"tv", "portable_tv", "massage_chair", "plant_grower"}


def test_energy_grade_is_lgecom_value_or_null():
    """에너지 소비효율등급은 LGE.COM 스펙 표에 적힌 1~5등급만 넣는다. 등급이 없는 제품과 확인 못 한 제품은 null."""
    real = [Product.model_validate(p) for p in REAL]
    graded = [p for p in real if p.energy_grade is not None]
    assert graded and all(p.energy_grade in (1, 2, 3, 4, 5) and p.energy_checked_at for p in graded)
    by = {p.sku: p for p in real}
    assert by["B312S31"].energy_grade == 1 and by["B332W34"].energy_grade == 4
    # 와인셀러는 표에 '해당없음', 전자레인지는 등급 항목이 없다
    assert by["W0082GLE"].energy_grade is None and by["W0082GLE"].energy_checked_at
    assert by["MW23BDI"].energy_grade is None


def test_energy_grade_reaches_the_product_list():
    from recommender.variants import families
    fams = families(REAL, {})
    v = next(v for f in fams for v in f["variants"] if v["sku"] == "DUE6BGE")
    assert v["energy_grade"] == 1
