"""도면을 조각으로 나눠 다시 읽은 결과를 처음 읽은 집에 합친다. 순수 계산.

조각을 읽는 AI는 그 조각 그림의 픽셀 좌표로 답한다. 조각 원점·배율로 전체 그림 픽셀로 되돌리고,
그림에서 찾은 집 테두리(px)와 처음 읽은 벽의 테두리(mm)를 맞대어 mm로 바꾼다.
창·문은 가장 가까운 벽에 붙이고, 이미 있는 것과 겹치면 뺀다. 벽은 양 끝이 기존 벽에 닿을 때만 더한다.
"""
from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field

from .plan_room import MIN_OPENING_MM, PlanOpening, PlanRead, PlanWall

SNAP_MM = 450          # 창·문이 벽에서 이만큼 떨어져 있어도 그 벽 것으로 본다
ANGLE_DEG = 20         # 창·문·벽이 이만큼 안쪽으로 기울어 있으면 같은 방향으로 본다
SAME_RATIO = 0.3       # 이미 있는 창·문과 폭의 이만큼 넘게 겹치면 같은 것
MIN_NEW_WALL_MM = 800
COVERED_MM = 300       # 새 벽이 기존 벽에서 이 안쪽이면 이미 읽은 벽
TOUCH_MM = 500         # 새 벽 끝이 기존 벽에서 이 안쪽이면 닿은 것으로 보고 붙인다


