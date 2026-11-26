"""자유 배치 판정 (plans/virtual-remodel.md S2) — 테스트 먼저.

좌표: 4m x 3m 방, 벽 두께 0.1(중심선 기준 안쪽 면 0.05).
yaw = 제품 정면 방향. UP(π/2)이면 정면이 +y, 등이 -y(벽 w1) 쪽.
"""
import math

import pytest

from core.models import BBox, Clearance, Dims, Opening, Product, Room, RoomObject, ScannedDims, Wall
from recommender.fit import FitConfig, Verdict
from recommender.pose import Pose, check_pose, snap_to_wall


def room(openings=(), objects=(), h=2.4):
    walls = [
        Wall(wall_id="w1", start=(0, 0), end=(4, 0), thickness_m=0.1, scanned=ScannedDims(length_m=4.0, height_m=h)),
        Wall(wall_id="w2", start=(4, 0), end=(4, 3), thickness_m=0.1, scanned=ScannedDims(length_m=3.0, height_m=h)),
        Wall(wall_id="w3", start=(4, 3), end=(0, 3), thickness_m=0.1, scanned=ScannedDims(length_m=4.0, height_m=h)),
        Wall(wall_id="w4", start=(0, 3), end=(0, 0), thickness_m=0.1, scanned=ScannedDims(length_m=3.0, height_m=h)),
    ]
    return Room(walls=walls, openings=list(openings), objects=list(objects))


def fridge(w=900, h=1800, d=700, side=5, top=10, back=50, sku="T-RF", category="refrigerator", install_type="built_in"):
    return Product(
        sku=sku, name="테스트 냉장고", category=category, zone_fit=["kitchen"], install_type=install_type,
        product_dims_mm=Dims(w=w, h=h, d=d), clearance_mm=Clearance(side=side, top=top, back=back),
        source_url=None, source_checked_at=None, demo_only=True,
    )


def free(**kw):
    """방 가운데에도 세울 수 있는 제품 (빌트인은 벽이나 장에 붙여야 해서 따로 본다: test_mount.py)."""
    return fridge(category="air_purifier", install_type="freestanding", **kw)


UP = math.pi / 2
CFG = FitConfig(margin_scanned_mm=30, margin_measured_mm=5)
codes = lambda r: {x["code"] for x in r.reasons}  # noqa: E731


def test_open_floor_is_fit():
    r = check_pose(room(), free(), Pose((2.0, 1.5), 0.0), CFG)
    assert r.verdict == Verdict.FIT and not r.reasons


def test_unknown_dims_is_unknown():
    r = check_pose(room(), fridge(w=None), Pose((2.0, 1.5), 0.0), CFG)
    assert r.verdict == Verdict.UNKNOWN and "dims_unknown" in codes(r)


def test_outside_room_is_no_fit():
    r = check_pose(room(), fridge(), Pose((6.0, 1.5), 0.0), CFG)
    assert r.verdict == Verdict.NO_FIT and "outside_room" in codes(r)


def test_through_wall_is_no_fit():
    r = check_pose(room(), fridge(), Pose((2.0, 0.2), UP), CFG)  # 깊이 0.7 → 벽 w1 관통
    assert r.verdict == Verdict.NO_FIT and "hits_wall" in codes(r)


def test_back_clearance_blocked_is_no_fit():
    # 제품 뒷면 y=0.06 → 벽 안쪽 면 0.05에서 1cm, 뒤 이격 50mm 부족
    r = check_pose(room(), fridge(), Pose((2.0, 0.06 + 0.35), UP), CFG)
    assert r.verdict == Verdict.NO_FIT and "clearance_blocked" in codes(r)


def test_within_margin_is_conditional():
    # 뒤 이격 50mm 확보 + 마진 30mm 중 20mm만 남김
    r = check_pose(room(), fridge(), Pose((2.0, 0.05 + 0.05 + 0.02 + 0.35), UP), CFG)
    assert r.verdict == Verdict.CONDITIONAL and "tight" in codes(r)


