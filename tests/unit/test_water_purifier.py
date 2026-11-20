"""정수기 설치 규격 (LGE.COM 정수기 설치가이드). 규칙은 docs/specs/fit-rules.md "정수기"."""
import json

from core import config
from core.models import Clearance, Dims, Product, Room, ScannedDims, Wall
from recommender.finder import Conditions, find_products
from recommender.fit import required_space
from recommender.install import install_checklist

REAL = [Product.model_validate(p) for p in
        json.loads((config.ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]]
WP = {p.sku: p for p in REAL if p.category == "water_purifier"}


def _p(**kw):
    base = dict(sku="X", name="X", category="water_purifier", zone_fit=["kitchen"], install_type="freestanding",
                product_dims_mm=Dims(w=168, h=398, d=400), source_url=None, source_checked_at=None)
    return Product(**{**base, **kw})


def test_side_total_is_added_once_not_per_side():
    req, unknown = required_space(_p(clearance_mm=Clearance(side_total=100, top=150, back=10)))
    assert req == {"width": 268, "height": 548, "depth": 410}
    assert unknown is False


def test_side_per_side_still_doubles():
    req, _ = required_space(_p(clearance_mm=Clearance(side=4, top=10, back=20)))
    assert req["width"] == 176


def test_every_water_purifier_has_guide_source_and_type():
    assert len(WP) == 29
    for p in WP.values():
        assert p.install_form in ("데스크", "스탠드", "빌트인"), p.sku
        assert any("lg-water-purifiers-install-guide" in n for n in p.spec_notes), p.sku


def test_desk_type_needs_100_side_150_top_10_back():
    p = WP["WD523AWB"]
    assert p.install_form == "데스크"
    assert (p.clearance_mm.side_total, p.clearance_mm.top, p.clearance_mm.back) == (100, 150, 10)
    assert required_space(p)[0] == {"width": 268, "height": 548, "depth": 410}


def test_stand_type_needs_100_behind():
    p = WP["WS513SH"]
    assert p.install_form == "스탠드"
    assert p.clearance_mm.back == 100 and p.clearance_mm.side is None and p.clearance_mm.side_total is None
    assert p.install_mm["cabinet_top_min"] == 350


def test_under_sink_models_are_built_in_with_faucet_spec():
    for sku in ("WU523AWB", "WU523ACB", "WU923AS", "WU923ACB", "WU823AS"):
        p = WP[sku]
        assert p.install_type == "built_in" and p.install_form == "빌트인", sku
        assert (p.clearance_mm.side_total, p.clearance_mm.back) == (100, 10)
        m = p.install_mm
        assert m["faucet_hole_dia"] == 28 and m["faucet_ring_dia"] == 52
        assert (m["faucet_under_w"], m["faucet_under_d"]) == (102, 70)
        assert m["faucet_to_body_max"] == 730 and m["water_source_max"] == 5000


def test_drain_needed_for_ice_lighton_voice_moving_types():
    assert WP["WD723RH"].needs_drain is True      # 냉동얼음
    assert WP["WD520MH"].needs_drain is True      # 라이트온
    assert WP["WD524VCT"].needs_drain is True     # 음성인식
    assert WP["WD525ACB"].needs_drain is True     # 상하좌우
    assert WP["WD520AWB"].needs_drain is None     # 가이드에 따로 없음


def test_typed_space_uses_install_clearance():
    """폭 250 자리: 제품 폭 168은 들어가지만 옆 여유 100을 더하면 268이라 안 들어간다."""
    res = find_products(REAL, Conditions(category="water_purifier", space_w=250, fits_only=True))
    assert "WD523AWB" not in [it["product"]["sku"] for it in res["items"]]
    res = find_products(REAL, Conditions(category="water_purifier", space_w=300, fits_only=True))
    assert "WD523AWB" in [it["product"]["sku"] for it in res["items"]]


def test_install_checklist_lists_water_purifier_site_checks():
    room = Room(walls=[Wall(wall_id="w1", start=(0, 0), end=(4, 0), thickness_m=0.1, scanned=ScannedDims(length_m=4.0, height_m=2.4))])
    out = install_checklist(room, [{"sku": "WU523AWB", "verdict": "fit", "reasons": []}], WP.__getitem__)
    codes = {c["code"]: c for c in out["items"][0]["checks"]}
    assert "28" in codes["faucet"]["detail"] and "52" in codes["faucet"]["detail"]
    assert "730" in codes["body"]["detail"] and "100" in codes["body"]["detail"]
    assert codes["faucet"]["status"] == "site"
