"""동선을 걷는 사람 모델 (apps/web/models/people/walker.glb).

몸은 MakeHuman 기본 메시·뼈대·가중치(CC0, github.com/makehumancommunity/makehuman)를 쓰고,
옷·신발은 MakeHuman 보조 메시(helper-tights)를, 머리카락은 두피 면을 떼어 띄워 만든다. 걷기 동작은 여기서 키프레임으로 만든다.
가져온 에셋은 없다 (MakeHuman 데이터는 scripts/fetch_makehuman.sh로 받는다).

실행:
  blender -b -P build_person.py -- --mh <makehuman/data> --out apps/web/models/people/walker.glb
  또는 pip bpy 환경에서 python build_person.py --mh ... --out ...

결과: 키 170 cm(신발 포함), 원점 = 두 발 사이 바닥, 정면 +Z(glTF), 동작 "walk"(제자리 걸음 1주기)와 "idle".
walk 한 주기 = 두 걸음. 웹(walker.js)은 WALK_SPEED(1.3 m/s)로 옮기고 이 동작을 STRIDE에 맞춰 돌린다.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

HEIGHT_M = 1.70
FPS = 30
CYCLE_FRAMES = 32           # 한 주기(두 걸음) 32프레임 = 1.067 s
STRIDE_M = 1.3 * CYCLE_FRAMES / FPS  # 1.3 m/s로 걸을 때 한 주기에 가는 거리 (한 걸음 ≈ 0.69 m)

# 얼굴·혀·가슴 같은 잔뼈는 큰 뼈에 합친다 (glb를 가볍게, 걷기에는 안 쓴다)
KEEP = {"root", "spine05", "spine04", "spine03", "spine02", "spine01", "neck01", "neck02", "neck03", "head",
        "pelvis.L", "pelvis.R", "upperleg01.L", "upperleg01.R", "upperleg02.L", "upperleg02.R",
        "lowerleg01.L", "lowerleg01.R", "lowerleg02.L", "lowerleg02.R", "foot.L", "foot.R",
        "toe1-1.L", "toe1-1.R", "clavicle.L", "clavicle.R", "shoulder01.L", "shoulder01.R",
        "upperarm01.L", "upperarm01.R", "upperarm02.L", "upperarm02.R", "lowerarm01.L", "lowerarm01.R",
        "lowerarm02.L", "lowerarm02.R", "wrist.L", "wrist.R"}
for s in "LR":
    for f in range(1, 6):
        for k in (1, 2, 3):
            KEEP.add(f"finger{f}-{k}.{s}")

# 옷 색·재질 (집 안 평상복: 오트밀 니트, 진청 면바지, 흰 운동화)
# 색은 선형(linear) 값. 괄호 안은 화면에 보이는 sRGB 근사
MATS = {
    "skin": dict(color=(0.50, 0.29, 0.19), rough=0.6),     # #BD9379
    "shirt": dict(color=(0.30, 0.26, 0.20), rough=0.95),   # #948B7C 오트밀
    "pants": dict(color=(0.022, 0.028, 0.045), rough=0.9),  # #29303B 진청
    "shoes": dict(color=(0.78, 0.78, 0.76), rough=0.55),    # #E5E5E2
    "sole": dict(color=(0.12, 0.11, 0.10), rough=0.8),
    "hair": dict(color=(0.012, 0.010, 0.009), rough=0.45),
    "eye": dict(color=(0.75, 0.72, 0.68), rough=0.2),
    "iris": dict(color=(0.02, 0.012, 0.008), rough=0.15),
}


# ---------- MakeHuman 데이터 읽기 ----------
def read_obj(path: Path):
    vs, faces = [], []
    group = None
    for line in path.read_text().splitlines():
        if line.startswith("v "):
            vs.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("g "):
            group = line.split()[1]
        elif line.startswith("f "):
            faces.append(([int(t.split("/")[0]) - 1 for t in line.split()[1:]], group))
    return np.array(vs), faces


def apply_target(vs: np.ndarray, path: Path, w: float = 1.0):
    for line in path.read_text().splitlines():
        if not line or line[0] == "#":
            continue
        i, x, y, z = line.split()
        vs[int(i)] += w * np.array([float(x), float(y), float(z)])


def mh_to_blender(v):
    """MakeHuman (Y-up, 정면 +Z, 단위 dm) → Blender (Z-up, 정면 -Y, 단위 m)."""
    return np.stack([v[:, 0], -v[:, 2], v[:, 1]], axis=1) * 0.1


# ---------- 메시 만들기 ----------
def make_mesh(name, verts, faces, mat_of_face, mats):
    used = sorted({i for f in faces for i in f})
    remap = {o: n for n, o in enumerate(used)}
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(verts[i]) for i in used], [], [[remap[i] for i in f] for f in faces])
    for m in mats:
        me.materials.append(m)
    for p, mi in zip(me.polygons, mat_of_face):
        p.material_index = mi
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob, used


def material(name):
    d = MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*d["color"], 1)
    b.inputs["Roughness"].default_value = d["rough"]
    return m


def vnormals(V: np.ndarray, faces) -> np.ndarray:
    """꼭짓점 법선. 같은 자리에 겹친 꼭짓점(메시 이음매)은 법선을 같이 써서 띄워도 틈이 안 벌어진다."""
    N = np.zeros_like(V)
    for f in faces:
        p = V[f]
        n = np.zeros(3)
        for a, b in zip(p, np.roll(p, -1, axis=0)):  # Newell
            n += np.cross(a, b)
        N[f] += n
    key = {}
    for i in {i for f in faces for i in f}:
        key.setdefault(tuple(np.round(V[i] * 1e4).astype(int)), []).append(i)
    for idx in key.values():
        s = N[idx].sum(axis=0)
        N[idx] = s / (np.linalg.norm(s) + 1e-12)
    return N


def main(mh: Path, out: Path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = FPS

    vs, faces = read_obj(mh / "3dobjs" / "base.obj")
    # 20대 동양인 남성, 보통 근육·체중 (MakeHuman 매크로 타깃)
    apply_target(vs, mh / "targets/macrodetails/asian-male-young.target")
    apply_target(vs, mh / "targets/macrodetails/universal-male-young-averagemuscle-averageweight.target")
    skel = json.loads((mh / "rigs/default.mhskel").read_text())
    weights = json.loads((mh / "rigs/default_weights.mhw").read_text())["weights"]

    # 잔뼈 가중치를 남길 뼈로 합친다
    bones = skel["bones"]

    def kept(b):
        while b not in KEEP:
            b = bones[b]["parent"]
        return b

    vw: dict[int, dict[str, float]] = {}
    for b, lst in weights.items():
        kb = kept(b)
        for i, w in lst:
            d = vw.setdefault(i, {})
            d[kb] = d.get(kb, 0.0) + w

    def region(i):
        d = vw.get(i, {})
        if not d:
            return "none"
        b = max(d, key=d.get)
        if b.startswith(("upperleg", "lowerleg", "pelvis")) or b == "root":
            return "legs"
        if b.startswith(("foot", "toe")):
            return "feet"
        if b.startswith(("upperarm", "lowerarm01")):
            return "arm"
        if b.startswith(("spine", "clavicle", "shoulder")):
            return "torso"
        if b.startswith(("lowerarm02",)):
            return "forearm"
        if b.startswith(("wrist", "finger")):
            return "hands"
        return "head"

    V = mh_to_blender(vs)
    joint = {k: V[idx].mean(axis=0) for k, idx in skel["joints"].items()}

    # 키 170 cm에 맞춘다 (발바닥 0, 정수리 1.70 — 신발 바닥 두께 1.5 cm 포함)
    body_idx = sorted({i for f, g in faces if g == "body" for i in f})
    zmin, zmax = V[body_idx, 2].min(), V[body_idx, 2].max()
    k = (HEIGHT_M - 0.015) / (zmax - zmin)
    cx, cy = V[body_idx, 0].mean(), V[body_idx, 1].mean()
    V = (V - [cx, cy, zmin]) * k + [0, 0, 0.015]
    joint = {n: (p - [cx, cy, zmin]) * k + [0, 0, 0.015] for n, p in joint.items()}

    M = {n: material(n) for n in MATS}
    objs = []

    # 허리선: 골반 관절 높이 조금 위. 셔츠는 그보다 아래까지 내려와 바지 허리를 덮는다
    waist_z = float(joint[bones["upperleg01.L"]["head"]][2]) + 0.10
    hem_z = waist_z - 0.12

    def zc(f):
        return float(V[f, 2].mean())

    def dom(f):
        rs = [region(i) for i in f]
        return max(set(rs), key=rs.count)

    # 몸: 옷에 덮이는 곳(몸통·윗팔·다리·발)은 지워서 걸을 때 옷 밖으로 비치지 않게
    covered = {"legs", "torso", "feet", "arm"}
    body_faces = [f for f, g in faces if g == "body" and not all(region(i) in covered for i in f)]
    body, used = make_mesh("body", V, body_faces, [0] * len(body_faces), [M["skin"]])
    objs.append((body, used))

    # 옷: tights 보조 메시(몸을 감싼 껍데기)를 셔츠(긴소매 니트)·바지·신발로 나눈다
    tights = [f for f, g in faces if g == "helper-tights"]
    arm_v = {i for f in tights if dom(f) == "arm" for i in f}
    shirt_f = [f for f in tights if dom(f) == "arm" or (dom(f) in ("torso", "legs") and V[f, 2].max() > hem_z)]
    pants_f = [f for f in tights if dom(f) in ("legs", "torso") and V[f, 2].min() < waist_z]
    shoe_f = [f for f in tights if dom(f) == "feet"]

    # 셔츠: 밑단을 한 높이로 반듯하게, 니트처럼 몸에서 1 cm 남짓 띄운다
    n_sh = vnormals(V, shirt_f)
    Vs = V.copy()
    for i in {i for f in shirt_f for i in f}:
        if i not in arm_v:
            Vs[i, 2] = max(Vs[i, 2], hem_z)
        Vs[i] += n_sh[i] * 0.011
    ob, used = make_mesh("shirt", Vs, shirt_f, [0] * len(shirt_f), [M["shirt"]])
    objs.append((ob, used))
    # 바지: 허리는 셔츠 안쪽에서 끝나고, 무릎 아래로 갈수록 통이 넓어지는 일자바지
    n_pa = vnormals(V, pants_f)
    Vp = V.copy()
    for i in {i for f in pants_f for i in f}:
        Vp[i, 2] = min(Vp[i, 2], waist_z)
        t = min(1.0, max(0.0, (0.55 - Vp[i, 2]) / 0.45))
        Vp[i] += n_pa[i] * (0.006 + 0.012 * t)
    ob, used = make_mesh("pants", Vp, pants_f, [0] * len(pants_f), [M["pants"]])
    objs.append((ob, used))
    # 신발: 발 둘레를 부풀리고 아래쪽은 밑창 색, 바닥은 평평하게
    n_so = vnormals(V, shoe_f)
    Vf = V.copy()
    for i in {i for f in shoe_f for i in f}:
        Vf[i] += n_so[i] * 0.009
        Vf[i, 2] = max(Vf[i, 2], 0.0)
    shoe_mat = [1 if Vf[f, 2].mean() < 0.03 else 0 for f in shoe_f]
    ob, used = make_mesh("shoes", Vf, shoe_f, shoe_mat, [M["shoes"], M["sole"]])
    objs.append((ob, used))

    # 머리카락: 두피(몸 메시 머리 부분)를 그대로 떼어 띄운 짧은 머리. 이마·귀 위·뒷목 선을 따라 자른다
    eye_z = float(joint[bones["eye.L"]["head"]][2])
    head_f = [f for f, g in faces if g == "body" and dom(f) == "head" and V[f, 2].mean() > eye_z - 0.09]
    hc = V[sorted({i for f in head_f for i in f})].mean(axis=0)

    def hairline(p):
        d = p[:2] - hc[:2]
        front = -d[1] / (np.linalg.norm(d) + 1e-9)  # 앞(-Y) = 1, 뒤 = -1
        return eye_z + 0.028 + (0.022 * front if front > 0 else 0.09 * front)

    hair_f = [f for f in head_f if all(V[i, 2] > hairline(V[i]) for i in f)]
    n_ha = vnormals(V, hair_f)
    Vh = V.copy()
    for i in {i for f in hair_f for i in f}:
        top = min(1.0, max(0.0, (V[i, 2] - eye_z) / 0.10))
        Vh[i] += n_ha[i] * (0.004 + 0.010 * top)
    ob, used = make_mesh("hair", Vh, hair_f, [0] * len(hair_f), [M["hair"]])
    objs.append((ob, used))
    # 눈
    eye_f = [f for f, g in faces if g in ("helper-l-eye", "helper-r-eye")]
    eye_c = {g: V[sorted({i for f, gg in faces if gg == g for i in f})].mean(axis=0) for g in ("helper-l-eye", "helper-r-eye")}
    eye_mat = []
    for f, g in [(f, g) for f, g in faces if g in ("helper-l-eye", "helper-r-eye")]:
        n = V[f].mean(axis=0) - eye_c[g]
        eye_mat.append(1 if -n[1] / (np.linalg.norm(n) + 1e-9) > 0.82 else 0)  # 앞쪽(-Y) 동공
    ob, used = make_mesh("eyes", V, eye_f, eye_mat, [M["eye"], M["iris"]])
    objs.append((ob, used))

    # ---------- 뼈대 ----------
    arm = bpy.data.armatures.new("rig")
    rig = bpy.data.objects.new("person", arm)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = {}
    for n in sorted(KEEP, key=lambda b: 0 if b == "root" else 1):
        b = arm.edit_bones.new(n)
        b.head = Vector(joint[bones[n]["head"]])
        b.tail = Vector(joint[bones[n]["tail"]])
        if (b.tail - b.head).length < 1e-4:
            b.tail = b.head + Vector((0, 0, 0.02))
        eb[n] = b
    for n in KEEP:
        p = bones[n]["parent"]
        if p:
            eb[n].parent = eb[kept(p)]
    # 뼈 roll: 무릎·팔꿈치가 옆축(X)으로 굽게 맞춘다
    for b in arm.edit_bones:
        b.align_roll(Vector((0, -1, 0)) if abs((b.tail - b.head).normalized().z) > 0.5 else Vector((0, 0, 1)))
    bpy.ops.object.mode_set(mode="OBJECT")

    for ob, used in objs:
        ob.parent = rig
        mod = ob.modifiers.new("rig", "ARMATURE")
        mod.object = rig
        for n in KEEP:
            ob.vertex_groups.new(name=n)
        for new_i, old_i in enumerate(used):
            for b, w in vw.get(old_i, {}).items():
                ob.vertex_groups[b].add([new_i], w, "REPLACE")

    animate(rig)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(out), export_format="GLB", use_selection=True, export_animations=True,
                              export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_step=2,
                              export_optimize_animation_size=True, export_def_bones=False, export_yup=True,
                              export_apply=False, export_skins=True, export_morph=False)
    print("saved", out, out.stat().st_size // 1024, "KB")


# ---------- 걷기 동작 ----------
def world_rot(pb, q_world: Quaternion):
    """부모가 쉬는 자세라고 보고, 월드 기준 회전을 뼈 로컬 회전으로."""
    m = pb.bone.matrix_local.to_3x3()
    return (m.inverted() @ q_world.to_matrix() @ m).to_quaternion()


def ax(axis, deg):
    return Quaternion(Vector(axis), math.radians(deg))


def bump(phase, center, width):
    d = (phase - center + 0.5) % 1.0 - 0.5
    return math.exp(-(d / width) ** 2)


def arm_down(rig, side):
    """MakeHuman 기본 A자 팔을 몸 옆으로 내린다 (월드 회전)."""
    pb = rig.pose.bones[f"upperarm01.{side}"]
    d = (pb.bone.tail_local - pb.bone.head_local).normalized()
    sx = 1 if side == "L" else -1
    target = Vector((0.12 * sx, 0.04, -1)).normalized()
    return d.rotation_difference(target)


def pose(rig, phase, walking=True):
    """phase 0~1 = 한 주기. 0에서 왼발 뒤꿈치가 닿는다."""
    P = rig.pose.bones
    X = (1, 0, 0)  # 옆축: +X로 돌리면 앞쪽(-Y)이 위로 → 다리를 앞으로 든다
    for pb in P:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector()
    a = 1.0 if walking else 0.0
    c = math.cos(2 * math.pi * phase)
    for side, off in (("L", 0.0), ("R", 0.5)):
        ph = (phase + off) % 1.0
        cc = math.cos(2 * math.pi * ph)
        hip = a * (24 * cc - 4)                                          # 앞 24° ~ 뒤 -28°
        knee = 4 + a * (12 * bump(ph, 0.1, 0.08) + 58 * bump(ph, 0.72, 0.12))
        ankle = a * (6 * bump(ph, 0.0, 0.06) - 14 * bump(ph, 0.6, 0.07) + 4 * bump(ph, 0.8, 0.1))
        P[f"upperleg01.{side}"].rotation_quaternion = world_rot(P[f"upperleg01.{side}"], ax(X, hip))
        P[f"lowerleg01.{side}"].rotation_quaternion = world_rot(P[f"lowerleg01.{side}"], ax(X, -knee))
        P[f"foot.{side}"].rotation_quaternion = world_rot(P[f"foot.{side}"], ax(X, ankle))
        # 팔: 같은 쪽 다리와 반대로 흔든다
        swing = -a * 16 * cc
        down = arm_down(rig, side)
        P[f"upperarm01.{side}"].rotation_quaternion = world_rot(P[f"upperarm01.{side}"], ax(X, swing) @ down)
        elbow = 14 + a * 10 * max(0.0, -cc)
        P[f"lowerarm01.{side}"].rotation_quaternion = world_rot(P[f"lowerarm01.{side}"], ax(X, elbow))
        for f in range(2, 6):
            for kk in (1, 2, 3):
                pb = P[f"finger{f}-{kk}.{side}"]
                pb.rotation_quaternion = world_rot(pb, ax(X, 14 + 4 * kk))
    # 골반: 걸음마다 오르내리고(2 cm), 좌우로 살짝 돈다. 상체는 반대로 돌아 균형
    root = P["root"]
    root.location = Vector((0, 0, 0))
    bob = a * 0.018 * (0.5 - 0.5 * math.cos(4 * math.pi * phase)) - a * 0.012
    root.rotation_quaternion = world_rot(root, ax((0, 0, 1), a * 4 * c))
    q = root.rotation_quaternion
    # root 뼈 이동은 로컬 축이라 월드 Z를 로컬로 바꿔 준다
    m = root.bone.matrix_local.to_3x3()
    root.location = m.inverted() @ Vector((0, 0, bob))
    sp = P["spine03"]
    sp.rotation_quaternion = world_rot(sp, ax((0, 0, 1), -a * 6 * c) @ ax(X, -3 * a))
    nk = P["neck01"]
    nk.rotation_quaternion = world_rot(nk, ax((0, 0, 1), a * 2 * c))
    _ = q


def animate(rig):
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    rig.animation_data_create()
    for name, frames, walking in (("walk", CYCLE_FRAMES, True), ("idle", 30, False)):
        act = bpy.data.actions.new(name)
        act.use_fake_user = True
        rig.animation_data.action = act
        for fr in range(0, frames + 1):
            ph = fr / frames
            pose(rig, ph, walking)
            if not walking:  # 서 있을 때 숨쉬기만
                P = rig.pose.bones
                P["spine03"].rotation_quaternion = world_rot(P["spine03"], ax((1, 0, 0), 1.2 * math.sin(2 * math.pi * ph)))
            for pb in rig.pose.bones:
                pb.keyframe_insert("rotation_quaternion", frame=fr)
                if pb.name == "root":
                    pb.keyframe_insert("location", frame=fr)
        track = rig.animation_data.nla_tracks.new()
        track.name = name
        track.strips.new(name, 0, act)
        rig.animation_data.action = None
    bpy.ops.object.mode_set(mode="OBJECT")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--mh", type=Path, required=True, help="MakeHuman data 폴더 (3dobjs, rigs, targets)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    main(a.mh, a.out)