def test_overlap_scanned_object_unless_hidden():
    chair = RoomObject(object_id="o1", category="chair", bbox_m=BBox(w=0.5, h=0.8, d=0.5), position=(2.0, 0.4, 1.5))
    r = check_pose(room(objects=[chair]), free(), Pose((2.0, 1.5), 0.0), CFG)
    assert r.verdict == Verdict.NO_FIT and "overlaps_object" in codes(r)
    r = check_pose(room(objects=[chair]), free(), Pose((2.0, 1.5), 0.0), CFG, hidden={"o1"})
    assert r.verdict == Verdict.FIT


def test_overlap_other_placement():
    other = {"placement_id": "pl1", "center_xz": [2.5, 1.5], "yaw_rad": UP, "size_m": [0.9, 1.8, 0.7]}
    r = check_pose(room(), fridge(), Pose((2.0, 1.5), UP), CFG, others=[other])
    assert r.verdict == Verdict.NO_FIT and "overlaps_placement" in codes(r)


def test_ceiling_too_low():
    r = check_pose(room(h=1.80), fridge(), Pose((2.0, 1.5), 0.0), CFG)
    assert r.verdict == Verdict.NO_FIT and "ceiling_low" in codes(r)


def test_nothing_may_stand_where_a_scanned_door_swings():
    door = Opening(opening_id="d1", type="door", wall_id="w1", offset_m=1.0, width_m=0.9, height_m=2.1)
    # 문 바로 앞(문짝 폭 안)에 본체가 걸치면 문을 못 연다
    r = check_pose(room(openings=[door]), free(w=600, d=600), Pose((1.45, 0.75), 0.0), CFG)
    assert r.verdict == Verdict.NO_FIT and "door_blocked" in codes(r)
    assert next(x for x in r.reasons if x["code"] == "door_blocked")["label"] == "여기 두면 문을 열 수 없어요"
    # 문짝 폭보다 멀리 떨어지면 된다
    r = check_pose(room(openings=[door]), free(w=600, d=600), Pose((1.45, 1.4), 0.0), CFG)
    assert "door_blocked" not in codes(r)
    # 문틀 바로 옆에 붙여 둔 것은 막은 것이 아니다
    r = check_pose(room(openings=[door]), free(w=600, d=600), Pose((2.2, 0.36), 0.0), CFG)
    assert "door_blocked" not in codes(r)


def test_wide_door_keeps_only_one_leaf_depth_clear():
    door = Opening(opening_id="d1", type="door", wall_id="w1", offset_m=1.0, width_m=1.8, height_m=2.1)
    r = check_pose(room(openings=[door]), free(w=600, d=600), Pose((1.9, 1.3), 0.0), CFG)
    assert "door_blocked" not in codes(r)


def test_nothing_may_stand_in_front_of_a_placed_door_either():
    door = {"placement_id": "pl9", "sku": "decor:door", "center_xz": [2.0, 1.5], "yaw_rad": math.pi / 2, "size_m": [0.9, 2.1, 0.14]}
    r = check_pose(room(), free(w=600, d=600), Pose((2.0, 2.0), 0.0), CFG, others=[door])
    assert r.verdict == Verdict.NO_FIT and "door_blocked" in codes(r)
    r = check_pose(room(), free(w=600, d=600), Pose((3.2, 2.0), 0.0), CFG, others=[door])
    assert "door_blocked" not in codes(r)


def test_covering_window_is_conditional():
    win = Opening(opening_id="win1", type="window", wall_id="w1", offset_m=1.5, width_m=1.0, height_m=1.0, sill_m=0.9)
    pose = snap_to_wall(room(openings=[win]), fridge(), Pose((2.0, 0.6), 0.3), CFG)
    r = check_pose(room(openings=[win]), fridge(), pose, CFG)
    assert r.verdict == Verdict.CONDITIONAL and "covers_window" in codes(r)
    # 창턱보다 낮은 제품은 괜찮다
    low = fridge(h=850)
    r = check_pose(room(openings=[win]), low, snap_to_wall(room(openings=[win]), low, Pose((2.0, 0.6), 0.0), CFG), CFG)
    assert "covers_window" not in codes(r)


def test_snap_aligns_back_to_nearest_wall():
    p = snap_to_wall(room(), fridge(), Pose((3.0, 0.7), 0.4), CFG)
    assert p.wall_id == "w1"
    assert p.yaw_rad == pytest.approx(UP, abs=1e-9)
    # 뒷면 = 벽 안쪽 면 0.05 + 뒤 이격 0.05 + 마진 0.03 → 중심 y = 0.13 + 0.35
    assert p.center_xz[1] == pytest.approx(0.48, abs=1e-6)
    assert check_pose(room(), fridge(), p, CFG).verdict == Verdict.FIT


