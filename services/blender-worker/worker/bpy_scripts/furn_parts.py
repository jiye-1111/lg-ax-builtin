"""가구 모델 부품 만들기 (build_furniture.py가 쓴다).

모든 부품은 glTF 기준으로 적는다: x 폭, y 높이(바닥 0), z 깊이(정면 +). Blender에서는 (x, -z, y).
부품은 돌리지 않고 꼭짓점을 제자리에 구워 둔다. 웹이 부품을 축마다 늘리기 때문이다 (rig: s/p/e).
"""
from __future__ import annotations

import math

import bpy  # noqa: I001  (pip bpy는 bpy를 먼저 불러야 bmesh가 생긴다)
import bmesh
from mathutils import Matrix, Vector


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
    "linen": ("#DCD7CD", 0.88, 0.0),
    "duvet": ("#CFC8BA", 0.9, 0.0),
    "white": ("#E8E5DF", 0.45, 0.0),
    "glass": ("#D6E6EE", 0.04, 0.0),  # 웹에서 비치게 바꾼다 (재질 이름 glass)
    "metal": ("#2F3134", 0.35, 0.8),
    "plinth": ("#3A3B3D", 0.6, 0.0),
    "ash": ("#C9B497", 0.6, 0.0),
    "island_wood": ("#B9996F", 0.58, 0.0),  # 아일랜드 식탁 몸통: 밝은 참나무
    "stone": ("#E4E1DA", 0.3, 0.0),
    "wool": ("#B9AE9C", 0.97, 0.0),
    "brass": ("#B08D57", 0.3, 0.9),
    "shade": ("#F3EDE2", 0.8, 0.0),
    "pot": ("#D8D2C7", 0.7, 0.0),
    "soil": ("#3B2E25", 0.95, 0.0),
    "leaf": ("#4E6B3A", 0.6, 0.0),
    "plaster": ("#EDEAE4", 0.9, 0.0),
    "steel": ("#C5C8CB", 0.28, 0.9),
    "basin": ("#A9ADB1", 0.35, 0.9),
    "door_leaf": ("#C4AD8E", 0.55, 0.0),
    # 천·쿠션 (밝은 웜톤 바탕에 포인트 색 조금)
    "seat": ("#CFC6B8", 0.93, 0.0),
    "sofa": ("#B5AA97", 0.95, 0.0),
    "sofa_seat": ("#C8C1B5", 0.95, 0.0),
    "sage": ("#93A088", 0.95, 0.0),
    "clay": ("#BF8E76", 0.95, 0.0),
    "blanket": ("#8E9A8B", 0.96, 0.0),
    "headboard": ("#A89D8B", 0.94, 0.0),
    "book_a": ("#7B8A8E", 0.8, 0.0),
    "book_b": ("#C9B79C", 0.8, 0.0),
    "book_c": ("#8C5E4A", 0.8, 0.0),
    "screen": ("#15171A", 0.25, 0.0),
    "leaf_dark": ("#3F5A34", 0.55, 0.0),
    # 2026-11 다시 만든 가구: 무광 문짝, 밝은 참나무, 부클·샤닐 천, 검은 무광 철물
    "matte": ("#BDB5A7", 0.62, 0.0),        # 무광 문짝 (PET·도장)
    "greige": ("#CFC7BA", 0.62, 0.0),
    "oak_light": ("#BFA47E", 0.6, 0.0),
    "teak": ("#8F6A45", 0.55, 0.0),
    "boucle": ("#BDB5A8", 0.97, 0.0),
    "caramel": ("#B07F52", 0.95, 0.0),
    "black": ("#2A2A2B", 0.5, 0.3),         # 무광 검정 철물·다리
    "shadow": ("#2B2B2C", 0.8, 0.0),        # 손끼움 홈·문 사이 틈
    "quartz": ("#D8D4CC", 0.34, 0.0),
    "ceramic": ("#D9D2C6", 0.55, 0.0),
    "steel_white": ("#CFCCC5", 0.5, 0.2),   # 흰 분체도장 철제 다리
}


# 무늬 종류: 웹이 재질 extras.tex를 보고 나뭇결·천 짜임 무늬를 입힌다. 나머지는 민무늬
WOODS = {"oak", "walnut", "ash", "island_wood", "door_leaf", "oak_light", "teak"}
FABRICS = {"fabric", "fabric_dark", "cushion", "linen", "duvet", "wool", "seat", "sofa", "sofa_seat", "sage", "clay", "blanket",
           "headboard", "shade", "boucle", "caramel"}


def kind_of(look: str) -> str:
    return "wood" if look in WOODS else "fabric" if look in FABRICS else ""


