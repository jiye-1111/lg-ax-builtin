"""바닥 모양: 바깥벽을 따라 한 바퀴 돈 선. 방 안쪽 벽은 빼고, 벽이 이어지지 않으면 없다(None)."""
from types import SimpleNamespace as W

from worker.outline import floor_outline, is_rectangle


def walls(*segs):
    return [W(start=a, end=b) for a, b in segs]


L_SHAPE = [((0, 0), (8, 0)), ((8, 0), (8, 4)), ((8, 4), (5, 4)), ((5, 4), (5, 7)), ((5, 7), (0, 7)), ((0, 7), (0, 0))]


def area(pts):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2


def test_rectangle_gives_four_corners():
    out = floor_outline(walls(((0, 0), (5, 0)), ((5, 0), (5, 3)), ((5, 3), (0, 3)), ((0, 3), (0, 0))))
    assert sorted(out) == [(0, 0), (0, 3), (5, 0), (5, 3)] and is_rectangle(out)


def test_l_shaped_home_keeps_the_notch():
    out = floor_outline(walls(*L_SHAPE))
    assert len(out) == 6 and area(out) == 8 * 7 - 3 * 3
    assert not is_rectangle(out)


def test_inner_walls_do_not_change_the_outline():
    inner = [((3, 0), (3, 4)), ((3, 4), (5, 4)), ((0, 5), (2, 5))]  # 바깥벽 중간에 붙은 벽, 방을 나누는 벽, 끝이 떠 있는 벽
    out = floor_outline(walls(*L_SHAPE, *inner))
    assert len(out) == 6 and area(out) == 8 * 7 - 3 * 3


def test_wall_order_and_direction_do_not_matter():
    mixed = [L_SHAPE[3], L_SHAPE[0][::-1], L_SHAPE[5], L_SHAPE[2][::-1], L_SHAPE[1], L_SHAPE[4]]
    assert area(floor_outline(walls(*mixed))) == 8 * 7 - 3 * 3


def test_small_gaps_at_corners_still_close():
    out = floor_outline(walls(((0, 0), (5, 0.04)), ((5.06, 0), (5, 3)), ((5, 3.05), (0, 3)), ((0.03, 3), (0, 0))))
    assert out and abs(area(out) - 15) < 0.5


def test_open_room_has_no_outline():
    assert floor_outline(walls(((0, 0), (5, 0)), ((5, 0), (5, 3)), ((5, 3), (0, 3)))) is None
    assert floor_outline([]) is None


def test_two_rooms_joined_by_one_wall_fall_back_to_the_rectangle():
    a = [((0, 0), (3, 0)), ((3, 0), (3, 3)), ((3, 3), (0, 3)), ((0, 3), (0, 0))]
    b = [((6, 0), (9, 0)), ((9, 0), (9, 3)), ((9, 3), (6, 3)), ((6, 3), (6, 0))]
    assert floor_outline(walls(*a, *b, ((3, 1.5), (6, 1.5)))) is None
