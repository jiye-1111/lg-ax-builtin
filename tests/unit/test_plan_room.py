"""도면에서 읽은 벽·문·창(mm)을 room.json으로 바꾸는 규칙.

도면을 읽는 쪽(AI)은 좌표가 조금씩 어긋난다. 길이·위치는 여기 코드가 다듬고 걸러 낸다.
"""
import pytest

from core.models import Room
from worker.plan_room import PlanOpening, PlanRead, PlanWall, room_from_plan


def rect(w=5200, d=3600, **kw):
    walls = [PlanWall(x1=0, y1=0, x2=w, y2=0), PlanWall(x1=w, y1=0, x2=w, y2=d),
             PlanWall(x1=w, y1=d, x2=0, y2=d), PlanWall(x1=0, y1=d, x2=0, y2=0)]
    return PlanRead(readable=True, scale_from="dimensions", walls=walls, **kw)


def test_rectangle_becomes_four_walls_in_metres():
    room = room_from_plan(rect())
    assert isinstance(room, Room) and room.source == "floorplan_image"
    assert [w.scanned.length_m for w in room.walls] == [5.2, 3.6, 5.2, 3.6]
    assert all(w.scanned.height_m == 2.4 for w in room.walls)
    assert room.walls[0].start == (0.0, 0.0) and room.walls[0].end == (5.2, 0.0)


def test_origin_moves_to_the_corner():
    plan = rect()
    for w in plan.walls:
        w.x1 += 12000; w.x2 += 12000; w.y1 -= 800; w.y2 -= 800
    room = room_from_plan(plan)
    xs = [p[0] for w in room.walls for p in (w.start, w.end)]
    ys = [p[1] for w in room.walls for p in (w.start, w.end)]
    assert min(xs) == 0 and min(ys) == 0 and max(xs) == 5.2 and max(ys) == 3.6


def test_slightly_crooked_walls_are_straightened_and_corners_meet():
    plan = rect()
    plan.walls[0].y2 = 40          # 위쪽 벽이 살짝 기울었다
    plan.walls[1].x1 = 5230        # 모서리가 30 mm 어긋났다
    room = room_from_plan(plan)
    for w in room.walls:
        assert w.start[0] == w.end[0] or w.start[1] == w.end[1]
    ends = {w.start for w in room.walls} | {w.end for w in room.walls}
    assert len(ends) == 4


def test_diagonal_wall_stays_diagonal():
    plan = rect()
    plan.walls.append(PlanWall(x1=0, y1=0, x2=2000, y2=2000))
    room = room_from_plan(plan)
    assert any(w.start[0] != w.end[0] and w.start[1] != w.end[1] for w in room.walls)


def test_stubs_and_duplicates_are_dropped():
    plan = rect()
    plan.walls += [PlanWall(x1=100, y1=100, x2=180, y2=100), PlanWall(x1=5200, y1=0, x2=0, y2=0)]
    assert len(room_from_plan(plan).walls) == 4


def test_openings_sit_on_their_wall():
    plan = rect(openings=[
        PlanOpening(type="door", wall=2, offset_mm=600, width_mm=900),
        PlanOpening(type="window", wall=1, offset_mm=800, width_mm=1800),
        PlanOpening(type="sliding_door", wall=0, offset_mm=4000, width_mm=2400),  # 벽 끝을 넘는다
    ])
    room = room_from_plan(plan)
    door, win, slide = room.openings
    assert (door.type, door.wall_id, door.offset_m, door.width_m, door.height_m, door.sill_m) == ("door", "w3", 0.6, 0.9, 2.1, 0.0)
    assert (win.type, win.height_m, win.sill_m) == ("window", 1.2, 0.9)
    assert slide.type == "window" and slide.sill_m == 0.0 and slide.height_m == 2.1
    assert slide.offset_m + slide.width_m <= 5.2  # 벽 안으로 밀어 넣는다


def test_opening_on_a_missing_or_tiny_wall_is_skipped():
    plan = rect(openings=[PlanOpening(type="door", wall=9, offset_mm=0, width_mm=900),
                          PlanOpening(type="door", wall=0, offset_mm=100, width_mm=20)])
    assert room_from_plan(plan).openings == []


@pytest.mark.parametrize("plan, why", [
    (PlanRead(readable=False, reason="사진이 흐려요", scale_from="none", walls=[]), "흐려요"),
    (PlanRead(readable=True, scale_from="none", walls=rect().walls), "치수"),
    (PlanRead(readable=True, scale_from="dimensions", walls=rect().walls[:2]), "벽"),
    (rect(w=90000, d=3600), "크기"),
    (rect(w=600, d=500), "크기"),
])
def test_unusable_plans_say_why(plan, why):
    with pytest.raises(ValueError, match=why):
        room_from_plan(plan)


# ---------- 스캔 + 도면: 도면 치수로 벽 길이 보정 ----------
from core.models import ScannedDims, Wall  # noqa: E402
from worker.plan_room import corrections  # noqa: E402


def scan_room(lengths):
    walls, x = [], 0.0
    for i, n in enumerate(lengths, 1):
        walls.append(Wall(wall_id=f"s{i}", start=(x, 0), end=(x + n, 0), scanned=ScannedDims(length_m=n, height_m=2.4)))
        x += n
    return Room(walls=walls)


def test_scan_walls_take_the_matching_plan_length():
    plan = room_from_plan(rect())                      # 5.2 × 3.6
    fix = corrections(scan_room([5.17, 3.63, 5.22, 3.58]), plan)
    assert fix == {"s1": 5.2, "s2": 3.6, "s3": 5.2, "s4": 3.6}


def test_walls_far_from_any_plan_length_are_left_alone():
    plan = room_from_plan(rect())
    fix = corrections(scan_room([5.17, 2.9, 0.6, 3.6]), plan)
    assert fix == {"s1": 5.2}  # 2.9는 맞는 벽이 없고, 0.6은 너무 짧고, 3.6은 이미 같다


def test_ambiguous_match_is_left_alone():
    # 도면에 3.50과 3.56이 둘 다 있으면 3.53짜리 스캔 벽은 어느 쪽인지 알 수 없다
    plan = room_from_plan(PlanRead(readable=True, scale_from="dimensions", walls=[
        PlanWall(x1=0, y1=0, x2=3500, y2=0), PlanWall(x1=3500, y1=0, x2=3500, y2=3560),
        PlanWall(x1=3500, y1=3560, x2=0, y2=3560), PlanWall(x1=0, y1=3560, x2=0, y2=0)]))
    assert corrections(scan_room([3.53]), plan) == {}
