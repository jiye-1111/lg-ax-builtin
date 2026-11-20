"""자유 배치 판정 (plans/virtual-remodel.md S2). 고객이 고른 위치·방향에 제품을 놓았을 때 들어가는지 본다.

yaw = 제품 정면이 향하는 방향 (영역 자동 배치·glb와 같은 규칙). 폭 방향은 yaw - 90°.
평면 좌표 (x, y) = 3D (x, z).
세 겹의 바닥 사각형을 쓴다.
- 본체(F): 제품 치수.
- 필요 공간(R): 본체 + 양옆·뒤 이격(clearance_mm). 이격이 없으면 0으로 보고 조건부 이하로 제한.
- 여유(M): R을 마진만큼 사방으로 키운 것.
장애물(벽·스캔 가구·다른 배치)과 F가 겹치면 불가, R이 겹치면 불가(이격 부족), M만 겹치면 조건부.
들여오는 길: 제품의 가장 얇은 쪽이 스캔된 문 폭보다 크면 조건부.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from core.models import Product, Room, Wall

from . import geometry as g
from .fit import FitConfig, Verdict, front_space, worst

DEFAULT_WALL_THICKNESS_M = 0.1
EPS = 1e-6

LABELS = {
    "dims_unknown": "제품 치수 정보 없음",
    "outside_room": "방 밖",
    "hits_wall": "벽을 뚫고 들어감",
    "clearance_blocked": "설치 이격 공간 부족",
    "tight": "여유가 마진보다 적음",
    "overlaps_object": "기존 가구와 겹침",
    "overlaps_placement": "다른 제품과 겹침",
    "ceiling_low": "천장이 낮음",
    "ceiling_tight": "천장 여유가 마진보다 적음",
    "door_blocked": "문이 열리지 않음",
    "door_swing_assumed": "문 열림 범위에 걸침 (반대쪽으로 열린다고 가정)",
    "covers_window": "창을 가림",
    "entry_narrow": "방 문보다 제품이 커서 들여올 길 확인 필요",
    "clearance_unknown": "이격 정보 없음 (제품 치수만으로 판단)",
    "scan_based": "스캔값 기준",
    "front_blocked": "앞쪽 문 열림 공간 부족",
    "front_space_assumed": "문 열림 공간 정보 없음 (기본값으로 가정)",
}


@dataclass
class Pose:
    center_xz: tuple[float, float]
    yaw_rad: float = 0.0
    wall_id: Optional[str] = None  # snap된 벽

    def to_dict(self) -> dict:
        return {"center_xz": [round(self.center_xz[0], 4), round(self.center_xz[1], 4)],
                "yaw_rad": round(self.yaw_rad, 6), "wall_id": self.wall_id}


@dataclass
class PoseResult:
    verdict: Verdict
    pose: Pose
    reasons: list[dict] = field(default_factory=list)
    footprint: list[tuple[float, float]] = field(default_factory=list)
    required: list[tuple[float, float]] = field(default_factory=list)
    size_m: Optional[tuple[float, float, float]] = None

    def to_dict(self) -> dict:
        r4 = lambda pts: [[round(x, 4), round(y, 4)] for x, y in pts]  # noqa: E731
        return {"verdict": self.verdict.value, "label": self.verdict.label, "pose": self.pose.to_dict(),
                "reasons": self.reasons, "footprint": r4(self.footprint), "required": r4(self.required),
                "size_m": list(self.size_m) if self.size_m else None}


# ---------- 사각형 ----------
def rect(center: g.Pt, yaw: float, w: float, d: float, left=0.0, right=0.0, back=0.0, front=0.0) -> list[g.Pt]:
    """yaw = 폭(u) 축 방향. 로컬 (u: 폭, v: 앞쪽) 범위 [-w/2-left, w/2+right] x [-d/2-back, d/2+front]의 네 꼭짓점."""
    ux, uy = math.cos(yaw), math.sin(yaw)
    vx, vy = -uy, ux
    pts = []
    for u, v in ((-w / 2 - left, -d / 2 - back), (w / 2 + right, -d / 2 - back),
                 (w / 2 + right, d / 2 + front), (-w / 2 - left, d / 2 + front)):
        pts.append((center[0] + ux * u + vx * v, center[1] + uy * u + vy * v))
    return pts


def overlaps(a: Sequence[g.Pt], b: Sequence[g.Pt]) -> bool:
    """볼록 다각형 SAT. 맞닿기만 한 경우는 겹침이 아니다."""
    for poly in (a, b):
        for i in range(len(poly)):
            p, q = poly[i], poly[(i + 1) % len(poly)]
            n = (q[1] - p[1], p[0] - q[0])
            L = math.hypot(*n) or 1.0
            n = (n[0] / L, n[1] / L)
            pa = [g.dot(n, x) for x in a]
            pb = [g.dot(n, x) for x in b]
            if max(pa) <= min(pb) + EPS or max(pb) <= min(pa) + EPS:
                return False
    return True


def _thick(w: Wall) -> float:
    return w.thickness_m or DEFAULT_WALL_THICKNESS_M


def wall_rect(w: Wall) -> list[g.Pt]:
    (x0, y0), (x1, y1) = w.start, w.end
    L = math.hypot(x1 - x0, y1 - y0) or 1e-9
    return rect(((x0 + x1) / 2, (y0 + y1) / 2), math.atan2(y1 - y0, x1 - x0), L, _thick(w))


def room_center(room: Room) -> g.Pt:
    mids = [((w.start[0] + w.end[0]) / 2, (w.start[1] + w.end[1]) / 2) for w in room.walls]
    return g.centroid(mids)


def _inward(room: Room, w: Wall) -> g.WallFrame:
    return g.WallFrame(tuple(w.start), tuple(w.end), room_center(room))


def inside_room(room: Room, p: g.Pt) -> bool:
    """네 방향 광선 중 셋 이상이 벽에 닿으면 방 안 (스캔 벽 사이 틈을 견디기 위해)."""
    segs = [(tuple(w.start), tuple(w.end)) for w in room.walls]
    hits = 0
    for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if any(g.ray_exit_distance(p, d, [a, b]) is not None for a, b in segs):
            hits += 1
    return hits >= 3


def _wall_height(w: Wall) -> float:
    return (w.measured.height_m if w.measured and w.measured.height_m else None) or w.scanned.height_m


def _nearest_wall(room: Room, p: g.Pt) -> tuple[Wall, float]:
    return min(((w, g.point_segment_distance(p, tuple(w.start), tuple(w.end))) for w in room.walls), key=lambda t: t[1])


# ---------- 제품 크기 ----------
def product_size(p: Product) -> Optional[tuple[float, float, float]]:
    d = p.product_dims_mm
    if d.w is None or d.h is None or d.d is None:
        return None
    return d.w / 1000, d.h / 1000, d.d / 1000


def _clear(p: Product) -> tuple[float, float, float, bool]:
    c = p.clearance_mm
    unknown = c.side is None or c.back is None or c.top is None
    return (c.side or 0) / 1000, (c.back or 0) / 1000, (c.top or 0) / 1000, unknown


# ---------- snap ----------
def snap_to_wall(room: Room, product: Product, pose: Pose, cfg: FitConfig) -> Pose:
    """가까운 벽(FIT_SNAP_M 안)이 있으면 제품 등을 그 벽에 붙이고 앞쪽을 방 안으로 돌린다.
    뒷면은 벽 안쪽 면 + 뒤 이격 + 마진 위치."""
    size = product_size(product)
    if size is None or not room.walls:
        return pose
    w_m, _, d_m = size
    side, back, _, _ = _clear(product)
    margin = cfg.margin_scanned_mm / 1000
    wall, dist = _nearest_wall(room, pose.center_xz)
    gap = dist - _thick(wall) / 2 - d_m / 2 - back
    if gap > cfg.snap_m:
        return pose
    f = _inward(room, wall)
    u, _ = f.to_local(pose.center_xz)
    half = w_m / 2 + side
    u = min(max(u, half), f.length - half) if f.length >= 2 * half else f.length / 2
    v = _thick(wall) / 2 + back + margin + d_m / 2
    nx, ny = f.v_axis
    return Pose(f.to_world(u, v), math.atan2(ny, nx), wall.wall_id)


# ---------- 판정 ----------
def check_pose(room: Room, product: Product, pose: Pose, cfg: FitConfig | None = None,
               others: Iterable[dict] = (), hidden: Iterable[str] = ()) -> PoseResult:
    cfg = cfg or FitConfig()
    size = product_size(product)
    reasons: list[dict] = []
    verdicts: list[Verdict] = []

    def add(code: str, v: Verdict, ref: str | None = None, label: str | None = None):
        reasons.append({"code": code, "label": label or LABELS[code], "ref": ref, "verdict": v.value})
        verdicts.append(v)

    if size is None:
        add("dims_unknown", Verdict.UNKNOWN)
        return PoseResult(Verdict.UNKNOWN, pose, reasons)
    w_m, h_m, d_m = size
    side, back, top, clear_unknown = _clear(product)
    margin = cfg.margin_scanned_mm / 1000
    c, yaw = pose.center_xz, pose.yaw_rad - math.pi / 2  # 폭 축
    F = rect(c, yaw, w_m, d_m)
    R = rect(c, yaw, w_m, d_m, left=side, right=side, back=back)
    M = rect(c, yaw, w_m, d_m, left=side + margin, right=side + margin, back=back + margin, front=margin)
    front_mm, front_assumed = front_space(product, cfg)
    # 문 열림 공간: 본체 앞면부터 문 열림 깊이만큼 (본체 폭)
    D = None if front_mm is None else rect(c, yaw, w_m, d_m, back=-d_m, front=front_mm / 1000)

    if not inside_room(room, c):
        add("outside_room", Verdict.NO_FIT)

    hidden = set(hidden)
    obstacles: list[tuple[str, str, list[g.Pt]]] = [("wall", w.wall_id, wall_rect(w)) for w in room.walls]
    obstacles += [("object", o.object_id, rect((o.position[0], o.position[2]), o.yaw_rad, o.bbox_m.w, o.bbox_m.d))
                  for o in room.objects if o.object_id not in hidden]
    for o in others:
        sw, _, sd = o["size_m"]
        oyaw = o.get("yaw_rad", 0.0) - math.pi / 2
        obstacles.append(("placement", o.get("placement_id") or o.get("sku"), rect(tuple(o["center_xz"]), oyaw, sw, sd)))

    hit_code = {"wall": "hits_wall", "object": "overlaps_object", "placement": "overlaps_placement"}
    for kind, ref, poly in obstacles:
        if overlaps(F, poly):
            add(hit_code[kind], Verdict.NO_FIT, ref)
        elif overlaps(R, poly):
            add("clearance_blocked", Verdict.NO_FIT, ref)
        elif D is not None and overlaps(D, poly):
            add("front_blocked", Verdict.NO_FIT, ref)
        elif overlaps(M, poly):
            add("tight", Verdict.CONDITIONAL, ref)

    # 천장: 가장 가까운 벽 높이
    if room.walls:
        wall, _ = _nearest_wall(room, c)
        slack = _wall_height(wall) - (h_m + top)
        if slack < -EPS:
            add("ceiling_low", Verdict.NO_FIT, wall.wall_id)
        elif slack < margin - EPS:
            add("ceiling_tight", Verdict.CONDITIONAL, wall.wall_id)

    # 문·창
    for op in room.openings:
        if not op.wall_id:
            continue
        try:
            wall = room.wall(op.wall_id)
        except KeyError:
            continue
        f = _inward(room, wall)
        t = _thick(wall) / 2
        a, b = op.offset_m, op.offset_m + op.width_m
        if op.type == "door":
            inner = [f.to_world(a, t), f.to_world(b, t), f.to_world(b, t + op.width_m), f.to_world(a, t + op.width_m)]
            outer = [f.to_world(a, -t), f.to_world(b, -t), f.to_world(b, -t - op.width_m), f.to_world(a, -t - op.width_m)]
            hi, ho = overlaps(R, inner), overlaps(R, outer)
            if hi and ho:
                add("door_blocked", Verdict.NO_FIT, op.opening_id)
            elif hi or ho:
                add("door_swing_assumed", Verdict.CONDITIONAL, op.opening_id)
        elif op.type == "window" and h_m > op.sill_m + EPS:
            band = [f.to_world(a, t), f.to_world(b, t), f.to_world(b, t + cfg.snap_m), f.to_world(a, t + cfg.snap_m)]
            if overlaps(R, band):
                add("covers_window", Verdict.CONDITIONAL, op.opening_id)

    if front_assumed:
        add("front_space_assumed", Verdict.CONDITIONAL,
            label=f"문 열림 공간 정보 없음 (앞 {cfg.front_default_mm:.0f} mm로 가정)")

    # 들여오는 길: 가장 넓은 문으로도 제품의 가장 얇은 쪽이 못 지나가면 확인 필요
    doors = [op for op in room.openings if op.type in ("door", "opening") and op.width_m > 0]
    if doors:
        widest = max(doors, key=lambda op: op.width_m)
        if min(w_m, d_m) > widest.width_m + EPS:
            add("entry_narrow", Verdict.CONDITIONAL, widest.opening_id)

    if clear_unknown:
        add("clearance_unknown", Verdict.CONDITIONAL)
    if cfg.scanned_max_conditional:
        add("scan_based", Verdict.CONDITIONAL)
    v = worst(verdicts) if verdicts else Verdict.FIT
    return PoseResult(v, pose, reasons, F, R, (w_m, h_m, d_m))
