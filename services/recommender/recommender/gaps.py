"""놓은 자리에서 옆·뒤·위로 남는 틈 재기 (docs/specs/fit-rules.md '남는 틈').

빌트인은 옆 몇 mm, 위 몇 mm가 남는지가 설치를 가른다. 판정(check_pose)과 같은 장애물(벽·스캔 가구·다른 배치)을 쓰고,
본체 옆면에서 폭 방향으로, 등에서 뒤로 가장 가까운 것까지의 거리를 mm로 돌려준다.
필요한 값(need_mm)은 카탈로그 clearance_mm에 있는 것만 쓴다. 없으면 None (판단하지 않는다).
"""
from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence

from core.models import Product, Room

from . import geometry as g
from .fit import FitConfig
from .pose import EPS, Pose, _nearest_wall, _wall_height, product_size, rect, wall_rect

BAND_TRIM_M = 0.002   # 띠를 이만큼 줄여서 모서리만 스치는 것(등 뒤 벽 등)은 옆 틈으로 세지 않는다
OK_TOL_MM = 0.5


def _clip(poly: Sequence[g.Pt], axis: int, lo: float, hi: float) -> list[g.Pt]:
    """볼록 다각형을 한 축의 [lo, hi] 띠로 자른다 (Sutherland–Hodgman)."""
    for bound, keep in ((lo, lambda v, b: v >= b), (hi, lambda v, b: v <= b)):
        out: list[g.Pt] = []
        for i, p in enumerate(poly):
            q = poly[(i + 1) % len(poly)]
            pin, qin = keep(p[axis], bound), keep(q[axis], bound)
            if pin:
                out.append(p)
            if pin != qin:
                t = (bound - p[axis]) / (q[axis] - p[axis])
                out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
        poly = out
        if not poly:
            return []
    return list(poly)


def _obstacles(room: Room, others: Iterable[dict], hidden: Iterable[str], base: float, top: float):
    """(종류, id, 바닥 사각형, 옆 가전이 요구하는 옆 여유 mm). 높이가 겹치지 않는 것은 뺀다."""
    hidden = set(hidden)
    out = [("wall", w.wall_id, wall_rect(w), 0.0) for w in room.walls if w.wall_id not in hidden]
    for o in room.objects:
        if o.object_id in hidden:
            continue
        lo, hi = o.position[1] - o.bbox_m.h / 2, o.position[1] + o.bbox_m.h / 2
        if base <= EPS or (hi > base + EPS and lo < top - EPS):
            out.append(("object", o.object_id, rect((o.position[0], o.position[2]), o.yaw_rad, o.bbox_m.w, o.bbox_m.d), 0.0))
    for o in others:
        sw, sh, sd = o["size_m"]
        lo = float(o.get("base_m") or 0.0)
        if lo + sh > base + EPS and lo < top - EPS:
            out.append(("placement", o.get("placement_id") or o.get("sku"),
                        rect(tuple(o["center_xz"]), o.get("yaw_rad", 0.0) - math.pi / 2, sw, sd), float(o.get("side_mm") or 0.0)))
    return out


def _entry(mm: Optional[float], need: Optional[float], kind=None, ref=None, line=None) -> dict:
    ok = None if mm is None or need is None else mm >= need - OK_TOL_MM
    return {"mm": None if mm is None else round(mm, 1), "need_mm": need, "ok": ok, "kind": kind, "ref": ref,
            "line": [[round(x, 4), round(y, 4)] for x, y in line] if line else None}


