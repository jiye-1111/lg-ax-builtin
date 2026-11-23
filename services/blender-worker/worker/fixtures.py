"""합성 RoomPlan형 USDZ 픽스처 생성기.

⚠️ 실제 UGScan 파일이 아니다. Apple RoomPlan 내보내기에서 흔히 보이는 구조를 *가정*해 만든다:
    /Room/Architecture/Walls/Wall0 (Xform) └ Wall0_geom (Cube, 크기 1 → scale로 치수)
    /Room/Architecture/Doors/Door0, /Windows/Window0
    /Room/Object/Storage/Storage0, /Refrigerator/Refrigerator0 ...
Y-up, metersPerUnit=1. 실제 샘플 확보 후 구조 차이는 converter.CLASSIFY_RULES로 맞춘다 (plan.md T1.6).
"""
from __future__ import annotations

import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdUtils


@dataclass
class BoxSpec:
    path: str
    center: tuple[float, float, float]  # (x, y, z), y = 높이
    size: tuple[float, float, float]    # (길이 x, 높이 y, 두께 z) — 로컬 축
    yaw_deg: float = 0.0                # Y축 회전


# 기본 시연 방: 5.2m × 3.6m, 천장 2.40m. 평면 (x, z).
#   w0: z=0 벽 (주방 벽, 5.2m)   w1: x=5.2 벽 (3.6m, 창문)
#   w2: z=3.6 벽 (거실 벽, 5.2m, 문)  w3: x=0 벽 (3.6m)
H = 2.40
T = 0.10
DEMO_ROOM = [
    BoxSpec("Architecture/Walls/Wall0", (2.6, H / 2, 0.0), (5.2, H, T), 0),
    BoxSpec("Architecture/Walls/Wall1", (5.2, H / 2, 1.8), (3.6, H, T), 90),
    BoxSpec("Architecture/Walls/Wall2", (2.6, H / 2, 3.6), (5.2, H, T), 180),
    BoxSpec("Architecture/Walls/Wall3", (0.0, H / 2, 1.8), (3.6, H, T), 270),
    # 문: w2(z=3.6)의 x 0.6~1.5 (폭 0.9, 높이 2.1)
    BoxSpec("Architecture/Doors/Door0", (1.05, 1.05, 3.6), (0.9, 2.1, T), 180),
    # 창문: w1(x=5.2)의 z 0.8~2.6 (폭 1.8, 높이 1.2, 바닥에서 0.9)
    BoxSpec("Architecture/Windows/Window0", (5.2, 0.9 + 0.6, 1.7), (1.8, 1.2, T), 90),
    # 기존 하부장: w0 앞 x 0~1.2
    BoxSpec("Object/Storage/Storage0", (0.6, 0.45, 0.3), (1.2, 0.9, 0.6), 0),
    # 소파: 거실 중앙
    BoxSpec("Object/Sofa/Sofa0", (3.4, 0.4, 2.9), (2.0, 0.8, 0.9), 0),
    BoxSpec("Object/Table/Table0", (3.4, 0.22, 2.0), (1.0, 0.45, 0.5), 0),
]

# 거실과 주방이 이어진 집(가상): 7.8m × 4.6m. 주방 벽 z=0, 큰 창 x=7.8, 현관 쪽 문 z=4.6
# 실제 집처럼: 주방 벽에 하부장 한 줄, 그 앞에 식탁, 소파는 벽에 붙여 맞은편 거실장을 본다.
APT_LIVING_KITCHEN = [
    BoxSpec("Architecture/Walls/Wall0", (3.9, H / 2, 0.0), (7.8, H, T), 0),
    BoxSpec("Architecture/Walls/Wall1", (7.8, H / 2, 2.3), (4.6, H, T), 90),
    BoxSpec("Architecture/Walls/Wall2", (3.9, H / 2, 4.6), (7.8, H, T), 180),
    BoxSpec("Architecture/Walls/Wall3", (0.0, H / 2, 2.3), (4.6, H, T), 270),
    BoxSpec("Architecture/Doors/Door0", (1.2, 1.05, 4.6), (0.9, 2.1, T), 180),
    BoxSpec("Architecture/Windows/Window0", (7.8, 1.2, 2.3), (2.8, 2.0, T), 90),
    BoxSpec("Architecture/Windows/Window1", (1.5, 1.45, 0.0), (1.0, 0.7, T), 0),
    # 주방 하부장: 폭 0.6 m 네 칸 (x 0.1~2.5)
    *[BoxSpec(f"Object/Storage/Storage{i}", (0.4 + 0.6 * i, 0.45, 0.32), (0.6, 0.9, 0.6), 0) for i in range(4)],
    # 식탁과 의자 넷 (의자는 식탁을 본다)
    BoxSpec("Object/Table/Table0", (2.3, 0.37, 2.5), (1.4, 0.74, 0.8), 0),
    BoxSpec("Object/Chair/Chair0", (1.95, 0.42, 1.88), (0.45, 0.84, 0.48), 0),
    BoxSpec("Object/Chair/Chair1", (2.65, 0.42, 1.88), (0.45, 0.84, 0.48), 0),
    BoxSpec("Object/Chair/Chair2", (1.95, 0.42, 3.12), (0.45, 0.84, 0.48), 180),
    BoxSpec("Object/Chair/Chair3", (2.65, 0.42, 3.12), (0.45, 0.84, 0.48), 180),
    # 거실: 벽에 붙인 소파, 앞에 낮은 탁자, 맞은편 벽에 거실장
    BoxSpec("Object/Sofa/Sofa0", (5.7, 0.4, 4.1), (2.2, 0.8, 0.9), 180),
    BoxSpec("Object/Table/Table1", (5.7, 0.2, 2.95), (1.1, 0.4, 0.6), 0),
    BoxSpec("Object/Tvstand/Tvstand0", (5.7, 0.225, 0.27), (1.8, 0.45, 0.42), 0),
    BoxSpec("Object/Plant/Plant0", (7.35, 0.6, 0.45), (0.5, 1.2, 0.5), 0),
    BoxSpec("Object/Lamp/Lamp0", (7.2, 0.8, 4.2), (0.4, 1.6, 0.4), 0),
]

