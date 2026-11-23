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
from .fit import DOOR_CATEGORIES, FitConfig, Verdict, front_space, worst

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
    "not_on_wall": "문은 벽이나 가벽에 달아 주세요",
    "front_space_assumed": "문 열림 공간 정보 없음 (기본값으로 가정)",
    "passage_narrow": "문을 열었을 때 앞 통로가 좁음",
    "surface_overhang": "올려 둔 가구 밖으로 나옴",
    "needs_counter": "하부장이나 아일랜드 위에 놓아야 해요",
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
    base_m: float = 0.0        # 바닥에서 제품 밑면까지 (가구 위에 올렸으면 그 윗면 높이)
    on: Optional[str] = None   # 올려 둔 가구 (배치 id 또는 스캔 가구 id)

    def to_dict(self) -> dict:
        r4 = lambda pts: [[round(x, 4), round(y, 4)] for x, y in pts]  # noqa: E731
        return {"verdict": self.verdict.value, "label": self.verdict.label, "pose": self.pose.to_dict(),
                "reasons": self.reasons, "footprint": r4(self.footprint), "required": r4(self.required),
                "size_m": list(self.size_m) if self.size_m else None, "base_m": round(self.base_m, 3), "on": self.on}


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
    # side_total(한쪽에만 두면 되는 옆 여유)은 어느 쪽에 둘지 몰라 사각형에는 넣지 않는다
    unknown = (c.side is None and c.side_total is None) or c.back is None or c.top is None
    return (c.side or 0) / 1000, (c.back or 0) / 1000, (c.top or 0) / 1000, unknown


# ---------- 가구 위에 올려 두기 ----------
# 식탁·아일랜드·하부장 같은 가구 윗면에 올려 쓰는 가전. 규칙은 docs/specs/fit-rules.md '가구 위에 올려 두기'
TABLETOP = frozenset({"water_purifier", "microwave", "oven", "humidifier", "air_purifier", "plant_grower", "tv"})
TABLETOP_MAX_MM = (700, 650, 700)  # 폭·높이·깊이가 이보다 작아야 올린다 (TV는 크기와 상관없이 거실장 위에)
SURFACE_MAX_M = 1.2                # 이보다 높은 윗면에는 올리지 않는다 (손이 닿는 조리대·식탁 높이까지)


COUNTER_ONLY = frozenset({"cooktop"})  # 상판을 따내고 넣는 제품: 하부장·아일랜드 위에만 놓는다


def needs_counter(p: Product) -> bool:
    """상판에 넣는 제품(인덕션·전기레인지)인지. 바닥에는 놓을 수 없다."""
    return p.category in COUNTER_ONLY


def can_sit(p: Product) -> bool:
    """가구 윗면에 올려 둘 수 있는 제품인지."""
    d = p.product_dims_mm
    if needs_counter(p):
        return None not in (d.w, d.h, d.d)
    if p.category not in TABLETOP or p.install_type == "built_in" or d.w is None or d.h is None or d.d is None:
        return False
    if p.category == "tv":
        return True
    if p.install_form in ("빌트인", "스탠드"):
        return False
    return d.w <= TABLETOP_MAX_MM[0] and d.h <= TABLETOP_MAX_MM[1] and d.d <= TABLETOP_MAX_MM[2]


def _local(s: dict, p: g.Pt) -> g.Pt:
    dx, dy = p[0] - s["center_xz"][0], p[1] - s["center_xz"][1]
    c, n = math.cos(s["yaw_rad"]), math.sin(s["yaw_rad"])
    return dx * c + dy * n, -dx * n + dy * c


def on_surface(s: dict, p: g.Pt, tol: float = EPS) -> bool:
    u, v = _local(s, p)
    return abs(u) <= s["w"] / 2 + tol and abs(v) <= s["d"] / 2 + tol


