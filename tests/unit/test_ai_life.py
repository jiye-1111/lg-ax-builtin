"""생활 이야기에서 사실만 뽑기: 규칙(키 없을 때)과 OpenAI 경로."""
from types import SimpleNamespace as NS

from core.ai_life import LifeFacts, is_life_story, read_life, rule_life


def test_rules_read_family_size_baby_and_habits():
    f = rule_life("맞벌이 4인 가족, 장은 주말에 몰아서 보고 아기가 있어요")
    assert f.people == 4 and f.baby and f.lots_of_food and f.dual_income


def test_rules_read_korean_number_words_and_living_alone():
    assert rule_life("세 식구예요").people == 3
    assert rule_life("혼자 자취해요").people == 1
    assert rule_life("신혼부부 둘이 살아요").people == 2


def test_rules_read_kimchi_amount():
    assert rule_life("김장을 많이 해요").kimchi == "lots"
    assert rule_life("김치는 조금 먹어요").kimchi == "small"
    assert rule_life("김치는 안 먹어요").kimchi == "none"


def test_life_story_detection_ignores_decor_and_product_questions():
    assert is_life_story("4인 가족이고 아기가 있어요")
    assert is_life_story("맞벌이 부부예요, 장은 몰아서 봐요")
    assert not is_life_story("호텔 느낌으로 꾸며 줘")
    assert not is_life_story("600L 냉장고 보여 줘")
    assert is_life_story("4인 가족인데 냉장고 추천해 줘")


class FakeOpenAI:
    def __init__(self, facts):
        self.chat = NS(completions=NS(parse=self.parse))
        self.facts, self.sent = facts, None

    def parse(self, **kw):
        self.sent = kw
        return NS(choices=[NS(message=NS(parsed=self.facts, refusal=None))])


def test_openai_path_returns_only_facts_and_engine():
    fake = FakeOpenAI(LifeFacts(people=5, baby=False, lots_of_food=True, kimchi="lots", dual_income=False, pet=False))
    life, engine = read_life("다섯 식구, 김장 많이 함", client=fake)
    assert engine == "openai" and life.people == 5 and life.kimchi == "lots"
    assert fake.sent["response_format"] is LifeFacts


def test_openai_failure_falls_back_to_rules():
    class Broken:
        chat = NS(completions=NS(parse=lambda **kw: (_ for _ in ()).throw(RuntimeError("down"))))
    life, engine = read_life("2인 가구", client=Broken())
    assert engine == "rules" and life.people == 2
