"""평면 기하 도우미. 평면 좌표 (x, y) = 3D (x, z)."""
from __future__ import annotations

import math
from typing import Iterable, Sequence

Pt = tuple[float, float]


def sub(a: Pt, b: Pt) -> Pt:
    return (a[0] - b[0], a[1] - b[1])


def dot(a: Pt, b: Pt) -> float:
    return a[0] * b[0] + a[1] * b[1]


def norm(a: Pt) -> float:
    return math.hypot(a[0], a[1])


def centroid(poly: Sequence[Pt]) -> Pt:
    n = len(poly)
    return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)


class WallFrame:
    """벽 시작점 기준 좌표계: u = 벽 방향 거리, v = 안쪽(영역 쪽) 수직 거리."""

    def __init__(self, start: Pt, end: Pt, inward_hint: Pt):
        self.start = start
        d = sub(end, start)
        self.length = norm(d) or 1e-9
        self.u_axis = (d[0] / self.length, d[1] / self.length)
        n = (-self.u_axis[1], self.u_axis[0])
        mid = (start[0] + d[0] / 2, start[1] + d[1] / 2)
        if dot(n, sub(inward_hint, mid)) < 0:
            n = (-n[0], -n[1])
        self.v_axis = n

    def to_local(self, p: Pt) -> Pt:
        r = sub(p, self.start)
        return (dot(r, self.u_axis), dot(r, self.v_axis))

    def to_world(self, u: float, v: float) -> Pt:
        return (
            self.start[0] + self.u_axis[0] * u + self.v_axis[0] * v,
            self.start[1] + self.u_axis[1] * u + self.v_axis[1] * v,
        )


def point_segment_distance(p: Pt, a: Pt, b: Pt) -> float:
    ab = sub(b, a)
    L2 = dot(ab, ab)
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, dot(sub(p, a), ab) / L2))
    proj = (a[0] + ab[0] * t, a[1] + ab[1] * t)
    return norm(sub(p, proj))


def distance_to_boundary(p: Pt, poly: Sequence[Pt]) -> float:
    return min(point_segment_distance(p, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def ray_exit_distance(origin: Pt, direction: Pt, poly: Sequence[Pt], eps: float = 1e-6) -> float | None:
    """origin에서 direction으로 쏜 광선이 다각형 경계와 만나는 가장 가까운 거리(> eps)."""
    best = None
    ox, oy = origin
    dx, dy = direction
    for i in range(len(poly)):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % len(poly)]
        ex, ey = bx - ax, by - ay
        den = dx * ey - dy * ex
        if abs(den) < 1e-12:
            continue
        t = ((ax - ox) * ey - (ay - oy) * ex) / den
        s = ((ax - ox) * dy - (ay - oy) * dx) / den
        if t > eps and -1e-9 <= s <= 1 + 1e-9:
            best = t if best is None else min(best, t)
    return best


def rect_footprint(cx: float, cy: float, w: float, d: float, yaw: float) -> list[Pt]:
    c, s = math.cos(yaw), math.sin(yaw)
    pts = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        lx, ly = sx * w / 2, sy * d / 2
        pts.append((cx + lx * c - ly * s, cy + lx * s + ly * c))
    return pts


def merge_intervals(iv: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for a, b in sorted((min(a, b), max(a, b)) for a, b in iv):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def free_intervals(lo: float, hi: float, blocked: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    free = []
    cur = lo
    for a, b in merge_intervals(blocked):
        if b <= cur:
            continue
        if a >= hi:
            break
        if a > cur:
            free.append((cur, min(a, hi)))
        cur = max(cur, b)
    if cur < hi:
        free.append((cur, hi))
    return free
