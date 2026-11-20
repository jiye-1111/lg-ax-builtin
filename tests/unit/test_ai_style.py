"""자연어 → 스타일(팔레트·재질 키워드) 해석. 점수 계산은 코드가 한다 (CLAUDE.md)."""
from types import SimpleNamespace

import pytest

from core.ai_style import MODEL, StyleIntent, interpret_style, rule_based_style


def test_rules_understand_korean_style_words():
    s = rule_based_style("따뜻한 우드톤에 대리석 포인트 주고 싶어")
    assert s.engine == "rules"
    assert {"wood", "stone"} <= set(s.materials)
    assert 1 <= len(s.palette) <= 6
    assert s.summary


def test_rules_dark_moody_gives_dark_palette():
    s = rule_based_style("어둡고 무드 있는 호텔 느낌")
    from recommender.cmf import hex_to_lab
    assert min(hex_to_lab(h)[0] for h in s.palette) < 40


def test_rules_unknown_text_still_returns_neutral_palette():
    s = rule_based_style("그냥 알아서 해줘")
    assert s.palette and s.engine == "rules"


def test_style_intent_rejects_bad_hex():
    with pytest.raises(ValueError):
        StyleIntent(palette=["red"], materials=[], summary="x")


class _FakeMessages:
    def __init__(self, out):
        self.out, self.kwargs = out, None

    def parse(self, **kw):
        self.kwargs = kw
        return SimpleNamespace(parsed_output=self.out, stop_reason="end_turn")


def test_claude_path_uses_latest_model_and_structured_output():
    want = StyleIntent(palette=["#F0EEE9", "#C9A47C"], materials=["wood", "fabric"], summary="밝은 오크와 린넨",
                       wall_texture="fabric", floor_texture="wood")
    msgs = _FakeMessages(want)
    client = SimpleNamespace(messages=msgs)
    got = interpret_style("린넨 느낌 벽에 밝은 오크 마루", catalog_brief="- 베스띠 패브릭", client=client)
    assert got.engine == "claude"
    assert got.palette == ["#F0EEE9", "#C9A47C"]
    assert msgs.kwargs["model"] == MODEL == "claude-opus-5-5"
    assert msgs.kwargs["output_format"] is StyleIntent
    assert "린넨 느낌" in str(msgs.kwargs["messages"])
    assert "베스띠 패브릭" in str(msgs.kwargs["system"])


def test_refusal_or_error_falls_back_to_rules():
    class Boom:
        def parse(self, **kw):
            raise RuntimeError("network")
    got = interpret_style("화이트 미니멀", client=SimpleNamespace(messages=Boom()))
    assert got.engine == "rules" and "white" in got.materials


def test_without_api_key_uses_rules(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    got = interpret_style("화이트 미니멀")
    assert got.engine == "rules"
