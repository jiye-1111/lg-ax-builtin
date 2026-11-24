"""제품 고르기 카드에 쓰는 제품 사진을 우리 3D 모델(glb)에서 Blender Cycles로 렌더한다.

    blender -b -P render_thumbs.py -- --models apps/web/models/products --out apps/web/img/products [--sku X ...]

- LG 공식 사진은 쓰지 않는다. 사진 = build_products.py가 도면대로 만든 모델 그 자체.
- 투명 배경 + 바닥 그림자만 남겨(쉐도우 캐처) 카드 바탕색 위에 자연스럽게 얹힌다.
- 정면에서 왼쪽 위로 살짝 돌아본 구도, 스튜디오 조명(큰 소프트박스 + 반사광).
- 결과: <sku>.webp (정사각형)
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

SIZE = 360
SAMPLES = 48


def setup_scene() -> bpy.types.Scene:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    sc.cycles.device = "CPU"
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = SIZE
    sc.render.image_settings.file_format = "WEBP"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.quality = 88
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = -0.45  # 밝은 베이지·화이트가 하얗게 날아가지 않게
    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.94, 0.93, 0.91, 1)  # Warm Grey 스튜디오 반사
    bg.inputs["Strength"].default_value = 0.55
    return sc


def light(name: str, loc, size: float, power: float, glossy: bool = True) -> None:
    """사각 소프트박스. glossy=False면 유리·화면에 비치지 않는다 (동그란 반사 자국 방지)."""
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = size, size * 1.6
    ld.energy = power
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector((0, 0, 0.4)) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    ob.visible_glossy = glossy


def lin(hex_: str) -> tuple[float, float, float, float]:
    h = hex_.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return (*[v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c], 1.0)


def tint(hex_: str) -> None:
    """겉면(finish) 재질을 그 제품 색으로 칠한다. 색 다른 모델이 파일 하나를 같이 쓰기 때문."""
    for m in bpy.data.materials:
        if not m.name.startswith("finish") or not m.node_tree:
            continue
        for n in m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED" and not n.inputs["Base Color"].is_linked:
                n.inputs["Base Color"].default_value = lin(hex_)
            elif n.type == "MIX" and n.blend_type == "MULTIPLY":      # 무늬 × 색
                for i in n.inputs:
                    if i.type == "RGBA" and not i.is_linked:
                        i.default_value = lin(hex_)


def render(glb: Path, out: Path, hex_: str | None = None) -> None:
    sc = setup_scene()
    bpy.ops.import_scene.gltf(filepath=str(glb))
    if hex_:
        tint(hex_)
    objs = [o for o in sc.objects if o.type == "MESH"]
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center, size = (lo + hi) / 2, hi - lo
    r = size.length / 2
    # 바닥 그림자 받이
    bpy.ops.mesh.primitive_plane_add(size=max(size.x, size.y, size.z) * 6, location=(center.x, center.y, lo.z))
    bpy.context.active_object.is_shadow_catcher = True
    # 조명: 왼쪽 앞 위 큰 소프트박스, 오른쪽 반사, 뒤 테두리광 (크기에 비례)
    s = max(r, 0.25)
    light("key", (center.x - 3.2 * s, center.y - 1.2 * s, lo.z + 3.4 * s), 2.5 * s, 260 * s * s)
    light("fill", (center.x + 2.6 * s, center.y - 1.6 * s, lo.z + 1.4 * s), 3.0 * s, 90 * s * s, glossy=False)
    light("rim", (center.x + 0.8 * s, center.y + 2.8 * s, lo.z + 2.6 * s), 1.5 * s, 120 * s * s, glossy=False)
    # 카메라: 정면(-Y)에서 왼쪽으로 28°, 위에서 12° 내려다봄. 경계구가 화면에 꼭 차게
    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 70
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    yaw, pitch = math.radians(-28), math.radians(12)
    fov = 2 * math.atan(cam_d.sensor_width / 2 / cam_d.lens)
    dist = r / math.sin(fov / 2) * 1.02
    dirv = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
    cam.location = center + dirv * dist
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sku", action="append")
    ap.add_argument("--catalog", help="있으면 모델명마다 index.json의 파일을 그 제품 색으로 칠해 렌더한다")
    ap.add_argument("--list", help="렌더할 모델명이 한 줄에 하나씩 적힌 파일 (--catalog와 같이)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.catalog:
        import json
        index = json.loads((Path(a.models) / "index.json").read_text(encoding="utf-8"))["models"]
        want = set(a.sku or []) | (set(Path(a.list).read_text().split()) if a.list else set())
        for p in json.loads(Path(a.catalog).read_text(encoding="utf-8"))["products"]:
            if want and p["sku"] not in want or p["sku"] not in index:
                continue
            opt = (p.get("cmf_options") or [{}])[0]
            render(Path(a.models) / index[p["sku"]]["file"], out / f"{p['sku']}.webp", opt.get("hex_approx"))
            print(p["sku"], flush=True)
        return
    for glb in sorted(Path(a.models).glob("*.glb")):
        if a.sku and glb.stem not in a.sku:
            continue
        render(glb, out / f"{glb.stem}.webp")
        print(glb.stem)


if __name__ == "__main__":
    main()
