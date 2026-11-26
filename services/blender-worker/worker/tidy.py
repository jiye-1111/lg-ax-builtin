"""읽은 문·창 자리 바로잡기.

스캔이나 도면에서 읽은 문·창은 가끔 있을 수 없는 자리에 놓인다: 다른 벽이 와 닿는 곳에 걸친 문,
한 벽에서 서로 겹친 문, 모서리를 같이 쓰는 두 문. 그런 것은 같은 벽에서 가까운 빈자리로 조금 옮기고,
옮길 자리가 없는 문은 뺀다. 창은 빼지 않는다 (자리가 없으면 그대로 둔다).
"""
from __future__ import annotations

import math

from core.models import Opening, Room, Wall

GAP_M = 0.05          # 문·창 사이, 닿는 벽과의 사이에 남기는 틈
MAX_SHIFT_M = 0.6     # 이보다 멀리 옮겨야 하면 잘못 읽은 것으로 본다
SAME_M = 0.5          # 같은 종류가 이만큼 넘게 겹치면 같은 것을 두 번 읽은 것 (겹친 비율)
DEFAULT_T = 0.1


def _len(w: Wall) -> float:
    return math.dist(w.start, w.end)


def _thick(w: Wall) -> float:
    return w.thickness_m or DEFAULT_T


def _touches(w: Wall, o: Wall) -> list[float]:
    """벽 o가 벽 w에 닿거나 가로지르는 자리들 (w의 start에서 잰 거리)."""
    L = _len(w)
    if L < 1e-6:
        return []
    ux, uy = (w.end[0] - w.start[0]) / L, (w.end[1] - w.start[1]) / L
    tol = (_thick(w) + _thick(o)) / 2 + 0.02

    def uv(p):  # 벽 w 기준: 따라간 거리, 옆으로 벗어난 거리
        dx, dy = p[0] - w.start[0], p[1] - w.start[1]
        return dx * ux + dy * uy, -dx * uy + dy * ux

    (u1, v1), (u2, v2) = uv(o.start), uv(o.end)
    if abs(v1) <= tol and abs(v2) <= tol:
        return []  # 같은 줄에 나란히 놓인 벽: 이어진 벽이지 와 닿는 벽이 아니다
    out = []
    if abs(v1) <= tol:
        out.append(u1)
    elif abs(v2) <= tol:
        out.append(u2)
    elif v1 * v2 < 0:  # 가로지른다
        out.append(u1 + (u2 - u1) * (-v1) / (v2 - v1))
    return [u for u in out if -tol <= u <= L + tol]


