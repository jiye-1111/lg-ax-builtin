"""벽지·바닥재 카탈로그와 스타일 기반 순위 (docs/specs/finishes.md)."""
import re

import pytest

from core import config
from recommender.finishes import load_finishes, rank_finishes

HEX = re.compile(r"^#[0-9A-F]{6}$")


@pytest.fixture(scope="module")
def items():
    return load_finishes(config.ROOT / "data" / "finishes" / "finishes.json")


def test_every_finish_is_a_real_product_with_source(items):
    assert len(items) >= 12
    assert {f.kind for f in items} == {"wall", "floor"}
    for f in items:
        if f.generic:  # 상표 없는 색상표: 출처도 상표도 적지 않는다
            assert not f.source_url and not f.brand, f.id
            continue
        assert f.source_url.startswith("https://"), f.id
        assert f.source_checked_at, f.id
        assert f.brand and f.line and f.name
        assert f.texture in {"plaster", "fabric", "stone", "wood", "paint"}
        assert f.tones and all(HEX.match(t.hex) for t in f.tones)
        assert f.tone_basis in {"official", "approx"}


def test_wall_has_a_wide_colour_range_beyond_beige(items):
    """벽 색은 베이지·회색만이 아니라 초록·파랑·분홍·노랑·짙은 색까지 고를 수 있다."""
    import colorsys
    tones = [t.hex for f in items if f.kind == "wall" for t in f.tones]
    assert len(tones) >= 38 and len(set(tones)) == len(tones)

    def hsv(h):
        return colorsys.rgb_to_hsv(*(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)))
    vivid = [hsv(h) for h in tones if hsv(h)[1] >= 0.12]
    for name, lo, hi in (("노랑", 0.11, 0.17), ("초록", 0.22, 0.45), ("파랑", 0.52, 0.68), ("분홍·빨강", 0.92, 1.0)):
        assert any(lo <= h <= hi for h, _, _ in vivid), name
    assert sum(1 for h in tones if hsv(h)[2] < 0.45) >= 3  # 짙은 포인트 색


def test_generic_colours_are_paint_without_a_brand(items):
    generic = [f for f in items if f.generic]
    assert generic and all(f.kind == "wall" and f.texture == "paint" for f in generic)


def test_ids_are_unique(items):
    ids = [f.id for f in items]
    assert len(ids) == len(set(ids))


def test_wood_style_puts_wood_floor_first(items):
    r = rank_finishes(items, kind="floor", palette=["#D5B48C", "#F0EEE9"], materials=["우드", "내추럴"])
    assert r[0].finish.texture == "wood"
    assert all(x.finish.kind == "floor" for x in r)
    assert r[0].score >= r[-1].score
    assert any("우드" in s for s in r[0].reasons)


def test_marble_style_puts_stone_floor_first(items):
    r = rank_finishes(items, kind="floor", palette=["#E6E3DE"], materials=["대리석"])
    assert r[0].finish.texture == "stone"


def test_texture_preference_breaks_ties_toward_that_texture(items):
    r = rank_finishes(items, kind="wall", palette=["#E6DFD3"], materials=[], prefer_texture="fabric")
    assert r[0].finish.texture == "fabric"


def test_picks_the_closest_tone_of_a_finish(items):
    r = rank_finishes(items, kind="wall", palette=["#C08E73"], materials=["회벽"])
    top = r[0]
    assert top.tone.hex == "#C08E73"  # 디아망 회벽 테라코타 톤
    assert top.min_delta_e == pytest.approx(0, abs=0.01)


def test_empty_style_keeps_catalog_order_with_zero_score(items):
    r = rank_finishes(items, kind="wall", palette=[], materials=[])
    assert [x.finish.id for x in r] == [f.id for f in items if f.kind == "wall"]
    assert all(x.score == 0 for x in r)


def test_to_dict_carries_source_and_approx_flag(items):
    d = rank_finishes(items, kind="floor", palette=["#E2CDB0"], materials=["wood"], top_k=1)[0].to_dict()
    assert d["finish"]["source_url"].startswith("https://")
    assert d["tone"]["hex"].startswith("#")
    assert d["approx_color"] is True
    assert 0 <= d["score"] <= 1


def test_wall_list_has_no_wood_grain(items):
    """나무결 벽 패널은 바닥재처럼 보여서 벽지 목록에 두지 않는다. 나무 무늬는 바닥에서만 고른다."""
    assert not [f.id for f in items if f.kind == "wall" and f.texture == "wood"]
    assert any(f.kind == "floor" and f.texture == "wood" for f in items)


def test_wall_finish_cannot_be_wood():
    from recommender.finishes import Finish
    with pytest.raises(ValueError):
        Finish.model_validate({"id": "w_x", "kind": "wall", "brand": "", "line": "", "name": "x", "texture": "wood",
                               "tones": [{"name": "a", "hex": "#C9A47C"}], "tone_basis": "approx", "generic": True})
