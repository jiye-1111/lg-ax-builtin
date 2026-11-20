"""스캔 가구(RoomPlan 종류별) 3D 모델을 Blender로 만든다.

    blender -b -P build_furniture.py -- --out apps/web/models/furniture
    python build_furniture.py --out ...      (pip bpy 모듈로 실행할 때)

- 종류마다 기준 크기(ref_m)로 한 벌씩 만든다. 바닥 가운데가 원점, 정면 = glTF +Z.
- 부품은 따로 둔다. 웹이 스캔 크기에 맞춰 부품별로 늘리기 때문이다 (다리 굵기·상판 두께는 그대로).
- 부품 extras.rig: glTF 축(x 폭, y 높이, z 깊이)마다 한 글자
    s = 크기와 위치를 같이 늘림, p = 위치만 늘림, e = 크기 그대로 + 가까운 모서리와 거리 유지
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy  # noqa: I001  (pip bpy는 bpy를 먼저 불러야 bmesh가 생긴다)
import bmesh


def lin(hex_: str) -> tuple[float, float, float, float]:
    h = hex_.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return (*[v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c], 1.0)


MATS: dict[str, bpy.types.Material] = {}
LOOK = {  # 이름: (색, 거칠기, 금속성)
    "oak": ("#A27A52", 0.55, 0.0),
    "walnut": ("#7A5638", 0.5, 0.0),
    "fabric": ("#8E918C", 0.92, 0.0),
    "fabric_dark": ("#5E625F", 0.92, 0.0),
    "cushion": ("#B2ADA4", 0.9, 0.0),
    "linen": ("#F2EFE9", 0.85, 0.0),
    "duvet": ("#D9D3C8", 0.88, 0.0),
    "white": ("#E8E5DF", 0.45, 0.0),
    "metal": ("#2F3134", 0.35, 0.8),
    "plinth": ("#3A3B3D", 0.6, 0.0),
    "ash": ("#C9B497", 0.6, 0.0),
    "stone": ("#E4E1DA", 0.3, 0.0),
    "wool": ("#B9AE9C", 0.97, 0.0),
    "brass": ("#B08D57", 0.3, 0.9),
    "shade": ("#F3EDE2", 0.8, 0.0),
    "pot": ("#D8D2C7", 0.7, 0.0),
    "soil": ("#3B2E25", 0.95, 0.0),
    "leaf": ("#4E6B3A", 0.6, 0.0),
    "plaster": ("#EDEAE4", 0.9, 0.0),
}


def mat(name: str) -> bpy.types.Material:
    if name not in MATS:
        hex_, rough, metal = LOOK[name]
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = lin(hex_)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        MATS[name] = m
    return MATS[name]


def part(name: str, m: str, x0: float, x1: float, z0: float, z1: float, y0: float, y1: float,
         rig: str, bevel: float = 0.004) -> None:
    """glTF 기준으로 적는다: x 폭, y 높이(바닥 0), z 깊이(정면 +). Blender에서는 (x, -z, y)."""
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    sx, sy, sz = x1 - x0, y1 - y0, z1 - z0
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:  # Blender 좌표: x = 폭, y = -깊이, z = 높이
        v.co.x, v.co.y, v.co.z = v.co.x * sx, v.co.y * sz, v.co.z * sy
    b = min(bevel, sx / 2.5, sy / 2.5, sz / 2.5)
    if b > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=b, segments=3, profile=0.5, affect="EDGES")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat(m))
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    ob.location = (cx, -cz, cy)
    ob["rig"] = rig
    bpy.context.scene.collection.objects.link(ob)


def cyl(name: str, m: str, cx: float, cz: float, r: float, y0: float, y1: float, rig: str,
        seg: int = 32, r_top: float | None = None) -> None:
    """원기둥(또는 원뿔대). 조명 기둥·화분·잎 덩어리용. glTF 기준 (cx, cz) 가운데."""
    bm = bmesh.new()
    rt = r if r_top is None else r_top
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=rt, depth=y1 - y0)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat(m))
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    ob.location = (cx, -cz, (y0 + y1) / 2)
    ob["rig"] = rig
    bpy.context.scene.collection.objects.link(ob)


def ball(name: str, m: str, cx: float, cy: float, cz: float, r: float, rig: str) -> None:
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=r)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat(m))
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    ob.location = (cx, -cz, cy)
    ob["rig"] = rig
    bpy.context.scene.collection.objects.link(ob)


# ---------- 종류별 모양 ----------
def chair(w, h, d):
    seat = 0.45
    for i, (sx, sz) in enumerate([(-1, 1), (1, 1), (-1, -1), (1, -1)]):
        x = sx * (w / 2 - 0.04)
        z = sz * (d / 2 - 0.04)
        part(f"leg{i}", "metal", x - 0.016, x + 0.016, z - 0.016, z + 0.016, 0, seat - 0.02, "ese", 0.006)
    part("seat", "fabric_dark", -w / 2, w / 2, -d / 2, d / 2, seat - 0.02, seat + 0.035, "sps", 0.018)
    part("back", "oak", -w / 2 + 0.02, w / 2 - 0.02, -d / 2 + 0.01, -d / 2 + 0.035, seat + 0.12, h, "sse", 0.01)
    for i, sx in enumerate((-1, 1)):
        x = sx * (w / 2 - 0.04)
        part(f"post{i}", "metal", x - 0.012, x + 0.012, -d / 2 + 0.025, -d / 2 + 0.05, seat, h - 0.04, "ese", 0.006)


def table(w, h, d):
    top = 0.03
    part("top", "oak", -w / 2, w / 2, -d / 2, d / 2, h - top, h, "ses", 0.006)
    for i, (sx, sz) in enumerate([(-1, 1), (1, 1), (-1, -1), (1, -1)]):
        x, z = sx * (w / 2 - 0.07), sz * (d / 2 - 0.07)
        part(f"leg{i}", "metal", x - 0.022, x + 0.022, z - 0.022, z + 0.022, 0, h - top, "ese", 0.008)
    for i, sz in enumerate((-1, 1)):
        z = sz * (d / 2 - 0.07)
        part(f"apron{i}", "metal", -w / 2 + 0.07, w / 2 - 0.07, z - 0.01, z + 0.01, h - top - 0.07, h - top, "see", 0.003)


def storage(w, h, d):
    base, hd = 0.08, 0.018  # 걸레받이 높이, 손잡이가 앞으로 나온 길이 (깊이 d 안에)
    part("plinth", "plinth", -w / 2 + 0.02, w / 2 - 0.02, -d / 2 + hd + 0.03, d / 2, 0, base, "ses", 0.003)
    part("body", "white", -w / 2, w / 2, -d / 2 + hd + 0.02, d / 2, base, h, "sss", 0.004)
    gap = 0.003
    for i in range(2):
        x0, x1 = -w / 2 + i * w / 2 + gap, -w / 2 + (i + 1) * w / 2 - gap
        part(f"door{i}", "white", x0, x1, -d / 2 + hd, -d / 2 + hd + 0.02, base + gap, h - gap, "sse", 0.004)
        hx = x1 - 0.04 if i == 0 else x0 + 0.04
        part(f"handle{i}", "metal", hx - 0.006, hx + 0.006, -d / 2, -d / 2 + hd, h * 0.45, h * 0.45 + 0.22, "ppe", 0.005)


def sofa(w, h, d):
    arm, seat = 0.16, 0.42
    for i, (sx, sz) in enumerate([(-1, 1), (1, 1), (-1, -1), (1, -1)]):
        x, z = sx * (w / 2 - 0.06), sz * (d / 2 - 0.06)
        part(f"foot{i}", "walnut", x - 0.02, x + 0.02, z - 0.02, z + 0.02, 0, 0.08, "eee", 0.006)
    part("base", "fabric", -w / 2 + arm, w / 2 - arm, -d / 2 + 0.02, d / 2, 0.08, seat - 0.1, "sss", 0.02)
    for i, sx in enumerate((-1, 1)):
        x0 = -w / 2 if sx < 0 else w / 2 - arm
        part(f"arm{i}", "fabric", x0, x0 + arm, -d / 2, d / 2, 0.08, 0.62, "ess", 0.04)
    part("back", "fabric", -w / 2 + arm, w / 2 - arm, -d / 2, -d / 2 + 0.2, 0.08, h, "sse", 0.04)
    inner = w - 2 * arm
    for i in range(2):
        x0 = -w / 2 + arm + i * inner / 2 + 0.005
        part(f"cushion{i}", "cushion", x0, x0 + inner / 2 - 0.01, -d / 2 + 0.2, d / 2 - 0.01, seat - 0.1, seat, "sps", 0.05)
        part(f"pillow{i}", "cushion", x0 + 0.02, x0 + inner / 2 - 0.03, -d / 2 + 0.2, -d / 2 + 0.34, seat, h - 0.06, "sse", 0.06)


def bed(w, h, d):
    for i, (sx, sz) in enumerate([(-1, 1), (1, 1), (-1, -1), (1, -1)]):
        x, z = sx * (w / 2 - 0.08), sz * (d / 2 - 0.08)
        part(f"leg{i}", "walnut", x - 0.025, x + 0.025, z - 0.025, z + 0.025, 0, 0.1, "eee", 0.006)
    part("frame", "walnut", -w / 2, w / 2, -d / 2 + 0.06, d / 2, 0.1, 0.3, "sps", 0.01)
    part("headboard", "walnut", -w / 2, w / 2, -d / 2, -d / 2 + 0.06, 0.1, h, "sse", 0.012)
    part("mattress", "linen", -w / 2 + 0.03, w / 2 - 0.03, -d / 2 + 0.08, d / 2 - 0.03, 0.3, 0.52, "sps", 0.04)
    part("duvet", "duvet", -w / 2 + 0.02, w / 2 - 0.02, -d / 2 + 0.6, d / 2 - 0.02, 0.45, 0.545, "sps", 0.03)
    for i, sx in enumerate((-1, 1)):
        x = sx * w / 4
        part(f"pillow{i}", "linen", x - w / 5, x + w / 5, -d / 2 + 0.12, -d / 2 + 0.48, 0.52, 0.62, "ppe", 0.05)


def desk(w, h, d):
    top = 0.025
    part("top", "ash", -w / 2, w / 2, -d / 2, d / 2, h - top, h, "ses", 0.004)
    for i, sx in enumerate((-1, 1)):
        x = sx * (w / 2 - 0.05)
        part(f"side{i}", "metal", x - 0.015, x + 0.015, -d / 2 + 0.04, d / 2 - 0.04, 0, h - top, "ess", 0.004)
    part("drawer", "white", w / 2 - 0.5, w / 2 - 0.08, -d / 2 + 0.05, d / 2 - 0.02, h - top - 0.14, h - top - 0.01, "pss", 0.004)


def shelf(w, h, d):
    side = 0.02
    for i, sx in enumerate((-1, 1)):
        x0 = -w / 2 if sx < 0 else w / 2 - side
        part(f"side{i}", "oak", x0, x0 + side, -d / 2, d / 2, 0, h, "ess", 0.003)
    part("back", "oak", -w / 2 + side, w / 2 - side, -d / 2, -d / 2 + 0.01, 0, h, "sse", 0.002)
    n = 5
    for i in range(n):
        y = 0.04 + i * (h - 0.06) / (n - 1)
        part(f"board{i}", "oak", -w / 2 + side, w / 2 - side, -d / 2 + 0.01, d / 2, y - 0.009, y + 0.009, "sps", 0.002)


def tvstand(w, h, d):
    for i, (sx, sz) in enumerate([(-1, 1), (1, 1), (-1, -1), (1, -1)]):
        x, z = sx * (w / 2 - 0.06), sz * (d / 2 - 0.05)
        part(f"leg{i}", "metal", x - 0.012, x + 0.012, z - 0.012, z + 0.012, 0, 0.12, "eee", 0.004)
    part("body", "walnut", -w / 2, w / 2, -d / 2, d / 2, 0.12, h, "sps", 0.006)
    gap = 0.004
    for i in range(3):
        x0 = -w / 2 + i * w / 3 + gap
        part(f"door{i}", "oak", x0, x0 + w / 3 - 2 * gap, d / 2 - 0.002, d / 2 + 0.006, 0.14, h - 0.02, "sse", 0.003)


def island(w, h, d):
    part("plinth", "plinth", -w / 2 + 0.05, w / 2 - 0.05, -d / 2 + 0.05, d / 2 - 0.05, 0, 0.1, "ses", 0.003)
    part("body", "white", -w / 2 + 0.02, w / 2 - 0.02, -d / 2 + 0.02, d / 2 - 0.02, 0.1, h - 0.03, "sss", 0.004)
    part("top", "stone", -w / 2, w / 2, -d / 2, d / 2, h - 0.03, h, "ses", 0.006)


def rug(w, h, d):
    part("rug", "wool", -w / 2, w / 2, -d / 2, d / 2, 0, h, "sss", 0.004)


def lamp(w, h, d):
    r = min(w, d) / 2
    cyl("base", "metal", 0, 0, r * 0.7, 0, 0.025, "eee")
    cyl("pole", "brass", 0, 0, 0.012, 0.025, h - 0.3, "ese", 16)
    cyl("shade", "shade", 0, 0, r * 0.75, h - 0.32, h, "ese", 40, r)


def plant(w, h, d):
    r = min(w, d) / 2
    cyl("pot", "pot", 0, 0, r * 0.62, 0, h * 0.3, "eee", 32, r * 0.7)
    cyl("soil", "soil", 0, 0, r * 0.64, h * 0.3 - 0.02, h * 0.3, "eee")
    cyl("stem", "walnut", 0, 0, 0.012, h * 0.3, h * 0.7, "ese", 12)
    for i, (dx, dy, dz, rr) in enumerate([(0, 0.78, 0, 0.55), (-0.35, 0.68, 0.2, 0.42), (0.38, 0.72, -0.15, 0.45),
                                          (0.1, 0.92, 0.25, 0.4), (-0.15, 0.88, -0.3, 0.38)]):
        ball(f"leaf{i}", "leaf", dx * r, dy * h, dz * r, rr * r, "eee")


def coffee(w, h, d):
    part("top", "oak", -w / 2, w / 2, -d / 2, d / 2, h - 0.03, h, "ses", 0.01)
    part("shelf", "oak", -w / 2 + 0.06, w / 2 - 0.06, -d / 2 + 0.06, d / 2 - 0.06, 0.08, 0.1, "sps", 0.004)
    for i, (sx, sz) in enumerate([(-1, 1), (1, 1), (-1, -1), (1, -1)]):
        x, z = sx * (w / 2 - 0.05), sz * (d / 2 - 0.05)
        part(f"leg{i}", "oak", x - 0.02, x + 0.02, z - 0.02, z + 0.02, 0, h - 0.03, "ese", 0.004)


def partition(w, h, d):
    """세로 살 파티션: 위아래 틀 + 살. 폭을 늘리면 살 간격이 같이 늘어난다."""
    part("bottom", "oak", -w / 2, w / 2, -d / 2, d / 2, 0, 0.04, "ses", 0.003)
    part("top", "oak", -w / 2, w / 2, -d / 2, d / 2, h - 0.04, h, "sps", 0.003)
    n = 12
    for i in range(n):
        x = -w / 2 + 0.025 + i * (w - 0.05) / (n - 1)
        part(f"slat{i}", "oak", x - 0.018, x + 0.018, -d / 2 + 0.005, d / 2 - 0.005, 0.04, h - 0.04, "psp", 0.003)


def wall(w, h, d):
    part("wall", "plaster", -w / 2, w / 2, -d / 2, d / 2, 0, h, "sss", 0.004)
    part("skirt", "white", -w / 2 - 0.004, w / 2 + 0.004, -d / 2 - 0.004, d / 2 + 0.004, 0, 0.08, "ses", 0.002)


TEMPLATES = {  # 기준 크기 (m): 스캔에서 자주 나오는 크기 근처
    "chair": ((0.5, 0.85, 0.52), chair),
    "table": ((1.6, 0.74, 0.8), table),
    "storage": ((1.0, 1.9, 0.45), storage),
    "sofa": ((2.0, 0.85, 0.9), sofa),
    "bed": ((1.6, 0.95, 2.1), bed),
    # 공간 꾸미기 라이브러리용 (제품 정보 없는 일반 모양)
    "desk": ((1.2, 0.73, 0.6), desk),
    "shelf": ((0.8, 1.8, 0.3), shelf),
    "tvstand": ((1.6, 0.45, 0.4), tvstand),
    "island": ((1.8, 0.9, 0.9), island),
    "rug": ((2.0, 0.012, 1.4), rug),
    "lamp": ((0.4, 1.6, 0.4), lamp),
    "plant": ((0.5, 1.2, 0.5), plant),
    "coffee": ((1.0, 0.4, 0.6), coffee),
    "partition": ((1.2, 2.1, 0.05), partition),
    "wall": ((2.0, 2.4, 0.1), wall),
}


def build(cat: str, out: Path) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    MATS.clear()
    (w, h, d), fn = TEMPLATES[cat]
    fn(w, h, d)
    path = out / f"{cat}.glb"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_yup=True, export_apply=True,
                              export_extras=True, export_materials="EXPORT", export_cameras=False, export_lights=False)
    return {"file": path.name, "ref_m": {"w": w, "h": h, "d": d}}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    index = {"_note": "build_furniture.py로 생성. 웹이 스캔 크기에 맞춰 부품별로 늘린다 (rig: s/p/e).",
             "models": {cat: build(cat, out) for cat in TEMPLATES}}
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(index["models"]))


if __name__ == "__main__":
    main()
