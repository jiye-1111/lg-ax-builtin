"""카탈로그 제품마다 3D 모델(glb)을 Blender로 만든다.

    blender -b -P build_products.py -- --catalog data/catalog/products.json --out apps/web/models/products
    python build_products.py --catalog ... --out ...      (pip bpy 모듈로 실행할 때)

- 크기: 카탈로그 product_dims_mm (LGE.COM 값) 그대로. 바닥 가운데가 원점, 정면 = glTF +Z.
- 모양: data/drawings/<sku>.json(Figma에서 그린 정면·옆면 도면)이 있으면 그 도면대로,
  없으면 카테고리별 화면용 표현(문 나눔, 손잡이, 화구 등).
- 재질 이름 "finish"는 웹에서 색을 바꿀 때 쓰는 문 앞판 재질이다.
- 결과: <sku>.glb + index.json (모델 파일, 치수, 모양 종류)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # worker 패키지 (Blender로 바로 실행할 때)
from worker.drawing import boxes_from_drawing, load_drawing, top_items

DRAWINGS = Path(__file__).resolve().parents[4] / "data" / "drawings"
ROLE_MAT = {"body": "body", "door": "finish", "handle": "handle", "vent": "trim", "display": "display",
            "glass": "finish", "housing": "trim", "spout": "chrome", "tray": "trim"}
ROLE_BEVEL = {"door": 0.006, "handle": 0.005, "body": 0.004, "display": 0.003, "glass": 0.003,
              "spout": 0.006, "tray": 0.005}

GAP = 0.004        # 문 사이 틈
DOOR_T = 0.04      # 문 두께
BEVEL = 0.006      # 문 모서리 라운드
HANDLE = 0.022     # 손잡이가 문 앞으로 나온 길이


# ---------- 재질 ----------
def lin(hex_: str) -> tuple[float, float, float, float]:
    h = hex_.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return (*[v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c], 1.0)


def material(name: str, hex_: str, rough: float, metal: float = 0.0, coat: float = 0.0) -> bpy.types.Material:
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = lin(hex_)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if coat and "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
    return m


# 카탈로그 재질 이름 → 표면 느낌 (거칠기, 금속성, 코팅)
FINISH_FEEL = {
    "글라스": (0.12, 0.0, 1.0),
    "메탈": (0.32, 0.55, 0.0),
    "스테인리스": (0.28, 0.85, 0.0),
    "스톤 (스테인리스)": (0.45, 0.6, 0.0),
}


def palette(hex_: str, mat_name: str | None) -> dict:
    rough, metal, coat = FINISH_FEEL.get(mat_name or "", (0.42, 0.0, 0.3))
    dark_top = sum(lin(hex_)[:3]) < 0.15  # 검은 유리 상판이면 무늬를 밝게
    return {
        "finish": material("finish", hex_, rough, metal, coat),
        "body": material("body", "#C9CACB", 0.45, 0.6),
        "gap": material("gap", "#141516", 0.7),
        "handle": material("handle", "#8E9194", 0.25, 1.0),
        "trim": material("trim", "#2B2D30", 0.5),
        "print": material("print", "#B9BCC0" if dark_top else "#5A5E63", 0.4),
        "display": material("display", "#0E1012", 0.08, 0.0, 1.0),
        "chrome": material("chrome", "#D5D8DB", 0.12, 1.0),
    }


# ---------- 형상 ----------
def box(parts: list, mat: bpy.types.Material, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float,
        bevel: float = 0.0) -> None:
    """Blender 좌표(Z-up, 정면 = -Y) 기준 축 정렬 상자. x 폭, y 깊이(앞 -), z 높이."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 + (v.co.x + 0.5) * (x1 - x0)
        v.co.y = y0 + (v.co.y + 0.5) * (y1 - y0)
        v.co.z = z0 + (v.co.z + 0.5) * (z1 - z0)
    if bevel > 0:
        b = min(bevel, (x1 - x0) / 2.5, (y1 - y0) / 2.5, (z1 - z0) / 2.5)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=b, segments=3, profile=0.5, affect="EDGES")
    me = bpy.data.meshes.new("part")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("part", me)
    bpy.context.scene.collection.objects.link(ob)
    parts.append(ob)