def measure(room: Room, product: Product, pose: Pose, cfg: FitConfig | None = None, others: Iterable[dict] = (),
            hidden: Iterable[str] = (), base: float = 0.0) -> dict:
    """왼쪽·오른쪽·뒤·위 틈. 왼쪽 = 폭 축의 음(-) 방향 (정면에서 봤을 때가 아니라 판정 사각형의 u 축 기준).

    각 항목: mm(틈), need_mm(필요한 값, 없으면 None), ok, kind·ref(막고 있는 것), line(그릴 선의 양 끝 [본체 쪽, 막는 쪽]).
    """
    size = product_size(product)
    if size is None:
        return {}
    w, h, d = size
    c = product.clearance_mm
    ux, uy = math.cos(pose.yaw_rad - math.pi / 2), math.sin(pose.yaw_rad - math.pi / 2)
    vx, vy = -uy, ux
    cx, cy = pose.center_xz

    def local(p: g.Pt) -> g.Pt:
        return ((p[0] - cx) * ux + (p[1] - cy) * uy, (p[0] - cx) * vx + (p[1] - cy) * vy)

    def world(u: float, v: float) -> g.Pt:
        return (cx + ux * u + vx * v, cy + uy * u + vy * v)

    obs = [(k, ref, [local(p) for p in poly], side) for k, ref, poly, side in _obstacles(room, others, hidden, base, base + h)]

    def nearest(axis: int, sign: int, half: float, band_half: float):
        """axis 방향(sign)으로 본체 면(half)에서 가장 가까운 것. 띠 = 다른 축의 본체 범위."""
        best = None
        for kind, ref, poly, side in obs:
            cut = _clip(poly, 1 - axis, -band_half + BAND_TRIM_M, band_half - BAND_TRIM_M)
            vals = [sign * p[axis] for p in cut]
            if not vals or max(vals) <= 0:   # 띠 밖이거나 반대쪽에 있는 것
                continue
            dist = max(min(vals) - half, 0.0)
            if best is None or dist < best[0]:
                best = (dist, kind, ref, side)
        return best

    out = {}
    own_side = c.side
    for name, sign in (("left", -1), ("right", 1)):
        hit = nearest(0, sign, w / 2, d / 2)
        if hit is None:
            out[name] = _entry(None, own_side)
            continue
        dist, kind, ref, side = hit
        need = max(own_side or 0.0, side) if (own_side is not None or side > 0) else None
        out[name] = _entry(dist * 1000, need, kind, ref, [world(sign * w / 2, 0), world(sign * (w / 2 + dist), 0)])
    hit = nearest(1, -1, d / 2, w / 2)
    out["back"] = (_entry(None, c.back) if hit is None else
                   _entry(hit[0] * 1000, c.back, hit[1], hit[2], [world(0, -d / 2), world(0, -d / 2 - hit[0])]))
    if room.walls:
        wall, _ = _nearest_wall(room, pose.center_xz)
        out["top"] = _entry((_wall_height(wall) - (base + h)) * 1000, c.top, "ceiling", wall.wall_id)
    else:
        out["top"] = _entry(None, c.top)
    return out


def fill_width(room: Room, product: Product, pose: Pose, cfg: FitConfig | None = None, others: Iterable[dict] = (),
               hidden: Iterable[str] = (), base: float = 0.0, min_w: float = 0.1) -> Optional[tuple[g.Pt, float]]:
    """양옆 빈틈을 꽉 채우는 폭과 가운데 자리. 옆 가전이 요구하는 옆 여유는 남긴다.
    이미 겹쳐 있거나 한쪽이 뚫려 있으면 None."""
    size = product_size(product)
    gp = measure(room, product, pose, cfg, others, hidden, base)
    if size is None or not gp:
        return None
    left, right = gp["left"], gp["right"]
    if left["mm"] is None or right["mm"] is None or left["mm"] <= 0 or right["mm"] <= 0:
        return None
    gl = (left["mm"] - (left["need_mm"] or 0)) / 1000
    gr = (right["mm"] - (right["need_mm"] or 0)) / 1000
    new_w = size[0] + gl + gr
    if new_w < min_w:
        return None
    ux, uy = math.cos(pose.yaw_rad - math.pi / 2), math.sin(pose.yaw_rad - math.pi / 2)
    shift = (gr - gl) / 2
    return (pose.center_xz[0] + ux * shift, pose.center_xz[1] + uy * shift), new_w
