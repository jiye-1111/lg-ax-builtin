"""스캔 가구가 어느 쪽을 보는지 정하기 (worker/orient.py).

RoomPlan 상자에는 앞뒤가 없다. 긴 변 방향만 알 수 있어서, 벽과 식탁을 보고 앞을 정한다.
room.json의 yaw는 폭(w) 축의 방향이고, 정면은 그 축에서 왼쪽으로 90° = (-sin yaw, cos yaw).
"""
import math

import pytest

from core.models import BBox, RoomObject, ScannedDims, Wall
from worker.orient import front_of, orient_objects


def wall(i, a, b):
    return Wall(wall_id=f"w{i}", start=a, end=b, thickness_m=0.1,
                scanned=ScannedDims(length_m=math.dist(a, b), height_m=2.4))


# 6 × 4 m 방: z=0 위쪽 벽, z=4 아래쪽 벽
WALLS = [wall(1, (0, 0), (6, 0)), wall(2, (6, 0), (6, 4)), wall(3, (6, 4), (0, 4)), wall(4, (0, 4), (0, 0))]


def obj(i, cat, x, z, w, d, yaw=0.0, h=0.8):
    return RoomObject(object_id=f"o{i}", category=cat, bbox_m=BBox(w=w, h=h, d=d), position=(x, h / 2, z), yaw_rad=yaw)


def facing(o, target):
    f = front_of(o.yaw_rad)
    v = (target[0] - o.position[0], target[1] - o.position[2])
    return (f[0] * v[0] + f[1] * v[1]) / math.hypot(*v)


def test_sofa_against_a_wall_turns_its_back_to_that_wall():
    sofa = obj(1, "sofa", 3.0, 3.5, 2.0, 0.9, yaw=0.0)  # 아래쪽 벽에 붙어 있고, 앞이 벽을 보고 있다
    out, = orient_objects([sofa], WALLS)
    assert front_of(out.yaw_rad) == pytest.approx((0.0, -1.0), abs=1e-3)  # 방 안쪽(-z)을 본다
    assert (out.bbox_m.w, out.bbox_m.d) == (2.0, 0.9) and out.position == sofa.position


def test_sofa_already_facing_the_room_is_left_alone():
    sofa = obj(1, "sofa", 3.0, 0.5, 2.0, 0.9, yaw=0.0)  # 위쪽 벽에 붙어 있고 앞이 방 안쪽(+z)
    out, = orient_objects([sofa], WALLS)
    assert out.yaw_rad == pytest.approx(0.0)


def test_chairs_face_the_table_whichever_side_they_are_on():
    table = obj(1, "table", 3.0, 2.0, 1.4, 0.8)
    # 의자는 거의 정사각형이라 스캔의 긴 변이 폭인지 깊이인지 알 수 없다
    chairs = [obj(2, "chair", 2.7, 1.35, 0.48, 0.45, yaw=math.pi / 2), obj(3, "chair", 3.3, 2.65, 0.48, 0.45, yaw=math.pi / 2),
              obj(4, "chair", 1.95, 2.0, 0.48, 0.45, yaw=0.0), obj(5, "chair", 4.05, 2.0, 0.45, 0.48, yaw=0.0)]
    out = orient_objects([table, *chairs], WALLS)
    centre = {2: (2.7, 2.0), 3: (3.3, 2.0), 4: (3.0, 2.0), 5: (3.0, 2.0)}
    for o in out[1:]:
        assert facing(o, centre[int(o.object_id[1:])]) > 0.95, o.object_id
    # 90° 돌린 의자는 폭과 깊이를 바꿔 적는다 (차지하는 자리는 그대로)
    assert (out[1].bbox_m.w, out[1].bbox_m.d) == (0.45, 0.48)
    assert out[0] == table


def test_bed_lies_along_its_long_side_with_the_head_at_the_wall():
    bed = obj(1, "bed", 1.1, 2.0, 2.1, 1.6, yaw=0.0, h=0.9)  # 긴 변이 x 방향, 왼쪽 벽(x=0)에 머리
    out, = orient_objects([bed], WALLS)
    assert (out.bbox_m.w, out.bbox_m.d) == (1.6, 2.1)
    assert front_of(out.yaw_rad) == pytest.approx((1.0, 0.0), abs=1e-3)  # 발치가 방 안쪽(+x)


def test_furniture_in_the_middle_of_the_room_is_left_alone():
    t = obj(1, "sofa", 3.0, 2.0, 2.0, 0.9, yaw=0.3)
    assert orient_objects([t], WALLS) == [t]
