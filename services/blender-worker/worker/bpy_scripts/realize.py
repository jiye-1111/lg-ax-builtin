"""worker.shapes 부품 목록(mm)을 Blender 메시로 만들고 glb로 내보낸다.

- 좌표: 부품은 mm, Blender는 m. x 폭, y 깊이(정면 -), z 높이. 내보낼 때 Y-up, 정면 +Z.
- 날카로운 모서리(35° 넘는 면 사이)는 꼭짓점을 갈라 두고 전부 부드럽게 칠한다. 둥근 면은 매끈하고 각진 곳은 각지게 보인다.
- 재질 이름이 finish로 시작하면 웹에서 제품 색으로 칠하는 겉면이다. 내보낸 파일 안에서는 이름을 모두 "finish"로 맞춘다.
"""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

MM = 0.001
SHARP = math.radians(35)

# 재질: 이름 → (색, 거칠기, 금속성, 코팅). 색이 None이면 제품 색
MATS = {
    "finish": (None, 0.45, 0.0, 0.25),
    "finish_dots": (None, 0.5, 0.0, 0.1),
    "finish_matte": (None, 0.75, 0.0, 0.0),
    "body": ("#2B2B2D", 0.5, 0.0, 0.2),
    "dark": ("#1B1C1E", 0.5, 0.0, 0.1),
    "black": ("#0B0C0D", 0.12, 0.0, 1.0),
    "screen": ("#050608", 0.05, 0.0, 1.0),
    "window": ("#14171B", 0.04, 0.0, 1.0),
    "chrome": ("#D5D8DB", 0.14, 1.0, 0.0),
    "steel": ("#A9ADB1", 0.34, 0.9, 0.0),
    "grey": ("#8C8F93", 0.5, 0.0, 0.1),
    "lightgrey": ("#C9CACB", 0.5, 0.0, 0.1),
    "white": ("#F1F1EF", 0.45, 0.0, 0.25),
    "rubber": ("#202122", 0.85, 0.0, 0.0),
    "glass": ("#20262B", 0.04, 0.0, 1.0),
    "print": ("#B9BCC0", 0.4, 0.0, 0.0),
    "glow": ("#FFE9C4", 0.4, 0.0, 0.0),
}
# 카탈로그 재질 이름 → 겉면 느낌 (거칠기, 금속성, 코팅)
FINISH_FEEL = {
    "글라스": (0.12, 0.0, 1.0), "메탈": (0.32, 0.55, 0.0), "스테인리스": (0.28, 0.85, 0.0),
    "스톤 (스테인리스)": (0.45, 0.6, 0.0), "글라스 (크리스탈)": (0.08, 0.0, 1.0), "미러": (0.04, 0.9, 1.0),
}
FEEL_SUFFIX = {"m": (0.3, 0.9, 0.0), "g": (0.1, 0.0, 1.0), "f": (0.9, 0.0, 0.0), "s": (0.5, 0.0, 0.15)}


def lin(hex_: str) -> tuple[float, float, float, float]:
    h = hex_.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return (*[v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c], 1.0)


def dots_image() -> bpy.types.Image:
    """구멍 뚫린 판 무늬 (밝은 바탕에 어두운 점). 숫자로 만든다."""
    n = 32
    img = bpy.data.images.new("dots", n, n, alpha=False)
    px = []
    for j in range(n):
        for i in range(n):
            d = math.hypot(i + 0.5 - n / 2, j + 0.5 - n / 2) / (n / 2)
            v = 0.16 if d < 0.5 else (0.16 + (1 - 0.16) * min(1, (d - 0.5) / 0.14))
            px += [v, v, v, 1.0]
    img.pixels = px
    img.pack()
    return img


