"""창으로 들어오는 직사광 (S6). 태양 방향으로 창 윗변·아랫변을 바닥에 투영한 사각형이 그 시각의 볕 드는 자리.

평면 좌표 (x, y) = 3D (x, z), 평면은 위에서 본 모습(y가 화면 아래쪽). 북쪽은 Site.north_rad로 받는다:
북쪽 벡터 n = (cos, sin), 동쪽 = 북쪽을 위에서 보아 시계 방향 90° = (-n_y, n_x).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from core.models import Room
from recommender.pose import _inward, inside_room

from .solar import sun_position

KST = timezone(timedelta(hours=9))

ASSUMPTIONS = [
    "직사광만 계산 (하늘빛·반사광은 제외)",
    "앞 건물·발코니·나무·가구 그림자는 없다고 가정",
    "창 전체가 투명 유리라고 가정 (창틀·블라인드 제외)",
    "북쪽 방향은 직접 지정한 값 사용",
]


@dataclass(frozen=True)
class Site:
    lat: float
    lon: float
    north_rad: float  # 평면에서 북쪽이 향하는 각도
    tz: timezone = KST


def _vectors(site: Site, az_deg: float) -> tuple[float, float]:
    n = (math.cos(site.north_rad), math.sin(site.north_rad))
    e = (-n[1], n[0])
    a = math.radians(az_deg)
    return (math.cos(a) * n[0] + math.sin(a) * e[0], math.cos(a) * n[1] + math.sin(a) * e[1])


def _kelvin_rgb(k: float) -> tuple[int, int, int]:
    """색온도 → sRGB (Tanner Helland 근사, 1000~40000 K)."""
    t = k / 100
    r = 255 if t <= 66 else 329.698727446 * (t - 60) ** -0.1332047592
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * (t - 60) ** -0.0755148492
    b = 255 if t >= 66 else (0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)
    return tuple(int(max(0, min(255, round(v)))) for v in (r, g, b))  # type: ignore[return-value]


def sun_light(site: Site, when: datetime) -> dict:
    """3D 해 빛. direction은 해 쪽을 가리키는 단위 벡터 (웹 3D 좌표: x, y 위, z = 평면 y).

    색: 해가 25° 이상이면 6500 K(중립 흰빛), 낮아질수록 대기를 길게 지나 따뜻해져 지평선에서 약 2000 K.
    세기(0~1): 고도가 낮을수록 대기에서 줄어든다. 해가 지면 0.
    """
    alt, az = sun_position(site.lat, site.lon, when)
    hx, hz = _vectors(site, az)
    a = math.radians(alt)
    d = (hx * math.cos(a), math.sin(a), hz * math.cos(a))
    n = math.sqrt(sum(c * c for c in d)) or 1.0
    up = alt > 0
    w = min(1.0, max(0.0, alt / 25))
    w = w * w * (3 - 2 * w)  # 부드럽게
    kelvin = 2000 + (6500 - 2000) * w
    r, g, b = _kelvin_rgb(kelvin)
    # 고도가 낮을수록 대기에서 줄어든다. 지평선 근처(0~8°)는 부드럽게 0으로 (시간에 따라 뚝 꺼지지 않게)
    h = min(1.0, max(0.0, alt / 8))
    intensity = 0.0 if not up else round(min(1.0, math.sin(a) ** 0.5) * h * h * (3 - 2 * h), 3)
    # 하늘빛(0~1): 해가 져도 시민 박명(-6°)까지는 남는다. -6°~10° 사이를 부드럽게 잇는다
    k = min(1.0, max(0.0, (alt + 6) / 16))
    sky = round(k * k * (3 - 2 * k), 3)
    return {"altitude_deg": round(alt, 2), "azimuth_deg": round(az, 2), "up": up,
            "direction": [round(c / n, 7) for c in d], "color": f"#{r:02X}{g:02X}{b:02X}",
            "kelvin": round(kelvin), "intensity": intensity, "sky": sky}


def sun_path(site: Site, day: date, step_min: int = 5, start_min: int = 240, end_min: int = 1320) -> list[dict]:
    """하루 해 경로 (기본 04:00~22:00, 5분 간격). 화면은 이 사이를 이어 그려 시간에 따라 끊김 없이 바뀐다."""
    base = datetime(day.year, day.month, day.day, tzinfo=site.tz)
    return [{"minute": m, **sun_light(site, base + timedelta(minutes=m))}
            for m in range(start_min, end_min + 1, step_min)]


def sun_patches(room: Room, site: Site, when: datetime) -> list[dict]:
    """그 시각 각 창으로 바닥에 비치는 사각형. 해가 졌거나 창 반대편이면 없음."""
    alt, az = sun_position(site.lat, site.lon, when)
    if alt <= 0.5:
        return []
    s = _vectors(site, az)  # 해 쪽 수평 방향
    reach = 1 / math.tan(math.radians(alt))  # 높이 1 m당 바닥에서 안쪽으로 가는 거리
    out = []
    for op in room.openings:
        if op.type != "window" or not op.wall_id:
            continue
        try:
            wall = room.wall(op.wall_id)
        except KeyError:
            continue
        f = _inward(room, wall)
        if -(s[0] * f.v_axis[0] + s[1] * f.v_axis[1]) <= 0.02:  # 해가 창 바깥쪽에 있어야 한다
            continue
        a, b = op.offset_m, op.offset_m + op.width_m
        lo, hi = op.sill_m, op.sill_m + op.height_m

        def hit(u: float, h: float) -> tuple[float, float]:
            x, y = f.to_world(u, 0)
            return (x - s[0] * h * reach, y - s[1] * h * reach)

        out.append({"opening_id": op.opening_id, "polygon": [hit(a, lo), hit(b, lo), hit(b, hi), hit(a, hi)]})
    return out


def _inside(p: tuple[float, float], poly) -> bool:
    x, y = p
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def daily_sun_hours(room: Room, site: Site, day: date, cell_m: float = 0.25, step_min: int = 15,
                    points: Optional[dict[str, tuple[float, float]]] = None) -> dict:
    """하루 동안 직사광이 드는 시간(시간 단위) 격자와 지정 지점 값."""
    xs = [c for w in room.walls for c in (w.start[0], w.end[0])]
    ys = [c for w in room.walls for c in (w.start[1], w.end[1])]
    x0, y0 = min(xs), min(ys)
    nx, ny = max(1, math.ceil((max(xs) - x0) / cell_m)), max(1, math.ceil((max(ys) - y0) / cell_m))
    centers = [[(x0 + (i + 0.5) * cell_m, y0 + (j + 0.5) * cell_m) for i in range(nx)] for j in range(ny)]
    mask = [[inside_room(room, c) for c in row] for row in centers]
    values = [[0.0 if m else None for m in row] for row in mask]
    pts = dict(points or {})
    pvals = {k: 0.0 for k in pts}
    step_h = step_min / 60
    t = datetime(day.year, day.month, day.day, tzinfo=site.tz)
    for _ in range(24 * 60 // step_min):
        polys = [p["polygon"] for p in sun_patches(room, site, t + timedelta(minutes=step_min / 2))]
        if polys:
            for j, row in enumerate(centers):
                for i, c in enumerate(row):
                    if mask[j][i] and any(_inside(c, q) for q in polys):
                        values[j][i] += step_h
            for k, c in pts.items():
                if any(_inside(c, q) for q in polys):
                    pvals[k] += step_h
        t += timedelta(minutes=step_min)
    rnd = lambda v: None if v is None else round(v, 2)  # noqa: E731
    return {"origin": [x0, y0], "cell_m": cell_m, "nx": nx, "ny": ny,
            "values": [[rnd(v) for v in row] for row in values],
            "points": {k: round(v, 2) for k, v in pvals.items()}, "step_min": step_min,
            "assumptions": list(ASSUMPTIONS)}


def sun_hours_at(room: Room, site: Site, day: date, points: dict[str, tuple[float, float]], step_min: int = 15) -> dict[str, float]:
    """지정 지점만 하루 직사광 시간을 센다 (격자 없이, 제품 자리 판정용)."""
    if not points:
        return {}
    out = {k: 0.0 for k in points}
    t = datetime(day.year, day.month, day.day, tzinfo=site.tz)
    for _ in range(24 * 60 // step_min):
        polys = [p["polygon"] for p in sun_patches(room, site, t + timedelta(minutes=step_min / 2))]
        for k, c in points.items():
            if polys and any(_inside(c, q) for q in polys):
                out[k] += step_min / 60
        t += timedelta(minutes=step_min)
    return {k: round(v, 2) for k, v in out.items()}
