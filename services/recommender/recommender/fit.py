"""빌트인 적합 판정 (기획 §9.1). 결정론적 규칙 — LLM은 이 결과를 설명만 한다."""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.models import Product, Room, Wall, Zone

from . import geometry as g


class Verdict(str, Enum):
    FIT = "fit"
    CONDITIONAL = "conditional"
    NO_FIT = "no_fit"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return {"fit": "적합", "conditional": "조건부", "no_fit": "불가", "unknown": "판정 불가"}[self.value]


# 최종 판정은 "가장 나쁜" 값 — 불가 > 판정 불가 > 조건부 > 적합
_WORST_ORDER = [Verdict.NO_FIT, Verdict.UNKNOWN, Verdict.CONDITIONAL, Verdict.FIT]
# 여러 벽 중 고를 때는 "가장 좋은" 값
_BEST_ORDER = [Verdict.FIT, Verdict.CONDITIONAL, Verdict.UNKNOWN, Verdict.NO_FIT]


@dataclass(frozen=True)
class FitConfig:
    margin_scanned_mm: float = 30.0
    margin_measured_mm: float = 5.0
    wall_snap_m: float = 0.15  # 영역 경계와 벽이 이 거리 안이면 영역의 벽으로 본다
    min_wall_overlap_m: float = 0.3
    snap_m: float = 0.3  # 자유 배치: 이 거리 안의 벽에 제품 등을 붙인다
    scanned_max_conditional: bool = False  # True면 스캔값만으로는 조건부까지만 (기획 초안 규칙)
    front_default_mm: float = 600.0  # 일반 가전의 문 열림 공간을 모를 때 가정하는 앞 공간
    passage_mm: float = 600.0  # 문을 연 앞으로 사람이 지나갈 통로 (0이면 보지 않음)

    @classmethod
    def from_env(cls) -> "FitConfig":
        return cls(
            margin_scanned_mm=float(os.getenv("FIT_MARGIN_SCANNED_MM", 30)),
            margin_measured_mm=float(os.getenv("FIT_MARGIN_MEASURED_MM", 5)),
            snap_m=float(os.getenv("FIT_SNAP_M", 0.3)),
            scanned_max_conditional=os.getenv("FIT_SCANNED_MAX_CONDITIONAL", "0") == "1",
            front_default_mm=float(os.getenv("FIT_FRONT_DEFAULT_MM", 600)),
            passage_mm=float(os.getenv("FIT_PASSAGE_MM", 600)),
        )


@dataclass
class DimResult:
    verdict: Verdict
    available_mm: Optional[float]
    required_mm: Optional[float]
    slack_mm: Optional[float]
    margin_mm: float
    source: str = "scanned"  # scanned | measured

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value, "label": self.verdict.label,
            "available_mm": _r(self.available_mm), "required_mm": _r(self.required_mm),
            "slack_mm": _r(self.slack_mm), "margin_mm": self.margin_mm, "source": self.source,
        }


@dataclass
class FitResult:
    sku: str
    verdict: Verdict
    wall_id: Optional[str]
    dims: dict[str, DimResult] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    placement: Optional[dict] = None  # 배치 미리보기용: 벽 위 구간 중심·방향

    def to_dict(self) -> dict:
        return {
            "sku": self.sku, "verdict": self.verdict.value, "label": self.verdict.label,
            "wall_id": self.wall_id, "dims": {k: v.to_dict() for k, v in self.dims.items()},
            "notes": self.notes, "placement": self.placement,
        }


def _r(x):
    return None if x is None else round(x, 1)


def worst(vs) -> Verdict:
    vs = list(vs)
    return min(vs, key=_WORST_ORDER.index)


def judge_dimension(available_mm, required_mm, measured: bool, cfg: FitConfig) -> DimResult:
    margin = cfg.margin_measured_mm if measured else cfg.margin_scanned_mm
    src = "measured" if measured else "scanned"
    if available_mm is None or required_mm is None:
        return DimResult(Verdict.UNKNOWN, available_mm, required_mm, None, margin, src)
    slack = available_mm - required_mm
    if slack < 0:
        v = Verdict.NO_FIT
    elif slack < margin:
        v = Verdict.CONDITIONAL
    else:
        v = Verdict.CONDITIONAL if (not measured and cfg.scanned_max_conditional) else Verdict.FIT
    return DimResult(v, available_mm, required_mm, slack, margin, src)