class TileSeg(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    exterior: bool = True


class TileOpening(BaseModel):
    type: Literal["door", "window", "sliding_door"]
    x1: float = Field(description="벽을 따라 한쪽 끝 (조각 그림 px)")
    y1: float
    x2: float = Field(description="반대쪽 끝")
    y2: float


class TileRead(BaseModel):
    walls: list[TileSeg] = Field(default_factory=list)
    openings: list[TileOpening] = Field(default_factory=list)


def _to_mm(plan: PlanRead, box_px: tuple[float, float, float, float]):
    xs = [v for w in plan.walls for v in (w.x1, w.x2)]
    ys = [v for w in plan.walls for v in (w.y1, w.y2)]
    px0, py0, px1, py1 = box_px
    kx = (max(xs) - min(xs)) / max(px1 - px0, 1e-6)
    ky = (max(ys) - min(ys)) / max(py1 - py0, 1e-6)
    return lambda x, y: (min(xs) + (x - px0) * kx, min(ys) + (y - py0) * ky)


def _angle(ax, ay, bx, by) -> float:
    return math.degrees(math.atan2(by - ay, bx - ax)) % 180


def _parallel(a: float, b: float) -> bool:
    d = abs(a - b) % 180
    return min(d, 180 - d) <= ANGLE_DEG


def _project(w: PlanWall, x: float, y: float) -> tuple[float, float, float]:
    """(벽 시작점에서 따라간 거리, 벽선까지 거리, 벽 길이)"""
    dx, dy = w.x2 - w.x1, w.y2 - w.y1
    L = math.hypot(dx, dy) or 1e-6
    t = ((x - w.x1) * dx + (y - w.y1) * dy) / L
    return t, abs((x - w.x1) * dy - (y - w.y1) * dx) / L, L


def _seg_dist(w: PlanWall, x: float, y: float) -> tuple[float, tuple[float, float]]:
    t, _, L = _project(w, x, y)
    t = min(max(t, 0.0), L)
    px, py = w.x1 + (w.x2 - w.x1) * t / L, w.y1 + (w.y2 - w.y1) * t / L
    return math.hypot(x - px, y - py), (px, py)


def _add_opening(walls: list[PlanWall], openings: list[PlanOpening], kind: str, a, b) -> None:
    ang = _angle(*a, *b)
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    best = None
    for i, w in enumerate(walls):
        if not _parallel(ang, _angle(w.x1, w.y1, w.x2, w.y2)):
            continue
        t, d, L = _project(w, *mid)
        if d <= SNAP_MM and -100 <= t <= L + 100 and (best is None or d < best[0]):
            best = (d, i, L)
    if best is None:
        return
    _, i, L = best
    ta, tb = sorted(min(max(_project(walls[i], *p)[0], 0.0), L) for p in (a, b))
    if tb - ta < MIN_OPENING_MM:
        return
    for o in openings:
        if o.wall == i:
            overlap = min(tb, o.offset_mm + o.width_mm) - max(ta, o.offset_mm)
            if overlap > SAME_RATIO * min(tb - ta, o.width_mm):
                return
    openings.append(PlanOpening(type=kind, wall=i, offset_mm=round(ta), width_mm=round(tb - ta)))


def _snap_end(walls: list[PlanWall], p) -> tuple[float, float] | None:
    ends = [(math.dist(p, q), q) for w in walls for q in ((w.x1, w.y1), (w.x2, w.y2))]
    d, q = min(ends)
    if d <= TOUCH_MM:
        return q
    d, q = min(_seg_dist(w, *p) for w in walls)
    return q if d <= TOUCH_MM else None


def _add_wall(walls: list[PlanWall], a, b, exterior: bool) -> None:
    if math.dist(a, b) < MIN_NEW_WALL_MM:
        return
    ang = _angle(*a, *b)
    samples = [(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f) for f in (0.25, 0.5, 0.75)]
    if all(any(_parallel(ang, _angle(w.x1, w.y1, w.x2, w.y2)) and _seg_dist(w, *s)[0] <= COVERED_MM for w in walls)
           for s in samples):
        return
    sa, sb = _snap_end(walls, a), _snap_end(walls, b)
    if sa is None or sb is None or math.dist(sa, sb) < MIN_NEW_WALL_MM:
        return  # 떠 있는 벽은 집 모양을 망친다
    walls.append(PlanWall(x1=sa[0], y1=sa[1], x2=sb[0], y2=sb[1], exterior=exterior))


def fit_to_picture(plan: PlanRead, box_px) -> PlanRead:
    """치수 없이 어림한 집은 가로세로 비를 그림 속 집 테두리에 맞춘다 (넓이는 그대로).

    AI는 그림 비율을 자주 틀리게 옮긴다. 그림의 비율은 코드가 잰 것이라 더 믿을 만하다.
    도면에 적힌 치수로 읽은 집은 손대지 않는다.
    """
    if plan.scale_from != "door_width" or not plan.walls:
        return plan
    xs = [v for w in plan.walls for v in (w.x1, w.x2)]
    ys = [v for w in plan.walls for v in (w.y1, w.y2)]
    mw, mh = max(xs) - min(xs), max(ys) - min(ys)
    pw, ph = box_px[2] - box_px[0], box_px[3] - box_px[1]
    if min(mw, mh, pw, ph) <= 0:
        return plan
    r = math.sqrt((pw / ph) / (mw / mh))
    kx, ky = r, 1 / r
    x0, y0 = min(xs), min(ys)

    def wall(w: PlanWall) -> PlanWall:
        return w.model_copy(update={"x1": x0 + (w.x1 - x0) * kx, "x2": x0 + (w.x2 - x0) * kx,
                                    "y1": y0 + (w.y1 - y0) * ky, "y2": y0 + (w.y2 - y0) * ky})

    def opening(o: PlanOpening) -> PlanOpening:
        if not 0 <= o.wall < len(plan.walls):
            return o
        w = plan.walls[o.wall]
        L = math.hypot(w.x2 - w.x1, w.y2 - w.y1) or 1.0
        k = math.hypot((w.x2 - w.x1) / L * kx, (w.y2 - w.y1) / L * ky)
        return o.model_copy(update={"offset_mm": o.offset_mm * k, "width_mm": o.width_mm * k})

    return plan.model_copy(update={"walls": [wall(w) for w in plan.walls], "openings": [opening(o) for o in plan.openings]})


def merge_tiles(plan: PlanRead, tiles: list, box_px: tuple[float, float, float, float]) -> PlanRead:
    """tiles = [(TileRead, (조각 원점 x, y, 배율)), ...]. 배율 = 조각 그림 px / 원래 그림 px"""
    if not plan.walls:
        return plan
    mm = _to_mm(plan, box_px)
    walls, openings = list(plan.walls), list(plan.openings)
    reads = [(t, o) for t, o in tiles if isinstance(t, TileRead)]

    def back(o, x, y):
        ox, oy, k = o
        return mm(ox + x / k, oy + y / k)

    for t, o in reads:  # 벽을 먼저: 새로 더한 벽에 달린 창·문도 붙을 수 있게
        for s in t.walls:
            _add_wall(walls, back(o, s.x1, s.y1), back(o, s.x2, s.y2), s.exterior)
    for t, o in reads:
        for s in t.openings:
            _add_opening(walls, openings, s.type, back(o, s.x1, s.y1), back(o, s.x2, s.y2))
    if len(walls) == len(plan.walls) and len(openings) == len(plan.openings):
        return plan
    return plan.model_copy(update={"walls": walls, "openings": openings})