def ring(parts: list, mat: bpy.types.Material, cx: float, cy: float, z: float, r: float, w: float = 0.003) -> None:
    """상판 위 얇은 원 무늬 (화구 표시)"""
    bm = bmesh.new()
    n = 64
    outer = [bm.verts.new((cx + (r + w / 2) * math.cos(t), cy + (r + w / 2) * math.sin(t), z))
             for t in (2 * math.pi * i / n for i in range(n))]
    inner = [bm.verts.new((cx + (r - w / 2) * math.cos(t), cy + (r - w / 2) * math.sin(t), z))
             for t in (2 * math.pi * i / n for i in range(n))]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((inner[i], inner[j], outer[j], outer[i]))
    me = bpy.data.meshes.new("ring")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new("ring", me)
    bpy.context.scene.collection.objects.link(ob)
    parts.append(ob)


def front_doors(parts, pal, W, D, H, doors, handles):
    """캐비닛 + 앞판. doors: (x0,x1,z0,z1) 비율, handles: (door index, 'v' | 'h')"""
    fy = -D / 2 + HANDLE              # 정면 (손잡이까지 깊이 D 안에)
    box(parts, pal["body"], -W / 2, W / 2, fy + DOOR_T, D / 2, 0.0, H - 0.002, bevel=0.004)   # 몸통(옆판)
    box(parts, pal["gap"], -W / 2 + 0.002, W / 2 - 0.002, fy + DOOR_T - 0.002, fy + DOOR_T + 0.01, 0.0, H - 0.004)
    box(parts, pal["trim"], -W / 2 + 0.01, W / 2 - 0.01, fy + 0.02, fy + DOOR_T, 0.0, 0.045)  # 아래 통풍구
    for i, (a, b, c, d) in enumerate(doors):
        x0, x1 = -W / 2 + a * W + GAP / 2, -W / 2 + b * W - GAP / 2
        z0, z1 = c * H + GAP / 2, d * H - GAP / 2
        box(parts, pal["finish"], x0, x1, fy, fy + DOOR_T, z0, z1, bevel=BEVEL)
        for di, kind in handles:
            if di != i:
                continue
            if kind == "v":  # 세로 손잡이: 가운데 쪽 모서리
                inner = x1 - 0.03 if (a + b) / 2 < 0.5 else x0 + 0.03
                hz0, hz1 = max(z0 + 0.05, z1 - 0.55), z1 - 0.12
                box(parts, pal["handle"], inner - 0.007, inner + 0.007, fy - 0.022, fy, hz0, hz1, bevel=0.005)
            else:            # 가로 손잡이: 위쪽 모서리
                hw = (x1 - x0) * 0.32
                cx = (x0 + x1) / 2
                box(parts, pal["handle"], cx - hw, cx + hw, fy - 0.02, fy, z1 - 0.05, z1 - 0.036, bevel=0.005)


def fridge(parts, pal, W, D, H, layout):
    t = 0.045 / H  # 아래 통풍구 높이 비율
    if layout == "4door":        # 위 양문 + 아래 좌우 서랍
        doors = [(0, .5, .47, 1), (.5, 1, .47, 1), (0, .5, t, .47), (.5, 1, t, .47)]
        handles = [(0, "v"), (1, "v"), (2, "h"), (3, "h")]
    elif layout == "convertible":  # 위 양문 + 아래 서랍 2단
        doors = [(0, .5, .52, 1), (.5, 1, .52, 1), (0, 1, .29, .52), (0, 1, t, .29)]
        handles = [(0, "v"), (1, "v"), (2, "h"), (3, "h")]
    else:                        # 3door: 위 한 문 + 아래 서랍 2단
        doors = [(0, 1, .57, 1), (0, 1, .31, .57), (0, 1, t, .31)]
        handles = [(0, "h"), (1, "h"), (2, "h")]
    front_doors(parts, pal, W, D, H, doors, handles)
    # 문 위 작은 표시창
    fy = -D / 2 + HANDLE
    box(parts, pal["display"], W / 2 - 0.16, W / 2 - 0.06, fy - 0.0015, fy + 0.002, H * 0.86, H * 0.86 + 0.035, bevel=0.003)


