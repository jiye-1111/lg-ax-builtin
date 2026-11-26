"""꾸민 집을 보고 '여기에 이걸 더하면' 고르는 규칙 (recommender.addons)."""
from recommender.addons import pick_addons


def ids(have, **kw):
    return [a.id for a in pick_addons(have, **kw)]


def test_nothing_placed_means_nothing_to_add():
    assert ids([]) == []


def test_bed_asks_for_nightstand_and_rug_but_not_what_is_already_there():
    got = ids(["bed"])
    assert got[0] == "nightstand" and "rug" in got
    assert "nightstand" not in ids(["bed", "nightstand"])
    assert "rug" not in ids(["bed", "rug"])


def test_sofa_gets_table_in_front_unless_a_table_is_there():
    assert "coffee" in ids(["sofa"])
    assert "coffee" not in ids(["sofa", "table"])


def test_washer_gets_lg_dryer_unless_it_already_dries():
    a = next(a for a in pick_addons(["washer"]) if a.id == "dryer")
    assert a.category == "dryer" and a.sku is None
    assert "dryer" not in ids(["washer", "wash_tower"])
    assert "dryer" not in ids(["washer_dryer"])


def test_kitchen_gets_water_purifier_and_dishwasher():
    got = ids(["refrigerator", "basecab"])
    assert "water_purifier" in got and "dishwasher" in got


def test_desk_without_chair_gets_chair():
    assert ids(["desk"])[0] == "deskchair"
    assert "deskchair" not in ids(["desk", "chair"])


def test_every_addon_has_one_plain_sentence():
    for a in pick_addons(["bed", "sofa", "desk", "washer", "refrigerator", "cooktop", "wardrobe"]):
        assert a.text.endswith("요") and len(a.text) <= 40 and not any(ch.isdigit() for ch in a.text)