def surface_under(center: g.Pt, surfaces: Iterable[dict]) -> Optional[dict]:
    """그 자리 아래의 윗면. surfaces: {id, center_xz, yaw_rad(폭 축 방향), w, d, top_m}. 겹치면 가장 높은 것."""
    hits = [s for s in surfaces if on_surface(s, center)]
    return max(hits, key=lambda s: s["top_m"]) if hits else None


def settle_on(s: dict, center: g.Pt, yaw_rad: float, w: float, d: float) -> g.Pt:
    """윗면 가장자리에 걸친 자리를 몸 전체가 올라오는 가장 가까운 자리로 당긴다. yaw_rad = 제품 정면 방향.
    물건이 윗면보다 크면 그대로 돌려준다."""
    pts = [_local(s, q) for q in rect(center, yaw_rad - math.pi / 2, w, d)]
    cu, cv = _local(s, center)
    eu, ev = max(abs(u - cu) for u, _ in pts), max(abs(v - cv) for _, v in pts)
    if eu > s["w"] / 2 + EPS or ev > s["d"] / 2 + EPS:
        return center
    u = min(max(cu, -(s["w"] / 2 - eu)), s["w"] / 2 - eu)
    v = min(max(cv, -(s["d"] / 2 - ev)), s["d"] / 2 - ev)
    if abs(u - cu) < EPS and abs(v - cv) < EPS:
        return center
    c, n = math.cos(s["yaw_rad"]), math.sin(s["yaw_rad"])
    return s["center_xz"][0] + u * c - v * n, s["center_xz"][1] + u * n + v * c


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


def snap_door(segments: Iterable[tuple[g.Pt, g.Pt]], pose: Pose, width_m: float, snap_m: float = 0.6) -> Pose:
    """문 달기: 가까운 벽 선(스캔 벽·가벽의 가운데 줄, snap_m 안)에 문 가운데를 올리고, 누른 쪽으로 열리게 돌린다.
    벽 끝을 넘지 않게 당긴다. 가까운 벽이 없으면 그대로."""
    best = None
    for a, b in segments:
        d = g.point_segment_distance(pose.center_xz, tuple(a), tuple(b))
        if d <= snap_m and (best is None or d < best[0]):
            best = (d, tuple(a), tuple(b))
    if best is None:
        return pose
    _, a, b = best
    L = math.dist(a, b) or 1e-9
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    px, py = pose.center_xz[0] - a[0], pose.center_xz[1] - a[1]
    half = width_m / 2
    t = px * ux + py * uy
    t = min(max(t, half), L - half) if L >= width_m else L / 2
    side = -px * uy + py * ux  # 벽 선의 어느 쪽을 눌렀나
    if abs(side) < 1e-6:  # 선 위를 눌렀으면 지금 보던 쪽에 가까운 방향
        side = -math.cos(pose.yaw_rad) * uy + math.sin(pose.yaw_rad) * ux
    nx, ny = (-uy, ux) if side >= 0 else (uy, -ux)
    return Pose((round(a[0] + ux * t, 4), round(a[1] + uy * t, 4)), math.atan2(ny, nx))


# ---------- 판정 ----------
MOUNTED = frozenset({"decor_door"})  # 벽에 겹쳐 다는 것 (문)
WALL_LIKE = frozenset({"decor:wall", "decor:partition"})  # 문을 달 수 있는 배치
DOOR_SKU = "decor:door"
DOOR_BLOCKED_LABEL = "문을 열 공간이 부족해요"


