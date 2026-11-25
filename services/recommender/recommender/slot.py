"""장 칸에 끼워 넣기: 빌트인 가전을 하부장·키큰장 줄에 맞춰 넣고, 겹치는 장은 그만큼 칸을 내준다.

규칙은 docs/specs/fit-rules.md '장 칸에 끼워 넣는 빌트인'. 화면이 따라 쓰는 같은 계산은 apps/web/js/slot.js.
평면 좌표 (x, y) = 3D (x, z). yaw = 정면 방향, 폭 축 = yaw - 90°.
장 기준 좌표: u = 폭 축(장 가운데가 0), v = 정면 쪽(장 가운데가 0).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional

from core.models import Product

from .mount import BUILTIN, FLUSH, STANDOFF_M, mount_kind
from .pose import Pose

CATEGORIES = frozenset({"dishwasher", "refrigerator", "kimchi_refrigerator", "freezer"})
DOOR_BACK_M = {"decor:basecab": 0.02, "decor:tallcab": 0.0}  # 문짝 앞면이 장 깊이보다 이만큼 안쪽 (build_furniture.py)
UNDER_MAX_M = 1.0    # 이보다 낮은 제품은 하부장 줄(상판 아래)에, 높은 제품은 키큰장 줄에 들어간다
REACH_M = 0.3        # 장 줄에서 앞뒤로 이만큼 안에 오면 줄에 맞춘다
EDGE_M = 0.15        # 장 끝에서 이만큼 안이면 끝에 맞춘다
MIN_PIECE_M = 0.15   # 칸을 내주고 남은 장이 이보다 좁으면 없앤다
LINE_M = 0.03        # 등이 이만큼 안으로 나란하면 같은 줄
YAW_RAD = math.radians(3)
NEXT_M = 0.01        # 옆 장과 이만큼 안으로 붙어 있으면 이어진 것으로 본다
COVER_MIN_M = 0.005


def slotable(p: Product) -> bool:
    """장 칸에 끼워 넣는 제품: 바닥에 세우는 빌트인·핏 앤 맥스 (식기세척기, 냉장고·김치냉장고·냉동고)."""
    return p.category in CATEGORIES and mount_kind(p) in (BUILTIN, FLUSH)


@dataclass
class Slot:
    pose: Pose
    host: str                                  # 기준이 된 장
    edits: list[dict] = field(default_factory=list)
    # {"id", "center_xz", "w"}: 줄어든 장 · {"id", "remove": True}: 없어진 장 · {"like", "center_xz", "w"}: 갈라져 새로 생긴 장


def _turn(a: float) -> float:
    return abs((a + math.pi) % (2 * math.pi) - math.pi)


def _frame(c: dict):
    yaw = c["yaw_rad"]
    return (math.cos(yaw - math.pi / 2), math.sin(yaw - math.pi / 2)), (math.cos(yaw), math.sin(yaw))


def _local(c: dict, p) -> tuple[float, float]:
    (ux, uy), (fx, fy) = _frame(c)
    dx, dy = p[0] - c["center_xz"][0], p[1] - c["center_xz"][1]
    return dx * ux + dy * uy, dx * fx + dy * fy


def _world(c: dict, u: float, v: float) -> tuple[float, float]:
    (ux, uy), (fx, fy) = _frame(c)
    return c["center_xz"][0] + ux * u + fx * v, c["center_xz"][1] + uy * u + fy * v


def _hosts(size, cabinets: Iterable[dict]) -> list[dict]:
    """이 제품이 들어갈 수 있는 장: 낮은 제품은 하부장, 키 큰 제품은 그보다 큰 키큰장."""
    h = size[1]
    out = []
    for c in cabinets:
        if c.get("sku") not in DOOR_BACK_M or not c.get("size_m"):
            continue
        ch = c["size_m"][1]
        if ch + 1e-9 >= h and (ch <= UNDER_MAX_M) == (h <= UNDER_MAX_M):
            out.append(c)
    return out


def _v0(size, c: dict, back_m: float) -> float:
    """장 줄에서 제품 가운데의 앞뒤 자리. 장보다 얕으면 문짝 앞면에 맞추고, 깊으면 등을 장 등에 맞춘다(앞으로 나온다)."""
    d, cd = size[2], c["size_m"][2]
    door = DOOR_BACK_M[c["sku"]]
    if d <= cd - door + 1e-9:
        return cd / 2 - door - d / 2
    return -cd / 2 + back_m + STANDOFF_M + d / 2


def _run(host: dict, hosts: list[dict]) -> list[tuple[float, float, dict]]:
    """host와 한 줄로 선 장들을 host 기준 폭 축 구간 (a, b, 장)으로."""
    out = []
    for c in hosts:
        if _turn(c["yaw_rad"] - host["yaw_rad"]) > YAW_RAD:
            continue
        u, v = _local(host, c["center_xz"])
        if abs((v - c["size_m"][2] / 2) - (-host["size_m"][2] / 2)) > LINE_M:
            continue
        out.append((u - c["size_m"][0] / 2, u + c["size_m"][0] / 2, c))
    return sorted(out, key=lambda t: t[0])


def slot_in(size, pose: Pose, cabinets: Iterable[dict], side_m: float = 0.0, back_m: float = 0.0,
            keep: Iterable[str] = ()) -> Optional[Slot]:
    """size (w, h, d) 제품을 pose 근처 장 줄에 끼운 자리와, 칸을 내주려고 바뀌는 장들. 가까운 줄이 없으면 None.
    side_m: 제품 옆에 남겨야 하는 틈. keep: 자를 수 없는 장(고정했거나 안에 정수기가 든 장)."""
    w = size[0]
    hosts = _hosts(size, cabinets)
    half = w / 2 + side_m + STANDOFF_M
    best = None
    for c in hosts:
        u, v = _local(c, pose.center_xz)
        off_v = abs(v - _v0(size, c, back_m))
        gap = abs(u) - c["size_m"][0] / 2 - half
        if off_v > REACH_M or gap > EDGE_M:
            continue
        key = (max(0.0, gap), off_v)
        if best is None or key < best[0]:
            best = (key, c)
    if best is None:
        return None
    host = best[1]
    run = _run(host, hosts)
    s, _ = _local(host, pose.center_xz)
    # 장 끝에 가까우면 끝에 맞춘다 (가장 조금 움직이는 쪽)
    shift = None
    for a, b, _c in run:
        for edge in (a, b):
            for mine in (s - half, s + half):
                d = edge - mine
                if abs(d) <= EDGE_M and (shift is None or abs(d) < abs(shift) - 1e-9):
                    shift = d
    s += shift or 0.0
    lo, hi = s - half, s + half
    keep = set(keep)
    edits: list[dict] = []
    for a, b, c in run:
        if min(b, hi) - max(a, lo) <= 1e-4:
            continue
        if c["placement_id"] in keep:
            return None
        pieces = [(x, y) for x, y in ((a, lo), (hi, b)) if y - x >= MIN_PIECE_M]
        if not pieces:
            edits.append({"id": c["placement_id"], "remove": True})
            continue
        for i, (x, y) in enumerate(pieces):
            e = {"center_xz": _world(host, (x + y) / 2, _local(host, c["center_xz"])[1]), "w": y - x}
            edits.append({"id": c["placement_id"], **e} if i == 0 else {"like": c["placement_id"], **e})
    center = _world(host, s, _v0(size, host, back_m))
    return Slot(Pose(center, host["yaw_rad"], host.get("wall_id")), host["placement_id"], edits)


def cover(size, pose: Pose, cabinets: Iterable[dict], side_m: float = 0.0, back_m: float = 0.0) -> Optional[dict]:
    """끼워 넣은 제품 위를 덮는 판: 하부장 줄이면 상판이 이어지고, 키큰장 줄이면 위 가림판.
    옆 장과 나란히 붙어 있을 때만. off_m = 제품 가운데에서 장 가운데 줄까지(정면 쪽 +), left/right_m = 옆 장까지의 틈."""
    w, h, _ = size
    best = None
    sides = {-1: None, 1: None}
    for c in _hosts(size, cabinets):
        if _turn(c["yaw_rad"] - pose.yaw_rad) > YAW_RAD:
            continue
        u, v = _local(c, pose.center_xz)
        if abs(v - _v0(size, c, back_m)) > LINE_M:
            continue
        gap = abs(u) - c["size_m"][0] / 2 - w / 2
        if gap < -NEXT_M or gap > side_m + NEXT_M:
            continue
        side = -1 if u > 0 else 1  # 장이 제품의 왼쪽(-1)인지 오른쪽(1)인지
        if sides[side] is None or gap < sides[side]:
            sides[side] = max(0.0, gap)
        if best is None or c["size_m"][1] > best[0]["size_m"][1]:
            best = (c, v)
    if best is None or best[0]["size_m"][1] - h < COVER_MIN_M:
        return None
    c, v = best
    return {"top_m": c["size_m"][1], "depth_m": c["size_m"][2], "off_m": round(-v, 4), "look": c["sku"].split(":")[1],
            "hex": c.get("hex"), "left_m": round(sides[-1] or 0.0, 4), "right_m": round(sides[1] or 0.0, 4)}
