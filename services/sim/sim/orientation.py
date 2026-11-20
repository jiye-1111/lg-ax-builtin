"""집 방향: 창이 어느 쪽(남향·북향…)을 보는지, 북쪽을 모를 때의 추정.

north_deg = 평면도 위쪽(-y)에서 북쪽까지 시계 방향 각도. 북쪽 벡터 n = (sin, -cos), 동쪽 e = (cos, sin).
스캔(RoomPlan USDZ)에는 나침반 정보가 없다. 그래서 북쪽은
  1) 주소로 찾은 건물 외곽선의 변 방향(있으면)에 맞추고,
  2) 그중 가장 큰 창이 남쪽에 가장 가깝게 오는 방향을 고른다 (국내 주택은 주 채광면을 남쪽에 두는 경우가 많다).
추정이므로 화면에서 직접 고칠 수 있어야 한다.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

from core.models import Room
from recommender.pose import _inward

DIRS = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"]


def bearing_label(deg: float) -> str:
    return DIRS[int(((deg % 360) + 22.5) // 45) % 8]


def _bearing0(v: tuple[float, float]) -> float:
    """north_deg = 0(평면 위쪽이 북)일 때 평면 벡터의 방위각."""
    return math.degrees(math.atan2(v[0], -v[1])) % 360


def _window_walls(room: Room) -> list[tuple[str, float, tuple[float, float]]]:
    """창이 있는 벽: (wall_id, 창 넓이 합, 바깥쪽 방향). 넓은 순."""
    area: dict[str, float] = {}
    for op in room.openings:
        if op.type == "window" and op.wall_id:
            area[op.wall_id] = area.get(op.wall_id, 0.0) + op.width_m * op.height_m
    out = []
    for wid, a in area.items():
        try:
            f = _inward(room, room.wall(wid))
        except KeyError:
            continue
        out.append((wid, a, (-f.v_axis[0], -f.v_axis[1])))
    return sorted(out, key=lambda x: -x[1])


def window_facings(room: Room, north_deg: float) -> list[dict]:
    """창이 있는 벽마다 바라보는 방위. 창이 넓은 벽부터."""
    out = []
    for wid, a, o in _window_walls(room):
        b = (_bearing0(o) - north_deg) % 360
        out.append({"wall_id": wid, "area_m2": round(a, 2), "bearing_deg": round(b, 1), "label": bearing_label(b) + "향"})
    return out


def footprint_axis_deg(ring: Sequence[Sequence[float]]) -> Optional[float]:
    """건물 외곽선([경도, 위도] 고리)의 주된 변 방향 (북에서 시계 방향, 0~90°). 변 길이로 가중한다."""
    if len(ring) < 4:
        return None
    lat0 = math.radians(sum(p[1] for p in ring) / len(ring))
    sx = sy = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(ring, ring[1:]):
        e, n = (lon2 - lon1) * math.cos(lat0), lat2 - lat1
        length = math.hypot(e, n)
        if length < 1e-9:
            continue
        t = 4 * math.atan2(e, n)  # 90° 주기로 접는다
        sx += length * math.cos(t)
        sy += length * math.sin(t)
    if math.hypot(sx, sy) < 1e-12:
        return None
    return (math.degrees(math.atan2(sy, sx)) / 4) % 90


def estimate_north(room: Room, axis_deg: Optional[float] = None) -> Optional[dict]:
    """가장 큰 창이 남쪽(건물 방향을 알면 그 변 중 남쪽에 가장 가까운 면)을 본다고 보고 north_deg를 정한다."""
    walls = _window_walls(room)
    if not walls:
        return None
    wid, _, o = walls[0]
    target = 180.0
    if axis_deg is not None:
        target = min(((axis_deg % 90) + k * 90 for k in range(4)), key=lambda b: abs((b - 180 + 180) % 360 - 180))
    return {"north_deg": round((_bearing0(o) - target) % 360, 1) % 360, "main_wall_id": wid,
            "basis": "building_footprint" if axis_deg is not None else "main_window_south"}
