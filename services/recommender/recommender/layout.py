"""조합 자동 배치: 가구·가전 여러 개를 이 집 구조에 맞춰 한 번에 놓는다 (docs/specs/layout-rules.md).

Merrell 외(SIGGRAPH 2011) "Interactive Furniture Layout Using Interior Design Guidelines"가 인테리어 지침을
비용으로 바꾼 방식을 따른다. 치수는 그 논문 표 1(Panero & Repetto 인체치수)에서 가져왔다.
- 중심점(강조): 침대·소파 같은 중심 가구를 먼저 놓고, 나머지는 그것을 기준으로 대칭·마주 보기.
- 이격: 침대 옆 91 cm, 의자 앞 76 cm, 수납장 앞 61 cm, 소파~테이블 41~46 cm, 협탁~침대 0~30 cm.
- 정렬: 벽과 평행·직각. 시각 균형: 놓인 것들의 무게 중심이 방 가운데에서 멀지 않게.
- 문 앞(문 폭 x 0.9 m)은 비운다. 겹침·벽·이격은 check_pose 판정을 그대로 쓴다.
같은 입력이면 같은 배치가 나온다 (난수 없음).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Literal, Optional

from core.models import Product, Room

from . import geometry as g
from .fit import FitConfig, Verdict
from .pose import Pose, _clear, _inward, _thick, check_pose, inside_room, overlaps, product_size, rect, wall_rect

# 인체치수 (m). Merrell 외 2011 표 1
BEDSIDE_M = 0.91        # 침대 옆 통로 36 in
SEAT_FRONT_M = 0.76     # 의자·소파 앞 30 in
CABINET_FRONT_M = 0.61  # 수납장·선반 앞 24 in
TABLE_AROUND_M = 0.91   # 식탁 둘레 36 in
COFFEE_GAP_M = 0.43     # 소파~테이블 16~18 in의 가운데
NIGHTSTAND_GAP_M = 0.05  # 협탁~침대 0~12 in
DOOR_DEPTH_M = 0.9      # 문 앞 비우는 깊이
STEP_M = 0.1

Role = Literal["anchor", "pair", "front", "rug", "facing", "wall", "corner", "desk_chair", "appliance"]

_FRONT_NEED = {"bed": BEDSIDE_M, "sofa": SEAT_FRONT_M, "chair": SEAT_FRONT_M, "storage": CABINET_FRONT_M,
               "shelf": CABINET_FRONT_M, "dresser": CABINET_FRONT_M, "basecab": CABINET_FRONT_M,
               "tvstand": CABINET_FRONT_M, "table": TABLE_AROUND_M, "desk": SEAT_FRONT_M, "island": TABLE_AROUND_M}
_RANK = {Verdict.FIT: 0, Verdict.CONDITIONAL: 1, Verdict.UNKNOWN: 2}


@dataclass
class Item:
    key: str
    sku: str
    product: Product
    role: Role = "wall"
    color: Optional[str] = None
    hex: Optional[str] = None
    size_m: Optional[tuple[float, float, float]] = None  # decor 크기를 바꿨으면


@dataclass
class Placed:
    item: Item
    pose: Pose
    size: tuple[float, float, float]
    verdict: str
    reasons: list[dict] = field(default_factory=list)
    free_side_m: float = 0.0   # 중심 가구 양옆에 남은 벽 길이 중 짧은 쪽

    def as_placement(self, pid: str) -> dict:
        return {"placement_id": pid, "sku": self.item.sku, "center_xz": list(self.pose.center_xz),
                "yaw_rad": self.pose.yaw_rad, "size_m": list(self.size), "wall_id": self.pose.wall_id}


def _kind(it: Item) -> str:
    return it.sku.split(":", 1)[1] if it.sku.startswith("decor:") else it.product.category


def _front(yaw: float) -> g.Pt:
    return (math.cos(yaw), math.sin(yaw))


def _ahead(c: g.Pt, yaw: float, dist: float) -> g.Pt:
    return (c[0] + math.cos(yaw) * dist, c[1] + math.sin(yaw) * dist)


class _Planner:
    def __init__(self, room: Room, cfg: FitConfig, others: Iterable[dict], hidden: Iterable[str]):
        self.room, self.cfg = room, cfg
        self.hidden = list(hidden)
        self.others = list(others)
        self.placed: list[Placed] = []
        self.keepout: list[tuple[Optional[int], list[g.Pt]]] = [(None, z) for z in self._door_zones()]
        self.center = g.centroid([c for w in room.walls for c in (tuple(w.start), tuple(w.end))])

    # ---- 바탕 ----
    def _door_zones(self) -> list[list[g.Pt]]:
        zones = []
        for o in self.room.openings:
            if o.type == "window" or not o.wall_id or o.wall_id in self.hidden:
                continue
            w = self.room.wall(o.wall_id)
            f = _inward(self.room, w)
            u = o.offset_m + o.width_m / 2
            c = f.to_world(u, DOOR_DEPTH_M / 2)
            zones.append(rect(c, math.atan2(f.u_axis[1], f.u_axis[0]), o.width_m, DOOR_DEPTH_M))
        return zones

    def _walls(self):
        return [w for w in self.room.walls if w.wall_id not in self.hidden]

    def _judge(self, it: Item, pose: Pose):
        flat = it.role == "rug"
        others = [] if flat else self.others + [p.as_placement(f"plan-{i}") for i, p in enumerate(self.placed)
                                                 if p.item.role != "rug"]
        hidden = self.hidden + ([o.object_id for o in self.room.objects] if flat else [])
        return check_pose(self.room, it.product, pose, self.cfg, others=others, hidden=hidden)

    def _poly(self, pose: Pose, size, front=0.0) -> list[g.Pt]:
        return rect(pose.center_xz, pose.yaw_rad - math.pi / 2, size[0], size[2], front=front)

    def _front_blocked(self, pose: Pose, size, need: float) -> bool:
        """앞 공간(need m)이 벽·놓인 것과 겹치는지. 사람이 서고 문을 여는 자리."""
        if need <= 0:
            return False
        zone = rect(_ahead(pose.center_xz, pose.yaw_rad, size[2] / 2 + need / 2),
                    pose.yaw_rad - math.pi / 2, size[0], need)
        polys = [wall_rect(w) for w in self._walls()]
        polys += [self._poly(p.pose, p.size) for p in self.placed if p.item.role != "rug"]
        return any(overlaps(zone, q) for q in polys)

    def _in_keepout(self, pose: Pose, size, skip: Optional[int] = None) -> bool:
        poly = self._poly(pose, size)
        return any(overlaps(poly, z) for owner, z in self.keepout if owner is None or owner != skip)

    def _ok(self, it: Item, pose: Pose, skip: Optional[int] = None):
        """판정이 불가면 None. 아니면 (PoseResult, 벌점). skip = 앞 공간에 들어가도 되는 가구 번호."""
        r = self._judge(it, pose)
        if r.verdict == Verdict.NO_FIT or r.size_m is None:
            return None
        if it.role != "rug" and self._in_keepout(pose, r.size_m, skip):
            return None
        pen = _RANK.get(r.verdict, 2) * 2 + len(r.reasons)
        if self._front_blocked(pose, r.size_m, _FRONT_NEED.get(_kind(it), 0.0)):
            pen += 4
        return r, pen

    def _wall_poses(self, it: Item):
        """벽을 따라 등을 붙인 후보 자리 (벽, 벽 좌표계, u, 자세)."""
        size = product_size(it.product)
        if size is None:
            return
        w_m, _, d_m = size
        side, back, _, _ = _clear(it.product)
        margin = self.cfg.margin_scanned_mm / 1000
        for wall in self._walls():
            f = _inward(self.room, wall)
            half = w_m / 2 + side + margin
            if f.length < 2 * half:
                continue
            v = _thick(wall) / 2 + back + margin + d_m / 2
            yaw = math.atan2(f.v_axis[1], f.v_axis[0])
            for i in range(int((f.length - 2 * half) / STEP_M) + 1):
                u = half + i * STEP_M
                yield wall, f, u, Pose(f.to_world(u, v), yaw, wall.wall_id)

    def _balance(self, pose: Pose, size) -> float:
        """놓인 것들과 이 자리의 무게 중심(바닥 면적 가중)이 방 가운데에서 떨어진 거리."""
        pts = [(p.pose.center_xz, p.size[0] * p.size[2]) for p in self.placed if p.item.role != "rug"]
        pts.append((pose.center_xz, size[0] * size[2]))
        tot = sum(a for _, a in pts) or 1
        c = (sum(x[0] * a for x, a in pts) / tot, sum(x[1] * a for x, a in pts) / tot)
        return math.dist(c, self.center)

    def _add(self, it: Item, r, free_side=0.0) -> Placed:
        p = Placed(it, r.pose, r.size_m, r.verdict.value, r.reasons, free_side)
        self.placed.append(p)
        need = _FRONT_NEED.get(_kind(it), 0.0)
        if need and it.role != "rug":  # 앞 공간은 다음 가구가 막지 않게
            self.keepout.append((len(self.placed) - 1, rect(_ahead(p.pose.center_xz, p.pose.yaw_rad, p.size[2] / 2 + need / 2),
                                     p.pose.yaw_rad - math.pi / 2, p.size[0], need)))
        return p

    # ---- 역할별 ----
    def anchor(self, it: Item, side_need: float) -> Optional[Placed]:
        best, key = None, None
        for wall, f, u, pose in self._wall_poses(it):
            got = self._ok(it, pose)
            if not got:
                continue
            r, pen = got
            w = r.size_m[0]
            free = min(u - w / 2, f.length - u - w / 2)
            short = max(0.0, side_need - free)
            door_wall = any(o.wall_id == wall.wall_id and o.type != "window" for o in self.room.openings)
            win = any(o.wall_id == wall.wall_id and o.type == "window" for o in self.room.openings)
            k = (pen + short * 6 + (3 if door_wall else 0) + (1 if win else 0)
                 + abs(u - f.length / 2) / f.length * 2 - min(f.length, 6) * 0.1)
            if key is None or k < key:
                best, key = (r, free), k
        if best is None:
            return None
        return self._add(it, best[0], best[1])

    def pair(self, it: Item, anchor: Placed) -> list[Placed]:
        """중심 가구 양옆에 같은 방향으로 대칭. 한쪽만 들어가면 한쪽만."""
        size = product_size(it.product)
        if size is None:
            return []
        out = []
        ux, uz = math.cos(anchor.pose.yaw_rad - math.pi / 2), math.sin(anchor.pose.yaw_rad - math.pi / 2)
        fx, fz = _front(anchor.pose.yaw_rad)
        back = -anchor.size[2] / 2 + size[2] / 2   # 등을 같은 벽에 맞춘다
        for s in (-1, 1):
            off = anchor.size[0] / 2 + NIGHTSTAND_GAP_M + size[0] / 2
            c = (anchor.pose.center_xz[0] + s * ux * off + fx * back, anchor.pose.center_xz[1] + s * uz * off + fz * back)
            got = self._ok(it, Pose(c, anchor.pose.yaw_rad, anchor.pose.wall_id))
            if got:
                out.append(self._add(it, got[0]))
        return out

    def in_front(self, it: Item, anchor: Placed, gap: float) -> Optional[Placed]:
        size = product_size(it.product)
        if size is None:
            return None
        fx, fz = _front(anchor.pose.yaw_rad)
        d = anchor.size[2] / 2 + gap + size[2] / 2
        c = (anchor.pose.center_xz[0] + fx * d, anchor.pose.center_xz[1] + fz * d)
        got = self._ok(it, Pose(c, anchor.pose.yaw_rad), skip=self.placed.index(anchor))
        return self._add(it, got[0]) if got else None

    def rug(self, it: Item, anchor: Optional[Placed]) -> Optional[Placed]:
        size = product_size(it.product)
        if size is None:
            return None
        if anchor is None:
            c, yaw = self.center, 0.0
        else:
            fx, fz = _front(anchor.pose.yaw_rad)
            # 침대: 아래 2/3에 걸치게. 소파: 앞 테이블 밑
            d = anchor.size[2] * 0.25 if _kind(anchor.item) == "bed" else anchor.size[2] / 2 + COFFEE_GAP_M
            c, yaw = (anchor.pose.center_xz[0] + fx * d, anchor.pose.center_xz[1] + fz * d), anchor.pose.yaw_rad
        if not inside_room(self.room, c):
            return None
        got = self._ok(it, Pose(c, yaw))
        return self._add(it, got[0]) if got else None

    def facing(self, it: Item, anchor: Optional[Placed]) -> Optional[Placed]:
        """중심 가구를 마주 보는 벽, 중심 가구 정면 축에 가장 가까운 자리."""
        if anchor is None:
            return self.along_wall(it)
        af = _front(anchor.pose.yaw_rad)
        best, key = None, None
        for _, _, _, pose in self._wall_poses(it):
            if g.dot(_front(pose.yaw_rad), af) > -0.7:
                continue
            got = self._ok(it, pose)
            if not got:
                continue
            r, pen = got
            rel = g.sub(pose.center_xz, anchor.pose.center_xz)
            off = abs(rel[0] * -af[1] + rel[1] * af[0])  # 정면 축에서 옆으로 벗어난 거리
            k = pen + off * 2
            if key is None or k < key:
                best, key = r, k
        return self._add(it, best) if best else self.along_wall(it)

    def along_wall(self, it: Item) -> Optional[Placed]:
        best, key = None, None
        for _, _, _, pose in self._wall_poses(it):
            got = self._ok(it, pose)
            if not got:
                continue
            r, pen = got
            k = pen + self._balance(pose, r.size_m) * 0.5
            if key is None or k < key:
                best, key = r, k
        return self._add(it, best) if best else None

    def corner(self, it: Item, anchor: Optional[Placed], near: bool) -> Optional[Placed]:
        size = product_size(it.product)
        if size is None:
            return None
        cands = []
        for w in self._walls():
            f = _inward(self.room, w)
            inset = max(size[0], size[2]) / 2 + _thick(w) / 2 + 0.05
            for u in (inset, f.length - inset):
                cands.append(Pose(f.to_world(u, inset), math.atan2(f.v_axis[1], f.v_axis[0]), w.wall_id))
        ref = anchor.pose.center_xz if anchor else self.center
        cands.sort(key=lambda p: (math.dist(p.center_xz, ref) * (1 if near else -1), p.center_xz))
        for pose in cands:
            got = self._ok(it, pose)
            if got and got[1] == 0:
                return self._add(it, got[0])
        return None

    def desk_chair(self, it: Item) -> Optional[Placed]:
        desk = next((p for p in self.placed if _kind(p.item) == "desk"), None)
        if desk is None:
            return self.along_wall(it)
        size = product_size(it.product)
        fx, fz = _front(desk.pose.yaw_rad)
        d = desk.size[2] / 2 + size[2] / 2 + 0.02  # 책상 바로 앞 (판정에서 겹치지 않게)
        c = (desk.pose.center_xz[0] + fx * d, desk.pose.center_xz[1] + fz * d)
        got = self._ok(it, Pose(c, desk.pose.yaw_rad + math.pi), skip=self.placed.index(desk))
        return self._add(it, got[0]) if got else None


_ORDER = {"anchor": 0, "pair": 1, "front": 2, "facing": 3, "appliance": 4, "wall": 5, "desk_chair": 6, "rug": 7, "corner": 8}


def arrange(room: Room, items: list[Item], cfg: FitConfig | None = None, others: Iterable[dict] = (),
            hidden: Iterable[str] = ()) -> list[Placed]:
    """역할 순서(중심 → 양옆 → 앞 → 마주 → 가전 → 벽 → 러그 → 구석)로 하나씩 가장 좋은 자리에 놓는다.
    어디에도 안 들어가는 것은 억지로 넣지 않고 뺀다."""
    pl = _Planner(room, cfg or FitConfig(), others, hidden)
    anchor: Optional[Placed] = None
    for it in sorted(items, key=lambda i: _ORDER.get(i.role, 9)):
        if it.role == "anchor":
            got = pl.anchor(it, BEDSIDE_M if _kind(it) == "bed" else 0.3) if anchor is None else pl.along_wall(it)
            anchor = anchor or got
        elif it.role == "pair":
            if anchor:
                pl.pair(it, anchor)
        elif it.role == "front":
            if anchor:
                pl.in_front(it, anchor, COFFEE_GAP_M)
        elif it.role == "rug":
            pl.rug(it, anchor)
        elif it.role == "facing":
            pl.facing(it, anchor)
        elif it.role == "corner":
            pl.corner(it, anchor, near=_kind(it) == "lamp")
        elif it.role == "desk_chair":
            pl.desk_chair(it)
        else:
            pl.along_wall(it)
    return pl.placed
