"""태양 고도·방위 (NOAA Solar Calculator 식, Meeus 기반). 1900~2100년 오차 약 0.01°.
대기 굴절 보정은 하지 않는다 (지평선 근처 외에는 무시할 수준)."""
from __future__ import annotations

import math
from datetime import datetime, timezone

_d = math.radians
_r = math.degrees


def sun_position(lat: float, lon: float, when: datetime) -> tuple[float, float]:
    """(고도°, 방위°). 방위는 북쪽 0°, 시계 방향 (동 90°, 남 180°)."""
    if when.tzinfo is None:
        raise ValueError("시간대가 있는 datetime이 필요합니다")
    t = when.astimezone(timezone.utc)
    jd = t.timestamp() / 86400 + 2440587.5
    T = (jd - 2451545) / 36525  # 율리우스 세기
    L0 = (280.46646 + T * (36000.76983 + T * 0.0003032)) % 360
    M = 357.52911 + T * (35999.05029 - 0.0001537 * T)
    e = 0.016708634 - T * (0.000042037 + 0.0000001267 * T)
    C = (math.sin(_d(M)) * (1.914602 - T * (0.004817 + 0.000014 * T))
         + math.sin(_d(2 * M)) * (0.019993 - 0.000101 * T) + math.sin(_d(3 * M)) * 0.000289)
    omega = 125.04 - 1934.136 * T
    lam = L0 + C - 0.00569 - 0.00478 * math.sin(_d(omega))  # 겉보기 황경
    eps0 = 23 + (26 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(_d(omega))
    decl = math.asin(math.sin(_d(eps)) * math.sin(_d(lam)))
    y = math.tan(_d(eps / 2)) ** 2
    eqtime = 4 * _r(y * math.sin(2 * _d(L0)) - 2 * e * math.sin(_d(M)) + 4 * e * y * math.sin(_d(M)) * math.cos(2 * _d(L0))
                    - 0.5 * y * y * math.sin(4 * _d(L0)) - 1.25 * e * e * math.sin(2 * _d(M)))  # 분
    minutes = t.hour * 60 + t.minute + t.second / 60
    tst = (minutes + eqtime + 4 * lon) % 1440
    ha = _d(tst / 4 - 180)
    phi = _d(lat)
    cos_zen = math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.cos(ha)
    zen = math.acos(max(-1.0, min(1.0, cos_zen)))
    alt = 90 - _r(zen)
    az = _r(math.atan2(math.sin(ha), math.cos(ha) * math.sin(phi) - math.tan(decl) * math.cos(phi))) + 180
    return alt, az % 360
