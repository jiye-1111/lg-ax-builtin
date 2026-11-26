"""모션 캡처 걷기에서 한 주기(왼발 딛기 → 다음 왼발 딛기)를 고르는 계산 (worker/walkcycle.py)."""
import math

import numpy as np

from worker.walkcycle import close_loop, detrend_root, foot_strikes, pick_cycle


def fake_walk(n=480, fps=120, speed=1.3, period=1.1):
    """앞(-Y)으로 걷는 가짜 데이터: 발은 디딜 때 멈추고 들 때 두 배 빠르게 간다."""
    t = np.arange(n) / fps
    root = np.stack([np.zeros(n), -speed * t, 0.9 + 0.02 * np.cos(4 * math.pi * t / period)], 1)

    def foot(off):
        ph = ((t / period + off) % 1.0)
        # 0~0.6 디딤(멈춤), 0.6~1 흔듦: 한 주기에 speed*period만큼 간다
        cyc = np.floor(t / period + off)
        prog = np.where(ph < 0.6, 0.0, (ph - 0.6) / 0.4)
        y = -speed * period * (cyc + prog)
        z = np.where(ph < 0.6, 0.08, 0.08 + 0.1 * np.sin(math.pi * (ph - 0.6) / 0.4))
        return np.stack([np.full(n, 0.1), y, z], 1)

    return t, root, foot(0.0), foot(0.5)


def test_foot_strikes_are_the_start_of_each_stance():
    t, root, left, _ = fake_walk()
    s = foot_strikes(left, fps=120)
    gaps = np.diff(s) / 120
    assert len(s) >= 3
    assert np.allclose(gaps, 1.1, atol=0.02)


def test_pick_cycle_prefers_a_middle_cycle_with_matching_ends():
    t, root, left, right = fake_walk()
    a, b = pick_cycle(root, left, right, fps=120)
    assert 0 < a < b < len(t) - 1
    assert abs((b - a) / 120 - 1.1) < 0.02


def test_detrend_removes_forward_travel_but_keeps_bob():
    t, root, *_ = fake_walk()
    a, b = 60, 192
    local, travel = detrend_root(root[a:b + 1])
    assert abs(travel[1] - (root[b, 1] - root[a, 1])) < 1e-9
    assert np.abs(local[:, 1]).max() < 1e-6          # 앞으로 가는 몫은 웹이 옮긴다
    assert np.ptp(local[:, 2]) > 0.03                 # 오르내림은 남긴다


def test_close_loop_makes_last_frame_equal_first():
    x = np.linspace(0, 1, 40)[:, None] * np.ones((1, 3))
    y = close_loop(x, blend=8)
    assert np.allclose(y[-1], y[0])
    assert np.allclose(y[:20], x[:20])               # 앞부분은 그대로
