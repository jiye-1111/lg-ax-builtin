"""모션 캡처 걷기에서 고리처럼 이어 돌릴 한 주기를 고른다 (numpy만, Blender 없이 테스트).

좌표는 Blender 월드(Z-up), 단위 m. 걷는 쪽은 어느 쪽이든 된다.
한 주기 = 왼발이 바닥에 닿은 때부터 다음에 닿을 때까지 (두 걸음).
"""
from __future__ import annotations

import numpy as np


def _hspeed(p: np.ndarray, fps: float) -> np.ndarray:
    v = np.zeros(len(p))
    v[1:] = np.linalg.norm(np.diff(p[:, :2], axis=0), axis=1) * fps
    v[0] = v[1] if len(v) > 1 else 0.0
    return v


def foot_strikes(foot: np.ndarray, fps: float, still: float = 0.35) -> np.ndarray:
    """발이 멈추기 시작한 프레임들 (디딤의 시작). still = 걷는 빠르기 대비 멈췄다고 볼 비율."""
    v = _hspeed(foot, fps)
    k = max(1, int(round(fps * 0.03)))  # 30 ms 이동 평균으로 잡음을 줄인다
    v = np.convolve(v, np.ones(k) / k, mode="same")
    moving = v > still * max(np.median(v[v > 0]) if np.any(v > 0) else 0.0, 1e-6)
    out = [i for i in range(1, len(v)) if moving[i - 1] and not moving[i]]
    # 짧게 멈칫한 것(0.3초 안에 또 멈춤)은 같은 디딤으로 본다
    keep: list[int] = []
    for i in out:
        if not keep or (i - keep[-1]) > 0.3 * fps:
            keep.append(i)
    return np.array(keep, dtype=int)


def _mismatch(root, left, right, a, b) -> float:
    """주기 처음과 끝 자세 차이: 골반 기준 두 발 자리와 골반 높이."""
    def rel(i):
        return np.concatenate([(left[i] - root[i]), (right[i] - root[i]), root[i, 2:3]])
    return float(np.linalg.norm(rel(a) - rel(b)))


def pick_cycle(root: np.ndarray, left: np.ndarray, right: np.ndarray, fps: float) -> tuple[int, int]:
    """처음·끝 주기는 빼고(출발·정지라 걸음이 다르다) 끝이 가장 잘 이어지는 주기를 고른다."""
    s = foot_strikes(left, fps)
    if len(s) < 2:
        raise ValueError("왼발 디딤이 두 번 이상 있어야 한 주기를 고를 수 있다")
    cands = list(zip(s[:-1], s[1:]))
    inner = cands[1:-1] or cands
    mid = len(root) / 2

    def cost(ab):
        a, b = ab
        return _mismatch(root, left, right, a, b) + 1e-4 * abs((a + b) / 2 - mid)
    a, b = min(inner, key=cost)
    return int(a), int(b)


def detrend_root(root: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """골반 자리에서 주기 동안 앞으로 간 몫(직선)을 뺀다. 오르내림·좌우 흔들림은 남는다.
    돌려주는 것: (처음 자리 기준 남은 움직임, 한 주기에 간 거리 벡터)"""
    n = len(root)
    travel = root[-1] - root[0]
    travel = np.array([travel[0], travel[1], 0.0])
    u = np.linspace(0.0, 1.0, n)[:, None]
    local = root - root[0] - u * travel
    return local, travel


def close_loop(x: np.ndarray, blend: int = 8) -> np.ndarray:
    """마지막 blend 프레임을 처음 값 쪽으로 서서히 끌어 끝 = 처음이 되게 한다 (이음매 없는 반복)."""
    y = np.array(x, dtype=float, copy=True)
    n = len(y)
    blend = min(blend, n - 1)
    err = y[0] - y[-1]
    for j in range(blend):
        i = n - blend + j
        w = (j + 1) / blend
        w = w * w * (3 - 2 * w)
        y[i] = y[i] + err * w
    return y
