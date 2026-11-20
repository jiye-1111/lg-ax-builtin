"""공간 꾸미기 라이브러리 타일 그림: models/furniture/*.glb를 Cycles로 비스듬히 찍는다.

    python render_decor_thumbs.py --models apps/web/models/furniture --out apps/web/img/decor
    (pip bpy 또는 blender -b -P render_decor_thumbs.py -- ...)

배경은 투명. 벽 제거 타일(wall-remove)은 가벽 모델을 붉은 반투명으로 찍는다.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

SIZE = 256


def setup_scene() -> bpy.types.Scene:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.cycles.device = "CPU"
    sc.render.resolution_x = sc.render.resolution_y = SIZE
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "WEBP"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.quality = 88
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.96, 0.95, 0.93, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    sc.world = w
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.2
    sun.data.angle = math.radians(12)
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    sc.collection.objects.link(sun)
    return sc


def frame(sc: bpy.types.Scene, objs: list) -> None:
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    for o in objs:
        for c in o.bound_box:
            v = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, v))
            hi = Vector(map(max, hi, v))
    center, rad = (lo + hi) / 2, max((hi - lo).length / 2, 0.05)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.lens = 50
    d = Vector((0.9, -1.25, 0.85)).normalized()
    cam.location = center + d * rad * 3.4
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(cam)
    sc.camera = cam


def shoot(glb: Path, out: Path, tint=None) -> None:
    sc = setup_scene()
    bpy.ops.import_scene.gltf(filepath=str(glb))
    objs = [o for o in sc.objects if o.type == "MESH"]
    if tint:
        for o in objs:
            for m in o.data.materials:
                b = m.node_tree.nodes.get("Principled BSDF")
                if b:
                    b.inputs["Base Color"].default_value = tint
                    b.inputs["Alpha"].default_value = 0.55
    frame(sc, objs)
    sc.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    models, out = Path(a.models), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    idx = json.loads((models / "index.json").read_text(encoding="utf-8"))["models"]
    for key, e in idx.items():
        if a.only and key not in a.only:
            continue
        shoot(models / e["file"], out / f"{key}.webp")
    if not a.only or "wall-remove" in a.only:
        shoot(models / idx["wall"]["file"], out / "wall-remove.webp", tint=(0.75, 0.05, 0.12, 1))


if __name__ == "__main__":
    main()
