"""와이파이 시뮬레이션용 공유기 모델 (apps/web/models/devices/router.glb).

치수는 TP-Link Archer AX55 데이터시트 값: 261.1 × 134.5 × 41.0 mm, 고정 안테나 4개.
  https://www.tp-link.com/en/home-networking/wifi-router/archer-ax55/
  https://static.tp-link.com/upload/product-overview/2021/202112/20211209/Archer%20AX55(EU&US)1.0_Datasheet.pdf
안테나 길이·모양은 공개 값이 없어 제품 사진 비율로 잡은 화면용 표현이다. 로고·상표는 넣지 않는다.

실행: python build_router.py --out apps/web/models/devices/router.glb  (pip bpy 또는 blender -b -P ... --)
원점 = 바닥 가운데, 정면(LED 쪽) +Z(glTF), 단위 m.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy

W, D, H = 0.2611, 0.1345, 0.0410
ANT_L, ANT_W, ANT_T = 0.165, 0.018, 0.009   # 안테나 (화면용)


def mat(name, rgb, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def rbox(name, size, loc, bevel, m, segments=4):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(scale=True)
    bv = ob.modifiers.new("bevel", "BEVEL")
    bv.width = bevel
    bv.segments = segments
    bv.limit_method = "ANGLE"
    ob.data.materials.append(m)
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.shade_auto_smooth() if hasattr(ob.data, "shade_auto_smooth") else None
    return ob


def main(out: Path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    body_m = mat("body", (0.012, 0.012, 0.013), 0.42)
    top_m = mat("top", (0.02, 0.02, 0.022), 0.22)
    led_m = mat("led", (0.9, 0.95, 1.0), 0.3)
    led_m.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.55, 0.85, 1.0, 1)
    led_m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 3.0
    foot_m = mat("rubber", (0.03, 0.03, 0.03), 0.9)
    port_m = mat("port", (0.005, 0.005, 0.005), 0.6)

    parts = []
    # 본체: 아래 받침(조금 작게) + 윗판
    parts.append(rbox("base", (W - 0.006, D - 0.006, 0.010), (0, 0, 0.007), 0.004, body_m))
    parts.append(rbox("shell", (W, D, H - 0.010), (0, 0, 0.010 + (H - 0.010) / 2), 0.010, body_m, 6))
    # 윗면 무늬 판 (얇게 올라온 광택면)
    parts.append(rbox("top", (W - 0.03, D - 0.03, 0.0016), (0, 0.004, H - 0.0002), 0.0008, top_m))
    # 앞쪽 LED 줄 (정면 -Y)
    for i in range(6):
        x = -0.045 + i * 0.018
        parts.append(rbox(f"led{i}", (0.006, 0.0012, 0.0025), (x, -D / 2 - 0.0004, 0.022), 0.0004, led_m, 2))
    # 뒤쪽 포트 자리 (WAN 1 + LAN 4 + USB)
    for i in range(5):
        parts.append(rbox(f"port{i}", (0.0145, 0.002, 0.012), (-0.06 + i * 0.022, D / 2 + 0.0002, 0.020), 0.0008, port_m, 2))
    parts.append(rbox("usb", (0.0125, 0.002, 0.0055), (0.07, D / 2 + 0.0002, 0.020), 0.0006, port_m, 2))
    # 고무발
    for sx in (-1, 1):
        for sy in (-1, 1):
            bpy.ops.mesh.primitive_cylinder_add(radius=0.008, depth=0.003, location=(sx * (W / 2 - 0.03), sy * (D / 2 - 0.025), 0.0015))
            o = bpy.context.object
            o.data.materials.append(foot_m)
            parts.append(o)
    # 안테나 4개: 뒤쪽 모서리를 따라 세운다 (경첩 + 납작한 막대)
    xs = (-W / 2 + 0.03, -0.045, 0.045, W / 2 - 0.03)
    for i, x in enumerate(xs):
        y = D / 2 - 0.008
        bpy.ops.mesh.primitive_cylinder_add(radius=0.0075, depth=0.022, location=(x, y + 0.004, H - 0.002), rotation=(0, math.pi / 2, 0))
        hinge = bpy.context.object
        hinge.data.materials.append(body_m)
        for p in hinge.data.polygons:
            p.use_smooth = True
        parts.append(hinge)
        tilt = math.radians((-6, -2, 2, 6)[i])
        a = rbox(f"ant{i}", (ANT_W, ANT_T, ANT_L), (0, 0, ANT_L / 2), ANT_T / 2 - 0.0005, body_m, 5)
        # 끝으로 갈수록 살짝 가늘게
        for v in a.data.vertices:
            k = 1 - 0.25 * max(0.0, v.co.z / ANT_L)
            v.co.x *= k
        a.rotation_euler = (0, tilt, 0)
        a.location = (x, y + 0.006, H + 0.004)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        parts.append(a)

    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.join()
    parts[0].name = "router"
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(out), export_format="GLB", use_selection=True, export_yup=True, export_apply=True)
    print("saved", out, out.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    main(ap.parse_args(argv).out)
