"""Blender 헤드리스 스크립트 — `blender -b -P build_scene.py -- --job job.json`

job.json: {"usdz": ..., "room": room.json, "state": scene_state.json(선택),
           "out_glb": ..., "out_png": ..., "out_blend": ...}
1) USDZ 가져오기(원본 메시 유지)  2) 상태의 재질·색 적용(이름 규칙: Wall*, Floor*, Door*, Window*, Storage*)
3) 배치 제품을 치수 박스로 추가  4) 카메라·조명 → EEVEE 렌더 PNG  5) glb·blend 저장
⚠️ 이 클라우드 개발 환경에는 Blender가 없어 실행 검증 전이다. 팀 PC에서 docs/specs/manual-qa.md 순서로 확인.
"""
import json
import math
import sys

import bpy  # noqa: E402  (Blender 내부에서만 사용 가능)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return json.load(open(argv[argv.index("--job") + 1]))


def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def make_mat(name, hex_, rough=0.7):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    h = hex_.lstrip("#")
    rgb = [srgb_to_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = rough
    return m


def assign(obj, mat):
    if obj.type == "MESH":
        obj.data.materials.clear()
        obj.data.materials.append(mat)


def main():
    job = args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.usd_import(filepath=job["usdz"])
    state = json.load(open(job["state"])) if job.get("state") else {}
    mats = state.get("materials") or {}
    rough = {"matte": 0.85, "glossy": 0.2}.get(state.get("finish"), 0.7)
    rules = {"wall": "Wall", "floor": "Floor", "door": "Door", "window": "Window", "object": "Storage"}
    for key, prefix in rules.items():
        if key not in mats:
            continue
        mat = make_mat(f"lgb_{key}", mats[key], rough)
        for o in bpy.data.objects:
            if any(p.name.lower().startswith(prefix.lower()) for p in [o] + list(_parents(o))):
                assign(o, mat)

    # USD(Y-up) → Blender(Z-up): 평면 (x, z_usd) = Blender (x, -y)
    for pl in state.get("placements") or []:
        w, h, d = pl["size_m"]
        x, z = pl["center_xz"]
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, -z, h / 2))
        ob = bpy.context.active_object
        ob.name = f"product_{pl['sku']}"
        ob.scale = (w, d, h)
        ob.rotation_euler = (0, 0, pl["yaw_rad"] - math.pi / 2)
        assign(ob, make_mat(f"lgb_p_{pl['sku']}", pl.get("hex") or "#F4F4F2", 0.4))

    # 카메라·조명
    from mathutils import Vector
    pts = [o.matrix_world @ Vector(c) for o in bpy.data.objects if o.type == "MESH" for c in o.bound_box]
    center = sum(pts, Vector()) / len(pts) if pts else Vector()
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.location = center + Vector((-4, -5, 4.5))
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3
    bpy.context.scene.collection.objects.link(sun)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    if job.get("out_png"):
        sc.render.filepath = job["out_png"]
        bpy.ops.render.render(write_still=True)
    if job.get("out_glb"):
        bpy.ops.export_scene.gltf(filepath=job["out_glb"], export_format="GLB")
    if job.get("out_blend"):
        bpy.ops.wm.save_as_mainfile(filepath=job["out_blend"])


def _parents(o):
    while o.parent:
        o = o.parent
        yield o


main()
