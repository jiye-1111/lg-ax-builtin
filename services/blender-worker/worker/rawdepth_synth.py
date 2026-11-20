"""시험용 합성 캡처: 상자 모양 주방을 Stray Scanner 형식 원본 깊이 프레임으로 만든다.
실제 캡처가 없을 때 rawdepth 파이프라인을 테스트·실험하는 데만 쓴다."""
from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
from PIL import Image

from core.models import Room, ScannedDims, Wall

from .rawdepth import Frame, mat_to_quat

BOX = ((0.0, 0.0, 0.0), (3.0, 2.4, 2.4))  # (x, y=높이, z) 최소·최대, m
W, H = 256, 192
RGB_W, RGB_H = 1920, 1440


def _K(w=W, h=H, f=212.0):
    return np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1.0]])


def _look_at(eye, target):
    """OpenCV 카메라(x 오른쪽, y 아래, z 앞) → 월드(Y-up) 변환 T_wc."""
    z = np.asarray(target, float) - eye
    z /= np.linalg.norm(z)
    x = np.cross(z, [0, 1.0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    T = np.eye(4)
    T[:3, :3] = np.stack([x, y, z], axis=1)
    T[:3, 3] = eye
    return T


def _ray_box_depth(T, K, lo, hi):
    u, v = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
    rays_c = np.stack([(u - K[0, 2]) / K[0, 0], (v - K[1, 2]) / K[1, 1], np.ones_like(u)], -1)
    R, o = T[:3, :3], T[:3, 3]
    d = rays_c @ R.T
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.stack([np.where(d[..., i] > 0, (hi[i] - o[i]) / d[..., i], (lo[i] - o[i]) / d[..., i]) for i in range(3)], -1)
    t = np.where(np.isfinite(t) & (t > 0), t, np.inf).min(-1)
    return t  # 광선 길이 = z 깊이 (rays_c의 z = 1)


def synth_frames(n=24, seed=0, noise_m=0.01, box=BOX, drift_m=0.0) -> list[Frame]:
    """drift_m: 프레임마다 쌓이는 위치 추정 오차(랜덤 워크 한 걸음 크기). 깊이는 참 위치에서, 포즈는 밀린 값으로."""
    rng = np.random.default_rng(seed)
    lo, hi = np.array(box[0]), np.array(box[1])
    c = (lo + hi) / 2
    K = _K()
    frames = []
    drift = np.zeros(3)
    for i in range(n):
        a = 2 * math.pi * i / n
        eye = c + np.array([0.35 * math.cos(a), -0.1 + 0.2 * rng.random(), 0.3 * math.sin(a)])
        tgt = c + np.array([2.0 * math.cos(a + 0.6), -0.4 + 0.8 * rng.random(), 2.0 * math.sin(a + 0.6)])
        T = _look_at(eye, tgt)
        z = _ray_box_depth(T, K, lo, hi)
        conf = np.where(z < 1.6, 2, np.where(z < 2.4, 1, 0)).astype(np.uint8)
        z = z + rng.normal(0, noise_m, z.shape) * np.maximum(z, 0.5)
        drift = drift + rng.normal(0, drift_m, 3) if drift_m else drift
        T = T.copy()
        T[:3, 3] += drift
        frames.append(Frame(depth_m=z.astype(np.float32), conf=conf, K=K.copy(), T_wc=T))
    return frames


def write_stray(path, frames: list[Frame]) -> None:
    """Stray Scanner 내보내기 형식: depth/·confidence/ 16bit PNG(mm), odometry.csv(RGB 해상도 내부 파라미터)."""
    path = Path(path)
    (path / "depth").mkdir(parents=True, exist_ok=True)
    (path / "confidence").mkdir(parents=True, exist_ok=True)
    s = RGB_W / W
    with open(path / "odometry.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "frame", "x", "y", "z", "qx", "qy", "qz", "qw", "fx", "fy", "cx", "cy"])
        for i, fr in enumerate(frames):
            mm = np.clip(np.round(fr.depth_m * 1000), 0, 65535).astype(np.uint16)
            Image.fromarray(mm).save(path / "depth" / f"{i:06d}.png")
            Image.fromarray(fr.conf).save(path / "confidence" / f"{i:06d}.png")
            q = mat_to_quat(fr.T_wc[:3, :3])
            t = fr.T_wc[:3, 3]
            w.writerow([i * 0.1, f"{i:06d}", *t, *q, fr.K[0, 0] * s, fr.K[1, 1] * s, fr.K[0, 2] * s, fr.K[1, 2] * s])


def roomplan_with_error(scale=1.02, grid=0.03, yaw_deg=0.0, shift=(0.0, 0.0), box=BOX, thick=0.16) -> Room:
    """BOX 방을 RoomPlan처럼 내보낸 결과 + 오차. 벽은 두께 중심선, 길이는 중심선 사이 거리(실제 UGScan과 같은 규칙)."""
    q = lambda v: round(v / grid) * grid  # noqa: E731
    x0, x1 = box[0][0] * scale - thick / 2, box[1][0] * scale + thick / 2
    z0, z1 = box[0][2] * scale - thick / 2, box[1][2] * scale + thick / 2
    x0, x1, z0, z1 = q(x0), q(x1), q(z0), q(z1)
    h = q(box[1][1] * scale)
    a = math.radians(yaw_deg)

    def tr(p):
        x, z = p
        return (x * math.cos(a) - z * math.sin(a) + shift[0], x * math.sin(a) + z * math.cos(a) + shift[1])

    corners = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    walls = []
    for i in range(4):
        s, e = tr(corners[i]), tr(corners[(i + 1) % 4])
        walls.append(Wall(wall_id=f"w{i + 1}", start=s, end=e, thickness_m=thick,
                          scanned=ScannedDims(length_m=math.dist(s, e), height_m=h)))
    return Room(walls=walls)