def mat(name: str) -> bpy.types.Material:
    """재질. "부위:모양"으로 적으면 재질 이름은 부위(웹에서 색을 바꾸는 단위), 색·거칠기는 모양에서 가져온다.
    예: "top:oak" → 이름 top, 참나무 색. 그냥 "oak"면 이름도 oak."""
    role, _, look = name.rpartition(":")
    role = role or look
    if role not in MATS:
        hex_, rough, metal = LOOK[look]
        m = bpy.data.materials.new(role)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = lin(hex_)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        if kind_of(look):
            m["tex"] = kind_of(look)
        MATS[role] = m
    return MATS[role]


WOOD_U, WOOD_V, CLOTH = 1.2, 0.4, 0.05  # 무늬 한 장이 덮는 길이 (m): 나뭇결 방향, 결 가로, 천


def bake_uvs() -> None:
    """모든 부품에 UV를 넣는다. 실제 길이(m) 기준으로 펴서 무늬 크기가 가구마다 같다.
    나뭇결은 부품의 가장 긴 쪽을 따라 흐른다 (문짝은 세로, 상판은 가로)."""
    bpy.context.view_layer.update()
    for n, ob in enumerate(o for o in bpy.context.scene.objects if o.type == "MESH"):
        me, mw = ob.data, ob.matrix_world
        pts = [mw @ v.co for v in me.vertices]
        size = [max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)]
        g = max(range(3), key=lambda i: size[i])
        cloth = bool(me.materials) and me.materials[0].get("tex") == "fabric"
        uv = me.uv_layers.new(name="UVMap")
        rot = mw.to_3x3()
        shift = (n * 0.37) % 1.0
        for poly in me.polygons:
            nrm = rot @ poly.normal
            dom = max(range(3), key=lambda i: abs(nrm[i]))
            if dom == g:
                a, b = [i for i in range(3) if i != g]
            else:
                a, b = g, next(i for i in range(3) if i not in (g, dom))
            for li in poly.loop_indices:
                p = pts[me.loops[li].vertex_index]
                uv.data[li].uv = (p[a] / CLOTH, p[b] / CLOTH) if cloth else (p[a] / WOOD_U + shift, p[b] / WOOD_V + shift)


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


def bar(name: str, m: str, a: tuple[float, float, float], b: tuple[float, float, float], r: float, rig: str) -> None:
    """두 점(glTF 기준 x, y 높이, z 깊이)을 잇는 둥근 막대. 수전·문손잡이용."""
    pa, pb = Vector((a[0], -a[2], a[1])), Vector((b[0], -b[2], b[1]))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=r, radius2=r, depth=(pb - pa).length)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat(m))
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    ob.location = (pa + pb) / 2
    ob.rotation_euler = (pb - pa).to_track_quat("Z", "Y").to_euler()
    ob["rig"] = rig
    bpy.context.scene.collection.objects.link(ob)


# ---------- 둥근 모양: 쿠션, 굽은 등판, 가는 다리, 잎 ----------
def _emit(name: str, m: str, bm: bmesh.types.BMesh, rig: str) -> None:
    """Blender 좌표로 만든 bmesh를 부품으로 내보낸다. 원점은 부품 상자의 가운데."""
    lo = Vector([min(v.co[i] for v in bm.verts) for i in range(3)])
    hi = Vector([max(v.co[i] for v in bm.verts) for i in range(3)])
    mid = (lo + hi) / 2
    for v in bm.verts:
        v.co -= mid
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat(m))
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    ob.location = mid
    ob["rig"] = rig
    bpy.context.scene.collection.objects.link(ob)


def _g2b(x: float, y: float, z: float) -> Vector:
    return Vector((x, -z, y))


def soft(name: str, m: str, x0: float, x1: float, z0: float, z1: float, y0: float, y1: float, rig: str,
         r: float = 0.04, puff: float = 0.0, lean: float = 0.0, cuts: int = 9) -> None:
    """모서리가 둥근 덩어리(쿠션·매트리스·팔걸이). puff = 윗면이 가운데로 볼록한 높이,
    lean = 위로 갈수록 뒤(-z)로 눕는 길이 (등쿠션)."""
    hx, hy, hz = (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2
    r = min(r, hx * 0.95, hy * 0.95, hz * 0.95)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=cuts, use_grid_fill=True)
    half = Vector((hx, hy, hz))
    for v in bm.verts:
        p = Vector((v.co.x * hx, v.co.z * hy, v.co.y * hz))  # (x, y 높이, z 깊이)
        inner = Vector([max(-half[i] + r, min(half[i] - r, p[i])) for i in range(3)])
        off = p - inner
        if off.length > 1e-9:
            p = inner + off.normalized() * r
        if puff and p.y > 0:
            p.y += puff * (p.y / hy) * (1 - (p.x / hx) ** 2) * (1 - (p.z / hz) ** 2)
        if lean:
            p.z -= lean * (p.y + hy) / (2 * hy)
        v.co = _g2b(p.x + (x0 + x1) / 2, p.y + (y0 + y1) / 2, p.z + (z0 + z1) / 2)
    _emit(name, m, bm, rig)


