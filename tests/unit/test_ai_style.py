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
    client = SimpleNamespace(beta=SimpleNamespace(messages=msgs))
    got = interpret_style("린넨 느낌 벽에 밝은 오크 마루", catalog_brief="- 베스띠 패브릭", client=client)
    assert got.engine == "claude"
    assert got.palette == ["#F0EEE9", "#C9A47C"]
    assert msgs.kwargs["model"] == MODEL == "claude-opus-5-5"
    assert msgs.kwargs["output_format"] is StyleIntent
    assert "린넨 느낌" in str(msgs.kwargs["messages"])
    assert "베스띠 패브릭" in str(msgs.kwargs["system"])
    assert msgs.kwargs["fallbacks"] == "default"  # 거절되면 서버가 다른 모델로 다시 돌린다


def test_refusal_or_error_falls_back_to_rules():
    class Boom:
        def parse(self, **kw):
            raise RuntimeError("network")
    got = interpret_style("화이트 미니멀", client=SimpleNamespace(beta=SimpleNamespace(messages=Boom())))
    assert got.engine == "rules" and "white" in got.materials


def test_without_api_key_uses_rules(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    got = interpret_style("화이트 미니멀")
    assert got.engine == "rules"


# ---- OpenAI 키로도 (서버 .env에 둘 중 하나만 있어도 된다) ----
class _FakeCompletions:
    def __init__(self, out, refusal=None):
        self.out, self.refusal, self.kwargs = out, refusal, None

    def parse(self, **kw):
        self.kwargs = kw
        msg = SimpleNamespace(parsed=self.out, refusal=self.refusal)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")])


def test_openai_path_uses_structured_output():
    from core.ai_style import OPENAI_MODEL, interpret_with_openai
    want = StyleIntent(palette=["#E6E3DE"], materials=["stone"], summary="대리석", floor_texture="stone")
    comp = _FakeCompletions(want)
    got = interpret_with_openai("대리석 바닥", catalog_brief="- 에디톤 스톤", client=SimpleNamespace(chat=SimpleNamespace(completions=comp)))
    assert got.engine == "openai" and got.floor_texture == "stone"
    assert comp.kwargs["model"] == OPENAI_MODEL
    assert comp.kwargs["response_format"] is StyleIntent
    assert "에디톤 스톤" in comp.kwargs["messages"][0]["content"]
    assert comp.kwargs["messages"][1] == {"role": "user", "content": "대리석 바닥"}


def test_openai_refusal_falls_back_to_rules():
    from core.ai_style import interpret_with_openai
    comp = _FakeCompletions(None, refusal="no")
    got = interpret_with_openai("화이트", client=SimpleNamespace(chat=SimpleNamespace(completions=comp)))
    assert got.engine == "rules"


def test_provider_follows_whichever_key_is_set(monkeypatch):
    from core.ai_style import pick_provider
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("STYLE_AI_PROVIDER", raising=False)
    assert pick_provider() is None
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert pick_provider() == "openai"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert pick_provider() == "claude"
    monkeypatch.setenv("STYLE_AI_PROVIDER", "openai")  # 둘 다 있으면 고를 수 있다
    assert pick_provider() == "openai"
