"""카탈로그 규칙 (docs/specs/catalog.md): 실데이터는 출처 필수, 가상 데이터는 표시."""
import json

import pytest

from core import config
from core.models import BBox, MeasuredDims, Product, Room, ScannedDims, Wall, Zone
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
