"""원본 LiDAR 깊이로 RoomPlan 벽 치수 다듬기 (연구용 프로토타입, 앱에는 아직 연결하지 않음).

조사·수치 근거: docs/research/lidar-error-correction.md §8
입력: Stray Scanner 내보내기 폴더 (무료·MIT, 형식 https://github.com/strayrobots/scanner/blob/main/docs/format.md)
  depth/000000.png  16bit, mm, 256×192     confidence/000000.png  0·1·2
  odometry.csv      timestamp, frame, x, y, z, qx, qy, qz, qw, fx, fy, cx, cy (RGB 해상도 기준)

흐름
1. 신뢰도 2(높음)인 픽셀만 3D 점으로 (frame_points)
2. 여러 프레임 점을 1 cm 칸으로 평균 = 간단한 깊이 융합 (fuse_points)
3. RANSAC으로 평면을 찾고 안쪽 점으로 최소제곱 다시 맞춤 (fit_planes)
4. UGScan(RoomPlan) 벽과 좌표계가 달라서 회전(90° 단위 후보)·이동을 맞춘 뒤 벽 안쪽 면 ↔ 평면 짝짓기 (refine_room)
5. 마주 보는 벽 사이 거리를 평면 기준으로 다시 잰다

포즈 축 규칙: StrayVisualizer처럼 포즈를 카메라→월드, OpenCV 카메라(x 오른쪽, y 아래, z 앞)로 쓴다.
실제 캡처로 한 번 확인해야 한다 (ARKit 규칙이면 camera="arkit").
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from core.models import Room

DEPTH_W, DEPTH_H = 256, 192
ARKIT_TO_CV = np.diag([1.0, -1.0, -1.0])


@dataclass
class Frame:
    depth_m: np.ndarray   # H×W
    conf: np.ndarray      # H×W, 0·1·2
    K: np.ndarray         # 깊이 해상도 기준 3×3
    T_wc: np.ndarray      # 4×4 카메라→월드 (OpenCV 카메라 축)


# ---------- 회전 ----------
def quat_to_mat(qx, qy, qz, qw) -> np.ndarray:
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    x, y, z, w = qx / n, qy / n, qz / n, qw / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def mat_to_quat(R: np.ndarray) -> tuple[float, float, float, float]:
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        return ((R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s)
    i = int(np.argmax(np.diag(R)))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1.0 + R[i, i] - R[j, j] - R[k, k]) * 2
    q = [0.0, 0.0, 0.0]
    q[i] = 0.25 * s
    q[j] = (R[j, i] + R[i, j]) / s
    q[k] = (R[k, i] + R[i, k]) / s
    return (q[0], q[1], q[2], (R[k, j] - R[j, k]) / s)


# ---------- 불러오기 ----------
def load_stray(path, rgb_width: int = 1920, camera: str = "opencv") -> list[Frame]:
    path = Path(path)
    frames = []
    with open(path / "odometry.csv", newline="") as f:
        rows = list(csv.reader(f))
    head = [h.strip() for h in rows[0]]
    col = {h: i for i, h in enumerate(head)}
    for i, r in enumerate(rows[1:]):
        g = lambda k: float(r[col[k]])  # noqa: E731
        T = np.eye(4)
        R = quat_to_mat(g("qx"), g("qy"), g("qz"), g("qw"))
        T[:3, :3] = R @ ARKIT_TO_CV if camera == "arkit" else R
        T[:3, 3] = (g("x"), g("y"), g("z"))
        s = DEPTH_W / rgb_width
        K = np.array([[g("fx") * s, 0, g("cx") * s], [0, g("fy") * s, g("cy") * s], [0, 0, 1.0]])
        name = f"{i:06d}.png"
        depth = np.asarray(Image.open(path / "depth" / name), dtype=np.float32) / 1000.0
        cp = path / "confidence" / name
        conf = np.asarray(Image.open(cp), dtype=np.uint8) if cp.exists() else np.full(depth.shape, 2, np.uint8)
        frames.append(Frame(depth, conf, K, T))
    return frames


# ---------- 점 ----------
def frame_points(fr: Frame, min_conf: int = 2, max_range_m: float = 3.0) -> np.ndarray:
    h, w = fr.depth_m.shape
    u, v = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    z = fr.depth_m
    ok = (fr.conf >= min_conf) & np.isfinite(z) & (z > 0.1) & (z < max_range_m)
    x = (u[ok] - fr.K[0, 2]) / fr.K[0, 0] * z[ok]
    y = (v[ok] - fr.K[1, 2]) / fr.K[1, 1] * z[ok]
    pc = np.stack([x, y, z[ok]], 1)
    return pc @ fr.T_wc[:3, :3].T + fr.T_wc[:3, 3]


def fuse_points(frames: list[Frame], voxel_m: float = 0.01, min_conf: int = 2) -> np.ndarray:
    """프레임 점을 voxel_m 칸으로 평균. 같은 면을 여러 번 본 노이즈가 줄어든다."""
    pts = np.concatenate([frame_points(f, min_conf) for f in frames])
    key = np.floor(pts / voxel_m).astype(np.int64)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    out = np.zeros((len(cnt), 3))
    np.add.at(out, inv, pts)
    return out / cnt[:, None]


# ---------- 평면 ----------
@dataclass
class Plane:
    n: np.ndarray      # 단위 법선
    d: float           # n·p = d
    count: int
    rms_m: float


def _lsq_plane(p: np.ndarray) -> tuple[np.ndarray, float, float]:
    c = p.mean(0)
    _, _, vt = np.linalg.svd(p - c, full_matrices=False)
    n = vt[2]
    res = (p - c) @ n
    return n, float(n @ c), float(np.sqrt(np.mean(res ** 2)))


def fit_planes(pts: np.ndarray, max_planes: int = 8, thr_m: float = 0.03, min_points: int = 300,
               iters: int = 120, seed: int = 0) -> list[Plane]:
    rng = np.random.default_rng(seed)
    rest = pts
    planes: list[Plane] = []
    while len(planes) < max_planes and len(rest) >= min_points:
        best_in = None
        for _ in range(iters):
            a, b, c = rest[rng.choice(len(rest), 3, replace=False)]
            n = np.cross(b - a, c - a)
            nn = np.linalg.norm(n)
            if nn < 1e-9:
                continue
            n /= nn
            inl = np.abs(rest @ n - n @ a) < thr_m
            if best_in is None or inl.sum() > best_in.sum():
                best_in = inl
        if best_in is None or best_in.sum() < min_points:
            break
        n, d, rms = _lsq_plane(rest[best_in])
        inl = np.abs(rest @ n - d) < thr_m  # 다시 맞춘 면으로 안쪽 점 갱신
        n, d, rms = _lsq_plane(rest[inl])
        planes.append(Plane(n, d, int(inl.sum()), rms))
        rest = rest[~inl]
    return planes


def _vertical(planes: list[Plane], tol: float = 0.1, min_share: float = 0.2, merge_m: float = 0.15) -> list[Plane]:
    """벽 후보: 수직이고, 가장 큰 면의 min_share 이상 점을 가진 면. 노이즈 꼬리가 만든 얇은 평행 면은
    merge_m 안의 더 큰 면에 흡수한다."""
    vs = sorted((p for p in planes if abs(p.n[1]) < tol), key=lambda p: -p.count)
    if not vs:
        return []
    out: list[Plane] = []
    for p in vs:
        if p.count < min_share * vs[0].count:
            continue
        if any(abs(p.n @ q.n) > 0.99 and abs(p.d - q.d * np.sign(p.n @ q.n)) < merge_m for q in out):
            continue
        out.append(p)
    return out


def vertical_spans(planes: list[Plane]) -> dict[str, float]:
    """벽(수직 평면) 중 서로 마주 보는 쌍의 거리. 월드 x·z 축 기준 (합성 시험용)."""
    out = {}
    for ax, i in (("x", 0), ("z", 2)):
        ds = [p.d * np.sign(p.n[i]) for p in _vertical(planes) if abs(p.n[i]) > 0.9]
        if len(ds) >= 2:
            out[ax] = float(max(ds) - min(ds))
    return out


# ---------- RoomPlan 벽과 맞추기 ----------
@dataclass
class Span:
    axis: str            # 방 주축 기준 "x" 또는 "z" (같은 방향 벽 쌍)
    walls: tuple[str, str]
    scanned_m: float     # RoomPlan 안쪽 면 사이 거리
    refined_m: float     # 원본 깊이 평면 사이 거리
    planes_rms_mm: float


@dataclass
class RefineResult:
    matched: int
    yaw_rad: float
    shift: tuple[float, float]
    spans: list[Span] = field(default_factory=list)
    wall_offsets_mm: dict[str, float] = field(default_factory=dict)  # 벽 안쪽 면을 몇 mm 옮겨야 하는지


def _inner_faces(room: Room):
    """벽 안쪽 면의 2D 직선 (n, d, wall). n은 방 안쪽을 향한다."""
    cx = np.mean([[*w.start] for w in room.walls] + [[*w.end] for w in room.walls], axis=0)
    out = []
    for w in room.walls:
        s, e = np.array(w.start), np.array(w.end)
        t = (e - s) / np.linalg.norm(e - s)
        n = np.array([-t[1], t[0]])
        if n @ (cx - s) < 0:
            n = -n
        d = float(n @ s) + (w.thickness_m or 0) / 2
        out.append((n, d, w))
    return out


def refine_room(room: Room, pts: np.ndarray, seed: int = 0, match_m: float = 0.12) -> RefineResult:
    planes = _vertical(fit_planes(pts, seed=seed))
    faces = _inner_faces(room)
    # 평면을 2D(x, z)로, 방 안쪽을 향하게 (점 무게중심 쪽)
    c3 = pts.mean(0)
    P = []
    for p in planes:
        n = np.array([p.n[0], p.n[2]])
        n /= np.linalg.norm(n)
        d = p.d / np.linalg.norm([p.n[0], p.n[2]])
        if n @ c3[[0, 2]] - d < 0:
            n, d = -n, -d
        P.append((n, d, p))
    if len(P) < 2 or not faces:
        return RefineResult(0, 0.0, (0.0, 0.0))

    best = None
    ang = lambda v: math.atan2(v[1], v[0])  # noqa: E731
    # 회전 후보: 캡처 평면 하나 ↔ 벽 면 하나의 법선을 맞추는 모든 경우
    for pn, _, _ in P:
        for fn, _, _ in faces:
            yaw = ang(fn) - ang(pn)
            c, s = math.cos(yaw), math.sin(yaw)
            Rz = np.array([[c, -s], [s, c]])
            rot = [(Rz @ n, d) for n, d, _ in P]
            # 이동: 법선이 같은 짝마다 이동량 후보를 내고, 가장 많이 맞는 값
            cands = []
            for i, (n, d) in enumerate(rot):
                for fn2, fd2, _ in faces:
                    if n @ fn2 > 0.99:
                        cands.append((fn2, fd2 - d))
            for fnA, offA in cands:
                for fnB, offB in cands:
                    if abs(fnA @ fnB) > 0.1:
                        continue
                    # n·t = off 두 식으로 t 풀기
                    A = np.array([fnA, fnB])
                    t = np.linalg.solve(A, [offA, offB])
                    pairs = []
                    for i, (n, d) in enumerate(rot):
                        d2 = d + n @ t
                        for fn2, fd2, w in faces:
                            if n @ fn2 > 0.99 and abs(d2 - fd2) < match_m:
                                pairs.append((i, w.wall_id, d2 - fd2))
                    used = {}
                    for i, wid, off in sorted(pairs, key=lambda x: abs(x[2])):
                        if wid not in used and i not in {u[0] for u in used.values()}:
                            used[wid] = (i, off)
                    score = (len(used), -sum(abs(o) for _, o in used.values()))
                    if best is None or score > best[0]:
                        best = (score, yaw, t, used, rot)
    if best is None:
        return RefineResult(0, 0.0, (0.0, 0.0))
    (nmatch, _), yaw, t, used, rot = best
    if nmatch < 4:
        return RefineResult(nmatch, yaw, (float(t[0]), float(t[1])))

    fmap = {w.wall_id: (n, d) for n, d, w in faces}
    res = RefineResult(nmatch, yaw, (float(t[0]), float(t[1])))
    for wid, (i, off) in used.items():
        res.wall_offsets_mm[wid] = round(-off * 1000, 1)  # 안쪽 면을 법선 반대 방향으로 off만큼
    ids = list(used)
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            na, da = fmap[ids[a]]
            nb, db = fmap[ids[b]]
            if na @ nb > -0.99:
                continue  # 마주 보는 벽만
            ia, ib = used[ids[a]][0], used[ids[b]][0]
            scanned = abs(da + db)  # 안쪽 법선이 반대 → 거리 = -(d_a + d_b) 의 절댓값
            ra = rot[ia][1] + rot[ia][0] @ t
            rb = rot[ib][1] + rot[ib][0] @ t
            refined = abs(ra + rb)
            axis = "x" if abs(na[0]) > abs(na[1]) else "z"
            rms = max(P[ia][2].rms_m, P[ib][2].rms_m) * 1000
            res.spans.append(Span(axis, (ids[a], ids[b]), round(scanned, 4), round(refined, 4), round(rms, 1)))
    return res
