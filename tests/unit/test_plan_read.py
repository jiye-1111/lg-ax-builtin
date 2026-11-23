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


# ---- 한 번 더 보기: 읽은 결과를 그림으로 다시 그려 도면과 같이 보여 주고, 빠진 것을 채운 결과를 받는다 ----
def box(w=6000, d=4000, **kw):
    pts = [(0, 0), (w, 0), (w, d), (0, d)]
    return PlanRead(readable=True, scale_from="dimensions",
                    walls=[PlanWall(x1=a[0], y1=a[1], x2=b[0], y2=b[1]) for a, b in zip(pts, pts[1:] + pts[:1])], **kw)


class TwoAnswers:
    """첫 번째는 처음 읽은 것, 두 번째는 다시 보고 고친 것"""

    def __init__(self, first, second):
        self.calls, self._answers = [], [first, second]
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))

    def _parse(self, **kw):
        self.calls.append(kw)
        a = self._answers[len(self.calls) - 1]
        if isinstance(a, Exception):
            raise a
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=a, refusal=None))])


def test_second_look_gets_the_plan_the_sketch_and_the_first_reading():
    from worker.plan_room import PlanOpening

    better = box(openings=[PlanOpening(type="window", wall=0, offset_mm=1000, width_mm=1500)])
    c = TwoAnswers(box(), better)
    assert read_plan(b"\x89PNG", "image/png", "a.png", client=c, provider="openai") == better
    parts = c.calls[1]["messages"][1]["content"]
    assert [p["type"] for p in parts] == ["image_url", "image_url", "text"]
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert '"walls"' in parts[2]["text"]


def test_a_worse_second_look_is_thrown_away():
    first = box()
    for bad in (PlanRead(readable=False, scale_from="none"), box(w=600), box(w=12000),
                PlanRead(readable=True, scale_from="dimensions", walls=first.walls[:1]), RuntimeError("timeout"), None):
        c = TwoAnswers(first, bad)
        assert read_plan(b"x", "image/png", client=c, provider="openai") == first


def test_second_look_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("PLAN_AI_REVIEW", "0")
    c = TwoAnswers(box(), box(w=6100))
    assert read_plan(b"x", "image/png", client=c, provider="openai") == box() and len(c.calls) == 1


def test_unreadable_first_look_is_not_checked_again():
    c = TwoAnswers(PlanRead(readable=False, reason="사진이에요", scale_from="none"), box())
    assert read_plan(b"x", "image/png", client=c, provider="openai").readable is False and len(c.calls) == 1


def test_sketch_is_a_png_with_every_wall():
    from io import BytesIO

    from PIL import Image

    from core.plan_read import plan_sketch

    im = Image.open(BytesIO(plan_sketch(box())))
    assert im.format == "PNG" and min(im.size) >= 400
    assert im.convert("L").getextrema()[0] < 60  # 벽 선이 그려져 있다
