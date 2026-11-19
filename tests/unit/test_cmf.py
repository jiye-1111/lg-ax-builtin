"""CMF 매칭 (기획 §9.2)."""
import pytest

from core.models import CmfOption, Product, StyleTags
from recommender.cmf import delta_e2000, hex_to_lab, material_keywords, rank_cmf


def test_hex_to_lab_white_and_black():
    L, a, b = hex_to_lab("#FFFFFF")
    assert L == pytest.approx(100, abs=0.1) and abs(a) < 0.1 and abs(b) < 0.1
    assert hex_to_lab("#000000")[0] == pytest.approx(0, abs=0.1)


def test_delta_e2000_reference_pair():
    # Sharma et al. (2005) 표의 1번 쌍: ΔE00 = 2.0425
    assert delta_e2000((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485)) == pytest.approx(2.0425, abs=1e-3)


def test_delta_e_identity_is_zero():
    lab = hex_to_lab("#C8A27A")
    assert delta_e2000(lab, lab) == pytest.approx(0)


def test_material_keywords_normalize_korean_and_english():
    kw = material_keywords("내추럴 우드", "Matte")
    assert {"wood", "matte"} <= kw


def _p(opts):
    return Product(sku="X", name="x", category="refrigerator", zone_fit=["kitchen"], install_type="built_in",
                   cmf_options=opts, source_url=None, source_checked_at=None, demo_only=True)


def test_rank_prefers_close_color_and_matching_material():
    style = StyleTags(palette=["#F2EFEA", "#C8A27A"], materials=["wood", "matte"])
    p = _p([
        CmfOption(color="블랙", material="스테인리스", finish="glossy", hex_approx="#1A1A1A"),
        CmfOption(color="크림 화이트", material="글라스", finish="matte", hex_approx="#F1EEE8"),
        CmfOption(color="베이지", material="우드 패널", finish="matte", hex_approx="#CBA57D"),
    ])
    ranked = rank_cmf(p, style, top_k=3)
    assert [r.option.color for r in ranked][:2] == ["베이지", "크림 화이트"]
    assert ranked[0].reasons  # 점수 근거 문자열
    assert ranked[-1].option.color == "블랙"


def test_null_hex_uses_material_only_and_is_flagged():
    style = StyleTags(palette=["#FFFFFF"], materials=["matte"])
    p = _p([CmfOption(color="미확인", material=None, finish="matte", hex_approx=None)])
    r = rank_cmf(p, style)[0]
    assert r.color_score is None
    assert r.material_score == pytest.approx(1.0)
    assert "color_unknown" in r.flags


def test_empty_style_returns_options_with_zero_scores():
    p = _p([CmfOption(color="화이트", hex_approx="#FFFFFF")])
    r = rank_cmf(p, StyleTags())
    assert len(r) == 1 and r[0].score == 0


def test_top_k_limits():
    p = _p([CmfOption(color=str(i), hex_approx="#808080") for i in range(5)])
    assert len(rank_cmf(p, StyleTags(palette=["#808080"]), top_k=3)) == 3
