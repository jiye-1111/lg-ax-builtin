"""스캔 가구의 앞뒤 정하기.

RoomPlan 상자는 긴 변 방향만 알려 주고 어느 쪽이 앞인지는 없다. 그대로 두면 소파가 벽을 보고 앉고
의자가 식탁을 등진다. 사람이 가구를 놓는 방식대로 정한다:
- 의자는 가까운 식탁을 본다.
- 침대는 긴 변 방향으로 눕고 머리가 벽 쪽.
- 그 밖의 가구(소파·수납장 등)는 벽에 붙어 있으면 등을 벽에 댄다.
room.json의 yaw는 폭(w) 축 방향이고 정면은 (-sin yaw, cos yaw)다. 90° 돌릴 때는 폭과 깊이를 바꿔 적는다.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from core.models import BBox, RoomObject, Wall

NEAR_WALL_M = 0.6     # 등이 벽에서 이 안에 있으면 벽에 붙인 가구로 본다
TABLE_REACH_M = 1.0   # 의자가 식탁 가장자리에서 이 안에 있으면 그 식탁의 의자
BETTER_M = 0.05       # 이만큼은 더 가까워야 돌린다 (스캔 오차로 뒤집히지 않게)
SYMMETRIC = frozenset({"table"})  # 앞뒤가 없는 가구

Point = tuple[float, float]


def front_of(yaw: float) -> Point:
    return (-math.sin(yaw), math.cos(yaw))


def _centre(o: RoomObject) -> Point:
    return (o.position[0], o.position[2])


def _wall_dist(p: Point, walls: Sequence[Wall]) -> float:
    best = math.inf
    for w in walls:
        ax, ay, bx, by = *w.start, *w.end
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / ((dx * dx + dy * dy) or 1e-9)))
        best = min(best, math.hypot(p[0] - ax - dx * t, p[1] - ay - dy * t))
    return best


def _turned(o: RoomObject, quarters: int) -> RoomObject:
    """90°씩 quarters번 돌린 가구. 차지하는 자리는 그대로다."""
    if quarters % 4 == 0:
        return o
    yaw = math.atan2(math.sin(o.yaw_rad + quarters * math.pi / 2), math.cos(o.yaw_rad + quarters * math.pi / 2))
    b = o.bbox_m
    box = BBox(w=b.d, h=b.h, d=b.w) if quarters % 2 else b
    return o.model_copy(update={"yaw_rad": round(yaw, 4), "bbox_m": box})


def _edge_point(table: RoomObject, p: Point) -> Point:
    """식탁 네모에서 p와 가장 가까운 점 (p가 식탁 안이면 식탁 가운데)."""
    c, u, v = _centre(table), (math.cos(table.yaw_rad), math.sin(table.yaw_rad)), front_of(table.yaw_rad)
    rel = (p[0] - c[0], p[1] - c[1])
    a, b = rel[0] * u[0] + rel[1] * u[1], rel[0] * v[0] + rel[1] * v[1]
    ha, hb = table.bbox_m.w / 2, table.bbox_m.d / 2
    if abs(a) <= ha and abs(b) <= hb:
        return c
    a, b = max(-ha, min(ha, a)), max(-hb, min(hb, b))
    return (c[0] + u[0] * a + v[0] * b, c[1] + u[1] * a + v[1] * b)


def _face_table(chair: RoomObject, tables: Sequence[RoomObject]) -> RoomObject | None:
    c = _centre(chair)
    near = min(((math.dist(c, _edge_point(t, c)), t) for t in tables), key=lambda x: x[0], default=None)
    if near is None or near[0] > TABLE_REACH_M:
        return None
    target = _edge_point(near[1], c)
    to = (target[0] - c[0], target[1] - c[1])

    def toward(k: int) -> float:
        f = front_of(chair.yaw_rad + k * math.pi / 2)
        return f[0] * to[0] + f[1] * to[1]
    return _turned(chair, max(range(4), key=lambda k: (round(toward(k), 6), -k)))


def _back_to_wall(o: RoomObject, walls: Sequence[Wall], turns: Sequence[int]) -> RoomObject:
    def back_gap(k: int) -> float:
        t = _turned(o, k)
        f, c = front_of(t.yaw_rad), _centre(t)
        return _wall_dist((c[0] - f[0] * t.bbox_m.d / 2, c[1] - f[1] * t.bbox_m.d / 2), walls)
    best = min(turns, key=lambda k: (round(back_gap(k), 6), k))
    keep = turns[0]
    if best != keep and back_gap(best) <= NEAR_WALL_M and back_gap(best) + BETTER_M < back_gap(keep):
        return _turned(o, best)
    return _turned(o, keep)


def orient_objects(objects: Sequence[RoomObject], walls: Sequence[Wall]) -> list[RoomObject]:
    tables = [o for o in objects if o.category == "table"]
    out = []
    for o in objects:
        if o.category in SYMMETRIC:
            out.append(o)
        elif o.category == "chair":
            out.append(_face_table(o, tables) or _back_to_wall(o, walls, (0, 1, 2, 3)))
        elif o.category == "bed":  # 스캔은 긴 변을 폭으로 적는다. 침대는 긴 변이 눕는 방향(깊이)
            out.append(_back_to_wall(o, walls, (1, 3) if o.bbox_m.w > o.bbox_m.d else (0, 2)))
        else:
            out.append(_back_to_wall(o, walls, (0, 2)))
    return out