def dishwasher(parts, pal, W, D, H):
    fy = -D / 2 + 0.0015
    kick = 0.09
    box(parts, pal["body"], -W / 2, W / 2, fy + DOOR_T, D / 2, kick, H, bevel=0.003)
    box(parts, pal["trim"], -W / 2 + 0.01, W / 2 - 0.01, fy + 0.05, D / 2 - 0.02, 0.0, kick)          # 걸레받이 자리
    box(parts, pal["finish"], -W / 2 + 0.001, W / 2 - 0.001, fy, fy + DOOR_T, kick + 0.002, H - 0.002, bevel=BEVEL)
    box(parts, pal["trim"], -W / 2 + 0.03, W / 2 - 0.03, fy - 0.001, fy + 0.002, H - 0.045, H - 0.03, bevel=0.002)  # 손잡이 홈
    box(parts, pal["display"], -0.05, 0.05, fy - 0.0012, fy + 0.002, H - 0.09, H - 0.075, bevel=0.002)


def cooktop(parts, pal, W, D, H, wide):
    glass = 0.006
    box(parts, pal["trim"], -W / 2 + 0.03, W / 2 - 0.03, -D / 2 + 0.03, D / 2 - 0.03, 0.0, H - glass)   # 아래 몸체
    box(parts, pal["finish"], -W / 2, W / 2, -D / 2, D / 2, H - glass, H, bevel=0.003)                # 유리 상판
    z = H + 0.0004
    # Blender y: 앞쪽이 -D/2
    ring(parts, pal["print"], -W * 0.22, D * 0.17, z, 0.085)
    ring(parts, pal["print"], -W * 0.22, -D * 0.2, z, 0.075)
    if wide:  # 와이드존: 둥근 사각형 대신 큰 원 두 개
        ring(parts, pal["print"], W * 0.2, D * 0.12, z, 0.07)
        ring(parts, pal["print"], W * 0.2, -D * 0.16, z, 0.07)
    else:
        ring(parts, pal["print"], W * 0.2, 0.0, z, 0.105)
    for i in range(5):  # 조작부 점
        ring(parts, pal["print"], -0.08 + i * 0.04, -D / 2 + 0.035, z, 0.006, 0.002)


def purifier(parts, pal, W, D, H):
    fy = -D / 2 + 0.07                # 물받이까지 깊이 D 안에
    box(parts, pal["finish"], -W / 2, W / 2, fy, D / 2, 0.0, H, bevel=0.02)
    box(parts, pal["display"], -W / 2 + 0.03, W / 2 - 0.03, fy - 0.0015, fy + 0.01, H - 0.11, H - 0.04, bevel=0.006)
    box(parts, pal["chrome"], -0.012, 0.012, fy - 0.05, fy + 0.01, H * 0.52, H * 0.52 + 0.03, bevel=0.008)  # 출수구
    box(parts, pal["trim"], -W / 2 + 0.02, W / 2 - 0.02, fy - 0.07, fy + 0.02, 0.012, 0.03, bevel=0.006)    # 물받이