def check_pose(room: Room, product: Product, pose: Pose, cfg: FitConfig | None = None,
               others: Iterable[dict] = (), hidden: Iterable[str] = (), host: Optional[dict] = None) -> PoseResult:
    """host: 올려 둘 가구 윗면(surface_under 결과). 주면 그 높이에서 판정한다: 그 가구와는 겹쳐도 되고,
    키가 그 윗면보다 낮은 바닥 물건은 걸리지 않는다. 윗면 밖으로 나오면 불가."""
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
    base = float(host["top_m"]) if host else 0.0
    c, yaw = pose.center_xz, pose.yaw_rad - math.pi / 2  # 폭 축
    F = rect(c, yaw, w_m, d_m)
    R = rect(c, yaw, w_m, d_m, left=side, right=side, back=back)
    M = rect(c, yaw, w_m, d_m, left=side + margin, right=side + margin, back=back + margin, front=margin)
    front_mm, front_assumed = front_space(product, cfg)
    # 문 열림 공간: 본체 앞면부터 문 열림 깊이만큼 (본체 폭)
    D = None if front_mm is None else rect(c, yaw, w_m, d_m, back=-d_m, front=front_mm / 1000)
    # 통행 공간: 문 열림 공간(빌트인은 본체 앞면) 앞으로 사람이 지나갈 통로. 일반 기준값이라 걸려도 조건부
    P = None
    if product.category in DOOR_CATEGORIES and cfg.passage_mm > 0:
        start = (front_mm or 0) / 1000
        P = rect(c, yaw, w_m, d_m, back=-(d_m + start), front=start + cfg.passage_mm / 1000)
    passage_ref = None

    mounted = product.category in MOUNTED
    if not mounted and not inside_room(room, c):  # 문은 바깥벽 가운데 줄에 달리므로 방 안팎을 따지지 않는다
        add("outside_room", Verdict.NO_FIT)

    hidden = set(hidden)  # 치운 가구 id + 철거한 벽 id
    INF = float("inf")
    # (종류, id, 바닥 사각형, 밑면 높이, 윗면 높이)
    obstacles: list[tuple[str, str, list[g.Pt], float, float]] = [("wall", w.wall_id, wall_rect(w), 0.0, INF) for w in room.walls
                                                                   if w.wall_id not in hidden]
    obstacles += [("object", o.object_id, rect((o.position[0], o.position[2]), o.yaw_rad, o.bbox_m.w, o.bbox_m.d),
                   o.position[1] - o.bbox_m.h / 2, o.position[1] + o.bbox_m.h / 2)
                  for o in room.objects if o.object_id not in hidden]
    wall_like = product.sku in WALL_LIKE
    for o in others:
        if wall_like and o.get("sku") == DOOR_SKU:
            continue  # 이 벽에 달린 문은 겹침으로 보지 않는다
        sw, sh, sd = o["size_m"]
        oyaw = o.get("yaw_rad", 0.0) - math.pi / 2
        lo = float(o.get("base_m") or 0.0)
        kind = "wall" if mounted and o.get("sku") in WALL_LIKE else "placement"  # 문에게 가벽은 벽
        obstacles.append((kind, o.get("placement_id") or o.get("sku"), rect(tuple(o["center_xz"]), oyaw, sw, sd), lo, lo + sh))
    host_id = host["id"] if host else None
    if needs_counter(product) and host is None:
        add("needs_counter", Verdict.NO_FIT)
    # 올려 둔 가구 자신, 그리고 높이가 겹치지 않는 것(윗면보다 낮은 바닥 물건 등)은 뺀다
    # (바닥에 놓을 때 스캔 가구는 높이를 따지지 않고 전처럼 다 본다: 스캔 높이는 믿기 어렵다)
    obstacles = [ob for ob in obstacles if ob[1] != host_id
                 and ((base <= EPS and ob[0] == "object") or (ob[4] > base + EPS and ob[3] < base + h_m - EPS))]
    if host and not all(on_surface(host, q, 1e-4) for q in F):
        add("surface_overhang", Verdict.NO_FIT, host_id)

    hit_code = {"wall": "hits_wall", "object": "overlaps_object", "placement": "overlaps_placement"}
    on_wall = False
    for kind, ref, poly, _lo, _hi in obstacles:
        if mounted and kind == "wall" and overlaps(F, poly):
            on_wall = True
            continue  # 문이 달린 벽
        if overlaps(F, poly):
            add(hit_code[kind], Verdict.NO_FIT, ref)
        elif overlaps(R, poly):
            add("clearance_blocked", Verdict.NO_FIT, ref)
        elif D is not None and overlaps(D, poly):
            add("front_blocked", Verdict.NO_FIT, ref, label=DOOR_BLOCKED_LABEL if mounted else None)
        elif overlaps(M, poly):
            add("tight", Verdict.CONDITIONAL, ref)
        elif P is not None and passage_ref is None and overlaps(P, poly):
            passage_ref = ref
    if mounted and not on_wall:
        add("not_on_wall", Verdict.NO_FIT)
    if passage_ref is not None and not any(r["code"] == "front_blocked" for r in reasons):
        add("passage_narrow", Verdict.CONDITIONAL, passage_ref,
            label=f"문을 열었을 때 앞 통로가 {cfg.passage_mm:.0f} mm보다 좁음")

    # 천장: 가장 가까운 벽 높이
    if room.walls:
        wall, _ = _nearest_wall(room, c)
        slack = _wall_height(wall) - (base + h_m + top)
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
        elif op.type == "window" and base + h_m > op.sill_m + EPS:
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
    return PoseResult(v, pose, reasons, F, R, (w_m, h_m, d_m), base, host_id)