# 주방 겸 거실 원룸(가상): 5.2m × 3.6m. 주방 벽 z=0, 창 x=5.2, 문 z=3.6
STUDIO_LIVING = [
    *DEMO_ROOM[:6],
    *[BoxSpec(f"Object/Storage/Storage{i}", (0.4 + 0.6 * i, 0.45, 0.32), (0.6, 0.9, 0.6), 0) for i in range(3)],
    # 벽에 붙인 2인 식탁
    BoxSpec("Object/Table/Table0", (0.45, 0.37, 1.65), (0.7, 0.74, 0.7), 0),
    BoxSpec("Object/Chair/Chair0", (1.03, 0.42, 1.65), (0.45, 0.84, 0.48), 270),
    BoxSpec("Object/Chair/Chair1", (0.45, 0.42, 2.25), (0.45, 0.84, 0.48), 180),
    # 소파는 벽에 붙여 맞은편 거실장을 본다
    BoxSpec("Object/Sofa/Sofa0", (3.7, 0.4, 3.1), (2.0, 0.8, 0.9), 180),
    BoxSpec("Object/Table/Table1", (3.7, 0.2, 2.0), (1.0, 0.4, 0.55), 0),
    BoxSpec("Object/Tvstand/Tvstand0", (3.7, 0.225, 0.27), (1.6, 0.45, 0.42), 0),
    BoxSpec("Object/Plant/Plant0", (4.85, 0.6, 0.4), (0.45, 1.2, 0.45), 0),
]
ROOMS = {"synthetic_room": DEMO_ROOM, "apt_living_kitchen": APT_LIVING_KITCHEN, "studio_living": STUDIO_LIVING}


def _rot_y(p, deg):
    r = math.radians(deg)
    x, y, z = p
    return (x * math.cos(r) + z * math.sin(r), y, -x * math.sin(r) + z * math.cos(r))


def build_stage(path: str | os.PathLike, boxes=DEMO_ROOM, room_yaw_deg: float = 0.0,
                offset=(0.0, 0.0, 0.0), meters_per_unit: float = 1.0, geom: str = "cube") -> Usd.Stage:
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, meters_per_unit)
    root = UsdGeom.Xform.Define(stage, "/Room")
    stage.SetDefaultPrim(root.GetPrim())
    s = 1.0 / meters_per_unit
    for b in boxes:
        full = Sdf.Path("/Room").AppendPath(b.path)
        # 그룹 Xform 생성
        for anc in reversed(list(full.GetParentPath().GetPrefixes())):
            if not stage.GetPrimAtPath(anc):
                UsdGeom.Xform.Define(stage, anc)
        xf = UsdGeom.Xform.Define(stage, full)
        c = _rot_y(b.center, room_yaw_deg)
        c = (c[0] + offset[0], c[1] + offset[1], c[2] + offset[2])
        xf.AddTranslateOp().Set(Gf.Vec3d(*(v * s for v in c)))
        xf.AddRotateYOp().Set(b.yaw_deg + room_yaw_deg)
        xf.AddScaleOp().Set(Gf.Vec3f(*(v * s for v in b.size)))
        child = full.AppendChild(full.name + "_geom")
        if geom == "mesh":  # RoomPlan 실제 내보내기처럼 메시로 표현
            mesh = UsdGeom.Mesh.Define(stage, child)
            pts = [Gf.Vec3f(x, y, z) for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)]
            mesh.GetPointsAttr().Set(pts)
            mesh.GetFaceVertexCountsAttr().Set([4] * 6)
            mesh.GetFaceVertexIndicesAttr().Set([0, 1, 3, 2, 4, 6, 7, 5, 0, 4, 5, 1, 2, 3, 7, 6, 0, 2, 6, 4, 1, 5, 7, 3])
        else:
            UsdGeom.Cube.Define(stage, child).GetSizeAttr().Set(1.0)
    stage.GetRootLayer().Save()
    return stage


def build_usdz(usdz_path: str | os.PathLike, **kw) -> Path:
    usdz_path = Path(usdz_path)
    with tempfile.TemporaryDirectory() as td:
        usdc = Path(td) / "room.usdc"
        build_stage(usdc, **kw)
        ok = UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(usdc)), str(usdz_path))
        if not ok:
            raise RuntimeError("usdz 패키징 실패")
    return usdz_path


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "data/samples/synthetic_room.usdz"
    print(build_usdz(out, boxes=ROOMS.get(Path(out).stem, DEMO_ROOM)))