def from_drawing(parts: list, pal: dict, drawing: dict, dims: dict) -> None:
    for b in boxes_from_drawing(drawing, dims):
        box(parts, pal[ROLE_MAT[b["role"]]], b["x0"], b["x1"], b["y0"], b["y1"], b["z0"], b["z1"],
            bevel=ROLE_BEVEL.get(b["role"], 0.0))
    rings, prints = top_items(drawing, dims)
    for r in rings:
        ring(parts, pal["print"], r["cx"], r["cy"], r["z"], r["r"])
    for b in prints:
        box(parts, pal["print"], b["x0"], b["x1"], b["y0"], b["y1"], b["z0"], b["z1"])


def layout_of(prod: dict) -> str:
    name = prod["name"]
    if prod["category"] == "refrigerator":
        return "convertible" if "컨버터블" in name else "4door"
    if prod["category"] == "kimchi_refrigerator":
        return "4door" if "480L" in name else "3door"
    if prod["category"] == "cooktop":
        return "wide" if "와이드" in name else "standard"
    return prod["category"]


def build(prod: dict, out: Path, drawings: Path = DRAWINGS) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    dims = prod["product_dims_mm"]
    W, H, D = dims["w"] / 1000, dims["h"] / 1000, dims["d"] / 1000
    opt = (prod.get("cmf_options") or [{}])[0]
    pal = palette(opt.get("hex_approx") or "#F2F2F0", opt.get("material"))
    parts: list = []
    cat, lay = prod["category"], layout_of(prod)
    drawing = load_drawing(drawings, prod["sku"])
    if drawing:
        lay = "drawing"
        from_drawing(parts, pal, drawing, dims)
    elif cat in ("refrigerator", "kimchi_refrigerator"):
        fridge(parts, pal, W, D, H, lay)
    elif cat == "dishwasher":
        dishwasher(parts, pal, W, D, H)
    elif cat == "cooktop":
        cooktop(parts, pal, W, D, H, lay == "wide")
    elif cat == "water_purifier":
        purifier(parts, pal, W, D, H)
    else:
        box(parts, pal["finish"], -W / 2, W / 2, -D / 2, D / 2, 0, H, bevel=BEVEL)
    # 하나로 합쳐 변형 없이 내보낸다 (튀어나온 손잡이·물받이까지 포함해 바닥 가운데 기준)
    ctx = bpy.context
    for o in parts:
        o.select_set(True)
    ctx.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = ctx.view_layer.objects.active
    ob.name = prod["sku"]
    # 바닥 가운데가 원점이 되게 맞춘다
    xs = [v.co.x for v in ob.data.vertices]
    ys = [v.co.y for v in ob.data.vertices]
    zs = [v.co.z for v in ob.data.vertices]
    off = ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, min(zs))
    for v in ob.data.vertices:
        v.co.x -= off[0]
        v.co.y -= off[1]
        v.co.z -= off[2]
    bb = {"w": (max(xs) - min(xs)) * 1000, "h": (max(zs) - min(zs)) * 1000, "d": (max(ys) - min(ys)) * 1000}
    path = out / f"{prod['sku']}.glb"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_yup=True, export_apply=True,
                              export_materials="EXPORT", export_cameras=False, export_lights=False)
    return {"file": path.name, "layout": lay, "bbox_mm": {k: round(v, 1) for k, v in bb.items()}}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sku", action="append", help="이 제품만 만들기 (여러 번 가능)")
    ap.add_argument("--drawings", default=str(DRAWINGS), help="Figma 도면 JSON 폴더")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prods = json.loads(Path(a.catalog).read_text(encoding="utf-8"))["products"]
    idx_path = out / "index.json"
    index = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {"models": {}}
    for p in prods:
        if a.sku and p["sku"] not in a.sku:
            continue
        if not p.get("product_dims_mm") or not all(p["product_dims_mm"].get(k) for k in ("w", "h", "d")):
            continue
        index["models"][p["sku"]] = build(p, out, Path(a.drawings))
        print(p["sku"], index["models"][p["sku"]]["bbox_mm"])
    index["_note"] = "build_products.py로 생성. 크기는 카탈로그 값, 모양은 Figma 도면(layout=drawing) 또는 화면용 표현."
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
