"""와이파이 신호 세기 근사 (S7). 다중 벽 모델:
RSSI(dBm) = 송신 출력 - 1 m 기준 손실 - 10·n·log10(거리) - Σ(통과한 벽·창·금속 가전 감쇠).
열린 문 구간을 지나가면 벽 감쇠를 더하지 않는다. 가구(나무·천)는 무시한다.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from core.models import Room
from recommender.pose import inside_room

Pt = tuple[float, float]

# 1 m 자유공간 손실: 20·log10(4π·1m/λ). 2.4 GHz ≈ 40.0 dB, 5 GHz(5.25) ≈ 46.8 → 흔히 쓰는 46.4 사용
PL0 = {"2.4": 40.0, "5": 46.4, "6": 48.2}


@dataclass(frozen=True)
class WifiConfig:
    band: str = "5"
    tx_dbm: float = 20.0
    pl0_db: float = 46.4
    n: float = 2.0
    wall_db: float = 12.0   # 콘크리트 벽 1장 (5 GHz 기준 흔한 값). 석고보드면 3~5
    glass_db: float = 4.0   # 창
    metal_db: float = 10.0  # 냉장고 같은 금속 대형 가전
    grade_good: float = -60.0
    grade_ok: float = -70.0

    @classmethod
    def from_env(cls, band: str = "5") -> "WifiConfig":
        if band not in PL0:
            raise ValueError("band는 2.4, 5, 6")
        g = lambda k, d: float(os.getenv(k, d))  # noqa: E731
        wall = {"2.4": ("WIFI_WALL_DB_24G", 8), "5": ("WIFI_WALL_DB_5G", 12), "6": ("WIFI_WALL_DB_6G", 14)}[band]
        return cls(band=band, tx_dbm=g("WIFI_TX_DBM", 20), pl0_db=PL0[band], n=g("WIFI_PATH_N", 2.0),
                   wall_db=g(*wall),
                   glass_db=g("WIFI_GLASS_DB", 4), metal_db=g("WIFI_METAL_DB", 10))

    def assumptions(self) -> list[str]:
        return [f"{self.band} GHz, 공유기 출력 {self.tx_dbm:g} dBm, 경로손실 지수 {self.n:g}",
                f"벽 1장 {self.wall_db:g} dB, 창 {self.glass_db:g} dB, 금속 가전 {self.metal_db:g} dB, 문은 열려 있다고 가정",
                "가구·사람·위아래 층 신호는 계산하지 않음", f"좋음 ≥ {self.grade_good:g} dBm, 보통 ≥ {self.grade_ok:g} dBm"]


def _cross(a: Pt, b: Pt, c: Pt, d: Pt) -> Optional[float]:
    """선분 ab와 cd가 교차하면 cd 위의 위치(0~1)."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-12:
        return None
    q = (c[0] - a[0], c[1] - a[1])
    t = (q[0] * s[1] - q[1] * s[0]) / den
    u = (q[0] * r[1] - q[1] * r[0]) / den
    if 1e-9 < t < 1 - 1e-9 and 0 <= u <= 1:
        return u
    return None


def _wall_loss(room: Room, a: Pt, b: Pt, cfg: WifiConfig) -> float:
    loss = 0.0
    for w in room.walls:
        u = _cross(a, b, tuple(w.start), tuple(w.end))
        if u is None:
            continue
        L = math.hypot(w.end[0] - w.start[0], w.end[1] - w.start[1])
        pos = u * L
        hit = cfg.wall_db
        for op in room.openings:
            if op.wall_id == w.wall_id and op.offset_m <= pos <= op.offset_m + op.width_m:
                hit = 0.0 if op.type in ("door", "opening") else min(hit, cfg.glass_db)
        loss += hit
    return loss


