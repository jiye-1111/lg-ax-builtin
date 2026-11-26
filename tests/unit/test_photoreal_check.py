"""실사 사진을 3D와 견줘 보기: 보는 AI의 답을 틀린 것 목록으로. 못 견줘 보면 None (사진은 그대로 낸다)."""
from types import SimpleNamespace as NS

from core import photoreal_check as pc
from PIL import Image


class Fake:
    def __init__(self, parsed=None, boom=False):
        self.sent, self.parsed, self.boom = None, parsed, boom
        self.chat = NS(completions=NS(parse=self.parse))

    def parse(self, **kw):
        self.sent = kw
        if self.boom:
            raise TimeoutError("slow")
        return NS(choices=[NS(message=NS(parsed=self.parsed, refusal=None))])


IMG = Image.new("RGB", (1536, 1024), (200, 190, 180))


def test_problems_come_back_as_plain_dicts_with_both_pictures_and_the_list_sent():
    f = Fake(pc.Verdict(problems=[pc.Problem(kind="added", what="a sofa", where="lower left")]))
    got = pc.check(IMG, IMG, ["Object 1 (x 70-98%, y 55-95% of the first image): a bed."], client=f)
    assert got == [{"kind": "added", "what": "a sofa", "where": "lower left"}]
    user = f.sent["messages"][1]["content"]
    assert "a bed" in user[0]["text"] and sum(x["type"] == "image_url" for x in user) == 2


def test_same_objects_means_no_problems():
    assert pc.check(IMG, IMG, [], client=Fake(pc.Verdict(problems=[]))) == []


def test_errors_or_no_key_skip_the_check(monkeypatch):
    assert pc.check(IMG, IMG, [], client=Fake(boom=True)) is None
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert pc.check(IMG, IMG, []) is None
