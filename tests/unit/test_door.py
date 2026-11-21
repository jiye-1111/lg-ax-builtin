"""문 달기: 벽(스캔 벽·가벽)에 겹쳐 달 수 있고, 앞쪽에 문짝 폭만큼 비어 있어야 열린다."""
import math

from core.decor import decor_product
from core.models import Room, ScannedDims, Wall
from recommender.fit import FitConfig
from recommender.pose import Pose, check_pose, snap_door

CFG = FitConfig(scanned_max_conditional=False)
UP = math.pi / 2  # 앞쪽이 +y (방 안쪽)
DOOR = decor_product("decor:door")


def room():
    pts = [(0, 0), (6, 0), (6, 4), (0, 4)]
    return Room(walls=[Wall(wall_id=f"w{i + 1}", start=pts[i], end=pts[(i + 1) % 4], thickness_m=0.2,
                            scanned=ScannedDims(length_m=6 if i % 2 == 0 else 4, height_m=2.4)) for i in range(4)])


def codes(r):
    return {x["code"] for x in r.reasons}


def test_door_product_needs_its_own_width_in_front():
    assert DOOR.door_swing_mm == DOOR.product_dims_mm.w == 900
    assert decor_product("decor:sofa").door_swing_mm is None


def test_door_can_sit_in_a_wall_and_opens_when_front_is_empty():
    r = check_pose(room(), DOOR, Pose((3.0, 0.0), UP), CFG)
    assert r.verdict.value != "no_fit", r.reasons
    assert not codes(r) & {"hits_wall", "outside_room", "clearance_blocked", "front_blocked"}


def test_door_cannot_open_when_something_stands_in_front():
    sofa = {"placement_id": "pl1", "sku": "decor:sofa", "center_xz": [3.0, 0.7], "yaw_rad": UP, "size_m": [2.0, 0.85, 0.9]}
    r = check_pose(room(), DOOR, Pose((3.0, 0.0), UP), CFG, others=[sofa])
    assert r.verdict.value == "no_fit"
    blocked = next(x for x in r.reasons if x["code"] == "front_blocked")
    assert blocked["label"] == "문을 열 공간이 부족해요" and blocked["ref"] == "pl1"


def test_door_fits_in_a_partition_wall_but_not_through_furniture():
    wall = {"placement_id": "pl1", "sku": "decor:wall", "center_xz": [3.0, 2.0], "yaw_rad": UP, "size_m": [3.0, 2.4, 0.1]}
    assert check_pose(room(), DOOR, Pose((3.0, 2.0), UP), CFG, others=[wall]).verdict.value != "no_fit"
    desk = {**wall, "sku": "decor:desk", "size_m": [1.2, 0.73, 0.6]}
    assert "overlaps_placement" in codes(check_pose(room(), DOOR, Pose((3.0, 2.0), UP), CFG, others=[desk]))


def test_other_walls_in_the_swing_still_block_the_door():
    # 모서리 바로 옆: 문은 w1에 달려 있지만 앞쪽 0.9 m 안에 다른 가벽이 가로막는다
    cross = {"placement_id": "pl2", "sku": "decor:wall", "center_xz": [3.0, 0.6], "yaw_rad": UP, "size_m": [2.0, 2.4, 0.1]}
    assert "front_blocked" in codes(check_pose(room(), DOOR, Pose((3.0, 0.0), UP), CFG, others=[cross]))


def test_ordinary_furniture_still_hits_walls():
    assert "hits_wall" in codes(check_pose(room(), decor_product("decor:desk"), Pose((3.0, 0.0), UP), CFG))


def test_snap_door_onto_nearest_wall_line_facing_the_pointer_side():
    segs = [((0.0, 0.0), (6.0, 0.0)), ((2.0, 2.0), (5.0, 2.0))]
    p = snap_door(segs, Pose((3.3, 2.25), 0.0), 0.9, snap_m=0.6)
    assert p.center_xz == (3.3, 2.0) and math.isclose(p.yaw_rad, UP)
    p = snap_door(segs, Pose((3.3, 1.8), 0.0), 0.9, snap_m=0.6)
    assert p.center_xz == (3.3, 2.0) and math.isclose(p.yaw_rad, -UP)
    # 벽 끝을 넘지 않게 당긴다
    assert snap_door(segs, Pose((5.2, 2.1), 0.0), 0.9, snap_m=0.6).center_xz == (4.55, 2.0)
    # 벽에서 멀면 그대로
    far = Pose((3.0, 1.0), 0.3)
    assert snap_door(segs, far, 0.9, snap_m=0.6) == far


def test_wall_is_not_blamed_for_the_door_mounted_in_it():
    door = {"placement_id": "pl9", "sku": "decor:door", "center_xz": [3.0, 2.0], "yaw_rad": UP, "size_m": [0.9, 2.1, 0.14]}
    r = check_pose(room(), decor_product("decor:wall", [3.0, 2.4, 0.1]), Pose((3.0, 2.0), UP), CFG, others=[door])
    assert "overlaps_placement" not in codes(r)


def test_door_must_hang_on_a_wall():
    r = check_pose(room(), DOOR, Pose((3.0, 2.0), UP), CFG)
    assert r.verdict.value == "no_fit" and "not_on_wall" in codes(r)
