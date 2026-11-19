"""USDZ(RoomPlan 계열) → 내부 표준 room.json (기획 §8.2). Blender 없이 usd-core(pxr)로 처리.

분류 규칙은 프림 이름 기반이며 CLASSIFY_RULES로 바꿀 수 있다.
- 이름이 규칙에 맞고 숫자를 포함한 프림(예: Wall0, Door3, Storage0)을 요소 1개로 본다.
- 이미 요소로 잡힌 프림의 자손은 건너뛴다 (지오메트리 자식 중복 방지).
- 'Walls', 'Architecture'처럼 숫자 없는 컨테이너와 '_grp'로 끝나는 그룹은 요소가 아니다.
  실제 UGScan 내보내기는 Wall_N_grp 안에 WallN·WindowK·DoorK가 함께 들어 있어서,
  그룹을 요소로 잡으면 문·창이 사라진다. 같은 그룹의 벽에 개구부를 붙인다.
- Section_grp(방 구역 라벨)는 가구가 아니므로 통째로 건너뛴다.
구조 분석: docs/specs/usdz-analysis-2026-11-18.md
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
from pxr import Gf, Usd, UsdGeom

from core.models import BBox, Opening, Room, RoomObject, ScannedDims, Wall

CLASSIFY_RULES: list[tuple[str, str]] = [
    # (정규식, 종류) — 위에서부터 먼저 맞는 규칙 사용
    (r"(?i)^wall", "wall"),
    (r"(?i)^door", "door"),
    (r"(?i)^window", "window"),
    (r"(?i)^opening", "opening"),
    (r"(?i)^(floor|ceiling)", "skip"),
    (r"(?i)^([a-z]+?)(?:_?\d+)", "object"),  # Storage0, Refrigerator_1, washerDryer2 ...
]


def classify(name: str) -> tuple[str, str] | None:
    if re.match(r"(?i)^section_grp$", name):
        return "skip", "skip"
    if re.search(r"(?i)_grp$", name) or not re.search(r"\d", name):
        return None
    for pat, kind in CLASSIFY_RULES:
        m = re.match(pat, name)
        if m:
            if kind == "object":
                return kind, _snake(m.group(1))
            return kind, kind
    return None


def _snake(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


def _obb_corners(prim, scale: float, up: str) -> np.ndarray:
    """요소 프림 아래 모든 지오메트리의 extent 꼭짓점을 월드 좌표로 (m, Y-up 정규화).
    회전된 벽도 정확한 방향 박스를 얻기 위해 축 정렬 bbox 대신 각 지오메트리의 로컬 extent를 변환한다."""
    t = Usd.TimeCode.Default()
    pts = []
    for p in Usd.PrimRange(prim):
        if not p.IsA(UsdGeom.Boundable):
            continue
        b = UsdGeom.Boundable(p)
        ext = UsdGeom.Boundable.ComputeExtentFromPlugins(b, t) or b.GetExtentAttr().Get(t)
        if not ext:
            continue
        lo, hi = ext[0], ext[1]
        m = b.ComputeLocalToWorldTransform(t)
        for x in (lo[0], hi[0]):
            for y in (lo[1], hi[1]):
                for z in (lo[2], hi[2]):
                    q = m.Transform(Gf.Vec3d(x, y, z))
                    pts.append((q[0], q[1], q[2]))
    if not pts:
        return np.empty((0, 3))
    a = np.array(pts) * scale
    if up == "Z":  # Z-up → Y-up (x, z, -y)
        a = np.stack([a[:, 0], a[:, 2], -a[:, 1]], axis=1)
    return a


def _plan_obb(corners: np.ndarray):
    """평면(x,z) 투영의 주축 분석 → (중심, 주축 단위벡터, 길이, 두께), 높이 범위."""
    p = corners[:, [0, 2]]
    c = (p.min(0) + p.max(0)) / 2
    q = p - p.mean(0)
    if np.allclose(q, 0):
        axis = np.array([1.0, 0.0])
    else:
        _, _, vt = np.linalg.svd(q, full_matrices=False)
        axis = vt[0]
    if axis[0] < -1e-9 or (abs(axis[0]) <= 1e-9 and axis[1] < 0):
        axis = -axis
    perp = np.array([-axis[1], axis[0]])
    u, v = q @ axis, q @ perp
    center = p.mean(0) + axis * (u.max() + u.min()) / 2 + perp * (v.max() + v.min()) / 2
    return center, axis, float(u.max() - u.min()), float(v.max() - v.min()), (float(corners[:, 1].min()), float(corners[:, 1].max()))


def _r(x: float, nd: int = 4) -> float:
    v = round(float(x), nd)
    return 0.0 if v == 0 else v


def convert_stage(stage: Usd.Stage) -> Room:
    scale = UsdGeom.GetStageMetersPerUnit(stage) or 1.0
    up = UsdGeom.GetStageUpAxis(stage)

    elements: list[tuple[str, str, str, np.ndarray]] = []  # (kind, category, parent path, corners)
    it = iter(Usd.PrimRange(stage.GetPseudoRoot()))
    for prim in it:
        if not prim.IsA(UsdGeom.Imageable):
            continue
        c = classify(prim.GetName())
        if c is None:
            continue
        it.PruneChildren()
        kind, cat = c
        if kind == "skip":
            continue
        corners = _obb_corners(prim, scale, up)
        if len(corners):
            elements.append((kind, cat, str(prim.GetParent().GetPath()), corners))

    walls_raw = [e for e in elements if e[0] == "wall"]
    floor_y = min((e[3][:, 1].min() for e in walls_raw), default=0.0)

    walls: list[Wall] = []
    wall_by_group: dict[str, Wall] = {}
    for i, (_, _, parent, cs) in enumerate(walls_raw):
        center, axis, length, thick, (y0, y1) = _plan_obb(cs)
        s, e = center - axis * length / 2, center + axis * length / 2
        walls.append(Wall(
            wall_id=f"w{i + 1}", start=(_r(s[0]), _r(s[1])), end=(_r(e[0]), _r(e[1])),
            thickness_m=_r(thick), scanned=ScannedDims(length_m=_r(length), height_m=_r(y1 - floor_y)),
        ))
        if parent.endswith("_grp"):
            wall_by_group[parent] = walls[-1]

    openings: list[Opening] = []
    objects: list[RoomObject] = []
    counters: dict[str, int] = {}
    for kind, cat, parent, cs in elements:
        if kind == "wall":
            continue
        center, axis, length, depth, (y0, y1) = _plan_obb(cs)
        if kind in ("door", "window", "opening"):
            own = wall_by_group.get(parent)
            wall, u = _nearest_wall([own] if own else walls, center)
            counters[kind] = counters.get(kind, 0) + 1
            prefix = {"door": "d", "window": "win", "opening": "op"}[kind]
            openings.append(Opening(
                opening_id=f"{prefix}{counters[kind]}", type=kind, wall_id=wall.wall_id if wall else None,
                offset_m=_r(max(0.0, u - length / 2)), width_m=_r(length), height_m=_r(y1 - y0),
                sill_m=_r(max(0.0, y0 - floor_y)),
            ))
        else:
            counters["o"] = counters.get("o", 0) + 1
            objects.append(RoomObject(
                object_id=f"o{counters['o']}", category=cat,
                bbox_m=BBox(w=_r(length), h=_r(y1 - y0), d=_r(depth)),
                position=(_r(center[0]), _r((y0 + y1) / 2 - floor_y), _r(center[1])),
                yaw_rad=_r(math.atan2(axis[1], axis[0])),
            ))
    return Room(walls=walls, openings=openings, objects=objects)


def _nearest_wall(walls: list[Wall], pt) -> tuple[Wall | None, float]:
    best, best_d, best_u = None, float("inf"), 0.0
    for w in walls:
        a, b = np.array(w.start), np.array(w.end)
        ab = b - a
        L = float(np.linalg.norm(ab)) or 1e-9
        t = float(np.clip(np.dot(np.array(pt) - a, ab) / L ** 2, 0, 1))
        d = float(np.linalg.norm(np.array(pt) - (a + ab * t)))
        if d < best_d:
            best, best_d, best_u = w, d, t * L
    return best, best_u


def convert_usdz(path: str | Path) -> Room:
    stage = Usd.Stage.Open(str(path))
    if stage is None:
        raise ValueError(f"USD 파일을 열 수 없음: {path}")
    return convert_stage(stage)


if __name__ == "__main__":
    import sys
    print(convert_usdz(sys.argv[1]).model_dump_json(indent=2))