# ---------- 알맞은 자리 찾기 ----------
_RANK = {Verdict.FIT: 0, Verdict.CONDITIONAL: 1, Verdict.UNKNOWN: 2, Verdict.NO_FIT: 3}


def find_spot(room: Room, product: Product, cfg: FitConfig | None = None, others: Iterable[dict] = (),
              hidden: Iterable[str] = (), step_m: float = 0.1,
              near: Iterable[tuple[g.Pt, float]] = ()) -> Optional[PoseResult]:
    """벽을 따라 step_m 간격으로 등을 붙여 놓아 보고 가장 잘 들어가는 자리를 고른다.
    적합 > 조건부 순, 같으면 걸리는 이유가 적은 곳, 그다음 벽 가운데에 가까운 곳. 어디에도 안 들어가면 None.
    near: (가운데, 폭의 반) 목록. 주면 그중 가장 가까운 것 바로 옆을 먼저 고른다 (식기세척기는 싱크대 옆)."""
    cfg = cfg or FitConfig()
    size = product_size(product)
    if size is None or not room.walls:
        return None
    others, hidden, near = list(others), list(hidden), list(near)
    w_m, _, d_m = size
    side, back, _, _ = _clear(product)
    margin = cfg.margin_scanned_mm / 1000
    best, best_key = None, None

    def away(c: g.Pt) -> float:  # 가장 가까운 조리대 끝에서 떨어진 거리 (10 cm 단위로 뭉쳐 본다)
        return round(min((max(0.0, math.dist(c, q) - half_w - w_m / 2) for q, half_w in near), default=0.0), 1)

    for wall in room.walls:
        if wall.wall_id in hidden:  # 철거한 벽에는 붙이지 않는다
            continue
        f = _inward(room, wall)
        half = w_m / 2 + side + margin
        if f.length < 2 * half:
            continue
        nx, ny = f.v_axis
        v = _thick(wall) / 2 + back + margin + d_m / 2
        n = int((f.length - 2 * half) / step_m) + 1
        for i in range(n):
            u = half + i * step_m
            pose = Pose(f.to_world(u, v), math.atan2(ny, nx), wall.wall_id)
            r = check_pose(room, product, pose, cfg, others=others, hidden=hidden)
            if r.verdict == Verdict.NO_FIT:
                continue
            key = (_RANK[r.verdict], away(pose.center_xz), len(r.reasons), abs(u - f.length / 2))
            if best_key is None or key < best_key:
                best, best_key = r, key
    return best