class Mats:
    def __init__(self, hex_: str, feel: str | None = None, body_hex: str | None = None):
        self.hex, self.feel, self.body_hex, self.cache = hex_, feel, body_hex, {}

    def get(self, name: str) -> bpy.types.Material:
        if name in self.cache:
            return self.cache[name]
        if name.startswith("#"):          # 정해진 색: "#RRGGBB" 또는 "#RRGGBB/m" (m 금속, g 유광, f 천, s 새틴)
            hex_, _, suf = name.partition("/")
            rough, metal, coat = FEEL_SUFFIX.get(suf or "s")
        else:
            hex_, rough, metal, coat = MATS[name]
            if name == "body" and self.body_hex:
                hex_ = self.body_hex
            if hex_ is None:
                hex_ = self.hex
                if name == "finish" and self.feel in FINISH_FEEL:
                    rough, metal, coat = FINISH_FEEL[self.feel]
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = lin(hex_)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        if coat and "Coat Weight" in b.inputs:
            b.inputs["Coat Weight"].default_value = coat
        if name == "finish_dots":
            tex = m.node_tree.nodes.new("ShaderNodeTexImage")
            tex.image = dots_image()
            mix = m.node_tree.nodes.new("ShaderNodeMix")
            mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
            mix.inputs[0].default_value = 1.0
            m.node_tree.links.new(tex.outputs["Color"], mix.inputs[6])
            mix.inputs[7].default_value = lin(hex_)
            m.node_tree.links.new(mix.outputs[2], b.inputs["Base Color"])
        if name == "glow":
            b.inputs["Emission Color"].default_value = lin(hex_)
            b.inputs["Emission Strength"].default_value = 0.6
        self.cache[name] = m
        return m


# ---------- 단면 ----------
def rounded_rect(u0, u1, v0, v1, r, seg=6) -> list[tuple[float, float]]:
    rs = list(r) if isinstance(r, (tuple, list)) else [r] * 4      # 왼쪽 아래, 오른쪽 아래, 오른쪽 위, 왼쪽 위
    lim = min(u1 - u0, v1 - v0) / 2 - 1e-6
    rs = [max(0.0, min(x, lim)) for x in rs]
    corners = [(u0, v0, 180), (u1, v0, 270), (u1, v1, 0), (u0, v1, 90)]
    pts = []
    for (cu, cv, a0), rr in zip(corners, rs):
        if rr <= 1e-6:
            pts.append((cu, cv))
            continue
        ox = cu + (rr if cu == u0 else -rr)
        oy = cv + (rr if cv == v0 else -rr)
        n = max(2, int(seg * (1 if rr > 6 else 0.5)))
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((ox + rr * math.cos(a), oy + rr * math.sin(a)))
    return pts


def _to_xyz(axis: str, u: float, v: float, a: float) -> tuple[float, float, float]:
    if axis == "y":
        return u, a, v
    if axis == "x":
        return a, u, v
    return u, v, a


def _prism(bm, axis, pts, a0, a1, bev):
    lo = [bm.verts.new(_to_xyz(axis, u, v, a0)) for u, v in pts]
    hi = [bm.verts.new(_to_xyz(axis, u, v, a1)) for u, v in pts]
    n = len(pts)
    caps = [bm.faces.new(lo), bm.faces.new(hi)]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    if bev > 0:
        edges = [e for f in caps for e in f.edges]
        b = min(bev, (a1 - a0) / 2.5)
        if b > 0.05:
            bmesh.ops.bevel(bm, geom=edges, offset=b, segments=2, profile=0.5, affect="EDGES", clamp_overlap=True)


def _finish(bm, mat_index_holder=None):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    sharp = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > SHARP]
    if sharp:
        bmesh.ops.split_edges(bm, edges=sharp)
    for f in bm.faces:
        f.smooth = True


def _planar_uv(bm, pitch):
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        for l in f.loops:
            co = l.vert.co
            if abs(n.y) >= max(abs(n.x), abs(n.z)):
                l[uv].uv = (co.x / pitch, co.z / pitch)
            elif abs(n.x) >= abs(n.z):
                l[uv].uv = (co.y / pitch, co.z / pitch)
            else:
                l[uv].uv = (co.x / pitch, co.y / pitch)


