"""설치 방식대로 붙이기: 벽에 거는 제품, 뒷면을 벽에 붙이는 제품, 벽이나 장에 맞물리는 빌트인.

규칙은 docs/specs/fit-rules.md '벽에 걸거나 붙여 설치하는 제품'. 어떤 제품이 어디에 붙는지는 LGE.COM 표기
(제품 이름의 '벽걸이형', 스펙 표 '구분: 벽걸이형', '월핏', 설치 방식)에서만 읽는다.
평면 좌표 (x, y) = 3D (x, z). yaw = 제품 정면 방향.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

from core.models import Product

from . import geometry as g

WALL, FLUSH, BUILTIN = "wall", "flush", "builtin"
LABELS = {WALL: "벽에 걸어야 해요", FLUSH: "뒷면을 벽에 붙여야 해요", BUILTIN: "벽이나 장에 붙여야 해요"}

# 빌트인 가전이 맞물릴 수 있는 장 (놓은 가구 / 스캔한 가구 종류)
CABINET_SKUS = frozenset({"decor:basecab", "decor:island", "decor:islandtable", "decor:tallcab", "decor:sink", "decor:storage", "decor:wardrobe",
                          "decor:cab_fridge", "decor:cab_dishwasher", "decor:cab_sink", "decor:cab_drawer", "decor:cab_pantry"})
CABINET_SCANNED = frozenset({"storage"})

REACH_M = 0.6    # 붙여야 하는 제품은 이 거리 안의 벽으로 끌려간다
TOUCH_M = 0.06   # 이 안에 있으면 붙은 것으로 본다 (스캔 오차)
SLIDE_M, SLIDE_STEP_M = 0.6, 0.02  # 건 자리가 옆 벽에 걸리면 벽을 따라 이만큼까지 밀어 본다
STANDOFF_M = 0.0005  # 벽면에서 아주 조금 띄운다 (계산 오차로 벽에 박힌 것으로 보이지 않게)
TV_EYE_M = 1.1   # 벽걸이 TV: 앉은 눈높이에 화면 가운데 (화면 기본값, 끌어서 바꿀 수 있다)
AC_DROP_M = 0.15  # 벽걸이 에어컨: 천장에서 이만큼 아래 (화면 기본값)


def mount_kind(p: Product) -> Optional[str]:
    """wall: 벽에 건다 · flush: 뒷면을 벽에 붙인다 · builtin: 벽이나 장에 붙인다 · None: 아무 데나 세운다."""
    if p.category == "tv" and "벽걸이" in p.name:
        return WALL
    if p.category == "air_conditioner" and p.options.get("kind") == "벽걸이형":
        return WALL
    if p.category in ("cooktop", "water_purifier"):  # 상판에 넣는 것, 하부장 안에 넣는 것은 따로 본다
        return None
    if p.category == "air_purifier" and "월핏" in p.name:
        return FLUSH
    if p.install_type == "built_in_look":
        return FLUSH
    if p.install_type == "built_in":
        return BUILTIN
    return None


def clamp_base(base_m: float, height_m: float, ceiling_m: float) -> float:
    """거는 높이(밑면)를 바닥과 천장 사이로."""
    return max(0.0, min(base_m, ceiling_m - height_m))


def default_base(p: Product, ceiling_m: float) -> float:
    """벽걸이 제품을 처음 걸 때의 밑면 높이."""
    h = (p.product_dims_mm.h or 0) / 1000
    if p.category == "air_conditioner":
        return clamp_base(ceiling_m - AC_DROP_M - h, h, ceiling_m)
    return clamp_base(TV_EYE_M - h / 2, h, ceiling_m)


def hang(faces: Iterable[tuple[g.Pt, g.Pt, float, Optional[str]]], pose, width_m: float, depth_m: float):
    """가장 가까운 벽에 등을 붙인다. faces: (시작, 끝, 두께, id). 누른 쪽 면에 걸고 벽 끝을 넘지 않게 당긴다.
    제품보다 짧은 벽은 다른 벽이 없을 때만 쓴다. 벽이 없으면 None."""
    from .pose import Pose

    faces = [(tuple(a), tuple(b), t, wid) for a, b, t, wid in faces]
    wide = [f for f in faces if math.dist(f[0], f[1]) >= width_m + f[2]]  # 제품이 다 걸리는 벽부터 (기둥 옆 짧은 벽은 건너뛴다)
    best = None
    for a, b, t, wid in wide or faces:
        d = g.point_segment_distance(pose.center_xz, a, b)
        if best is None or d < best[0]:
            best = (d, a, b, t, wid)
    if best is None:
        return None
    _, a, b, t, wid = best
    L = math.dist(a, b) or 1e-9
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    px, py = pose.center_xz[0] - a[0], pose.center_xz[1] - a[1]
    half = width_m / 2 + t / 2  # 모서리에서 만나는 옆 벽 두께만큼은 비운다
    along = px * ux + py * uy
    along = min(max(along, half), L - half) if L >= 2 * half else L / 2
    side = -px * uy + py * ux
    if abs(side) < 1e-6:  # 벽 선 위를 눌렀으면 지금 보던 쪽
        side = -math.cos(pose.yaw_rad) * uy + math.sin(pose.yaw_rad) * ux
    nx, ny = (-uy, ux) if side >= 0 else (uy, -ux)
    off = t / 2 + depth_m / 2 + STANDOFF_M
    yaw = math.atan2(ny, nx)

    def at(s: float) -> g.Pt:
        return (a[0] + ux * s + nx * off, a[1] + uy * s + ny * off)

    # 스캔한 벽은 모서리가 딱 맞지 않는다: 옆 벽에 걸리면 벽을 따라 걸리지 않는 가장 가까운 자리로 민다
    from .pose import overlaps, rect
    rest = [rect(((p[0] + q[0]) / 2, (p[1] + q[1]) / 2), math.atan2(q[1] - p[1], q[0] - p[0]), math.dist(p, q), th)
            for p, q, th, other in faces if other != wid]
    for k in range(int(SLIDE_M / SLIDE_STEP_M) + 1):
        for s in ((along,) if k == 0 else (along + k * SLIDE_STEP_M, along - k * SLIDE_STEP_M)):
            body = rect(at(s), yaw - math.pi / 2, width_m, depth_m)
            if not any(overlaps(body, poly) for poly in rest):
                return Pose(at(s), yaw, wid)
    return Pose(at(along), yaw, wid)
