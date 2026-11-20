"""창으로 들어오는 직사광 (S6). 4m x 3m 방, 남쪽 벽 w1(y=0)에 창. 북쪽 = 평면 +y 방향."""
import math
from datetime import date, datetime, timedelta, timezone


from core.models import Opening, Room, ScannedDims, Wall
from sim.daylight import Site, daily_sun_hours, sun_hours_at, sun_patches

KST = timezone(timedelta(hours=9))


def room(window_on="w1"):
    walls = [
        Wall(wall_id="w1", start=(0, 0), end=(4, 0), thickness_m=0.1, scanned=ScannedDims(length_m=4, height_m=2.4)),
        Wall(wall_id="w2", start=(4, 0), end=(4, 3), thickness_m=0.1, scanned=ScannedDims(length_m=3, height_m=2.4)),
        Wall(wall_id="w3", start=(4, 3), end=(0, 3), thickness_m=0.1, scanned=ScannedDims(length_m=4, height_m=2.4)),
        Wall(wall_id="w4", start=(0, 3), end=(0, 0), thickness_m=0.1, scanned=ScannedDims(length_m=3, height_m=2.4)),
    ]
    win = Opening(opening_id="win1", type="window", wall_id=window_on, offset_m=1.0, width_m=2.0, height_m=1.2, sill_m=0.8)
    return Room(walls=walls, openings=[win])


# 평면 +y가 북쪽이면 w1(y=0)은 남쪽 벽
SITE = Site(lat=37.5665, lon=126.9780, north_rad=math.pi / 2)


def test_south_window_lights_floor_at_noon_in_winter():
    patches = sun_patches(room(), SITE, datetime(2026, 12, 21, 12, 30, tzinfo=KST))
    assert len(patches) == 1
    ys = [p[1] for p in patches[0]["polygon"]]
    # 겨울 남중 고도 ~29° → 창 윗변(2.0 m)은 약 3.6 m 안쪽까지 → 방 깊이 3 m를 넘어서 비친다
    assert max(ys) > 2.5 and min(ys) > 0


def test_summer_sun_reaches_less_deep_than_winter():
    deep = lambda d: max(p[1] for p in sun_patches(room(), SITE, datetime(d.year, d.month, d.day, 12, 30, tzinfo=KST))[0]["polygon"])  # noqa: E731
    assert deep(date(2026, 6, 21)) < deep(date(2026, 12, 21))


def test_north_window_gets_no_direct_sun_at_noon():
    assert sun_patches(room("w3"), SITE, datetime(2026, 12, 21, 12, 30, tzinfo=KST)) == []


def test_night_has_no_patches():
    assert sun_patches(room(), SITE, datetime(2026, 12, 21, 22, 0, tzinfo=KST)) == []


def test_daily_hours_grid():
    g = daily_sun_hours(room(), SITE, date(2026, 12, 21), cell_m=0.25, step_min=15)
    assert g["cell_m"] == 0.25 and g["values"]
    vals = [v for row in g["values"] for v in row if v is not None]
    assert max(vals) > 2  # 남향 창 앞은 겨울에도 몇 시간 볕이 든다
    assert min(vals) == 0  # 창 양옆 구석은 볕이 안 든다
    assert g["assumptions"]  # 가정을 함께 돌려준다


def test_hours_at_points():
    g = daily_sun_hours(room(), SITE, date(2026, 12, 21), points={"pl1": (2.0, 2.0), "pl2": (0.2, 0.3)})
    # 창 정면 안쪽은 볕이 들고, 창 아래 벽 쪽 구석은 창턱 그림자라 안 든다
    assert g["points"]["pl1"] > 1 and g["points"]["pl2"] == 0


def test_sun_hours_at_points_only_matches_the_grid():
    pts = {"pl1": (2.0, 2.0), "pl2": (0.2, 0.3)}
    full = daily_sun_hours(room(), SITE, date(2026, 12, 21), points=pts)["points"]
    assert sun_hours_at(room(), SITE, date(2026, 12, 21), pts) == full
    assert sun_hours_at(room(), SITE, date(2026, 12, 21), {}) == {}
