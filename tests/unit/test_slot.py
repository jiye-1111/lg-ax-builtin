"""장 칸에 끼워 넣기 (docs/specs/fit-rules.md '장 칸에 끼워 넣는 빌트인') — 테스트 먼저.

하부장은 벽 w1(y=0, 안쪽 면 0.05)에 등을 붙이고 정면이 +y(UP). 폭 축은 +x.
"""
import math

from recommender.pose import Pose
from recommender.slot import MIN_PIECE_M, cover, slot_in, slotable

from .test_mount import dishwasher, item, wallfit
from .test_pose import fridge

UP = math.pi / 2
DW = (0.598, 0.815, 0.567)
FRONT_Y = 0.35 + 0.3 - 0.02 - 0.567 / 2  # 문짝 앞면에 식기세척기 앞면을 맞춘 가운데


def cab(pid, x, w, sku="decor:basecab", h=0.85, d=0.6, y=None, yaw=UP, **more):
    return {"placement_id": pid, "sku": sku, "center_xz": [x, 0.05 + d / 2 if y is None else y], "yaw_rad": yaw,
            "size_m": [w, h, d], "hex": None, **more}


def near(a, b, tol=2e-3):
    return math.isclose(a, b, abs_tol=tol)


def by_id(s):
    return {e.get("id") or "new": e for e in s.edits}


# ---------- 어떤 제품이 칸에 들어가나 ----------
def test_only_floor_standing_builtins_go_into_a_bay():
    assert slotable(dishwasher())
    assert slotable(item("냉장고 Fit & Max", "refrigerator", "built_in_look", w=914, h=1860, d=709))
    assert slotable(fridge())
    assert not slotable(wallfit())
    assert not slotable(item("세탁기", "washer", w=600, h=850, d=600))
    assert not slotable(item("인덕션", "cooktop", "built_in", w=600, h=50, d=500))


# ---------- 하부장 줄에 끼우기 ----------
def test_dropped_on_the_middle_of_a_cabinet_it_cuts_a_bay():
    s = slot_in(DW, Pose((2.0, 0.5), UP), [cab("c1", 2.0, 1.8)])
    assert s.host == "c1"
    assert near(s.pose.center_xz[0], 2.0) and near(s.pose.center_xz[1], FRONT_Y)
    assert near(s.pose.yaw_rad, UP)
    e = by_id(s)
    assert set(e) == {"c1", "new"}
    left, right = e["c1"], e["new"]
    assert near(left["center_xz"][0] + left["w"] / 2, 2.0 - 0.299) and near(left["center_xz"][0] - left["w"] / 2, 1.1)
    assert near(right["center_xz"][0] - right["w"] / 2, 2.0 + 0.299) and near(right["center_xz"][0] + right["w"] / 2, 2.9)
    assert right["like"] == "c1"
    assert near(left["w"] + right["w"] + 0.598, 1.8)


def test_near_the_end_it_lines_up_with_the_end_and_leaves_one_piece():
    s = slot_in(DW, Pose((1.1 + 0.299 + 0.08, 0.4), UP), [cab("c1", 2.0, 1.8)])
    assert near(s.pose.center_xz[0] - 0.299, 1.1)
    e = by_id(s)
    assert set(e) == {"c1"}
    assert near(e["c1"]["w"], 1.8 - 0.598) and near(e["c1"]["center_xz"][0] + e["c1"]["w"] / 2, 2.9)


def test_beside_the_end_it_sits_flush_and_cuts_nothing():
    s = slot_in(DW, Pose((2.9 + 0.299 + 0.07, 0.38), UP), [cab("c1", 2.0, 1.8)])
    assert s.edits == []
    assert near(s.pose.center_xz[0] - 0.299, 2.9) and near(s.pose.center_xz[1], FRONT_Y)


def test_far_from_any_cabinet_nothing_happens():
    assert slot_in(DW, Pose((0.5, 0.4), UP), [cab("c1", 2.5, 1.0)]) is None
    assert slot_in(DW, Pose((2.5, 1.6), UP), [cab("c1", 2.5, 1.0)]) is None  # 장 앞으로 멀리


def test_it_turns_to_face_the_same_way_as_the_cabinet():
    s = slot_in(DW, Pose((2.0, 0.4), 0.3), [cab("c1", 2.0, 1.8)])
    assert near(s.pose.yaw_rad, UP)


def test_a_cabinet_as_wide_as_the_item_is_replaced():
    s = slot_in(DW, Pose((2.0, 0.4), UP), [cab("c1", 2.0, 0.6)])
    assert s.edits == [{"id": "c1", "remove": True}]


def test_a_sliver_left_over_is_dropped():
    s = slot_in(DW, Pose((2.0, 0.4), UP), [cab("c1", 2.0, 0.7)])
    assert 0.7 - 0.598 < MIN_PIECE_M
    assert s.edits == [{"id": "c1", "remove": True}]
    assert near(s.pose.center_xz[0] - 0.299, 1.65)  # 한쪽 끝에 맞춰서 남는 쪽을 한데 모은다


