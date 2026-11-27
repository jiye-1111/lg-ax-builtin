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
OFF_M = 0.5            # 이만큼(또는 OFF_RATIO) 넘게 다르면 벽을 잘못 골랐거나 잘못 넣은 것
OFF_RATIO = 0.2

# 도면으로 만든 집: AI가 그림에서 읽은 길이라 집 전체 배율이 크게 틀릴 수 있다 (치수가 없으면 방문 폭 90 cm로 어림)
PLAN_SCALE_SD = 0.15
PLAN_WALL_SD_M = 0.03
PLAN_TRUST_RATIO = 0.05   # 배율을 뺀 뒤에도 이만큼 넘게 다르면 그 벽만 도면에서 잘못 읽힌 것
PLAN_OFF_RATIO = 0.6
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


def off_limit(scan_m: float, plan: bool = False) -> float:
    """잰 길이가 스캔(또는 도면) 길이와 이만큼 넘게 다르면 받지 않는다 (m)"""
    return PLAN_OFF_RATIO * scan_m if plan else max(OFF_M, OFF_RATIO * scan_m)


def _scale(refs, scale_sd: float, wall_sd: float) -> float:
    num = sum(w.scanned.length_m * (w.measured.length_m - w.scanned.length_m) for w in refs)
    den = sum(w.scanned.length_m ** 2 for w in refs) + (wall_sd / scale_sd) ** 2
    return 1.0 + num / den


def _plan_refs(measured):
    """도면 집: 잰 벽들의 배율 가운데값에서 크게 벗어난 벽만 뺀다 (배율 자체가 크게 틀릴 수 있어서)"""
    ratios = sorted(w.measured.length_m / w.scanned.length_m for w in measured)
    mid = ratios[len(ratios) // 2] if len(ratios) % 2 else ratios[len(ratios) // 2 - 1]
    return [w for w in measured if abs(w.measured.length_m / w.scanned.length_m - mid) <= PLAN_TRUST_RATIO * mid]


def estimate(walls, plan: bool = False) -> Estimate:
    """plan=True: 도면으로 만든 집 (배율 오차가 크고, 벽마다 오차도 크다)"""
    out = Estimate()
    measured = [w for w in walls if is_measured(w)]
    if plan:
        refs = _plan_refs(measured) if measured else []
    else:
        refs = [w for w in measured
                if abs(w.measured.length_m - w.scanned.length_m) <= max(TRUST_M, TRUST_RATIO * w.scanned.length_m)]
    out.used = [w.wall_id for w in refs]
    out.skipped = [w.wall_id for w in measured if w.wall_id not in out.used]
    if not refs:
        return out
    out.scale = _scale(refs, PLAN_SCALE_SD, PLAN_WALL_SD_M) if plan else _scale(refs, SCALE_SD, WALL_SD_M)
    for w in walls:
        m = w.measured
        if m is not None and m.length_m is not None and m.by != ESTIMATED_BY:
            continue  # 잰 벽, 도면으로 맞춘 벽은 그대로
        L = w.scanned.length_m
        twin = next((r for r in refs if abs(r.scanned.length_m - L) <= TWIN_M * (3 if plan else 1) and _facing(r, w)), None)
        out.lengths[w.wall_id] = round(twin.measured.length_m if twin else L * out.scale, 3)
    return out
