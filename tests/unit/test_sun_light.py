"""3D 해 빛 (실제 채광): 날짜·시각·위경도·북쪽 방향 → 해 쪽 방향(웹 3D 좌표)과 빛 색·세기."""
import math
from datetime import datetime, timedelta, timezone

import pytest

from sim.daylight import Site, _vectors, sun_light
from sim.solar import sun_position

KST = timezone(timedelta(hours=9))
# 평면 +y가 북쪽 (test_daylight.py와 같은 집)
SITE = Site(lat=37.5665, lon=126.9780, north_rad=math.pi / 2)


def _rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def test_winter_noon_sun_is_low_in_the_south():
    when = datetime(2026, 12, 21, 12, 30, tzinfo=KST)
    s = sun_light(SITE, when)
    alt, _ = sun_position(SITE.lat, SITE.lon, when)
    x, y, z = s["direction"]
    assert math.hypot(x, y, z) == pytest.approx(1, abs=1e-6)
    assert y == pytest.approx(math.sin(math.radians(alt)), abs=1e-3)  # 3D y = 위
    assert z < -0.8 and abs(x) < 0.15  # 남쪽 = 평면 -y = 3D -z
    assert s["up"] and s["altitude_deg"] == pytest.approx(alt, abs=0.01)


def test_morning_sun_comes_from_the_east_like_the_floor_patches():
    when = datetime(2026, 3, 20, 7, 30, tzinfo=KST)
    s = sun_light(SITE, when)
    _, az = sun_position(SITE.lat, SITE.lon, when)
    hx, hz = _vectors(SITE, az)  # 바닥 볕 자리 계산과 같은 수평 방향
    x, _, z = s["direction"]
    k = math.hypot(x, z)
    assert (x / k, z / k) == pytest.approx((hx, hz), abs=1e-6)
    assert x < -0.5  # 북쪽이 +y면 동쪽은 -x


def test_north_rotation_turns_the_sun_with_the_house():
    when = datetime(2026, 12, 21, 12, 30, tzinfo=KST)
    turned = Site(lat=SITE.lat, lon=SITE.lon, north_rad=0.0)  # 북쪽 = 평면 +x
    x, _, z = sun_light(turned, when)["direction"]
    assert x < -0.8 and abs(z) < 0.15  # 남쪽 = 평면 -x


def test_daylight_is_neutral_white_and_only_low_sun_is_warm():
    noon = _rgb(sun_light(SITE, datetime(2026, 6, 21, 12, 30, tzinfo=KST))["color"])
    assert max(noon) - min(noon) <= 12 and min(noon) >= 240  # 노랗지 않은 흰빛
    afternoon = _rgb(sun_light(SITE, datetime(2026, 6, 21, 16, 0, tzinfo=KST))["color"])
    assert max(afternoon) - min(afternoon) <= 20
    dusk = sun_light(SITE, datetime(2026, 6, 21, 19, 30, tzinfo=KST))
    assert 0 < dusk["altitude_deg"] < 6
    r, g, b = _rgb(dusk["color"])
    assert r - b >= 40 and r >= g >= b  # 해 질 녘만 따뜻하게
    assert dusk["intensity"] < sun_light(SITE, datetime(2026, 6, 21, 12, 30, tzinfo=KST))["intensity"]


def test_no_sun_at_night():
    s = sun_light(SITE, datetime(2026, 6, 21, 23, 0, tzinfo=KST))
    assert not s["up"] and s["intensity"] == 0