def test_snap_on_side_wall_rotates():
    p = snap_to_wall(room(), fridge(), Pose((3.7, 1.5), 0.0), CFG)
    assert p.wall_id == "w2"
    # 정면이 -x(방 안쪽) → yaw = 180°
    assert abs(p.yaw_rad) == pytest.approx(math.pi, abs=1e-9)


def test_snap_ignores_far_walls():
    p = snap_to_wall(room(), fridge(), Pose((2.0, 1.5), 0.2), CFG)
    assert p.wall_id is None and p.center_xz == (2.0, 1.5) and p.yaw_rad == 0.2


def test_result_is_serializable():
    r = check_pose(room(), free(), Pose((2.0, 1.5), 0.0), CFG).to_dict()
    assert r["verdict"] == "fit" and len(r["footprint"]) == 4 and r["pose"]["center_xz"] == [2.0, 1.5]


# ---- 일반(프리스탠딩) 가전: 앞쪽 문 열림 공간 ----
def washer(door=580, install="freestanding", category="washer"):
    return Product(
        sku="T-WM", name="테스트 세탁기", category=category, zone_fit=["laundry"], install_type=install,
        product_dims_mm=Dims(w=700, h=990, d=830), clearance_mm=Clearance(side=5, top=10, back=50),
        door_swing_mm=door, source_url=None, source_checked_at=None, demo_only=True,
    )


TABLE = RoomObject(object_id="t1", category="table", bbox_m=BBox(w=1.0, h=0.75, d=0.5), position=(2.0, 0.375, 1.3))
AT_WALL = Pose((2.0, 0.05 + 0.05 + 0.03 + 0.415), UP)  # 등이 벽 w1, 앞면 y=0.96


def test_freestanding_with_room_to_open_door_is_fit():
    r = check_pose(room(), washer(), AT_WALL, CFG)
    assert r.verdict == Verdict.FIT and not r.reasons


def test_freestanding_door_space_blocked_is_no_fit():
    # 문 열림 580mm → 앞면에서 y=1.54까지 필요한데 테이블이 y=1.05부터 있음
    r = check_pose(room(objects=[TABLE]), washer(), AT_WALL, CFG)
    assert r.verdict == Verdict.NO_FIT and "front_blocked" in codes(r)


def test_built_in_ignores_front_door_space():
    r = check_pose(room(objects=[TABLE]), washer(install="built_in"), AT_WALL, CFG)
    # 문 열림 공간은 안 보지만, 바로 앞 탁자는 통로를 막으니 조건부로 알린다
    assert "front_blocked" not in codes(r) and codes(r) == {"passage_narrow"} and r.verdict == Verdict.CONDITIONAL


def test_freestanding_door_space_unknown_uses_default_and_is_conditional():
    cfg = FitConfig(margin_scanned_mm=30, margin_measured_mm=5, front_default_mm=600)
    r = check_pose(room(), washer(door=None, category="refrigerator"), AT_WALL, cfg)
    assert r.verdict == Verdict.CONDITIONAL and "front_space_assumed" in codes(r)
    r = check_pose(room(objects=[TABLE]), washer(door=None, category="refrigerator"), AT_WALL, cfg)
    assert r.verdict == Verdict.NO_FIT and "front_blocked" in codes(r)


def test_doorless_freestanding_needs_no_front_space():
    r = check_pose(room(objects=[TABLE]), washer(door=None, category="tv"), AT_WALL, CFG)
    assert r.verdict == Verdict.FIT and not r.reasons


# ---- 들여오는 길: 방 문 폭 ----
def door(width, oid="d1"):
    return Opening(opening_id=oid, type="door", wall_id="w3", offset_m=0.2, width_m=width, height_m=2.0)


def test_product_wider_than_every_door_needs_entry_check():
    r = check_pose(room(openings=[door(0.65)]), free(), Pose((2.0, 1.2), 0.0), CFG)  # 가장 얇은 쪽 0.7 m
    assert r.verdict == Verdict.CONDITIONAL and codes(r) == {"entry_narrow"}
    assert r.reasons[0]["ref"] == "d1"


