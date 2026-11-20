"""스캔 오차 보정 (docs/research/lidar-error-correction.md).

- 직각 맞추기: 거의 직각인 벽을 방의 주축에 맞춘다. 길이(스캔값)는 그대로 둔다.
- 배율 보정: 사람이 잰 길이 1개 이상으로 스캔 전체 배율을 구한다.
- 길이 따라 커지는 여유: 짧은 자리보다 긴 자리가 오차가 크다.
"""
import math

import pytest

from core import config
from core.models import Room, ScannedDims, Wall
from recommender.scan_correction import (
    angle_deviation_deg,
    corrected_length_m,
    fit_scale,
    margin_mm,
    snap_manhattan,
)
from worker.converter import convert_usdz

SAMPLE = config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"


def _wall(i, start, end):
    L = math.dist(start, end)
    return Wall(wall_id=f"w{i}", start=start, end=end, scanned=ScannedDims(length_m=L, height_m=2.4))


def _box(rot_deg=0.0, skew_deg=(0, 0, 0, 0)):
    """4×3 m 방. 벽마다 skew만큼 비틀어진 스캔을 흉내 낸다."""
    pts = [(0, 0), (4, 0), (4, 3), (0, 3)]
    walls = []
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        t = math.radians(rot_deg + skew_deg[i])
        def rot(p):
            x, y = p[0] - mx, p[1] - my
            return (mx + x * math.cos(t) - y * math.sin(t), my + x * math.sin(t) + y * math.cos(t))
        g = math.radians(rot_deg)
        ra, rb = rot(a), rot(b)
        # 방 전체 회전
        R = lambda p: (p[0] * math.cos(g) - p[1] * math.sin(g), p[0] * math.sin(g) + p[1] * math.cos(g))
        walls.append(_wall(i + 1, R(ra), R(rb)) if rot_deg else _wall(i + 1, ra, rb))
    return Room(walls=walls)


def test_square_room_has_no_deviation():
    assert max(angle_deviation_deg(_box()).values()) < 1e-6


def test_deviation_ignores_whole_room_rotation():
    room = _box(rot_deg=17.0)
    assert max(angle_deviation_deg(room).values()) < 1e-6


def test_snap_fixes_small_skew_and_keeps_length():
    room = _box(skew_deg=(1.5, -2.0, 0.8, 0.0))
    before = angle_deviation_deg(room)
    assert before["w2"] == pytest.approx(2.0, abs=0.5)  # 주축은 기운 벽들의 가중 평균이라 조금 움직인다
    snapped = snap_manhattan(room)
    after = angle_deviation_deg(snapped)
    assert max(after.values()) < 0.01
    for a, b in zip(room.walls, snapped.walls):
        assert math.dist(b.start, b.end) == pytest.approx(a.scanned.length_m, abs=1e-6)
        assert b.scanned == a.scanned  # 스캔값은 절대 덮어쓰지 않는다


def test_snap_leaves_real_diagonal_walls_alone():
    room = _box(skew_deg=(0, 30.0, 0, 0))
    snapped = snap_manhattan(room, tol_deg=10)
    assert angle_deviation_deg(snapped)["w2"] == pytest.approx(30.0, abs=0.5)


def test_fit_scale_from_one_reference():
    fit = fit_scale([(4.040, 4.000)])
    assert fit.scale == pytest.approx(4.0 / 4.04)
    assert fit.residual_mm == 0
    assert corrected_length_m(2.02, fit) == pytest.approx(2.0)


def test_fit_scale_from_several_references_reports_residual():
    fit = fit_scale([(4.040, 4.000), (0.909, 0.900), (2.010, 2.000)])
    assert fit.scale == pytest.approx(0.9906, abs=5e-4)
    assert 0 < fit.residual_mm < 15


def test_fit_scale_rejects_bad_input():
    with pytest.raises(ValueError):
        fit_scale([])
    with pytest.raises(ValueError):
        fit_scale([(0.0, 1.0)])


def test_margin_grows_with_length_and_shrinks_after_calibration():
    short, long_ = margin_mm(0.6), margin_mm(3.0)
    assert long_ > short
    assert margin_mm(3.0, calibrated=True) < long_
    assert margin_mm(0.0) > 0  # 절대 오차는 남는다


def test_real_ugscan_is_already_orthogonal():
    """실제 UGScan(RoomPlan) 출력은 벽이 이미 주축에 맞춰져 있다 (0.01° 이하)."""
    room = convert_usdz(SAMPLE)
    dev = angle_deviation_deg(room)
    assert max(dev.values()) < 0.05
    snapped = snap_manhattan(room)
    for a, b in zip(room.walls, snapped.walls):
        assert math.dist(a.start, b.start) < 0.002
