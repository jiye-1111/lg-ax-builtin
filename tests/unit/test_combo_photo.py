"""사진을 AI에 넘기는 모양 (OpenAI·Claude) — 키 없이 가짜 클라이언트로."""
from types import SimpleNamespace

import pytest
from core.combos import Ideas, ask_ideas, parse_photo


class FakeOpenAI:
    def __init__(self):
        self.sent = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))

    def _parse(self, **kw):
        self.sent = kw
        msg = SimpleNamespace(refusal=None, parsed=Ideas(purpose="living", ideas=[]))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_openai_gets_the_photo_as_an_image_part_and_photo_rules():
    cl = FakeOpenAI()
    ask_ideas("집 요약", client=cl, image=("image/jpeg", "QUJD"))
    user = cl.sent["messages"][1]["content"]
    assert user[0] == {"type": "text", "text": "집 요약"}
    assert user[1]["type"] == "image_url" and user[1]["image_url"]["url"] == "data:image/jpeg;base64,QUJD"
    assert "사진" in cl.sent["messages"][0]["content"]


def test_without_photo_the_message_stays_plain_text():
    cl = FakeOpenAI()
    ask_ideas("집 요약", client=cl)
    assert cl.sent["messages"][1]["content"] == "집 요약"


def test_parse_photo_checks_type_bytes_and_size():
    jpg = "data:image/jpeg;base64," + __import__("base64").b64encode(b"\xff\xd8\xff" + b"0" * 10).decode()
    assert parse_photo(jpg)[0] == "image/jpeg"
    with pytest.raises(ValueError):
        parse_photo("data:image/jpeg;base64," + __import__("base64").b64encode(b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024)).decode())


def test_openai_reasoning_models_are_asked_to_think_briefly():
    from core.ai_style import openai_extra
    assert openai_extra("gpt-5-mini") == {"reasoning_effort": "minimal"}
    assert openai_extra("gpt-4o-mini") == {}  # 생각 단계가 없는 모델엔 보내지 않는다
    cl = FakeOpenAI()
    ask_ideas("집 요약", client=cl)
    assert cl.sent.get("reasoning_effort") == "minimal"
