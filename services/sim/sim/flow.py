"""이동 동선 (S8). 바닥을 격자로 나눠 벽·가구·놓은 제품을 막힌 칸으로 두고, 현관에서 각 지점까지 A* 최단 경로.

- 사람 몸 폭(body_width_m)의 절반만큼 비어 있어야 지나갈 수 있다.
- 통로 폭 ≈ 경로 위 칸에서 가장 가까운 장애물까지 거리 × 2. min_width_m보다 좁으면 '좁음'.
- 경로는 좁은 칸을 피하도록 가중치를 준다 (넓은 길이 있으면 그쪽으로).
"""
from __future__ import annotations

import heapq
import math
import os
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from core.models import Room
from recommender.pose import _inward, rect

Pt = tuple[float, float]
SQ2 = math.sqrt(2)


@dataclass(frozen=True)
class FlowConfig:
    cell_m: float = 0.05
    min_width_m: float = 0.9
    body_width_m: float = 0.6
    narrow_penalty: float = 3.0

    @classmethod
    def from_env(cls) -> "FlowConfig":
        return cls(min_width_m=float(os.getenv("FLOW_MIN_WIDTH_M", 0.9)))

    def assumptions(self) -> list[str]:
        return [f"통로 최소 폭 {self.min_width_m:g} m, 사람 몸 폭 {self.body_width_m:g} m",
                "현관 = 가장 넓은 문 (방 안쪽 0.4 m에서 출발)", "문은 열려 있고, 가전 문 열림 범위는 따로 표시",
                "작업 삼각형 권장: 합계 4.0~7.9 m, 각 변 1.2~2.7 m (NKBA 주방 설계 지침)"]


def _pip(p: Pt, poly: Sequence[Pt]) -> bool:
    x, y = p
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


class _Grid:
    def __init__(self, room: Room, cfg: FlowConfig, polys: list[Sequence[Pt]], gaps: Iterable[Sequence[Pt]] = ()):
        xs = [c for w in room.walls for c in (w.start[0], w.end[0])]
        ys = [c for w in room.walls for c in (w.start[1], w.end[1])]
        pad = 0.6
        self.x0, self.y0, self.c = min(xs) - pad, min(ys) - pad, cfg.cell_m
        self.nx = math.ceil((max(xs) - min(xs) + 2 * pad) / self.c)
        self.ny = math.ceil((max(ys) - min(ys) + 2 * pad) / self.c)
        self.block = [[False] * self.nx for _ in range(self.ny)]
        self._walls(room)
        for poly in polys:
            self._fill(poly)
        for poly in gaps:  # 열리는 문: 벽에 난 틈
            self._fill(poly, False)
        self.clear = self._distance()

    def center(self, i: int, j: int) -> Pt:
        return (self.x0 + (i + 0.5) * self.c, self.y0 + (j + 0.5) * self.c)

    def cell(self, p: Pt) -> tuple[int, int]:
        return (min(self.nx - 1, max(0, int((p[0] - self.x0) / self.c))),
                min(self.ny - 1, max(0, int((p[1] - self.y0) / self.c))))

    def _walls(self, room: Room):
        for w in room.walls:
            (ax, ay), (bx, by) = w.start, w.end
            L = math.hypot(bx - ax, by - ay) or 1e-9
            ux, uy = (bx - ax) / L, (by - ay) / L
            half = (w.thickness_m or 0.1) / 2 + self.c / 2
            gaps = [(o.offset_m, o.offset_m + o.width_m) for o in room.openings
                    if o.wall_id == w.wall_id and o.type in ("door", "opening")]
            i0, j0 = self.cell((min(ax, bx) - half, min(ay, by) - half))
            i1, j1 = self.cell((max(ax, bx) + half, max(ay, by) + half))
            for j in range(j0, j1 + 1):
                for i in range(i0, i1 + 1):
                    x, y = self.center(i, j)
                    t = (x - ax) * ux + (y - ay) * uy
                    d = abs(-(x - ax) * uy + (y - ay) * ux)
                    if -half <= t <= L + half and d <= half and not any(g0 < t < g1 for g0, g1 in gaps):
                        self.block[j][i] = True

    def _fill(self, poly: Sequence[Pt], blocked: bool = True):
        i0, j0 = self.cell((min(p[0] for p in poly), min(p[1] for p in poly)))
        i1, j1 = self.cell((max(p[0] for p in poly), max(p[1] for p in poly)))
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                if _pip(self.center(i, j), poly):
                    self.block[j][i] = blocked

    def _distance(self) -> list[list[float]]:
        """가장 가까운 막힌 칸 '가장자리'까지 거리(m). 두 번 훑는 근사 유클리드 거리 변환."""
        INF = 1e9
        d = [[0.0 if self.block[j][i] else INF for i in range(self.nx)] for j in range(self.ny)]
        src = [[(i, j) if self.block[j][i] else None for i in range(self.nx)] for j in range(self.ny)]
        passes = [((0, self.ny, 1), (0, self.nx, 1), ((-1, -1), (0, -1), (1, -1), (-1, 0))),
                  ((self.ny - 1, -1, -1), (self.nx - 1, -1, -1), ((1, 1), (0, 1), (-1, 1), (1, 0)))]
        for (js, je, jd), (is_, ie, id_), nbrs in passes:
            for j in range(js, je, jd):
                for i in range(is_, ie, id_):
                    for di, dj in nbrs:
                        a, b = i + di, j + dj
                        if 0 <= a < self.nx and 0 <= b < self.ny and src[b][a] is not None:
                            si, sj = src[b][a]
                            v = math.hypot(i - si, j - sj)
                            if v < d[j][i]:
                                d[j][i], src[j][i] = v, (si, sj)
        # 칸 중심 간 거리 → 장애물 가장자리까지 (반 칸 뺌)
        return [[max(0.0, (v - 0.5) * self.c) if v < INF else 99.0 for v in row] for row in d]