def make(part: dict) -> bmesh.types.BMesh:
    bm = bmesh.new()
    k = part["kind"]
    if k == "box":
        ax = part["ax"]
        if ax == "y":
            pts, a0, a1 = rounded_rect(part["x0"], part["x1"], part["z0"], part["z1"], part["r"]), part["y0"], part["y1"]
        elif ax == "x":
            pts, a0, a1 = rounded_rect(part["y0"], part["y1"], part["z0"], part["z1"], part["r"]), part["x0"], part["x1"]
        else:
            pts, a0, a1 = rounded_rect(part["x0"], part["x1"], part["y0"], part["y1"], part["r"]), part["z0"], part["z1"]
        _prism(bm, ax, pts, a0, a1, part["bev"])
    elif k == "ext":
        _prism(bm, part["axis"], part["pts"], part["a0"], part["a1"], part["bev"])
    elif k == "cyl":
        r1, r2, l = part["r"], part["r2"], part["l"]
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=part["seg"], radius1=r1, radius2=r2, depth=l)
        if part["bev"] > 0:
            caps = [e for f in bm.faces if len(f.verts) > 4 for e in f.edges]
            b = min(part["bev"], min(r1, r2) / 3 if min(r1, r2) > 0 else 0, l / 3)
            if b > 0.05:
                bmesh.ops.bevel(bm, geom=caps, offset=b, segments=2, profile=0.5, affect="EDGES")
        if part["axis"] == "y":
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
        elif part["axis"] == "x":
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
        bmesh.ops.translate(bm, verts=bm.verts, vec=part["c"])
    elif k == "lathe":
        cx, cy = part["c"]
        prof, seg, ribs, sy = part["prof"], part["seg"], part["ribs"], part.get("sy", 1.0)
        if ribs:
            seg = ribs[0] * 2
        rings = []
        for r, z in prof:
            if r <= 1e-6:
                rings.append([bm.verts.new((cx, cy, z))])
                continue
            ring = []
            for i in range(seg):
                a = 2 * math.pi * (i + 0.5) / seg
                rr = r - (ribs[1] if ribs and (i // 1) % 2 else 0)
                ring.append(bm.verts.new((cx + rr * math.cos(a), cy + rr * math.sin(a) * sy, z)))
            rings.append(ring)
        for a, b in zip(rings, rings[1:]):
            if len(a) == 1 and len(b) == 1:
                continue
            for i in range(seg):
                j = (i + 1) % seg
                if len(a) == 1:
                    bm.faces.new((a[0], b[j], b[i]))
                elif len(b) == 1:
                    bm.faces.new((a[i], a[j], b[0]))
                else:
                    bm.faces.new((a[i], a[j], b[j], b[i]))
        for ring in (rings[0], rings[-1]):   # 열린 끝은 막는다
            if len(ring) > 1:
                bm.faces.new(ring)
        if part.get("uv"):
            uv = bm.loops.layers.uv.verify()
            rr = max(p[0] for p in prof)
            for f in bm.faces:
                for l in f.loops:
                    co = l.vert.co
                    a = math.atan2(co.y - cy, co.x - cx)
                    l[uv].uv = (a * rr / part["uv"], co.z / part["uv"])
    elif k == "torus":
        R, r = part["R"], part["r"]
        nu, nv = 56, 12
        grid = [[None] * nv for _ in range(nu)]
        for i in range(nu):
            a = 2 * math.pi * i / nu
            for j in range(nv):
                b = 2 * math.pi * j / nv
                x, y, z = (R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)
                grid[i][j] = bm.verts.new((x, y, z))
        for i in range(nu):
            for j in range(nv):
                bm.faces.new((grid[i][j], grid[(i + 1) % nu][j], grid[(i + 1) % nu][(j + 1) % nv], grid[i][(j + 1) % nv]))
        if part["axis"] == "y":
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
        elif part["axis"] == "x":
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
        bmesh.ops.translate(bm, verts=bm.verts, vec=part["c"])
    elif k == "ell":
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
        e = 2.0 / part["n"]
        rx, ry, rz = part["rad"]
        cut = part.get("cut")          # (축, 값 -1~1): 그 아래(또는 위)를 평평하게 자른다
        for v in bm.verts:
            c = v.co
            p = [math.copysign(abs(t) ** e, t) for t in (c.x, c.y, c.z)]
            if cut:
                i, lim = "xyz".index(cut[0]), cut[1]
                p[i] = max(p[i], lim) if lim < 0 else min(p[i], lim)
            v.co = (p[0] * rx, p[1] * ry, p[2] * rz)
        rot = Matrix.Rotation(math.radians(part["rot"][2]), 3, "Z") @ Matrix.Rotation(math.radians(part["rot"][1]), 3, "Y") \
            @ Matrix.Rotation(math.radians(part["rot"][0]), 3, "X")
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=rot)
        bmesh.ops.translate(bm, verts=bm.verts, vec=part["c"])
    elif k == "tube":
        pts = [Vector(p) for p in part["pts"]]
        if part.get("smooth", True) and len(pts) > 2:   # 꺾인 곳을 둥글게 (Catmull-Rom)
            out = []
            ext = [pts[0]] + pts + [pts[-1]]
            for i in range(1, len(ext) - 2):
                p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
                for s in range(6):
                    t = s / 6
                    out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                                      + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
            out.append(pts[-1])
            pts = out
        n, r = 12, part["r"]
        tan = [(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(len(pts))]
        up = Vector((0, 0, 1)) if abs(tan[0].z) < 0.9 else Vector((1, 0, 0))
        nrm = (up - tan[0] * up.dot(tan[0])).normalized()
        rings = []
        for i, p in enumerate(pts):
            if i:
                nrm = (nrm - tan[i] * nrm.dot(tan[i]))
                nrm = nrm.normalized() if nrm.length > 1e-6 else rings and nrm
            bi = tan[i].cross(nrm)
            rings.append([bm.verts.new(p + (nrm * math.cos(2 * math.pi * j / n) + bi * math.sin(2 * math.pi * j / n)) * r)
                          for j in range(n)])
        for a, b in zip(rings, rings[1:]):
            for j in range(n):
                bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
        bm.faces.new(rings[0])
        bm.faces.new(rings[-1])
    else:
        raise ValueError(k)
    if part.get("uvs"):
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        _planar_uv(bm, part["uvs"])
    _finish(bm)
    return bm


def realize(parts: list[dict], mats: Mats, name: str, dims: dict | None = None) -> bpy.types.Object:
    """부품을 한 물체로 합친다. dims(mm)가 있으면 바닥 가운데를 원점으로 옮기고 크기를 그 값에 맞춘다."""
    me = bpy.data.meshes.new(name)
    out = bmesh.new()
    uv = out.loops.layers.uv.verify()
    slots: list[str] = []
    for part in parts:
        bm = make(part)
        if part["mat"] not in slots:
            slots.append(part["mat"])
        idx = slots.index(part["mat"])
        src_uv = bm.loops.layers.uv.active
        vmap = {v: out.verts.new(v.co * MM) for v in bm.verts}
        for f in bm.faces:
            try:
                nf = out.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                continue
            nf.material_index, nf.smooth = idx, True
            if src_uv:
                for l0, l1 in zip(f.loops, nf.loops):
                    l1[uv].uv = l0[src_uv].uv
        bm.free()
    if dims:
        xs, ys, zs = zip(*[v.co for v in out.verts])
        lo, hi = Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))
        want = Vector((dims["w"], dims["d"], dims["h"])) * MM
        got = hi - lo
        sc = [want[i] / got[i] for i in range(3)]
        if any(abs(s - 1) > 0.05 for s in sc):
            raise ValueError(f"{name}: 부품 크기 {[round(g * 1000) for g in got]}mm가 치수 "
                             f"{[round(w * 1000) for w in want]}mm와 5% 넘게 다르다")
        cen = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
        for v in out.verts:
            v.co = Vector(((v.co[i] - cen[i]) * sc[i] for i in range(3)))
    out.to_mesh(me)
    out.free()
    for s in slots:
        me.materials.append(mats.get(s))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def export_glb(ob: bpy.types.Object, path: Path) -> None:
    for o in bpy.context.scene.objects:
        o.select_set(o is ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_yup=True, export_apply=True,
                              use_selection=True, export_materials="EXPORT", export_cameras=False,
                              export_lights=False, export_image_format="AUTO")
    tidy_glb(path)


def tidy_glb(path: Path) -> None:
    """재질 이름 finish_*·finish.001을 finish로 맞추고, 무늬가 있는 겉면도 색을 곱해 쓸 수 있게 한다."""
    data = path.read_bytes()
    jlen = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + jlen])
    rest = data[20 + jlen:]
    for m in doc.get("materials", []):
        if m.get("name", "").startswith("finish"):
            m["name"] = "finish"
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    out = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + len(rest)) + struct.pack("<I4s", len(js), b"JSON") + js + rest
    path.write_bytes(out)
