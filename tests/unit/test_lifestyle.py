"""생활 이야기 → 가전 용량: 규칙은 LGE.COM 구매 가이드 숫자만 쓴다 (docs/specs/lifestyle.md)."""
from recommender.lifestyle import Life, needs, pick


def by_cat(life, **kw):
    return {n.category: n for n in needs(life, **kw)}


def test_one_or_two_people_get_300_to_500_litre_fridge():
    n = by_cat(Life(people=2))["refrigerator"]
    assert (n.key, n.min, n.max) == ("capacity_l", 300, 500)
    assert "lge.co.kr" in n.source_url and n.quote


def test_four_people_with_lots_of_food_get_600_litre_class_fridge():
    n = by_cat(Life(people=4, lots_of_food=True))["refrigerator"]
    assert (n.min, n.max) == (600, 699)


def test_big_food_storage_without_a_size_rule_gets_800_litre_class():
    n = by_cat(Life(people=5, lots_of_food=True))["refrigerator"]
    assert n.min == 800 and n.max is None


def test_no_lge_rule_means_no_capacity_filter():
    # 3인·장보기 보통: LGE.COM에 숫자가 없다 → 지어내지 않고 용량 조건 없이
    n = by_cat(Life(people=3))["refrigerator"]
    assert n.min is None and n.max is None and n.quote is None


def test_kimchi_fridge_only_when_they_eat_kimchi():
    assert "kimchi_refrigerator" not in by_cat(Life(people=4))
    assert "kimchi_refrigerator" not in by_cat(Life(people=4, kimchi="none"))
    small = by_cat(Life(people=2, kimchi="small"))["kimchi_refrigerator"]
    assert (small.min, small.max) == (200, 299)
    lots = by_cat(Life(people=4, kimchi="lots"))["kimchi_refrigerator"]
    assert (lots.min, lots.max) == (480, 499)


def test_washer_follows_family_size_and_baby():
    assert by_cat(Life(people=4))["washer"].min == 25
    baby = by_cat(Life(people=3, baby=True))["washer"]
    assert (baby.key, baby.min, baby.max) == ("wash_kg", 21, 24)


def test_dual_income_gets_wash_combo_instead_of_plain_washer():
    got = by_cat(Life(people=4, dual_income=True))
    assert "washer" not in got and got["washer_dryer"].key == "wash_kg"


def test_unknown_people_and_nothing_else_gives_nothing():
    assert needs(Life()) == []


class P:
    def __init__(self, sku, cat, **opt):
        self.sku, self.category, self.options = sku, cat, opt


def item(p, verdict="fit"):
    return {"product": {"sku": p.sku, "category": p.category}, "fit": {"verdict": verdict}, "_p": p}


def test_pick_takes_first_fitting_product_in_range():
    need = by_cat(Life(people=2))["refrigerator"]
    small, big, ok = P("A", "refrigerator", capacity_l=250), P("B", "refrigerator", capacity_l=800), P("C", "refrigerator", capacity_l=450)
    tight = P("D", "refrigerator", capacity_l=400)
    items = [item(small), item(tight, "no_fit"), item(big), item(ok)]
    got = pick(need, items, lambda it: it["_p"].options)
    assert got["product"]["sku"] == "C"


def test_pick_returns_none_when_nothing_in_range():
    need = by_cat(Life(people=2))["refrigerator"]
    assert pick(need, [item(P("B", "refrigerator", capacity_l=800))], lambda it: it["_p"].options) is None
