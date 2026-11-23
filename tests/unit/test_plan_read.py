"""도면 읽기: 그림을 AI에 넘기는 모양과 실패했을 때 하는 말."""
from types import SimpleNamespace

import pytest

from core.plan_read import PlanReadError, read_plan
from worker.plan_room import PlanRead, PlanWall

PLAN = PlanRead(readable=True, scale_from="dimensions", walls=[PlanWall(x1=0, y1=0, x2=3000, y2=0)])


class FakeOpenAI:
    def __init__(self, parsed=PLAN, refusal=None, boom=False):
        self.sent, self._parsed, self._refusal, self._boom = None, parsed, refusal, boom
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))

    def _parse(self, **kw):
        if self._boom:
            raise RuntimeError("timeout")
        self.sent = kw
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=self._parsed, refusal=self._refusal))])


class FakeClaude:
    def __init__(self):
        self.sent = None
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kw):
        self.sent = kw
        return SimpleNamespace(stop_reason="end_turn", parsed_output=PLAN)


def test_image_goes_to_openai_as_a_data_url():
    c = FakeOpenAI()
    assert read_plan(b"\x89PNG", "image/png", "a.png", client=c, provider="openai") == PLAN
    part = c.sent["messages"][1]["content"][0]
    assert part["type"] == "image_url" and part["image_url"]["url"].startswith("data:image/png;base64,")
    assert c.sent["response_format"] is PlanRead


def test_pdf_goes_as_a_file():
    c = FakeOpenAI()
    read_plan(b"%PDF", "application/pdf", "집.pdf", client=c, provider="openai")
    part = c.sent["messages"][1]["content"][0]
    assert part["type"] == "file" and part["file"]["filename"] == "집.pdf"
    k = FakeClaude()
    read_plan(b"%PDF", "application/pdf", "집.pdf", client=k, provider="claude")
    assert k.sent["messages"][0]["content"][0]["type"] == "document"


def test_image_goes_to_claude_as_base64():
    k = FakeClaude()
    assert read_plan(b"\xff\xd8", "image/jpeg", client=k, provider="claude") == PLAN
    src = k.sent["messages"][0]["content"][0]["source"]
    assert src["media_type"] == "image/jpeg" and src["type"] == "base64"


@pytest.mark.parametrize("client", [FakeOpenAI(boom=True), FakeOpenAI(parsed=None), FakeOpenAI(refusal="no")])
def test_failures_become_a_plain_message(client):
    with pytest.raises(PlanReadError) as e:
        read_plan(b"x", "image/png", client=client, provider="openai")
    assert "도면" in str(e.value) and "timeout" not in str(e.value)


def test_without_a_key_it_says_to_use_a_scan(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(PlanReadError, match="스캔"):
        read_plan(b"x", "image/png")
