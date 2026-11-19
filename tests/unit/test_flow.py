"""이동 동선 (S8): 점유 격자 + A*. 6m x 4m 방, 현관문 d1은 w4(x=0) 가운데."""
import pytest

from core.models import BBox, Opening, Room, RoomObject, ScannedDims, Wall
from sim.flow import FlowConfig, plan_routes

CFG = FlowConfig(cell_m=0.05, min_width_m=0.9, body_width_m=0.6)


def room(objects=()):
    walls = [
        Wall(wall_id="w1", start=(0, 0), end=(6, 0), thickness_m=0.1, scanned=ScannedDims(length_m=6, height_m=2.4)),
        Wall(wall_id="w2", start=(6, 0), end=(6, 4), thickness_m=0.1, scanned=ScannedDims(length_m=4, height_m=2.4)),
        Wall(wall_id="w3", start=(6, 4), end=(0, 4), thickness_m=0.1, scanned=ScannedDims(length_m=6, height_m=2.4)),
        Wall(wall_id="w4", start=(0, 4), end=(0, 0), thickness_m=0.1, scanned=ScannedDims(length_m=4, height_m=2.4)),
    ]
    door = Opening(opening_id="d1", type="door", wall_id="w4", offset_m=1.5, width_m=1.0, height_m=2.1)
    return Room(walls=walls, openings=[door], objects=list(objects))


def box(oid, x, z, w, d):
    return RoomObject(object_id=oid, category="storage", bbox_m=BBox(w=w, h=1.0, d=d), position=(x, 0.5, z))


def test_open_room_route_is_short_and_wide():
    r = plan_routes(room(), {"냉장고": (5.0, 2.0)}, CFG)
    rt = r["routes"]["냉장고"]
    # 출발점은 문에서 방 안쪽 0.4 m (x≈0.45)
    assert rt["reachable"] and rt["length_m"] == pytest.approx(4.55, abs=0.1)
    assert rt["min_width_m"] >= 0.9 and rt["narrow"] == []
    assert r["entrance"]["opening_id"] == "d1"


def test_blocked_route_is_unreachable():
    # x=3에 벽처럼 꽉 막는 가구 → 반대편으로 못 감
    r = plan_routes(room([box("o1", 3.0, 2.0, 0.4, 4.0)]), {"안쪽": (5.0, 2.0)}, CFG)
    assert r["routes"]["안쪽"]["reachable"] is False


def test_narrow_gap_is_flagged():
    # 위아래에 가구를 두어 가운데 통로를 0.75 m로 만든다
    objs = [box("o1", 3.0, 0.8125, 0.4, 1.625), box("o2", 3.0, 3.1875, 0.4, 1.625)]
    rt = plan_routes(room(objs), {"안쪽": (5.0, 2.0)}, CFG)["routes"]["안쪽"]
    assert rt["reachable"] and rt["min_width_m"] == pytest.approx(0.75, abs=0.12)
    assert rt["narrow"]  # 좁은 구간 좌표가 나온다


def test_extra_obstacles_and_hidden():
    obj = box("o1", 3.0, 2.0, 0.4, 4.0)
    assert plan_routes(room([obj]), {"안쪽": (5.0, 2.0)}, CFG, hidden={"o1"})["routes"]["안쪽"]["reachable"]
    wall_of_fridges = [[(2.8, 0.0), (3.2, 0.0), (3.2, 4.0), (2.8, 4.0)]]
    assert not plan_routes(room(), {"안쪽": (5.0, 2.0)}, CFG, extra=wall_of_fridges)["routes"]["안쪽"]["reachable"]


def test_target_inside_obstacle_uses_nearest_free_cell():
    # 목표가 가구 안이면(제품 앞에 서는 자리) 가장 가까운 빈 칸까지
    r = plan_routes(room([box("o1", 5.0, 2.0, 1.0, 1.0)]), {"수납장": (5.0, 2.0)}, CFG)
    assert r["routes"]["수납장"]["reachable"]


def test_work_triangle():
    r = plan_routes(room(), {"냉장고": (5, 1), "싱크": (5, 3), "쿡탑": (3, 3)}, CFG, triangle=("냉장고", "싱크", "쿡탑"))
    assert r["triangle"]["perimeter_m"] == pytest.approx(2 + 2 + (8 ** 0.5), abs=0.01)
    assert r["assumptions"]
