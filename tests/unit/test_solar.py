"""태양 위치 (S6 채광). 기준값: 남중 고도 = 90 - 위도 + 적위."""
from datetime import date, datetime, timedelta, timezone

import pytest

from sim.solar import sun_position

SEOUL = (37.5665, 126.9780)
KST = timezone(timedelta(hours=9))


def _noon_max(d: date):
    best = (-90.0, 0.0)
    t = datetime(d.year, d.month, d.day, 10, 0, tzinfo=KST)
    for _ in range(4 * 60):
        alt, az = sun_position(*SEOUL, t)
        best = max(best, (alt, az))
        t += timedelta(minutes=1)
    return best


@pytest.mark.parametrize("d, expected", [
    (date(2026, 6, 21), 90 - 37.5665 + 23.44),
    (date(2026, 12, 21), 90 - 37.5665 - 23.44),
    (date(2026, 3, 20), 90 - 37.5665),
])
def test_noon_altitude(d, expected):
    alt, az = _noon_max(d)
    assert alt == pytest.approx(expected, abs=0.5)
    assert az == pytest.approx(180, abs=3)  # 남중 = 정남


def test_equinox_sunrise_is_east_and_night_is_below_horizon():
    alt, az = sun_position(*SEOUL, datetime(2026, 3, 20, 6, 45, tzinfo=KST))
    assert -3 < alt < 5 and az == pytest.approx(90, abs=5)
    assert sun_position(*SEOUL, datetime(2026, 3, 20, 23, 0, tzinfo=KST))[0] < 0


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        sun_position(*SEOUL, datetime(2026, 3, 20, 12, 0))
