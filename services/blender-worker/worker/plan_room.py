"""도면에서 읽은 벽·문·창(mm)을 room.json(Room)으로 바꾼다.

도면을 읽는 일(그림 → 좌표)은 core/plan_read.py가 하고, 여기는 순수 계산이다.
읽은 좌표는 조금씩 어긋나므로 벽을 곧게 펴고 모서리를 맞춘 뒤 너무 짧거나 겹친 벽을 버린다.
평면 좌표 (x, y)는 그림의 오른쪽·아래쪽이 +다 (room.json의 (x, y) = 3D (x, z)).
"""
from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field

from core.models import Opening, Room, ScannedDims, Wall

from worker.tidy import tidy_openings

WALL_HEIGHT_M = 2.4        # 도면에는 천장 높이가 없다. 아파트 기준 높이
EXTERIOR_M, INTERIOR_M = 0.2, 0.1
STRAIGHTEN_DEG = 8         # 이만큼 안쪽으로 기운 벽은 가로·세로로 편다
JOIN_MM = 120              # 이 안에서 어긋난 모서리는 같은 점으로 본다
MIN_WALL_MM = 250
MIN_OPENING_MM = 400
SIZE_RANGE_M = (1.5, 40.0)  # 집 한 변이 이 범위를 벗어나면 축척을 잘못 읽은 것
DOOR = {"height_m": 2.1, "sill_m": 0.0}
WINDOW = {"height_m": 1.2, "sill_m": 0.9}
SLIDING = {"height_m": 2.1, "sill_m": 0.0}  # 베란다로 나가는 큰 유리문
# 스캔 벽을 도면 치수로 맞출 때: 아이폰 LiDAR 오차(1~3 cm)보다 넉넉하되 다른 벽과 헷갈리지 않을 만큼만
MATCH_M, MATCH_RATIO = 0.08, 0.02
MIN_MATCH_WALL_M = 1.0
SAME_M = 0.005


REVIEW_KEEP_WALLS, REVIEW_SIZE_DRIFT = 0.8, 0.2  # 다시 본 결과를 받아들이는 한계: 벽 수, 집 크기 변화


