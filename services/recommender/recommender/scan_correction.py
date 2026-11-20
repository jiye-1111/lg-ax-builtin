"""LiDAR 스캔 오차 보정 (연구용, 아직 판정에는 연결하지 않음).

조사 내용과 수치 근거: docs/research/lidar-error-correction.md

- angle_deviation_deg / snap_manhattan: 방의 주축(직각 두 방향)을 길이 가중 평균으로 구하고,
  주축에서 tol_deg 이내로 기운 벽만 벽 중점을 기준으로 돌려 맞춘다. 길이와 scanned 값은 그대로.
- fit_scale: (스캔 길이, 실제 길이) 쌍으로 배율 하나를 최소제곱으로 구한다. 실제 길이는
  사람이 잰 값이나 도면 치수처럼 믿을 수 있는 값만 넣는다.
- margin_mm: 길이에 비례하는 오차와 고정 오차를 합친 여유 (k·√(abs² + (rel·L)²)).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from core.models import Room

# 오차 모델 기본값 (근거: 연구 문서 §2). 판정에 쓰기 전에 .env로 옮긴다.
SIGMA_ABS_MM = 10.0       # 길이와 무관한 오차 (벽면 노이즈, 모서리 위치)
SIGMA_REL = 0.010         # 보정 전 길이 비례 오차 1%
SIGMA_REL_CALIBRATED = 0.003  # 실측 1개로 배율 보정 후 남는 비례 오차
K_SIGMA = 2.0             # 약 95%


def _dir(w) -> float:
    return math.atan2(w.end[1] - w.start[1], w.end[0] - w.start[0])


def _weighted_axis(walls) -> float:
    sx = sy = 0.0
    for w in walls:
        L = math.dist(w.start, w.end)
        sx += L * math.cos(4 * _dir(w))
        sy += L * math.sin(4 * _dir(w))
    return (math.atan2(sy, sx) / 4) % (math.pi / 2)


def room_axis(room: Room, tol_deg: float = 10.0) -> float:
    """주축 각도(라디안, 0 ≤ θ < π/2). RANSAC처럼 각 벽 방향을 후보로 놓고, tol_deg 안에 드는
    벽 길이 합이 가장 큰 후보를 고른 뒤 그 벽들만 길이 가중 평균한다
    (각도를 4배 하면 직각 방향이 하나로 겹친다). 진짜 사선 벽은 평균을 끌고 가지 못한다."""
    tol = math.radians(tol_deg)
    best, best_score = None, -1.0
    for cand in room.walls:
        a = _dir(cand) % (math.pi / 2)
        score = sum(math.dist(w.start, w.end) for w in room.walls if abs(_dev(_dir(w), a)) <= tol)
        if score > best_score:
            best, best_score = a, score
    if best is None:
        return 0.0
    inliers = [w for w in room.walls if abs(_dev(_dir(w), best)) <= tol]
    return _weighted_axis(inliers)


def _dev(theta: float, axis: float) -> float:
    """theta를 가장 가까운 주축 방향에 맞추려면 돌려야 하는 각 (라디안, -45°~45°)."""
    q = math.pi / 2
    return ((theta - axis + q / 2) % q) - q / 2


def angle_deviation_deg(room: Room, tol_deg: float = 10.0) -> dict[str, float]:
    axis = room_axis(room, tol_deg)
    return {w.wall_id: abs(math.degrees(_dev(_dir(w), axis))) for w in room.walls}


def snap_manhattan(room: Room, tol_deg: float = 10.0) -> Room:
    axis = room_axis(room, tol_deg)
    walls = []
    for w in room.walls:
        d = _dev(_dir(w), axis)
        if abs(math.degrees(d)) > tol_deg or d == 0:
            walls.append(w.model_copy())
            continue
        mx, my = (w.start[0] + w.end[0]) / 2, (w.start[1] + w.end[1]) / 2
        c, s = math.cos(-d), math.sin(-d)

        def rot(p):
            x, y = p[0] - mx, p[1] - my
            return (mx + x * c - y * s, my + x * s + y * c)

        walls.append(w.model_copy(update={"start": rot(w.start), "end": rot(w.end)}))
    return room.model_copy(update={"walls": walls})


@dataclass(frozen=True)
class ScaleFit:
    scale: float          # 실제 / 스캔
    residual_mm: float    # 기준값들을 배율 하나로 맞추고 남은 RMS 오차
    n: int


def fit_scale(pairs: list[tuple[float, float]]) -> ScaleFit:
    """pairs = [(스캔 길이 m, 실제 길이 m)]. s = Σab / Σa² (원점 지나는 최소제곱)."""
    if not pairs:
        raise ValueError("기준 길이가 하나 이상 필요하다")
    if any(a <= 0 or b <= 0 for a, b in pairs):
        raise ValueError("길이는 0보다 커야 한다")
    s = sum(a * b for a, b in pairs) / sum(a * a for a, _ in pairs)
    rms = math.sqrt(sum((s * a - b) ** 2 for a, b in pairs) / len(pairs)) * 1000
    return ScaleFit(scale=s, residual_mm=round(rms, 3), n=len(pairs))


def corrected_length_m(scanned_m: float, fit: ScaleFit) -> float:
    return scanned_m * fit.scale


def margin_mm(length_m: float, calibrated: bool = False, *, sigma_abs_mm: float = SIGMA_ABS_MM,
              sigma_rel: float | None = None, k: float = K_SIGMA) -> float:
    rel = sigma_rel if sigma_rel is not None else (SIGMA_REL_CALIBRATED if calibrated else SIGMA_REL)
    return k * math.hypot(sigma_abs_mm, rel * length_m * 1000)
