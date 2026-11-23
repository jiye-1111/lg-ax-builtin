"""도면 조각에서 찾은 창·문·벽(픽셀)을 처음 읽은 집(mm)에 합치는 규칙."""
from worker.plan_merge import TileOpening, TileRead, TileSeg, merge_tiles
from worker.plan_room import PlanOpening, PlanRead, PlanWall

BOX = (100, 100, 700, 500)   # 그림에서 집 바깥벽 테두리 (px). 6000 × 4000 mm 집이므로 1 px = 10 mm
WHOLE = (0, 0, 1.0)          # 조각 원점 (x, y)와 배율: 그림 전체를 그대로 본 조각


def rect(**kw):
    pts = [(0, 0), (6000, 0), (6000, 4000), (0, 4000)]
    return PlanRead(readable=True, scale_from="dimensions",
                    walls=[PlanWall(x1=a[0], y1=a[1], x2=b[0], y2=b[1]) for a, b in zip(pts, pts[1:] + pts[:1])], **kw)


def window(x1, y1, x2, y2, kind="window"):
    return TileOpening(type=kind, x1=x1, y1=y1, x2=x2, y2=y2)


def test_window_found_in_a_tile_goes_onto_the_nearest_wall():
    out = merge_tiles(rect(), [(TileRead(openings=[window(200, 102, 300, 98)]), WHOLE)], BOX)
    o = out.openings[0]
    assert (o.type, o.wall) == ("window", 0)
    assert abs(o.offset_mm - 1000) < 1 and abs(o.width_mm - 1000) < 1


def test_tile_position_and_zoom_are_undone():
    # 그림의 (400, 100)부터 2배로 키운 조각: 조각 (0, 0)~(200, 0)은 그림 (400, 100)~(500, 100)
    out = merge_tiles(rect(), [(TileRead(openings=[window(0, 0, 200, 0)]), (400, 100, 2.0))], BOX)
    assert abs(out.openings[0].offset_mm - 3000) < 1 and abs(out.openings[0].width_mm - 1000) < 1


def test_something_already_read_is_not_added_twice():
    first = rect(openings=[PlanOpening(type="window", wall=0, offset_mm=1100, width_mm=900)])
    tiles = [(TileRead(openings=[window(200, 100, 300, 100)]), WHOLE), (TileRead(openings=[window(205, 100, 298, 100)]), WHOLE)]
    assert len(merge_tiles(first, tiles, BOX).openings) == 1


def test_openings_away_from_any_wall_or_too_small_are_dropped():
    tiles = [(TileRead(openings=[window(300, 300, 400, 300), window(200, 100, 230, 100), window(200, 100, 300, 100, "door")]), WHOLE)]
    out = merge_tiles(rect(), tiles, BOX)
    assert [o.type for o in out.openings] == ["door"]


def test_missing_inner_wall_is_added_when_both_ends_touch_walls():
    out = merge_tiles(rect(), [(TileRead(walls=[TileSeg(x1=400, y1=104, x2=403, y2=497, exterior=False)]), WHOLE)], BOX)
    w = out.walls[-1]
    assert len(out.walls) == 5 and not w.exterior
    assert (w.y1, w.y2) == (0, 4000) and abs(w.x1 - 3000) < 40 and abs(w.x2 - 3000) < 40  # 끝은 벽 위로 붙는다 (곧게 펴기는 room_from_plan)


def test_wall_that_was_already_read_or_floats_is_not_added():
    tiles = [(TileRead(walls=[TileSeg(x1=150, y1=102, x2=650, y2=101),      # 위쪽 바깥벽 그대로
                              TileSeg(x1=300, y1=250, x2=500, y2=250)]), WHOLE)]  # 양 끝이 벽에 안 닿는다
    assert len(merge_tiles(rect(), tiles, BOX).walls) == 4


def test_door_on_a_wall_added_from_a_tile_keeps_its_wall():
    tile = TileRead(walls=[TileSeg(x1=400, y1=100, x2=400, y2=500, exterior=False)],
                    openings=[window(400, 200, 400, 290, "door")])
    out = merge_tiles(rect(), [(tile, WHOLE)], BOX)
    assert out.openings[0].wall == 4 and abs(out.openings[0].offset_mm - 1000) < 1


def test_bad_tile_reading_leaves_the_plan_as_it_was():
    first = rect()
    assert merge_tiles(first, [(None, WHOLE), ("x", WHOLE)], BOX) == first