def test_on_the_joint_of_two_cabinets_both_give_way():
    s = slot_in(DW, Pose((2.0, 0.4), UP), [cab("a", 1.4, 1.2), cab("b", 2.6, 1.2)])
    e = by_id(s)
    assert set(e) == {"a", "b"}
    assert near(e["a"]["w"], 1.2 - 0.299) and near(e["b"]["w"], 1.2 - 0.299)
    assert near(e["a"]["center_xz"][0] - e["a"]["w"] / 2, 0.8) and near(e["b"]["center_xz"][0] + e["b"]["w"] / 2, 3.2)


def test_an_empty_bay_between_cabinets_takes_it_without_cutting():
    s = slot_in(DW, Pose((2.02, 0.4), UP), [cab("a", 1.4, 0.6), cab("b", 2.6, 0.6)])  # 1.7 ~ 2.3 빈 칸
    assert s.edits == []
    assert near(s.pose.center_xz[0], 2.0)


def test_a_cabinet_that_must_stay_is_not_cut():
    assert slot_in(DW, Pose((2.0, 0.4), UP), [cab("c1", 2.0, 1.8)], keep={"c1"}) is None
    s = slot_in(DW, Pose((2.9 + 0.299 + 0.05, 0.4), UP), [cab("c1", 2.0, 1.8)], keep={"c1"})
    assert s is not None and s.edits == []  # 옆에 붙이는 것은 된다


def test_slotting_twice_changes_nothing_more():
    cabs = [cab("c1", 2.0, 1.8)]
    s = slot_in(DW, Pose((2.0, 0.5), UP), cabs)
    e = by_id(s)
    after = [cab("c1", e["c1"]["center_xz"][0], e["c1"]["w"]), cab("c2", e["new"]["center_xz"][0], e["new"]["w"])]
    again = slot_in(DW, s.pose, after)
    assert again.edits == []
    assert near(again.pose.center_xz[0], s.pose.center_xz[0], 1e-6) and near(again.pose.center_xz[1], s.pose.center_xz[1], 1e-6)


def test_cabinets_along_another_wall_are_measured_in_their_own_direction():
    # 벽 w4(x=0)에 붙은 하부장: 정면이 +x (yaw 0)
    c = cab("c1", 0.35, 1.8, y=1.5, yaw=0.0)
    s = slot_in(DW, Pose((0.45, 1.5), UP), [c])
    assert near(s.pose.yaw_rad, 0.0)
    assert near(s.pose.center_xz[0], 0.35 + 0.3 - 0.02 - 0.567 / 2) and near(s.pose.center_xz[1], 1.5)


# ---------- 키큰장 ----------
TALL = (0.914, 1.86, 0.709)


def test_low_items_ignore_tall_cabinets_and_tall_items_ignore_base_cabinets():
    assert slot_in(DW, Pose((2.0, 0.4), UP), [cab("t", 2.0, 0.6, "decor:tallcab", h=2.0)]) is None
    assert slot_in(TALL, Pose((2.0, 0.4), UP), [cab("c1", 2.0, 1.8)]) is None


def test_a_deep_fridge_keeps_its_back_on_the_cabinet_back_and_its_side_gap():
    cabs = [cab("t1", 1.0, 0.6, "decor:tallcab", h=2.0), cab("t2", 2.6, 0.6, "decor:tallcab", h=2.0)]
    s = slot_in(TALL, Pose((1.8, 0.45), UP), cabs, side_m=0.004)  # 1.3 ~ 2.3 빈 칸
    assert s.edits == []
    assert near(s.pose.center_xz[1] - 0.709 / 2, 0.05, 2e-3)
    assert s.pose.center_xz[0] - 0.457 >= 1.3 + 0.004 - 1e-9


def test_a_fridge_taller_than_the_cabinet_does_not_slot():
    assert slot_in(TALL, Pose((2.0, 0.4), UP), [cab("t", 2.0, 1.2, "decor:tallcab", h=1.8)]) is None


# ---------- 위를 덮는 상판 ----------
def test_cover_joins_the_countertop_over_a_slotted_dishwasher():
    c = cover(DW, Pose((2.9 + 0.299, FRONT_Y), UP), [cab("c1", 2.0, 1.8, hex="#DDDDDD")])
    assert c["top_m"] == 0.85 and c["depth_m"] == 0.6 and c["look"] == "basecab" and c["hex"] == "#DDDDDD"
    assert near(c["off_m"], 0.35 - FRONT_Y)
    assert c["left_m"] >= 0 and c["right_m"] == 0


def test_no_cover_away_from_the_run_or_turned():
    cabs = [cab("c1", 2.0, 1.8)]
    assert cover(DW, Pose((2.9 + 0.299 + 0.2, FRONT_Y), UP), cabs) is None
    assert cover(DW, Pose((2.9 + 0.299, FRONT_Y + 0.2), UP), cabs) is None
    assert cover(DW, Pose((2.9 + 0.299, FRONT_Y), 0.0), cabs) is None