def _cross_t(a: Pt, b: Pt, c: Pt, d: Pt) -> Optional[float]:
    """선분 ab와 cd가 교차하면 ab 위의 위치(0~1)."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-12:
        return None
    q = (c[0] - a[0], c[1] - a[1])
    t = (q[0] * s[1] - q[1] * s[0]) / den
    u = (q[0] * r[1] - q[1] * r[0]) / den
    return t if 1e-9 < t < 1 - 1e-9 and 0 <= u <= 1 else None


def _blocker_loss(a: Pt, b: Pt, blockers: Iterable, cfg: WifiConfig, tx_h: float = 0.0, rx_h: float = 0.0) -> float:
    """blockers: 바닥 사각형, 또는 (바닥 사각형, 윗면 높이). 높이가 있으면 신호가 그 위로 지나갈 때는 막지 않는다."""
    loss = 0.0
    for b_ in blockers:
        poly, top = (b_[0], b_[1]) if len(b_) == 2 and not isinstance(b_[1], tuple) else (b_, None)
        ts = [t for i in range(len(poly)) if (t := _cross_t(a, b, poly[i], poly[(i + 1) % len(poly)])) is not None]
        if ts and (top is None or any(tx_h + t * (rx_h - tx_h) <= top for t in ts)):
            loss += cfg.metal_db
    return loss


def rssi_at(room: Room, router: Pt, p: Pt, cfg: WifiConfig, blockers: Iterable = (),
            tx_h: float = 0.0, rx_h: float = 0.0) -> float:
    """tx_h: 공유기 높이(가구 위에 올렸으면 그 윗면), rx_h: 받는 쪽 높이. 둘 다 0이면 평면 거리."""
    d = max(1.0, math.hypot(p[0] - router[0], p[1] - router[1], tx_h - rx_h))
    return (cfg.tx_dbm - cfg.pl0_db - 10 * cfg.n * math.log10(d)
            - _wall_loss(room, router, p, cfg) - _blocker_loss(router, p, blockers, cfg, tx_h, rx_h))


def _grid(room: Room, cell_m: float):
    xs = [c for w in room.walls for c in (w.start[0], w.end[0])]
    ys = [c for w in room.walls for c in (w.start[1], w.end[1])]
    x0, y0 = min(xs), min(ys)
    nx, ny = max(1, math.ceil((max(xs) - x0) / cell_m)), max(1, math.ceil((max(ys) - y0) / cell_m))
    centers = [[(x0 + (i + 0.5) * cell_m, y0 + (j + 0.5) * cell_m) for i in range(nx)] for j in range(ny)]
    mask = [[inside_room(room, c) for c in row] for row in centers]
    return (x0, y0), nx, ny, centers, mask


def grade(v: float, cfg: WifiConfig) -> str:
    return "good" if v >= cfg.grade_good else "ok" if v >= cfg.grade_ok else "weak"


def coverage(room: Room, router: Pt, cfg: WifiConfig, cell_m: float = 0.25,
             blockers: Iterable = (), points: Optional[dict[str, Pt]] = None,
             tx_h: float = 0.0, rx_h: float = 0.0) -> dict:
    blockers = list(blockers)
    origin, nx, ny, centers, mask = _grid(room, cell_m)
    values = [[round(rssi_at(room, router, c, cfg, blockers, tx_h, rx_h), 1) if m else None for c, m in zip(row, mrow)]
              for row, mrow in zip(centers, mask)]
    flat = [v for row in values for v in row if v is not None]
    share = {k: 0.0 for k in ("good", "ok", "weak")}
    for v in flat:
        share[grade(v, cfg)] += 1 / len(flat)
    pts = {k: round(rssi_at(room, router, c, cfg, blockers, tx_h, rx_h), 1) for k, c in (points or {}).items()}
    return {"origin": list(origin), "cell_m": cell_m, "nx": nx, "ny": ny, "values": values, "router": list(router),
            "share": share, "min_dbm": min(flat) if flat else None, "points": pts,
            "grades": {k: grade(v, cfg) for k, v in pts.items()}, "assumptions": cfg.assumptions()}


def best_router_spot(room: Room, cfg: WifiConfig, cell_m: float = 0.5, cand_m: float = 0.75,
                     blockers: Iterable[Sequence[Pt]] = ()) -> tuple[Pt, float]:
    """가장 약한 곳의 신호가 가장 센 공유기 자리 (방 안 후보 격자에서)."""
    blockers = list(blockers)
    _, _, _, centers, mask = _grid(room, cell_m)
    targets = [c for row, mrow in zip(centers, mask) for c, m in zip(row, mrow) if m]
    _, _, _, cands, cmask = _grid(room, cand_m)
    best, best_v = None, -math.inf
    for row, mrow in zip(cands, cmask):
        for c, m in zip(row, mrow):
            if not m:
                continue
            v = min(rssi_at(room, c, t, cfg, blockers) for t in targets)
            if v > best_v:
                best, best_v = c, v
    return best, best_v