def rod(name: str, m: str, a: tuple[float, float, float], b: tuple[float, float, float], r0: float, r1: float,
        rig: str, seg: int = 20) -> None:
    """두 점 a(아래)·b(위)를 잇는 둥근 막대. 굵기 r0 → r1 (가늘어지는 다리)."""
    pa, pb = _g2b(*a), _g2b(*b)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r0, radius2=r1, depth=(pb - pa).length)
    rot = (pb - pa).to_track_quat("Z", "Y").to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation((pa + pb) / 2) @ rot, verts=list(bm.verts))
    _emit(name, m, bm, rig)


def bowed(name: str, m: str, x0: float, x1: float, y0: float, y1: float, z_edge: float, bow: float, t: float,
          rig: str, nx: int = 16, edge: float = 0.006) -> None:
    """가로로 굽은 판(의자 등판). 양 끝이 z_edge, 가운데가 bow만큼 뒤(-z)로 들어간다. t = 두께."""
    bm = bmesh.new()
    rings = []
    for i in range(nx + 1):
        u = -1 + 2 * i / nx
        x, zc = x0 + (x1 - x0) * i / nx, z_edge - bow * (1 - u * u)
        rings.append([bm.verts.new(_g2b(x, y, z)) for y, z in
                      ((y0, zc - t / 2), (y1, zc - t / 2), (y1, zc + t / 2), (y0, zc + t / 2))])
    for ra, rb in zip(rings, rings[1:]):
        for k in range(4):
            bm.faces.new((ra[k], ra[(k + 1) % 4], rb[(k + 1) % 4], rb[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    sharp = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(40)]
    bmesh.ops.bevel(bm, geom=sharp, offset=min(edge, t / 2.5), segments=3, profile=0.5, affect="EDGES")
    _emit(name, m, bm, rig)


def leaf(name: str, m: str, root: tuple[float, float, float], tip: tuple[float, float, float], width: float,
         rig: str = "eee") -> None:
    """잎 한 장: 뿌리에서 끝으로 뻗은 납작한 타원."""
    pa, pb = _g2b(*root), _g2b(*tip)
    length = (pb - pa).length
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.5)
    for v in bm.verts:
        s = 1 - 0.55 * max(0.0, v.co.z * 2) ** 2  # 끝으로 갈수록 좁게
        v.co = Vector((v.co.x * width * s, v.co.y * width * 0.12, v.co.z * length))
    rot = (pb - pa).to_track_quat("Z", "Y").to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation((pa + pb) / 2) @ rot, verts=list(bm.verts))
    _emit(name, m, bm, rig)


def slab(name: str, m: str, x0: float, x1: float, z0: float, z1: float, y0: float, y1: float, rig: str,
         corner: float = 0.06, edge: float = 0.005, seg: int = 8) -> None:
    """위에서 봤을 때 네 귀를 크게 굴린 판 (식탁·탁자 상판, 러그). corner = 귀 반지름, edge = 위아래 모서리 굴림."""
    hx, hz = (x1 - x0) / 2, (z1 - z0) / 2
    r = min(corner, hx * 0.98, hz * 0.98)
    ring = []
    for qx, qz, a0 in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg)
            ring.append((qx * (hx - r) + r * math.cos(a), qz * (hz - r) + r * math.sin(a)))
    bm = bmesh.new()
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    lo = [bm.verts.new(_g2b(cx + x, y0, cz + z)) for x, z in ring]
    hi = [bm.verts.new(_g2b(cx + x, y1, cz + z)) for x, z in ring]
    n = len(ring)
    for i in range(n):
        bm.faces.new((lo[i], lo[(i + 1) % n], hi[(i + 1) % n], hi[i]))
    bm.faces.new(hi)
    bm.faces.new(lo[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    e = min(edge, (y1 - y0) / 2.5)
    if e > 0:
        rim = [ed for ed in bm.edges if len(ed.link_faces) == 2 and ed.calc_face_angle(0) > math.radians(60)]
        bmesh.ops.bevel(bm, geom=rim, offset=e, segments=3, profile=0.5, affect="EDGES")
    _emit(name, m, bm, rig)