def _free(L: float, blocked: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """[0, L]에서 막힌 구간을 뺀 빈 구간들."""
    out, cur = [], 0.0
    for a, b in sorted(blocked):
        if a > cur:
            out.append((cur, min(a, L)))
        cur = max(cur, b)
        if cur >= L:
            break
    if cur < L:
        out.append((cur, L))
    return [(a, b) for a, b in out if b - a > 1e-6]


def _fit(o: Opening, free: list[tuple[float, float]]) -> float | None:
    """가장 조금 옮겨서 들어가는 자리. 없으면 None."""
    best = None
    for a, b in free:
        if b - a + 1e-6 < o.width_m:
            continue
        off = min(max(o.offset_m, a), b - o.width_m)
        if best is None or abs(off - o.offset_m) < abs(best - o.offset_m):
            best = off
    return best


def tidy_openings(room: Room) -> Room:
    walls = {w.wall_id: w for w in room.walls}
    placed: dict[str, list[Opening]] = {}
    result: dict[str, Opening | None] = {}
    # 넓은 문부터 자리를 잡는다 (현관·거실문이 먼저). 창은 문 다음
    order = sorted(room.openings, key=lambda o: (o.type == "window", -o.width_m))
    for o in order:
        w = walls.get(o.wall_id) if o.wall_id else None
        if w is None:
            result[o.opening_id] = o
            continue
        L = _len(w)
        blocked = []
        for other in room.walls:
            if other.wall_id == w.wall_id:
                continue
            for u in _touches(w, other):
                half = _thick(other) / 2 + GAP_M
                blocked.append((u - half, u + half))
        mine = placed.setdefault(w.wall_id, [])
        twin = next((q for q in mine if q.type == o.type and
                     min(q.offset_m + q.width_m, o.offset_m + o.width_m) - max(q.offset_m, o.offset_m) > SAME_M * min(q.width_m, o.width_m)), None)
        if twin is not None:
            result[o.opening_id] = None  # 같은 문·창을 두 번 읽었다
            continue
        blocked += [(q.offset_m - GAP_M, q.offset_m + q.width_m + GAP_M) for q in mine]
        off = _fit(o, _free(L, blocked))
        if off is not None and abs(off - o.offset_m) <= MAX_SHIFT_M:
            if abs(off - o.offset_m) > 1e-6:
                o = o.model_copy(update={"offset_m": round(off, 3)})
        elif o.type != "window":
            result[o.opening_id] = None
            continue
        mine.append(o)
        result[o.opening_id] = o
    kept = [result[o.opening_id] for o in room.openings if result[o.opening_id] is not None]
    return room if kept == room.openings else room.model_copy(update={"openings": kept})


MIN_W_M, MAX_W_M = 0.4, 6.0   # 문·창 폭으로 받아 주는 범위
MIN_H_M = 0.3


class NoRoom(ValueError):
    """그 크기로는 벽에 자리가 없다."""


def resize_opening(room: Room, opening_id: str, width_m: float | None = None, height_m: float | None = None) -> Room:
    """문·창 하나의 폭(과 높이)을 바꾼다. 가운데는 그대로 두고, 벽 끝·닿는 벽·옆 문·창에 걸리면
    같은 벽에서 가까운 빈자리로 조금 옮긴다. 들어갈 자리가 없으면 NoRoom."""
    o = next((q for q in room.openings if q.opening_id == opening_id), None)
    if o is None:
        raise KeyError(opening_id)
    w = next((q for q in room.walls if q.wall_id == o.wall_id), None)
    new_w = o.width_m if width_m is None else float(width_m)
    new_h = o.height_m if height_m is None else float(height_m)
    if not (MIN_W_M - 1e-9 <= new_w <= MAX_W_M + 1e-9):
        raise ValueError("width")
    top = 3.0 if w is None else ((w.measured.height_m if w.measured else None) or w.scanned.height_m or 3.0)
    if not (MIN_H_M - 1e-9 <= new_h) or o.sill_m + new_h > top + 1e-6:
        raise ValueError("height")
    off = o.offset_m + (o.width_m - new_w) / 2
    if w is not None:
        blocked = []
        for other in room.walls:
            if other.wall_id == w.wall_id:
                continue
            for u in _touches(w, other):
                half = _thick(other) / 2 + GAP_M
                blocked.append((u - half, u + half))
        blocked += [(q.offset_m - GAP_M, q.offset_m + q.width_m + GAP_M) for q in room.openings
                    if q.wall_id == w.wall_id and q.opening_id != opening_id]
        # 지금 있는 칸 안에서만 넓힌다 (옆 문·창을 건너뛰어 딴 자리로 가지 않게)
        here = [(a, b) for a, b in _free(_len(w), blocked) if a < o.offset_m + o.width_m and b > o.offset_m]
        fit = _fit(o.model_copy(update={"offset_m": off, "width_m": new_w}), here)
        if fit is None:
            raise NoRoom(opening_id)
        off = fit
    new = o.model_copy(update={"offset_m": round(off, 3), "width_m": round(new_w, 3), "height_m": round(new_h, 3)})
    return room.model_copy(update={"openings": [new if q.opening_id == opening_id else q for q in room.openings]})
