"""Blender 헤드리스 렌더 — `blender -b -P build_scene.py -- --job job.json`

job.json (runner.build_scene이 만든다)
    boxes:         glb.py의 상자 목록 (지금 집 모습: 옮긴 가구 자리, 치운 가구 빠짐). 좌표는 glTF Y-up
    state:         scene_state.json (놓은 제품 sku·색·자리)
    models_dir:    제품 모델 폴더 (build_products.py 결과, <sku>.glb)
    furniture_dir: 스캔 가구 모델 폴더 (build_furniture.py 결과, index.json + <종류>.glb)
    out_png, out_blend, engine(CYCLES 기본 | EEVEE, .env BLENDER_ENGINE)
    camera:        (선택) 웹에서 보던 시점 {pos, target, fov}. 없으면 방 전체가 들어오는 자리에서 내려다본다

웹 3D 파일(scene.glb)은 여기서 만들지 않는다. 웹이 쓰는 노드 규칙은 glb.py 하나만 지킨다.

만드는 것
1) 벽(창·문 자리는 구멍), 걸레받이, 마루 바닥, 유리창·창틀, 나무 문
2) 스캔 가구 → 종류별 모델을 스캔 크기에 맞춰 부품별로 늘림 (웹 room3d.js fitFurniture와 같은 규칙)
3) 놓은 제품 → 제품 모델 + 고른 색
4) 카메라 쪽 벽은 낮게 잘라 방 안이 보이게 (웹 컷어웨이와 같은 방향)
5) 해 + 하늘 + 넓은 면광, AgX 색 관리 → PNG, .blend
"""
import json
import math
import os
import sys

import bpy  # noqa: E402  (Blender 내부에서만 사용 가능)
from mathutils import Vector

VIEW_DIR = Vector((-0.45, -0.7, 0.85)).normalized()  # 카메라가 방을 내려다보는 방향 (Blender Z-up)
BASEBOARD_H, FRAME_W, CUT_WALL_H = 0.08, 0.05, 0.14
BACKDROP = "#E7DFD3"  # 웹 3D 바탕과 같은 따뜻한 베이지


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return json.load(open(argv[argv.index("--job") + 1], encoding="utf-8"))


def lin(hex_):
    h = hex_.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return (*[v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c], 1.0)


def gl_to_bl(p):
    """glTF (x, y 높이, z) → Blender (x, -z, y)"""
    return Vector((p[0], -p[2], p[1]))


# ---------- 재질 ----------
_MATS = {}


def principled(name, color, rough=0.5, metal=0.0, **extra):
    key = (name, tuple(round(c, 4) for c in color))
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    for k, v in extra.items():
        if k in b.inputs:
            b.inputs[k].default_value = v
    _MATS[key] = m
    return m


def paint(hex_):
    """벽 페인트: 아주 거친 무광, 미세한 요철"""
    m = principled("paint", lin(hex_), rough=0.92)
    nt = m.node_tree
    if "Noise Texture" not in nt.nodes:
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 400
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.04
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], nt.nodes["Principled BSDF"].inputs["Normal"])
    return m


