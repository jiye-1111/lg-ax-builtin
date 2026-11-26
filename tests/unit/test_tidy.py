"""읽은 문·창 가운데 있을 수 없는 자리(벽이 가로지르는 문, 서로 겹친 문)를 바로잡는 규칙."""
from core.models import Opening, Room, ScannedDims, Wall
from worker.tidy import tidy_openings


def wall(wid, start, end, t=0.1):
    length = ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
    return Wall(wall_id=wid, start=start, end=end, thickness_m=t, scanned=ScannedDims(length_m=length, height_m=2.4))


def door(oid, wid, off, width=0.9):
    return Opening(opening_id=oid, type="door", wall_id=wid, offset_m=off, width_m=width, height_m=2.1)


def window(oid, wid, off, width=1.2):
    return Opening(opening_id=oid, type="window", wall_id=wid, offset_m=off, width_m=width, height_m=1.2, sill_m=0.9)


def box(openings, extra=()):
    walls = [wall("w1", (0, 0), (6, 0), 0.2), wall("w2", (6, 0), (6, 4), 0.2), wall("w3", (6, 4), (0, 4), 0.2), wall("w4", (0, 4), (0, 0), 0.2)]
    return Room(source="floorplan_image", walls=walls + list(extra), openings=list(openings), objects=[])


def by_id(room):
    return {o.opening_id: o for o in room.openings}


def test_good_openings_are_left_alone():
    room = box([door("d1", "w1", 1.0), window("win1", "w1", 3.0), door("d2", "w3", 2.0)])
    assert tidy_openings(room) == room


def test_door_moves_off_a_wall_that_runs_into_it():
    # 칸막이 벽이 x = 3.2에서 w1에 닿는데 문이 2.5 ~ 3.4에 걸쳐 있다
    room = box([door("d1", "w1", 2.5)], extra=[wall("w5", (3.2, 0), (3.2, 2.0))])
    d = by_id(tidy_openings(room))["d1"]
    assert d.offset_m + d.width_m <= 3.2 - 0.05 and d.offset_m >= 2.0  # 조금만 옮긴다


def test_door_with_no_room_on_its_wall_is_dropped():
    # 길이 1.2 m 벽 한가운데(0.5 m)를 다른 벽이 가로지른다: 0.9 m 문이 들어갈 자리가 없다
    cross = [wall("w5", (0, 2.0), (6, 2.0)), wall("w6", (3.2, 1.5), (3.2, 2.7))]
    room = box([door("d1", "w6", 0.2)], extra=cross)
    assert tidy_openings(room).openings == []


def test_overlapping_doors_on_one_wall_are_separated():
    room = box([door("d1", "w1", 2.0), door("d2", "w1", 2.6)])
    out = by_id(tidy_openings(room))
    a, b = sorted(out.values(), key=lambda o: o.offset_m)
    assert len(out) == 2 and b.offset_m >= a.offset_m + a.width_m + 0.05


def test_same_door_read_twice_is_kept_once():
    room = box([door("d1", "w1", 2.0), door("d2", "w1", 2.05)])
    assert [o.opening_id for o in tidy_openings(room).openings] == ["d1"]


def test_doors_at_a_corner_do_not_share_the_corner():
    # w1 끝과 w2 시작이 같은 모서리 (6, 0). 두 문이 모서리에 붙어 서로 겹친다
    room = box([door("d1", "w1", 5.1), door("d2", "w2", 0.0)])
    out = by_id(tidy_openings(room))
    assert out["d1"].offset_m + out["d1"].width_m <= 6 - 0.1
    assert out["d2"].offset_m >= 0.1


def test_window_is_never_dropped_only_moved():
    room = box([window("win1", "w1", 2.5)], extra=[wall("w5", (3.2, 0), (3.2, 2.0))])
    w = by_id(tidy_openings(room))["win1"]
    assert not (w.offset_m < 3.2 < w.offset_m + w.width_m)


def test_real_plan_home_with_a_door_through_a_wall():
    # 실제로 도면에서 읽힌 집: w8이 w5를 가로지르는데 d4(w5)와 d7(w8)이 그 자리에서 겹쳤다
    walls = [wall("w1", (0, 0), (15, 0), 0.2), wall("w2", (15, 0), (15, 9), 0.2), wall("w3", (15, 9), (0, 9), 0.2), wall("w4", (0, 9), (0, 0), 0.2),
             wall("w5", (0, 3.5), (15, 3.5)), wall("w6", (4.2, 3.5), (4.2, 9)), wall("w7", (1.2, 4.2), (3.2, 4.2)),
             wall("w8", (3.2, 3.0), (3.2, 4.2)), wall("w9", (10, 3.5), (10, 9))]
    ops = [door("d4", "w5", 2.5), door("d5", "w5", 5.5, 1.8), door("d6", "w6", 4.0), door("d7", "w8", 0.2), door("d1", "w3", 6.0, 1.2)]
    out = by_id(tidy_openings(Room(source="floorplan_image", walls=walls, openings=ops, objects=[])))
    assert "d7" not in out                                   # 들어갈 자리가 없는 문
    assert out["d4"].offset_m + out["d4"].width_m < 3.2      # 벽을 피해 옆으로
    assert out["d5"].offset_m == 5.5 and out["d6"].offset_m == 4.0 and out["d1"].offset_m == 6.0


def test_tidy_twice_changes_nothing_more():
    room = box([door("d1", "w1", 2.5), door("d2", "w1", 2.9)], extra=[wall("w5", (3.2, 0), (3.2, 2.0))])
    once = tidy_openings(room)
    assert tidy_openings(once) == once