def test_widest_door_decides_entry():
    r = check_pose(room(openings=[door(0.65), door(0.9, "d2").model_copy(update={"offset_m": 2.5})]),
                   fridge(), Pose((2.0, 1.2), 0.0), CFG)
    assert "entry_narrow" not in codes(r)


def test_no_scanned_door_skips_entry_check():
    r = check_pose(room(), fridge(), Pose((2.0, 1.5), 0.0), CFG)
    assert "entry_narrow" not in codes(r)


# ---- 통행 공간: 문 열림 공간 앞으로 사람이 지나갈 통로 ----
def test_passage_free_is_fit():
    r = check_pose(room(), washer(), AT_WALL, CFG)  # 앞면 y=0.96, 통로 끝 0.96+0.58+0.6=2.14 < 벽 2.95
    assert "passage_narrow" not in codes(r)


def test_furniture_in_passage_is_conditional():
    # 문 열림 공간(~1.54) 뒤, 통로(1.54~2.14) 안에 탁자
    t = RoomObject(object_id="t2", category="table", bbox_m=BBox(w=1.0, h=0.75, d=0.3), position=(2.0, 0.375, 1.9))
    r = check_pose(room(objects=[t]), washer(), AT_WALL, CFG)
    assert r.verdict == Verdict.CONDITIONAL and codes(r) == {"passage_narrow"}
    assert r.reasons[0]["ref"] == "t2"


def test_passage_reported_once_and_not_when_door_space_blocked():
    r = check_pose(room(objects=[TABLE]), washer(), AT_WALL, CFG)  # 문 열림 공간이 이미 막힘
    assert "front_blocked" in codes(r) and "passage_narrow" not in codes(r)


def test_built_in_checks_passage_from_front_face():
    # 빌트인은 문 열림 공간을 따로 안 보지만, 앞 통로는 본다 (앞면 0.96 ~ 1.56)
    t = RoomObject(object_id="t3", category="table", bbox_m=BBox(w=1.0, h=0.75, d=0.3), position=(2.0, 0.375, 1.3))
    r = check_pose(room(objects=[t]), washer(install="built_in"), AT_WALL, CFG)
    assert codes(r) == {"passage_narrow"}


def test_doorless_products_skip_passage():
    t = RoomObject(object_id="t3", category="table", bbox_m=BBox(w=1.0, h=0.75, d=0.3), position=(2.0, 0.375, 1.3))
    r = check_pose(room(objects=[t]), washer(door=None, category="tv"), AT_WALL, CFG)
    assert "passage_narrow" not in codes(r)


# ---- 알맞은 자리 찾기 (자동 배치) ----
from recommender.pose import find_spot  # noqa: E402


def test_find_spot_puts_product_against_a_wall():
    r = find_spot(room(), fridge(), CFG)
    assert r is not None and r.verdict == Verdict.FIT and r.pose.wall_id
    # 등이 벽에 붙어 있다: 다시 판정해도 같은 결과
    assert check_pose(room(), fridge(), r.pose, CFG).verdict == Verdict.FIT


def test_find_spot_avoids_furniture_and_other_products():
    # 벽 w1 앞을 탁자가 막고 있으면 다른 자리를 고른다
    t = RoomObject(object_id="t9", category="table", bbox_m=BBox(w=3.8, h=0.75, d=1.2), position=(2.0, 0.375, 0.65))
    r = find_spot(room(objects=[t]), fridge(), CFG)
    assert r is not None and r.verdict == Verdict.FIT and r.pose.wall_id != "w1"


def test_find_spot_returns_none_when_nothing_fits():
    r = find_spot(room(h=1.5), fridge(), CFG)  # 천장이 낮아 어디에도 안 들어감
    assert r is None


def test_find_spot_unknown_dims_is_none():
    assert find_spot(room(), fridge(w=None), CFG) is None


def test_removed_wall_is_not_an_obstacle():
    # 벽 철거: hidden에 벽 id를 넣으면 그 벽은 장애물이 아니다 (방 안 판정은 나머지 벽으로)
    pose = Pose((2.0, 0.2), UP)
    assert "hits_wall" in codes(check_pose(room(), fridge(), pose, CFG))
    assert "hits_wall" not in codes(check_pose(room(), fridge(), pose, CFG, hidden=["w1"]))
