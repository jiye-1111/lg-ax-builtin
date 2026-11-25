"""가구 위에 올려 두기: 식탁·아일랜드·하부장 윗면에 작은 가전을 올린다 (docs/specs/fit-rules.md '가구 위에 올려 두기')."""
import math

import pytest

from core.models import Clearance, Dims, Product
from recommender.fit import FitConfig, Verdict
from recommender.pose import Pose, can_sit, check_pose, surface_under

from .test_pose import fridge, room

UP = math.pi / 2
CFG = FitConfig(margin_scanned_mm=30, margin_measured_mm=5)
codes = lambda r: {x["code"] for x in r.reasons}  # noqa: E731


def small(category="microwave", w=500, h=280, d=400, install="freestanding", form=None):
    return Product(sku="T-S", name="작은 가전", category=category, zone_fit=["kitchen"], install_type=install,
                   product_dims_mm=Dims(w=w, h=h, d=d), clearance_mm=Clearance(side=0, top=0, back=0), install_form=form,
                   door_swing_mm=0, source_url=None, source_checked_at=None, demo_only=True)


# 방 가운데 아일랜드 (1.8 x 0.9 x 0.9)
ISLAND = {"placement_id": "pl1", "sku": "decor:island", "center_xz": [2.0, 1.5], "yaw_rad": UP, "size_m": [1.8, 0.9, 0.9]}
TOP = {"id": "pl1", "center_xz": (2.0, 1.5), "yaw_rad": 0.0, "w": 1.8, "d": 0.9, "top_m": 0.9}


def test_which_products_can_sit():
    assert can_sit(small("microwave")) and can_sit(small("water_purifier", form="데스크")) and can_sit(small("oven"))
    assert can_sit(small("tv", w=1450, h=900, d=260))            # TV는 거실장 위에
    assert not can_sit(fridge())                                   # 큰 가전
    assert can_sit(small("wine_cellar", w=282, h=497, d=534))      # 미니 와인셀러
    assert can_sit(small("refrigerator", w=443, h=501, d=450))     # 미니 냉장고
    assert not can_sit(small("wine_cellar", w=595, h=838, d=580))  # 큰 와인셀러는 바닥에
    assert not can_sit(small("dehumidifier", w=410, h=640, d=210)) # 바닥에 두는 것
    assert not can_sit(small("water_purifier", install="built_in", form="빌트인"))  # 하부장 안에 들어가는 것
    assert not can_sit(small("water_purifier", h=1200, form="스탠드"))
    assert not can_sit(small("vacuum"))                            # 바닥에 두는 것
    assert not can_sit(small(w=None))


def test_surface_under_picks_top_below_center():
    assert surface_under((2.0, 1.5), [TOP])["id"] == "pl1"
    assert surface_under((2.85, 1.5), [TOP])["id"] == "pl1"
    assert surface_under((3.0, 1.5), [TOP]) is None
    low = {**TOP, "id": "low", "top_m": 0.4}
    assert surface_under((2.0, 1.5), [low, TOP])["id"] == "pl1"   # 겹치면 높은 윗면


def test_on_top_of_island_fits_and_reports_height():
    r = check_pose(room(), small(), Pose((2.0, 1.5), UP), CFG, others=[ISLAND], host=TOP)
    assert r.verdict == Verdict.FIT, r.reasons
    d = r.to_dict()
    assert d["base_m"] == 0.9 and d["on"] == "pl1"


def test_without_host_the_island_blocks():
    r = check_pose(room(), small(), Pose((2.0, 1.5), UP), CFG, others=[ISLAND])
    assert r.verdict == Verdict.NO_FIT and "overlaps_placement" in codes(r)
    assert r.to_dict()["base_m"] == 0


def test_hanging_over_the_edge_is_no_fit():
    r = check_pose(room(), small(), Pose((2.8, 1.5), UP), CFG, others=[ISLAND], host=TOP)
    assert r.verdict == Verdict.NO_FIT and "surface_overhang" in codes(r)


def test_two_things_on_the_same_top_collide():
    other = {"placement_id": "pl2", "sku": "T-S2", "center_xz": [2.1, 1.5], "yaw_rad": UP, "size_m": [0.5, 0.3, 0.4], "base_m": 0.9}
    r = check_pose(room(), small(), Pose((2.0, 1.5), UP), CFG, others=[ISLAND, other], host=TOP)
    assert r.verdict == Verdict.NO_FIT and "overlaps_placement" in codes(r)
    far = {**other, "center_xz": [1.4, 1.5]}
    assert check_pose(room(), small(), Pose((2.5, 1.5), UP), CFG, others=[ISLAND, far], host=TOP).verdict == Verdict.FIT


def test_low_things_on_the_floor_do_not_block_what_is_on_top():
    # 아일랜드 옆 낮은 의자(0.45 m)는 0.9 m 위에 올린 물건의 여유 공간을 막지 않는다
    stool = {"placement_id": "pl3", "sku": "decor:chair", "center_xz": [2.0, 0.75], "yaw_rad": UP, "size_m": [0.5, 0.45, 0.5]}
    r = check_pose(room(), small(d=800), Pose((2.0, 1.5), UP), CFG, others=[ISLAND, stool], host=TOP)
    assert "overlaps_placement" not in codes(r) and "tight" not in codes(r)


def test_ceiling_counts_from_the_top_it_sits_on():
    tall = small("tv", w=1400, h=1600, d=260)
    assert check_pose(room(h=2.4), tall, Pose((2.0, 1.5), UP), CFG, others=[ISLAND], host=TOP).verdict == Verdict.NO_FIT
    r = check_pose(room(h=2.4), tall, Pose((2.0, 1.5), UP), CFG, others=[ISLAND], host=TOP)
    assert "ceiling_low" in codes(r)


def test_near_the_edge_it_is_pulled_back_onto_the_top():
    from recommender.pose import settle_on
    # 가운데는 윗면 안인데 몸이 밖으로 나오는 자리 → 다 올라오는 가장 가까운 자리로
    c = settle_on(TOP, (2.8, 1.5), UP, 0.5, 0.4)
    assert c == pytest.approx((2.65, 1.5))
    r = check_pose(room(), small(), Pose(c, UP), CFG, others=[ISLAND], host=TOP)
    assert "surface_overhang" not in codes(r)
    assert settle_on(TOP, (2.0, 1.5), UP, 0.5, 0.4) == pytest.approx((2.0, 1.5))   # 이미 다 올라와 있으면 그대로
    assert settle_on(TOP, (2.0, 1.9), UP, 0.5, 0.4) == pytest.approx((2.0, 1.75))
    # 윗면보다 큰 물건은 옮겨도 소용없으니 그대로 둔다 (판정이 '밖으로 나옴'을 알려 준다)
    assert settle_on(TOP, (2.8, 1.5), UP, 2.4, 0.4) == pytest.approx((2.8, 1.5))
