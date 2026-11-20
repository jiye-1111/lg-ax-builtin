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


def fridge(w=900, h=1800, d=700, side=5, top=10, back=50, sku="T-RF"):
    return Product(
        sku=sku, name="테스트 냉장고", category="refrigerator", zone_fit=["kitchen"], install_type="built_in",
        product_dims_mm=Dims(w=w, h=h, d=d), clearance_mm=Clearance(side=side, top=top, back=back),
        source_url=None, source_checked_at=None, demo_only=True,
    )


UP = math.pi / 2
CFG = FitConfig(margin_scanned_mm=30, margin_measured_mm=5)
codes = lambda r: {x["code"] for x in r.reasons}  # noqa: E731


def test_open_floor_is_fit():
    r = check_pose(room(), fridge(), Pose((2.0, 1.5), 0.0), CFG)
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
    r = check_pose(room(objects=[chair]), fridge(), Pose((2.0, 1.5), 0.0), CFG)
    assert r.verdict == Verdict.NO_FIT and "overlaps_object" in codes(r)
    r = check_pose(room(objects=[chair]), fridge(), Pose((2.0, 1.5), 0.0), CFG, hidden={"o1"})
    assert r.verdict == Verdict.FIT


def test_overlap_other_placement():
    other = {"placement_id": "pl1", "center_xz": [2.5, 1.5], "yaw_rad": UP, "size_m": [0.9, 1.8, 0.7]}
    r = check_pose(room(), fridge(), Pose((2.0, 1.5), UP), CFG, others=[other])
    assert r.verdict == Verdict.NO_FIT and "overlaps_placement" in codes(r)


def test_ceiling_too_low():
    r = check_pose(room(h=1.80), fridge(), Pose((2.0, 1.5), 0.0), CFG)
    assert r.verdict == Verdict.NO_FIT and "ceiling_low" in codes(r)


def test_door_swing_one_side_is_conditional_both_sides_no_fit():
    door = Opening(opening_id="d1", type="door", wall_id="w1", offset_m=1.0, width_m=0.9, height_m=2.1)
    # 문 안쪽(방 쪽) 열림 범위에만 걸침 → 반대쪽으로 열린다고 보고 조건부
    r = check_pose(room(openings=[door]), fridge(w=600, d=600), Pose((1.45, 0.75), 0.0), CFG)
    assert r.verdict == Verdict.CONDITIONAL and "door_swing_assumed" in codes(r)


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
    r = check_pose(room(), fridge(), Pose((2.0, 1.5), 0.0), CFG).to_dict()
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
    assert "front_blocked" not in codes(r) and r.verdict == Verdict.FIT


def test_freestanding_door_space_unknown_uses_default_and_is_conditional():
    cfg = FitConfig(margin_scanned_mm=30, margin_measured_mm=5, front_default_mm=600)
    r = check_pose(room(), washer(door=None, category="refrigerator"), AT_WALL, cfg)
    assert r.verdict == Verdict.CONDITIONAL and "front_space_assumed" in codes(r)
    r = check_pose(room(objects=[TABLE]), washer(door=None, category="refrigerator"), AT_WALL, cfg)
    assert r.verdict == Verdict.NO_FIT and "front_blocked" in codes(r)


def test_doorless_freestanding_needs_no_front_space():
    r = check_pose(room(objects=[TABLE]), washer(door=None, category="tv"), AT_WALL, CFG)
    assert r.verdict == Verdict.FIT and not r.reasons