def wall_top(hex_):
    """벽 윗면: 그늘과 상관없이 벽 색으로 보인다"""
    key = ("wall_top", hex_)
    if key not in _MATS:
        m = bpy.data.materials.new("wall_top")
        m.use_nodes = True
        nt = m.node_tree
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = lin(hex_)
        em.inputs["Strength"].default_value = 0.75
        nt.links.new(em.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
        _MATS[key] = m
    return _MATS[key]


def wood_floor(hex_):
    """마루: 판 무늬(벽돌 텍스처) × 나뭇결(웨이브) × 바닥 색. 판 이음은 살짝 패이게."""
    m = bpy.data.materials.new("floor_wood")
    m.use_nodes = True
    nt, L = m.node_tree, m.node_tree.links
    b = nt.nodes["Principled BSDF"]
    co = nt.nodes.new("ShaderNodeTexCoord")
    brick = nt.nodes.new("ShaderNodeTexBrick")
    brick.offset, brick.offset_frequency = 0.42, 1
    brick.squash, brick.squash_frequency = 1.0, 1
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Brick Width"].default_value = 1.2
    brick.inputs["Row Height"].default_value = 0.16
    brick.inputs["Mortar Size"].default_value = 0.0025
    brick.inputs["Mortar Smooth"].default_value = 0.3
    brick.inputs["Bias"].default_value = 0.0
    base = lin(hex_)
    brick.inputs["Color1"].default_value = base
    brick.inputs["Color2"].default_value = tuple(c * 0.78 for c in base[:3]) + (1.0,)
    brick.inputs["Mortar"].default_value = tuple(c * 0.35 for c in base[:3]) + (1.0,)
    L.new(co.outputs["Object"], brick.inputs["Vector"])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type, wave.bands_direction = "BANDS", "X"
    wave.inputs["Scale"].default_value = 14.0
    wave.inputs["Distortion"].default_value = 2.5
    wave.inputs["Detail"].default_value = 3.0
    L.new(co.outputs["Object"], wave.inputs["Vector"])
    grain = nt.nodes.new("ShaderNodeMix")
    grain.data_type, grain.blend_type = "RGBA", "MULTIPLY"
    grain.inputs["Factor"].default_value = 0.12
    sock = lambda socks, ident: next(s for s in socks if s.identifier == ident)  # noqa: E731  (A/B는 종류별로 여럿)
    L.new(brick.outputs["Color"], sock(grain.inputs, "A_Color"))
    L.new(wave.outputs["Color"], sock(grain.inputs, "B_Color"))
    L.new(sock(grain.outputs, "Result_Color"), b.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value, rough.inputs["To Max"].default_value = 0.38, 0.55
    L.new(wave.outputs["Fac"], rough.inputs["Value"])
    L.new(rough.outputs["Result"], b.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    L.new(brick.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def mats(colors):
    return {
        "trim": principled("trim", lin("#F3F2EE"), rough=0.35),
        "glass": principled("glass", (0.92, 0.96, 0.98, 1), rough=0.02,
                            **{"Transmission Weight": 1.0, "IOR": 1.45, "Alpha": 1.0}),
        "door": principled("door", lin(colors.get("door", "#9C7652")), rough=0.55),
        "object": principled("object", lin("#B9BEC4"), rough=0.6),
        "product": principled("product", lin("#F4F4F2"), rough=0.4),
    }


# ---------- 상자 ----------
def box(name, center_bl, size_gl, yaw, mat, coll):
    """단위 상자를 (폭, 높이, 깊이)로 늘린 메시. center_bl은 Blender 좌표의 가운데."""
    me = bpy.data.meshes.new(name)
    w, h, d = size_gl
    v = [(x * w / 2, y * d / 2, z * h / 2) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    me.update()
    if mat:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = center_bl
    ob.rotation_euler = (0, 0, -yaw)  # glTF Y축 -yaw = Blender Z축 -yaw
    coll.objects.link(ob)
    return ob


def bevel(ob, width=0.004):
    mod = ob.modifiers.new("bevel", "BEVEL")
    mod.width, mod.segments, mod.limit_method = width, 2, "ANGLE"
    return ob


# ---------- 모델 불러오기 ----------
def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def furniture_templates(fdir):
    if not fdir or not os.path.exists(os.path.join(fdir, "index.json")):
        return {}
    idx = json.load(open(os.path.join(fdir, "index.json"), encoding="utf-8")).get("models", {})
    lib = bpy.data.collections.new("_furniture_lib")  # 장면에 넣지 않는 원본
    out = {}
    for cat, e in idx.items():
        p = os.path.join(fdir, e["file"])
        if not os.path.exists(p):
            continue
        objs = import_glb(p)
        for o in objs:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            lib.objects.link(o)
        r = e["ref_m"]
        out[cat] = ([o for o in objs if o.type == "MESH"], (r["w"], r["h"], r["d"]))
    return out


def fit_furniture(parts, ref, size, root, coll):
    """room3d.js fitFurniture와 같은 rig 규칙. glTF 축 i(폭·높이·깊이) → Blender 축 (x, z, y)."""
    R, T, BL = ref, size, (0, 2, 1)
    for src in parts:
        o = src.copy()  # 메시는 공유
        coll.objects.link(o)
        rig = str(src.get("rig", "sss"))
        c = src.location.copy()
        loc, sc = c.copy(), Vector((1, 1, 1))
        for i in range(3):
            a, k = BL[i], T[i] / R[i]
            if rig[i] == "s":
                loc[a], sc[a] = c[a] * k, k
            elif rig[i] == "p":
                loc[a] = c[a] * k
            elif i == 1:
                loc[a] = c[a] if c[a] < R[1] / 2 else T[1] - (R[1] - c[a])
            else:
                loc[a] = (math.copysign(1, c[a]) if c[a] else 1) * (T[i] / 2 - (R[i] / 2 - abs(c[a])))
        o.location, o.scale = loc, sc
        o.parent = root


# ---------- 장면 ----------
def build(job):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    coll = sc.collection
    state = json.load(open(job["state"], encoding="utf-8")) if job.get("state") else {}
    colors = state.get("materials") or {}
    M = mats(colors)
    boxes = job["boxes"]
    walls = {b["name"]: b for b in boxes if b["kind"] == "wall"}

    floor = next((b for b in boxes if b["kind"] == "floor"), None)
    center = gl_to_bl(floor["center"]) if floor else Vector()
    center.z = 0

    ceiling_h = max((b["size"][1] for b in walls.values()), default=2.4)
    view, inside = VIEW_DIR, False
    if job.get("camera") and floor:  # 웹에서 보던 자리: 집 안이면 벽을 자르지 않고 천장도 보인다
        eye = gl_to_bl(job["camera"]["pos"])
        w, _, d = floor["size"]
        inside = abs(eye.x - center.x) < w / 2 and abs(eye.y - center.y) < d / 2 and eye.z < ceiling_h
        view = eye - center

    def faces_camera(b):
        off = gl_to_bl(b["center"]) - center
        off.z = 0
        cam = Vector((view.x, view.y, 0))
        return off.length > 1e-6 and cam.length > 1e-6 and off.normalized().dot(cam.normalized()) > 0.35

    front = set() if inside else {n for n, b in walls.items() if faces_camera(b)}

    if floor and floor.get("outline"):  # 꺾인 집: 바깥벽을 따라 깐다
        pts = [(x, -z, 0.0) for x, z in floor["outline"]]
        if sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) < 0:
            pts.reverse()  # 면이 위를 보게
        me = bpy.data.meshes.new("floor")
        me.from_pydata(pts, [], [list(range(len(pts)))])
        me.update()
        fl = bpy.data.objects.new("floor", me)
        coll.objects.link(fl)
        fl.data.materials.append(wood_floor(floor["color"]))
    elif floor:
        w, _, d = floor["size"]
        bpy.ops.mesh.primitive_plane_add(size=1, location=(center.x, center.y, 0))
        fl = bpy.context.active_object
        fl.name = "floor"
        fl.scale = (w, d, 1)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)  # 무늬 좌표 = m
        fl.data.materials.append(wood_floor(floor["color"]))

    # 벽과 개구부: 개구부가 속한 벽을 위치로 찾는다 (가장 가깝고 같은 방향)
    wall_obs = {}
    for n, b in walls.items():
        w_, h_, t_ = b["size"]
        if n in front:  # 카메라 쪽 벽은 낮게 보이고, 그림자는 원래 높이로 (창으로만 볕이 든다)
            c = gl_to_bl(b["center"])
            c.z = CUT_WALL_H / 2
            box(f"{n}_low", c, (w_, CUT_WALL_H, t_), b["yaw"], paint(b["color"]), coll)
            # 그림자만 내는 나머지 높이 (낮은 벽과 겹치면 낮은 벽이 까맣게 그늘진다)
            c2 = gl_to_bl(b["center"])
            c2.z = CUT_WALL_H + (h_ - CUT_WALL_H) / 2 + 0.002
            ob = box(n, c2, (w_, h_ - CUT_WALL_H - 0.004, t_ * 0.6), b["yaw"], None, coll)
            ob.visible_camera = ob.visible_diffuse = ob.visible_glossy = ob.visible_transmission = False
            cap_c = gl_to_bl(b["center"])
            cap_c.z = CUT_WALL_H + 0.0006
            box(f"{n}_top", cap_c, (w_, 0.001, t_), b["yaw"], wall_top(b["color"]), coll)
        else:
            ob = box(n, gl_to_bl(b["center"]), (w_, h_, t_), b["yaw"], paint(b["color"]), coll)
            bb_c = gl_to_bl(b["center"])
            bb_c.z = BASEBOARD_H / 2
            box(f"{n}_baseboard", bb_c, (w_, BASEBOARD_H, t_ + 0.024), b["yaw"], M["trim"], coll)
            if not inside:  # 위에서 보면 천장 그늘로 벽 윗면이 까맣게 나온다: 벽 색으로 덮는다
                top_c = gl_to_bl(b["center"])
                top_c.z = h_ + 0.002
                box(f"{n}_top", top_c, (w_, 0.004, t_), b["yaw"], wall_top(b["color"]), coll)
        wall_obs[n] = ob

    def host_wall(o):
        oc = gl_to_bl(o["center"])
        best, bd = None, 1e9
        for n, b in walls.items():
            if abs(math.sin(b["yaw"] - o["yaw"])) > 0.1:
                continue
            dvec = oc.xy - gl_to_bl(b["center"]).xy
            along = Vector((math.cos(-b["yaw"]), math.sin(-b["yaw"])))
            dist = abs(dvec.x * along.y - dvec.y * along.x)
            if abs(dvec.dot(along)) <= b["size"][0] / 2 + 0.05 and dist < bd:
                best, bd = n, dist
        return best

    for o in (b for b in boxes if b["kind"] in ("window", "door", "opening")):
        n = host_wall(o)
        if not n:
            continue
        w_, h_, t_ = o["size"]
        cut = box(f"{o['name']}_cut", gl_to_bl(o["center"]), (w_, h_, t_ + 0.3), o["yaw"], None, coll)
        cut.hide_render, cut.display_type = True, "WIRE"
        mod = wall_obs[n].modifiers.new(f"cut_{o['name']}", "BOOLEAN")
        mod.operation, mod.object = "DIFFERENCE", cut
        try:
            mod.solver = "EXACT"
        except TypeError:
            pass
        if n in front:  # 낮게 자른 벽: 그림자용 벽에 구멍만 내고 틀은 안 그린다
            continue
        local = lambda dx, dy: Vector((dx, 0, dy))  # noqa: E731  (벽 방향 기준 오프셋)
        rot = wall_obs[n].rotation_euler.to_matrix()

        def piece(name, size, dx, dy, mat):
            c = gl_to_bl(o["center"]) + rot @ local(dx, dy)
            return bevel(box(name, c, size, o["yaw"], mat, coll), 0.003)

        # 틀은 구멍 안쪽 테두리에 벽 두께만큼 넣는다: 구멍 속 벽 단면(어두운 틈)이 안 보이게
        depth, F = t_ + 0.03, FRAME_W
        if o["kind"] == "window":
            glass = box(f"{o['name']}_glass", gl_to_bl(o["center"]), (w_ - 2 * F, h_ - 2 * F, 0.012), o["yaw"], M["glass"], coll)
            glass.visible_shadow = False  # Cycles 유리는 굴절이라 해를 막는다: 그림자에서 빼야 창으로 볕이 든다
            piece(f"{o['name']}_sill", (w_ + F, 0.035, depth + 0.05), 0, -h_ / 2 + 0.0175, M["trim"])
            piece(f"{o['name']}_mullion", (F * 0.6, h_ - 2 * F, 0.05), 0, 0, M["trim"])
        elif o["kind"] == "door":
            box(f"{o['name']}_leaf", gl_to_bl(o["center"]) + rot @ local(0, -F / 2), (w_ - 2 * F, h_ - F, 0.04),
                o["yaw"], M["door"], coll)
        piece(f"{o['name']}_top", (w_ - 2 * F, F, depth), 0, h_ / 2 - F / 2, M["trim"])  # 옆 틀과 겹치면 모서리가 까맣게 나온다
        piece(f"{o['name']}_l", (F, h_, depth), -w_ / 2 + F / 2, 0, M["trim"])
        piece(f"{o['name']}_r", (F, h_, depth), w_ / 2 - F / 2, 0, M["trim"])

    # 스캔 가구
    furn = furniture_templates(job.get("furniture_dir"))
    for o in (b for b in boxes if b["kind"] == "object"):
        w_, h_, d_ = o["size"]
        t = furn.get(o.get("category"))
        if t:
            root = bpy.data.objects.new(o["name"], None)
            coll.objects.link(root)
            base = gl_to_bl(o["center"])
            base.z -= h_ / 2
            root.location, root.rotation_euler = base, (0, 0, -o["yaw"])
            fit_furniture(t[0], t[1], (w_, h_, d_), root, coll)
        else:
            bevel(box(o["name"], gl_to_bl(o["center"]), o["size"], o["yaw"], M["object"], coll), 0.01)

    # 놓은 제품
    mdir = job.get("models_dir")
    for pl in state.get("placements") or []:
        w_, h_, d_ = pl["size_m"]
        x, z = pl["center_xz"]
        base = pl.get("base_m") or 0.0  # 가구 위에 올려 둔 높이
        yaw = pl["yaw_rad"] - math.pi / 2  # glb.py와 같은 90° 보정
        path = os.path.join(mdir, f"{pl['sku']}.glb") if mdir else None
        if path and os.path.exists(path):
            root = bpy.data.objects.new(f"product_{pl['sku']}", None)
            coll.objects.link(root)
            for ob in import_glb(path):
                if ob.parent is None:
                    ob.parent = root
                for slot in getattr(ob, "material_slots", []):
                    if slot.material and slot.material.name.startswith("finish") and pl.get("hex"):
                        slot.material = slot.material.copy()
                        slot.material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = lin(pl["hex"])
            root.location, root.rotation_euler = (x, -z, base), (0, 0, -yaw)
        else:
            mat = principled(f"p_{pl['sku']}", lin(pl.get("hex") or "#F4F4F2"), rough=0.35)
            bevel(box(f"product_{pl['sku']}", Vector((x, -z, base + h_ / 2)), (w_, h_, d_), yaw, mat, coll), 0.01)

    # 천장: 카메라에는 안 보이고 그림자만 낸다. 해는 창으로만 들어온다
    if floor:
        w, _, d = floor["size"]
        ceil = box("ceiling", Vector((center.x, center.y, ceiling_h + 0.05)), (w + 0.4, 0.1, d + 0.4), 0.0,
                   paint("#F4F3EF") if inside else None, coll)
        if not inside:
            ceil.visible_camera = ceil.visible_glossy = ceil.visible_transmission = False

    return center, floor, ceiling_h, inside


def light_and_camera(center, floor, ceiling_h=2.4, sun_job=None, view=None, inside=False):
    sc = bpy.context.scene
    w, _, d = floor["size"] if floor else (6, 0, 6)
    extent = math.hypot(w, d)

    # 하늘: 위는 맑은 하늘색, 지평선은 밝게 (반사·간접광용)
    world = bpy.data.worlds.new("sky")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    grad = nt.nodes.new("ShaderNodeTexGradient")
    co = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(co.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.5, (0.95, 0.93, 0.9, 1)
    ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 1.0, (0.55, 0.7, 0.95, 1)
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.55
    nt.nodes.remove(grad)
    if view and not inside:  # 밖에서 내려다볼 때 집 둘레는 웹 화면과 같은 바탕색으로 (빛은 하늘 그대로)
        back = nt.nodes.new("ShaderNodeBackground")
        back.inputs["Color"].default_value = lin(BACKDROP)
        path = nt.nodes.new("ShaderNodeLightPath")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
        nt.links.new(bg.outputs["Background"], mix.inputs[1])
        nt.links.new(back.outputs["Background"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], nt.nodes["World Output"].inputs["Surface"])

    # 해: 채광과 같은 해(날짜·시각·위치·북쪽)가 오면 그 방향·색·세기, 없으면 보기 좋은 기본 해
    sun = bpy.data.objects.new("LGT-sun", bpy.data.lights.new("LGT-sun", "SUN"))
    sun.data.angle = math.radians(0.53)  # 실제 해 크기: 그림자 가장자리가 또렷하다
    if sun_job:
        dx, dy, dz = sun_job["direction"]  # 웹 3D 좌표, 해 쪽
        to_sun = Vector((dx, -dz, dy)).normalized()
        sun.rotation_euler = (-to_sun).to_track_quat("-Z", "Y").to_euler()
        sun.data.color = lin(sun_job["color"])[:3]
        sun.data.energy = 7.0 * sun_job["intensity"] if sun_job.get("up") else 0.0
        if not sun_job.get("up"):
            bg.inputs["Strength"].default_value = 0.06  # 밤
        elif sun_job["altitude_deg"] < 10:
            bg.inputs["Strength"].default_value = 0.3  # 해 질 녘 하늘은 어둡다
    else:
        sun.data.energy, sun.data.angle = 6.0, math.radians(2.5)
        sun.data.color = (1.0, 0.98, 0.95)
        # 방 뒤쪽 위에서 카메라 쪽으로 비춘다: 가구 그림자가 카메라에 보이는 쪽 바닥에 떨어진다
        sun.rotation_euler = Vector((0.35, -0.55, -0.76)).normalized().to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(sun)

    # 천장 면광(천장 바로 아래): 창 없는 쪽도 어둡게 묻히지 않게 넓고 약하게
    fill = bpy.data.objects.new("LGT-fill", bpy.data.lights.new("LGT-fill", "AREA"))
    fill.data.shape, fill.data.size, fill.data.size_y = "RECTANGLE", w * 0.9, d * 0.9
    fill.data.energy = (1.5 if not sun_job else 2.0) * w * d
    fill.data.color = (1.0, 1.0, 1.0)
    fill.location = (center.x, center.y, ceiling_h - 0.02)
    sc.collection.objects.link(fill)

    # 카메라: 방 바닥·벽 윗모서리가 모두 들어오게 맞춘 뒤 조금 물린다
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.lens = 30
    cam.data.sensor_fit = "HORIZONTAL"
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.rotation_euler = (-VIEW_DIR).to_track_quat("-Z", "Y").to_euler()
    pts = []
    for z in (0.0, 2.4):
        for sx in (-1, 1):
            for sy in (-1, 1):
                pts += [center.x + sx * w / 2, center.y + sy * d / 2, z]
    rw = int(os.getenv("BLENDER_WIDTH") or 1600)  # 작은 서버는 줄여서 쓴다 (.env)
    sc.render.resolution_x, sc.render.resolution_y = rw, rw * 9 // 16
    if view:  # 웹 화면(3:2)과 같은 자리·방향·화각
        sc.render.resolution_y = rw * 2 // 3
        eye, target = gl_to_bl(view["pos"]), gl_to_bl(view["target"])
        cam.location = eye
        if (target - eye).length > 1e-6:
            cam.rotation_euler = (eye - target).to_track_quat("Z", "Y").to_euler()
        cam.data.sensor_fit = "VERTICAL"
        cam.data.angle_y = math.radians(view["fov"])
        cam.data.clip_start, cam.data.clip_end = 0.05, extent * 10
        return
    bpy.context.view_layer.update()
    loc, _ = cam.camera_fit_coords(bpy.context.evaluated_depsgraph_get(), pts)
    cam.location = Vector(loc) + VIEW_DIR * extent * 0.02
    cam.data.clip_end = extent * 10


def render_settings(engine):
    sc = bpy.context.scene
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    if (engine or "CYCLES").upper() == "CYCLES":  # 기본: CPU 경로 추적 + 노이즈 제거 (i7 기준 30초 안팎)
        sc.render.engine = "CYCLES"
        sc.cycles.device = os.getenv("BLENDER_DEVICE", "CPU")
        sc.cycles.samples = int(os.getenv("BLENDER_SAMPLES", 64))
        sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 6
    else:
        sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
        ee = sc.eevee
        for attr, val in (("use_raytracing", True), ("use_shadows", True), ("taa_render_samples", 64),
                          ("use_gtao", True), ("fast_gi_method", "GLOBAL_ILLUMINATION")):
            if hasattr(ee, attr):
                try:
                    setattr(ee, attr, val)
                except (TypeError, ValueError):
                    pass
    vs = sc.view_settings
    for vt, look in (("AgX", "AgX - Medium High Contrast"), ("Filmic", "Medium High Contrast")):
        try:
            vs.view_transform = vt
            try:
                vs.look = look
            except TypeError:
                pass
            break
        except TypeError:
            continue
    vs.exposure = -0.3
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"


def main():
    job = args()
    center, floor, ceiling_h, inside = build(job)
    light_and_camera(center, floor, ceiling_h, job.get("sun"), job.get("camera"), inside)
    render_settings(job.get("engine"))
    if job.get("camera") and not inside:
        bpy.context.scene.view_settings.exposure = 0.15  # 지붕 없이 내려다보는 그림은 조금 밝게
    if job.get("out_png"):
        bpy.context.scene.render.filepath = job["out_png"]
        bpy.ops.render.render(write_still=True)
    if job.get("out_blend"):
        bpy.ops.wm.save_as_mainfile(filepath=job["out_blend"])


main()