def _entrance(room: Room) -> Optional[dict]:
    doors = [o for o in room.openings if o.type == "door" and o.wall_id] or [o for o in room.openings if o.type == "opening" and o.wall_id]
    if not doors:
        return None
    o = max(doors, key=lambda x: x.width_m)
    f = _inward(room, room.wall(o.wall_id))
    return {"opening_id": o.opening_id, "point": f.to_world(o.offset_m + o.width_m / 2, (room.wall(o.wall_id).thickness_m or 0.1) / 2 + 0.4)}


def _astar(g: _Grid, start: tuple[int, int], goal: tuple[int, int], cfg: FlowConfig, ok) -> Optional[list[tuple[int, int]]]:
    half_min = cfg.min_width_m / 2
    h = lambda a: math.hypot(a[0] - goal[0], a[1] - goal[1])  # noqa: E731
    openq = [(h(start), 0.0, start)]
    came, cost = {start: None}, {start: 0.0}
    while openq:
        _, c0, cur = heapq.heappop(openq)
        if cur == goal:
            path = []
            while cur is not None:
                path.append(cur)
                cur = came[cur]
            return path[::-1]
        if c0 > cost[cur]:
            continue
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if not di and not dj:
                    continue
                n = (cur[0] + di, cur[1] + dj)
                if not ok(n):
                    continue
                step = SQ2 if di and dj else 1.0
                if g.clear[n[1]][n[0]] < half_min:
                    step *= 1 + cfg.narrow_penalty
                nc = c0 + step
                if nc < cost.get(n, math.inf):
                    cost[n], came[n] = nc, cur
                    heapq.heappush(openq, (nc + h(n), nc, n))
    return None


def plan_routes(room: Room, targets: dict[str, Pt], cfg: FlowConfig | None = None, hidden: Iterable[str] = (),
                extra: Iterable[Sequence[Pt]] = (), triangle: Optional[tuple[str, str, str]] = None,
                start: Optional[Pt] = None, gaps: Iterable[Sequence[Pt]] = ()) -> dict:
    """start: 출발 자리를 직접 정했으면 현관 대신 거기서 걷는다. gaps: 열리는 문 자리 (막힌 칸을 튼다)."""
    cfg = cfg or FlowConfig.from_env()
    hidden = set(hidden)
    polys = [rect((o.position[0], o.position[2]), o.yaw_rad, o.bbox_m.w, o.bbox_m.d) for o in room.objects if o.object_id not in hidden]
    polys += [list(p) for p in extra]
    g = _Grid(room, cfg, polys, gaps)
    body = cfg.body_width_m / 2
    ok = lambda n: 0 <= n[0] < g.nx and 0 <= n[1] < g.ny and not g.block[n[1]][n[0]] and g.clear[n[1]][n[0]] >= body - 1e-9  # noqa: E731

    def nearest_ok(p: Pt) -> Optional[tuple[int, int]]:
        s = g.cell(p)
        if ok(s):
            return s
        seen, q = {s}, [s]
        while q:
            nq = []
            for a in q:
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (a[0] + di, a[1] + dj)
                    if 0 <= n[0] < g.nx and 0 <= n[1] < g.ny and n not in seen:
                        if ok(n):
                            return n
                        seen.add(n)
                        nq.append(n)
            q = nq
            if len(seen) > 40000:
                break
        return None

    ent = _entrance(room)
    out = {"entrance": {"opening_id": ent["opening_id"], "point": [round(v, 3) for v in ent["point"]]} if ent else None,
           "routes": {}, "assumptions": cfg.assumptions()}
    origin = tuple(start) if start else (ent["point"] if ent else None)
    start = nearest_ok(origin) if origin else None
    out["start"] = [round(v, 3) for v in g.center(*start)] if start else None
    for name, p in targets.items():
        goal = nearest_ok(p)
        path = _astar(g, start, goal, cfg, ok) if start and goal else None
        if not path:
            out["routes"][name] = {"reachable": False, "length_m": None, "min_width_m": None, "narrow": [], "path": []}
            continue
        length = sum(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(path, path[1:])) * g.c
        widths = [2 * g.clear[j][i] for i, j in path]
        # 출발·도착 근처(문틀, 제품 앞)는 원래 좁으므로 폭 계산에서 0.3 m씩 뺀다
        trim = max(1, int(0.3 / g.c))
        core = widths[trim:-trim] or widths
        narrow = [[round(v, 2) for v in g.center(*path[k])] for k in range(trim, len(path) - trim)
                  if widths[k] < cfg.min_width_m][:: max(1, int(0.2 / g.c))]
        out["routes"][name] = {"reachable": True, "length_m": round(length, 2), "min_width_m": round(min(core), 2),
                               "narrow": narrow, "path": [[round(v, 3) for v in g.center(*c)] for c in path[:: max(1, int(0.1 / g.c))] + [path[-1]]]}
    if triangle and all(k in targets for k in triangle):
        a, b, c = (targets[k] for k in triangle)
        legs = [math.dist(a, b), math.dist(b, c), math.dist(c, a)]
        per = sum(legs)
        out["triangle"] = {"names": list(triangle), "legs_m": [round(x, 2) for x in legs], "perimeter_m": round(per, 2),
                           "ok": 4.0 <= per <= 7.9 and all(1.2 <= x <= 2.7 for x in legs)}
    return out
