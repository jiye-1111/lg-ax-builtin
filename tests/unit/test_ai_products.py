"""말로 적은 제품 조건 → 찾기 조건. AI는 말을 조건으로 옮기기만 하고 고르는 건 코드가 한다."""
from types import SimpleNamespace

from core.ai_products import ProductIntent, interpret_products, rule_based_products


def test_rules_read_all_conditions_from_one_sentence():
    i = rule_based_products("600L 이상 베이지 냉장고, 폭 950 안에 들어가는 걸로, 300만 원 이하")
    assert i.engine == "rules"
    assert i.wants_products and not i.also_style
    assert i.category == "refrigerator"
    assert i.capacity_min == 600 and i.capacity_max is None
    assert i.color == "베이지"
    assert i.space_w == 950
    assert i.price_max == 3_000_000 and i.price_min is None


def test_rules_kimchi_refrigerator_is_not_refrigerator():
    assert rule_based_products("김치냉장고 400리터 이하로 보여 줘").category == "kimchi_refrigerator"
    assert rule_based_products("김치냉장고 400리터 이하로 보여 줘").capacity_max == 400


def test_rules_units_cm_and_m_become_mm():
    assert rule_based_products("가로 95cm 자리에 놓을 식기세척기").space_w == 950
    assert rule_based_products("냉장고 높이 1.8m 깊이 700mm").space_h == 1800
    assert rule_based_products("냉장고 높이 1.8m 깊이 700mm").space_d == 700
    assert rule_based_products("60cm 폭 식기세척기").space_w == 600


def test_rules_price_forms():
    assert rule_based_products("200만원대 세탁기").price_min == 2_000_000
    assert rule_based_products("200만원대 세탁기").price_max == 3_000_000
    assert rule_based_products("150만 원 넘는 건조기").price_min == 1_500_000
    assert rule_based_products("냉장고 예산 250만원").price_max == 2_500_000


def test_rules_bare_capacity_means_about_that_size():
    i = rule_based_products("800L 냉장고 블랙")
    assert i.capacity_min == 720 and i.capacity_max == 880 and i.color == "블랙"


def test_rules_install_and_sort():
    i = rule_based_products("빌트인 오븐 제일 싼 순으로")
    assert i.install == "built_in" and i.sort == "price" and i.category == "oven"


def test_rules_style_only_sentence_does_not_ask_for_products():
    i = rule_based_products("따뜻한 우드톤에 대리석 포인트 주고 싶어")
    assert not i.wants_products
    assert i.category is None and i.color is None


def test_rules_style_and_products_together():
    i = rule_based_products("화이트 우드 분위기로 꾸미고 어울리는 냉장고도 골라 줘")
    assert i.wants_products and i.also_style and i.category == "refrigerator"


def test_intent_drops_nonsense_numbers():
    i = ProductIntent(wants_products=True, also_style=False, capacity_min=-5, price_max=0, space_w=999999)
    assert i.capacity_min is None and i.price_max is None and i.space_w is None


class _FakeMessages:
    def __init__(self, out, stop="end_turn"):
        self.out, self.stop, self.kwargs = out, stop, None

    def parse(self, **kw):
        self.kwargs = kw
        return SimpleNamespace(parsed_output=self.out, stop_reason=self.stop)


def _client(out, stop="end_turn"):
    m = _FakeMessages(out, stop)
    return SimpleNamespace(beta=SimpleNamespace(messages=m)), m


def test_claude_output_is_used_as_is():
    want = ProductIntent(wants_products=True, also_style=False, category="refrigerator", capacity_min=600)
    c, m = _client(want)
    got = interpret_products("음식 많이 들어가는 큰 냉장고", client=c)
    assert got.engine == "claude" and got.capacity_min == 600
    assert m.kwargs["output_format"] is ProductIntent


def test_refusal_or_error_falls_back_to_rules():
    c, _ = _client(None, stop="refusal")
    assert interpret_products("600L 이상 냉장고", client=c).engine == "rules"

    class Boom:
        beta = SimpleNamespace(messages=SimpleNamespace(parse=lambda **kw: 1 / 0))
    got = interpret_products("600L 이상 냉장고", client=Boom())
    assert got.engine == "rules" and got.capacity_min == 600


def test_no_key_uses_rules(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert interpret_products("베이지 냉장고").engine == "rules"
