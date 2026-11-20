"""Fusion에서 부품별로 내보낸 STL을 웹용 glb 하나로 묶는다.

    blender -b -P fusion_to_glb.py -- --sku G646GBB031 --catalog data/catalog/products.json \
        --src data/fusion/G646GBB031 --out apps/web/models/products

- Fusion 쪽: 정면 = -Y, Z-up, 바닥 가운데 원점 (build_products.py와 같은 좌표). 부품 하나 = 바디 하나 = STL 하나.
- 파일 이름 앞부분이 역할이다: body, door_*, top_*(상판, 색 바뀌는 겉판), handle_*, vent_*, trim_*, display,
  print_*(상판 인쇄), panel_*(drawing.json colors.panel 색), chrome_*, wood_*(나무).
- 같은 폴더의 drawing.json(레퍼런스 치수·색)에 colors.body.hex_approx가 있으면 본체 색으로 쓴다.
  geometry_from: "<다른 SKU>"가 있으면 그 SKU 폴더의 STL을 쓴다 (색·재질만 다른 모델).
  companion: {src, suffix, height_mm, offset_m}가 있으면 따로 놓이는 부품(정수기 파우셋 등)도 <SKU><suffix>.glb로
  만들고 apps/web/models/products/companions.json에 놓을 위치를 적는다. 색 옵션은 그 부품 finish에 들어간다. 역할별 재질은 build_products와 같다
  (문 앞판 재질 이름 "finish"는 웹에서 색을 바꿀 때 쓴다).
- 부품은 합치지 않고 따로 둔다. 웹에서 문만 골라 열거나 강조할 수 있게.
- STL 단위(mm/cm)는 카탈로그 높이와 비교해서 맞춘다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_products import material, palette  # noqa: E402  (같은 재질표를 쓴다)

ROLE_MAT = {"body": "body", "door": "finish", "top": "finish", "handle": "handle", "vent": "trim", "trim": "trim",
            "display": "display", "print": "print", "panel": "panel", "chrome": "chrome", "wood": "wood"}


def role_of(stem: str) -> str:
    role = stem.split("_")[0]
    if role not in ROLE_MAT:
        raise ValueError(f"모르는 부품 이름: {stem}")
    return role


def unit_scale(objs: list, height_mm: float) -> float:
    zs = [(o.matrix_world @ v.co).z for o in objs for v in o.data.vertices]
    raw = max(zs) - min(zs)
    for to_m in (0.001, 0.01, 1.0):  # mm, cm, m
        if abs(raw * to_m * 1000 - height_mm) <= 2.0:
            return to_m
    raise ValueError(f"STL 높이 {raw}가 카탈로그 높이 {height_mm}mm와 어떤 단위로도 안 맞는다")


def load_drawing(src: Path) -> dict:
    p = src / "drawing.json"  # 레퍼런스에서 확인한 치수·색
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def build(prod: dict, src: Path, out: Path, geo: Path | None = None, height_mm: float | None = None,
          name: str | None = None) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    opt = (prod.get("cmf_options") or [{}])[0]
    pal = palette(opt.get("hex_approx") or "#F2F2F0", opt.get("material"))
    drawing = load_drawing(src)
    body_hex = drawing.get("colors", {}).get("body", {}).get("hex_approx")
    if body_hex:
        pal["body"] = material("body", body_hex, 0.5, 0.3)
    panel_hex = drawing.get("colors", {}).get("panel", {}).get("hex_approx")  # 조작부처럼 색이 따로 있는 판
    pal["panel"] = material("panel", panel_hex, 0.35) if panel_hex else pal["trim"]
    pal["wood"] = material("wood", "#9A6A43", 0.55)  # 와인셀러 선반 앞 나무
    if geo is None:  # 색만 다른 모델은 몸체 공유
        geo = src.parent / drawing["geometry_from"] if drawing.get("geometry_from") else src
    objs = []
    for stl in sorted(geo.glob("*.stl")):
        bpy.ops.wm.stl_import(filepath=str(stl))
        ob = bpy.context.selected_objects[0]
        ob.name = stl.stem
        ob.data.materials.clear()
        ob.data.materials.append(pal[ROLE_MAT[role_of(stl.stem)]])
        objs.append(ob)
    if not objs:
        raise FileNotFoundError(f"{geo}에 STL이 없다")
    name = name or prod["sku"]
    s = unit_scale(objs, height_mm or prod["product_dims_mm"]["h"])
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    for ob in objs:
        ob.scale = (s, s, s)
    bpy.context.view_layer.update()
    for ob in objs:  # 크기를 메시에 굽고, 평평한 면은 각지게 / 필렛은 부드럽게
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.object.shade_auto_smooth(angle=0.5236)
    pts = [ob.matrix_world @ v.co for ob in objs for v in ob.data.vertices]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    if drawing.get("fit_depth") and name == prod["sku"]:  # 같은 몸체를 깊이만 조금 다른 모델에 쓸 때 (예: 830 → 824)
        sy = prod["product_dims_mm"]["d"] / 1000 / (hi[1] - lo[1])
        for ob in objs:
            for v in ob.data.vertices:
                v.co.y *= sy
        lo[1], hi[1] = lo[1] * sy, hi[1] * sy
    for ob in objs:  # 바닥 가운데 원점
        for v in ob.data.vertices:
            v.co.x -= (lo[0] + hi[0]) / 2
            v.co.y -= (lo[1] + hi[1]) / 2
            v.co.z -= lo[2]
        ob.parent = root
    bb = {"w": (hi[0] - lo[0]) * 1000, "h": (hi[2] - lo[2]) * 1000, "d": (hi[1] - lo[1]) * 1000}
    path = out / f"{name}.glb"
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_yup=True, export_apply=True,
                              export_materials="EXPORT", export_cameras=False, export_lights=False)
    return {"file": path.name, "layout": "fusion", "bbox_mm": {k: round(v, 1) for k, v in bb.items()}}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--sku", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--src", required=True, help="Fusion에서 내보낸 부품 STL 폴더")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    prods = {p["sku"]: p for p in json.loads(Path(a.catalog).read_text(encoding="utf-8"))["products"]}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    src = Path(a.src)
    info = build(prods[a.sku], src, out)  # 같은 이름으로 덮어쓰기만, index.json은 그대로 (docs/specs/drawings.md)
    print(a.sku, info)
    comp = load_drawing(src).get("companion")
    if comp:  # 정수기 파우셋처럼 본체와 떨어져 같이 놓이는 부품 → <SKU><suffix>.glb + companions.json
        name = a.sku + comp["suffix"]
        cinfo = build(prods[a.sku], src, out, geo=src.parent / comp["src"], height_mm=comp["height_mm"], name=name)
        cpath = out / "companions.json"
        comps = json.loads(cpath.read_text(encoding="utf-8")) if cpath.exists() else {"models": {}}
        comps["models"][a.sku] = {"file": cinfo["file"], "offset_m": comp["offset_m"], "note": comp.get("note", "")}
        comps["_note"] = "fusion_to_glb.py가 씀. 본체와 같이 놓이는 부품 (offset_m = 본체 바닥 가운데 기준 x, y(위), z(앞))"
        cpath.write_text(json.dumps(comps, ensure_ascii=False, indent=1), encoding="utf-8")
        print(name, cinfo)


if __name__ == "__main__":
    main()
