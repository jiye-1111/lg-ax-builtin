"""USDZ → room.json 변환기. 합성 픽스처(worker.fixtures)가 정답을 알고 있다.

⚠️ 실제 UGScan 샘플을 받으면 data/samples/에 넣고 정답(줄자 실측) 기반 테스트를 추가한다.
"""
import math

import pytest

from core.models import Room
from worker.converter import convert_usdz
from worker.fixtures import build_usdz


@pytest.fixture(scope="module")
def room(tmp_path_factory) -> Room:
    p = build_usdz(tmp_path_factory.mktemp("s") / "room.usdz")
    return convert_usdz(p)


def _wall_by_len_and_pos(room, length, pt):
    best = min(room.walls, key=lambda w: math.dist(((w.start[0] + w.end[0]) / 2, (w.start[1] + w.end[1]) / 2), pt))
    assert best.scanned.length_m == pytest.approx(length, abs=0.002)
    return best


def test_extracts_four_walls_with_dims(room):
    assert len(room.walls) == 4
    lengths = sorted(round(w.scanned.length_m, 3) for w in room.walls)
    assert lengths == [3.6, 3.6, 5.2, 5.2]
    assert all(w.scanned.height_m == pytest.approx(2.4, abs=1e-3) for w in room.walls)
    assert all(w.thickness_m == pytest.approx(0.1, abs=1e-3) for w in room.walls)
    assert all(w.measured is None for w in room.walls)


def test_wall_endpoints_on_floor_plan(room):
    w = _wall_by_len_and_pos(room, 5.2, (2.6, 0.0))
    xs = sorted([w.start[0], w.end[0]])
    assert xs == pytest.approx([0.0, 5.2], abs=1e-3)
    assert w.start[1] == pytest.approx(0.0, abs=1e-3)


def test_door_assigned_to_wall_with_offset(room):
    door = next(o for o in room.openings if o.type == "door")
    wall = room.wall(door.wall_id)
    assert wall is _wall_by_len_and_pos(room, 5.2, (2.6, 3.6))
    assert door.width_m == pytest.approx(0.9, abs=1e-3)
    assert door.height_m == pytest.approx(2.1, abs=1e-3)
    # offset은 벽 start 기준. 문 구간 x 0.6~1.5
    sx = wall.start[0]
    expected = 0.6 if sx < 1 else 5.2 - 1.5
    assert door.offset_m == pytest.approx(expected, abs=1e-3)


def test_window_has_sill(room):
    win = next(o for o in room.openings if o.type == "window")
    assert win.sill_m == pytest.approx(0.9, abs=1e-3)
    assert win.width_m == pytest.approx(1.8, abs=1e-3)
    assert room.wall(win.wall_id) is _wall_by_len_and_pos(room, 3.6, (5.2, 1.8))


def test_objects_with_category_and_bbox(room):
    cats = sorted(o.category for o in room.objects)
    assert cats == ["sofa", "storage", "table"]
    st = next(o for o in room.objects if o.category == "storage")
    assert (st.bbox_m.w, st.bbox_m.h, st.bbox_m.d) == pytest.approx((1.2, 0.9, 0.6), abs=1e-3)
    assert st.position == pytest.approx((0.6, 0.45, 0.3), abs=1e-3)


def test_geometry_child_not_double_counted(room):
    assert len(room.openings) == 2


def test_rotated_and_offset_room_keeps_dimensions(tmp_path):
    r = convert_usdz(build_usdz(tmp_path / "rot.usdz", room_yaw_deg=23.0, offset=(10.0, 0.5, -4.0)))
    assert sorted(round(w.scanned.length_m, 3) for w in r.walls) == [3.6, 3.6, 5.2, 5.2]
    # 바닥 높이를 기준으로 정규화
    win = next(o for o in r.openings if o.type == "window")
    assert win.sill_m == pytest.approx(0.9, abs=1e-3)


def test_centimeter_units_are_converted(tmp_path):
    r = convert_usdz(build_usdz(tmp_path / "cm.usdz", meters_per_unit=0.01))
    assert sorted(round(w.scanned.length_m, 3) for w in r.walls) == [3.6, 3.6, 5.2, 5.2]


def test_output_validates_as_room_json(room):
    Room.model_validate(room.model_dump())


def test_mesh_geometry_is_supported(tmp_path):
    r = convert_usdz(build_usdz(tmp_path / "mesh.usdz", geom="mesh", room_yaw_deg=-40))
    assert sorted(round(w.scanned.length_m, 3) for w in r.walls) == [3.6, 3.6, 5.2, 5.2]
    assert len(r.openings) == 2 and len(r.objects) == 3