def required_space(p: Product) -> tuple[dict[str, Optional[float]], bool]:
    """필요 설치 치수(mm). required_space_mm 우선, 없으면 제품 치수 + 이격.
    옆 이격은 양옆 각각(side × 2). 한쪽에만 두면 되는 값(side_total)이 있으면 그 값을 한 번만 더한다.
    두 번째 값: 이격 정보가 없어 제품 치수만으로 계산했는지."""
    rs, pd, cl = p.required_space_mm, p.product_dims_mm, p.clearance_mm
    clearance_unknown = False

    def pick(req, dim, extra):
        nonlocal clearance_unknown
        if req is not None:
            return req
        if dim is None:
            return None
        if extra is None:
            clearance_unknown = True
            return dim
        return dim + extra

    side = cl.side_total if cl.side_total is not None else None if cl.side is None else 2 * cl.side
    w = pick(rs.w, pd.w, side)
    h = pick(rs.h, pd.h, cl.top)
    d = pick(rs.d, pd.d, cl.back)
    return {"width": w, "height": h, "depth": d}, clearance_unknown


# 앞으로 여닫는 문이 있는 종류. 일반(프리스탠딩) 제품이면 앞쪽에 문 열림 공간이 필요하다.
# 빌트인과 Fit & Max(빌트인 핏)는 장 안에 들어가는지만 본다.
DOOR_CATEGORIES = {
    "refrigerator", "kimchi_refrigerator", "freezer", "wine_cellar", "dishwasher", "oven",
    "washer", "dryer", "wash_tower", "washer_dryer", "styler", "shoe_care",
}


def front_space(p: Product, cfg: FitConfig) -> tuple[Optional[float], bool]:
    """일반 가전의 앞쪽 문 열림 공간(mm). 빌트인·빌트인 핏이거나 문이 없으면 None.
    두 번째 값: LGE.COM 값이 없어 기본값(FIT_FRONT_DEFAULT_MM)을 가정했는지."""
    if p.install_type != "freestanding":
        return None, False
    if p.door_swing_mm is not None:
        return p.door_swing_mm, False
    if p.category in DOOR_CATEGORIES:
        return cfg.front_default_mm, True
    return None, False


def _front_free(room: Room, origin: g.Pt, direction: g.Pt) -> Optional[float]:
    """origin에서 direction으로 벽이나 기존 가구에 닿을 때까지의 거리(m)."""
    hits = [g.ray_exit_distance(origin, direction, [tuple(w.start), tuple(w.end)]) for w in room.walls]
    for ob in room.objects:
        hits.append(g.ray_exit_distance(origin, direction,
                                        g.rect_footprint(ob.position[0], ob.position[2], ob.bbox_m.w, ob.bbox_m.d, ob.yaw_rad)))
    hits = [h for h in hits if h is not None]
    return min(hits) if hits else None


def zone_walls(room: Room, zone: Zone, cfg: FitConfig) -> list[Wall]:
    if zone.wall_ids:
        return [room.wall(wid) for wid in zone.wall_ids]
    out = []
    c = g.centroid(zone.polygon_m)
    for w in room.walls:
        lo, hi = _zone_clip(w, zone, c)
        if hi - lo < cfg.min_wall_overlap_m:
            continue
        fr = g.WallFrame(w.start, w.end, c)
        samples = [fr.to_world(lo + (hi - lo) * t, 0) for t in (0.1, 0.5, 0.9)]
        if all(g.distance_to_boundary(s, zone.polygon_m) <= cfg.wall_snap_m for s in samples):
            out.append(w)
    return out


def _zone_clip(w: Wall, zone: Zone, inward: g.Pt) -> tuple[float, float]:
    fr = g.WallFrame(w.start, w.end, inward)
    us = [fr.to_local(p)[0] for p in zone.polygon_m]
    return max(0.0, min(us)), min(fr.length, max(us))