class PlanWall(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    exterior: bool = True


class PlanOpening(BaseModel):
    type: Literal["door", "window", "sliding_door"]
    wall: int = Field(description="walls 목록에서 몇 번째 벽인지 (0부터)")
    offset_mm: float = Field(description="그 벽의 (x1, y1)에서 문·창이 시작하는 곳까지")
    width_mm: float


class PlanRead(BaseModel):
    readable: bool
    reason: str = ""
    scale_from: Literal["dimensions", "door_width", "none"]
    walls: list[PlanWall] = Field(default_factory=list)
    openings: list[PlanOpening] = Field(default_factory=list)


def _straighten(w: PlanWall) -> PlanWall:
    ang = math.degrees(math.atan2(abs(w.y2 - w.y1), abs(w.x2 - w.x1)))
    if ang <= STRAIGHTEN_DEG:
        y = (w.y1 + w.y2) / 2
        return w.model_copy(update={"y1": y, "y2": y})
    if ang >= 90 - STRAIGHTEN_DEG:
        x = (w.x1 + w.x2) / 2
        return w.model_copy(update={"x1": x, "x2": x})
    return w


def _snap(values: list[float]) -> dict[float, float]:
    """가까운 좌표끼리 묶어 평균으로 맞춘다."""
    out, group = {}, []
    for v in sorted(set(values)):
        if group and v - group[-1] > JOIN_MM:
            out.update({g: sum(group) / len(group) for g in group})
            group = []
        group.append(v)
    out.update({g: sum(group) / len(group) for g in group})
    return out


def _span(plan: PlanRead) -> tuple[float, float]:
    xs = [v for w in plan.walls for v in (w.x1, w.x2)]
    ys = [v for w in plan.walls for v in (w.y1, w.y2)]
    return max(xs) - min(xs), max(ys) - min(ys)


def better_reading(first: PlanRead, second: PlanRead | None) -> PlanRead:
    """다시 보고 고친 결과(second)를 쓸지 정한다. 집 크기가 크게 달라졌거나 벽이 많이 줄었으면 처음 것을 쓴다."""
    if second is None or not second.readable or second.scale_from == "none" or not second.walls:
        return first
    if len(second.walls) < REVIEW_KEEP_WALLS * len(first.walls):
        return first
    a, b = _span(first), _span(second)
    if any(p <= 0 or abs(q - p) / p > REVIEW_SIZE_DRIFT for p, q in zip(a, b)):
        return first
    try:
        room_from_plan(second)
    except ValueError:
        return first
    return second


def room_from_plan(plan: PlanRead) -> Room:
    if not plan.readable:
        raise ValueError(plan.reason or "도면을 읽지 못했어요")
    if plan.scale_from == "none":
        raise ValueError("도면에 치수가 없어서 크기를 알 수 없어요. 치수가 적힌 도면을 올려 주세요")
    walls = [_straighten(w) for w in plan.walls]
    sx = _snap([v for w in walls for v in (w.x1, w.x2)])
    sy = _snap([v for w in walls for v in (w.y1, w.y2)])
    walls = [w.model_copy(update={"x1": sx[w.x1], "x2": sx[w.x2], "y1": sy[w.y1], "y2": sy[w.y2]}) for w in walls]

    kept: list[tuple[int, PlanWall]] = []  # (읽은 목록에서의 번호, 벽)
    seen = set()
    for i, w in enumerate(walls):
        if math.hypot(w.x2 - w.x1, w.y2 - w.y1) < MIN_WALL_MM:
            continue
        key = frozenset({(round(w.x1), round(w.y1)), (round(w.x2), round(w.y2))})
        if key in seen:
            continue
        seen.add(key)
        kept.append((i, w))
    if len(kept) < 3:
        raise ValueError("도면에서 벽을 충분히 찾지 못했어요")

    x0 = min(v for _, w in kept for v in (w.x1, w.x2))
    y0 = min(v for _, w in kept for v in (w.y1, w.y2))
    span = (max(v for _, w in kept for v in (w.x1, w.x2)) - x0, max(v for _, w in kept for v in (w.y1, w.y2)) - y0)
    if not all(SIZE_RANGE_M[0] <= s / 1000 <= SIZE_RANGE_M[1] for s in span):
        raise ValueError(f"읽은 집 크기가 이상해요 ({span[0] / 1000:.1f} × {span[1] / 1000:.1f} m). 치수가 잘 보이는 도면을 올려 주세요")

    def m(v: float, o: float) -> float:
        return round((v - o) / 1000, 3)

    out, ids = [], {}
    for n, (i, w) in enumerate(kept, 1):
        start, end = (m(w.x1, x0), m(w.y1, y0)), (m(w.x2, x0), m(w.y2, y0))
        ids[i] = f"w{n}"
        out.append(Wall(wall_id=f"w{n}", start=start, end=end, thickness_m=EXTERIOR_M if w.exterior else INTERIOR_M,
                        scanned=ScannedDims(length_m=round(math.dist(start, end), 3), height_m=WALL_HEIGHT_M)))

    openings, count = [], {"door": 0, "window": 0}
    lengths = {w.wall_id: w.scanned.length_m for w in out}
    for o in plan.openings:
        wall_id = ids.get(o.wall)
        if wall_id is None or o.width_mm < MIN_OPENING_MM:
            continue
        width = min(o.width_mm / 1000, lengths[wall_id])
        offset = min(max(o.offset_mm / 1000, 0.0), lengths[wall_id] - width)  # 벽을 넘으면 안으로 밀어 넣는다
        kind = "door" if o.type == "door" else "window"
        dims = DOOR if o.type == "door" else SLIDING if o.type == "sliding_door" else WINDOW
        count[kind] += 1
        openings.append(Opening(opening_id=f"{'d' if kind == 'door' else 'win'}{count[kind]}", type=kind, wall_id=wall_id,
                                offset_m=round(offset, 3), width_m=round(width, 3), **dims))
    # 벽이 가로지르는 문, 서로 겹친 문처럼 있을 수 없는 자리는 바로잡는다
    return tidy_openings(Room(source="floorplan_image", walls=out, openings=openings, objects=[]))


def corrections(scan: Room, plan: Room) -> dict[str, float]:
    """스캔한 벽마다 길이가 거의 같은 도면 벽을 찾아 {wall_id: 도면 길이(m)}를 돌려준다.

    스캔과 도면은 방향·원점이 달라서 위치로는 맞추지 않고 길이로만 맞춘다.
    가까운 도면 길이가 둘 이상이면 어느 벽인지 알 수 없으니 그대로 둔다.
    """
    lengths = sorted({w.scanned.length_m for w in plan.walls})
    out = {}
    for w in scan.walls:
        n = w.scanned.length_m
        if n < MIN_MATCH_WALL_M:
            continue
        near = [x for x in lengths if abs(x - n) <= max(MATCH_M, n * MATCH_RATIO)]
        if len(near) == 1 and abs(near[0] - n) > SAME_M:
            out[w.wall_id] = near[0]
    return out
