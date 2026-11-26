"""기준 벽: 줄자로 잰 벽 길이로 나머지 벽의 스캔 길이를 바로잡는다. 순수 계산.

라이다 스캔 오차는 길이에 비례하는 부분(길수록 더 틀린다)과 벽마다 따로 생기는 부분으로 나뉜다.
잰 벽에서 비례하는 부분(배율)을 구해 다른 벽에 곱한다. 짧은 벽의 차이는 벽마다 따로 생긴 오차일 수 있어서
벽이 짧을수록 배율을 덜 믿는다. 규칙은 docs/specs/fit-rules.md '기준 벽'과 같아야 한다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

SCALE_SD = 0.012       # 길이에 비례하는 오차 (1σ, 길이의 1.2%)
WALL_SD_M = 0.01       # 벽마다 따로 생기는 오차 (1σ)
TRUST_M = 0.06         # 스캔과 이만큼(또는 TRUST_RATIO) 넘게 다르면 배율에는 쓰지 않는다
TRUST_RATIO = 0.03
TWIN_M = 0.03          # 스캔 길이가 이 안쪽으로 같고 마주 보면 같은 길이의 맞은편 벽
TWIN_DEG = 3.0
MEASURED_BY = ("technician", "customer")
ESTIMATED_BY = "reference"


@dataclass
class Estimate:
    scale: float = 1.0
    lengths: dict[str, float] = field(default_factory=dict)  # 바로잡은 벽 {wall_id: 길이 m}. 잰 벽·도면 벽은 없다
    used: list[str] = field(default_factory=list)            # 배율에 쓴 잰 벽
    skipped: list[str] = field(default_factory=list)         # 스캔과 너무 달라 그 벽만 고친 벽


def is_measured(wall) -> bool:
    m = wall.measured
    return m is not None and m.length_m is not None and m.by in MEASURED_BY


def _facing(a, b) -> bool:
    """나란하고, 떨어져 있고, 서로 마주 보는 구간이 있다"""
    ax, ay = a.end[0] - a.start[0], a.end[1] - a.start[1]
    bx, by = b.end[0] - b.start[0], b.end[1] - b.start[1]
    la, lb = math.hypot(ax, ay), math.hypot(bx, by)
    if la < 1e-6 or lb < 1e-6:
        return False
    if abs(ax * by - ay * bx) / (la * lb) > math.sin(math.radians(TWIN_DEG)):
        return False
    ux, uy = ax / la, ay / la
    ts = sorted(((p[0] - a.start[0]) * ux + (p[1] - a.start[1]) * uy) for p in (b.start, b.end))
    apart = abs((b.start[0] - a.start[0]) * uy - (b.start[1] - a.start[1]) * ux)
    return apart > 0.05 and min(ts[1], la) - max(ts[0], 0.0) > 0.5 * min(la, lb)


def estimate(walls) -> Estimate:
    out = Estimate()
    refs = []
    for w in walls:
        if not is_measured(w):
            continue
        L = w.scanned.length_m
        if abs(w.measured.length_m - L) <= max(TRUST_M, TRUST_RATIO * L):
            refs.append(w)
            out.used.append(w.wall_id)
        else:
            out.skipped.append(w.wall_id)
    if not refs:
        return out
    num = sum(w.scanned.length_m * (w.measured.length_m - w.scanned.length_m) for w in refs)
    den = sum(w.scanned.length_m ** 2 for w in refs) + (WALL_SD_M / SCALE_SD) ** 2
    out.scale = 1.0 + num / den
    for w in walls:
        m = w.measured
        if m is not None and m.length_m is not None and m.by != ESTIMATED_BY:
            continue  # 잰 벽, 도면으로 맞춘 벽은 그대로
        L = w.scanned.length_m
        twin = next((r for r in refs if abs(r.scanned.length_m - L) <= TWIN_M and _facing(r, w)), None)
        out.lengths[w.wall_id] = round(twin.measured.length_m if twin else L * out.scale, 3)
    return out