def _check_wall(room: Room, zone: Zone, wall: Wall, p: Product, cfg: FitConfig) -> FitResult:
    req, clearance_unknown = required_space(p)
    c = g.centroid(zone.polygon_m)
    fr = g.WallFrame(wall.start, wall.end, c)
    m = wall.measured

    len_measured = m is not None and m.length_m is not None
    h_measured = m is not None and m.height_m is not None
    d_measured = m is not None and m.depth_m is not None
    wall_len = m.length_m if len_measured else wall.scanned.length_m
    wall_h = m.height_m if h_measured else wall.scanned.height_m

    # 1) 폭: 영역이 덮는 벽 구간 − 개구부 − 기존 오브젝트 → 최대 연속 구간
    lo, hi = _zone_clip(wall, zone, c)
    hi = min(hi, wall_len)
    req_h_m = None if req["height"] is None else req["height"] / 1000
    req_d_m = 0.6 if req["depth"] is None else req["depth"] / 1000
    blocked = []
    for o in room.openings:
        if o.wall_id != wall.wall_id:
            continue
        if o.type == "window" and req_h_m is not None and o.sill_m >= req_h_m:
            continue  # 제품보다 높은 창문은 간섭하지 않음
        blocked.append((o.offset_m, o.offset_m + o.width_m))
    for ob in room.objects:
        fp = g.rect_footprint(ob.position[0], ob.position[2], ob.bbox_m.w, ob.bbox_m.d, ob.yaw_rad)
        loc = [fr.to_local(q) for q in fp]
        vmin, vmax = min(v for _, v in loc), max(v for _, v in loc)
        if vmax > -0.05 and vmin < req_d_m:
            blocked.append((min(u for u, _ in loc), max(u for u, _ in loc)))
    free = g.free_intervals(lo, hi, blocked)
    best = max(free, key=lambda ab: ab[1] - ab[0], default=None)
    avail_w = None if best is None else (best[1] - best[0]) * 1000

    # 2) 높이
    avail_h = wall_h * 1000 if wall_h is not None else None

    # 3) 깊이: 실측 깊이, 없으면 구간 중앙에서 영역 경계까지
    if d_measured:
        avail_d = m.depth_m * 1000
    elif best is not None:
        mid_u = (best[0] + best[1]) / 2
        dist = g.ray_exit_distance(fr.to_world(mid_u, 1e-4), fr.v_axis, zone.polygon_m)
        avail_d = None if dist is None else (dist + 1e-4) * 1000
    else:
        avail_d = None

    dims = {
        "width": judge_dimension(avail_w, req["width"], len_measured, cfg),
        "height": judge_dimension(avail_h, req["height"], h_measured, cfg),
        "depth": judge_dimension(avail_d, req["depth"], d_measured, cfg),
    }
    # 4) 일반 가전: 제품 앞면에서 벽·가구까지 남는 거리 ≥ 문 열림 공간
    front_req, front_assumed = front_space(p, cfg)
    if front_req is not None:
        front_avail = None
        if best is not None and req["depth"] is not None:
            mid = fr.to_world((best[0] + best[1]) / 2, 1e-4)
            free = _front_free(room, mid, fr.v_axis)
            front_avail = None if free is None else (free + 1e-4) * 1000 - req["depth"]
        dims["front"] = judge_dimension(front_avail, front_req, False, cfg)
    verdict = worst(d.verdict for d in dims.values())
    notes = []
    if front_assumed:
        notes.append("front_space_assumed")
        if verdict == Verdict.FIT:
            verdict = Verdict.CONDITIONAL
    if clearance_unknown:
        notes.append("clearance_unknown")
        if verdict == Verdict.FIT:
            verdict = Verdict.CONDITIONAL
    if any(d.source == "scanned" for d in dims.values()):
        notes.append("scan_based")

    placement = None
    if best is not None and req["width"] is not None:
        w_m = (p.product_dims_mm.w or req["width"]) / 1000
        u0 = best[0] + (req["width"] / 1000 - w_m) / 2  # 이격 절반만큼 띄움
        cu = u0 + w_m / 2
        dd = (p.product_dims_mm.d or req["depth"] or 600) / 1000
        x, y = fr.to_world(cu, dd / 2)
        placement = {
            "center_xz": [round(x, 4), round(y, 4)],
            "yaw_rad": round(math.atan2(fr.v_axis[1], fr.v_axis[0]), 4),
            "size_m": [w_m, (p.product_dims_mm.h or req["height"] or 0) / 1000, dd],
        }
    return FitResult(p.sku, verdict, wall.wall_id, dims, notes, placement)


def check_fit(room: Room, zone: Zone, product: Product, cfg: FitConfig | None = None) -> FitResult:
    cfg = cfg or FitConfig.from_env()
    walls = zone_walls(room, zone, cfg)
    if not walls:
        return FitResult(product.sku, Verdict.UNKNOWN, None, {}, ["no_wall_in_zone"])
    results = [_check_wall(room, zone, w, product, cfg) for w in walls]

    def key(r: FitResult):
        slacks = [d.slack_mm for d in r.dims.values() if d.slack_mm is not None]
        return (_BEST_ORDER.index(r.verdict), -(min(slacks) if slacks else -1e9))

    return min(results, key=key)
