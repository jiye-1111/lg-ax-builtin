"""모션 캡처 걷기(CMU, BVH)를 build_person.py의 MakeHuman 뼈대로 옮긴다.

방법: 뼈마다 '기준 자세(BVH 첫 프레임 T자)에서 얼마나 돌았는지'를 월드 기준으로 재서 사람 뼈에 똑같이 준다.
팔·다리는 먼저 사람의 쉬는 자세를 T자 방향으로 맞춘 뒤 돌린다(MakeHuman은 A자 팔).
골반은 앞으로 가는 몫을 빼서 제자리 걸음으로 만든다. 앞으로 가는 건 웹이 경로를 따라 옮긴다.
한 주기(왼발 딛기 → 다음 왼발 딛기)만 골라 끝을 처음에 이어 붙여 끊김 없이 반복한다.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # services/blender-worker
from worker.walkcycle import close_loop, detrend_root, pick_cycle  # noqa: E402

# 사람 뼈 → BVH 뼈. 같은 BVH 뼈를 쓰는 사람 뼈들은 한 덩어리로 같이 돈다
MAP = {
    "root": "Hips", "spine05": "LowerBack", "spine04": "LowerBack", "spine03": "Spine", "spine02": "Spine",
    "spine01": "Spine1", "neck01": "Neck", "neck02": "Neck", "neck03": "Neck1", "head": "Head",
}
for s, S in (("L", "Left"), ("R", "Right")):
    MAP.update({
        f"pelvis.{s}": "Hips", f"upperleg01.{s}": f"{S}UpLeg", f"upperleg02.{s}": f"{S}UpLeg",
        f"lowerleg01.{s}": f"{S}Leg", f"lowerleg02.{s}": f"{S}Leg", f"foot.{s}": f"{S}Foot", f"toe1-1.{s}": f"{S}ToeBase",
        f"clavicle.{s}": f"{S}Shoulder", f"shoulder01.{s}": f"{S}Shoulder", f"upperarm01.{s}": f"{S}Arm",
        f"upperarm02.{s}": f"{S}Arm", f"lowerarm01.{s}": f"{S}ForeArm", f"lowerarm02.{s}": f"{S}ForeArm",
        f"wrist.{s}": f"{S}Hand",
    })
# 쉬는 자세 방향을 BVH T자에 맞출 덩어리: (첫 뼈, 끝 뼈) → 이 구간의 방향을 BVH 뼈 방향에 맞춘다
ALIGN = {}
for s, S in (("L", "Left"), ("R", "Right")):
    ALIGN.update({
        f"{S}UpLeg": (f"upperleg01.{s}", f"upperleg02.{s}"), f"{S}Leg": (f"lowerleg01.{s}", f"lowerleg02.{s}"),
        f"{S}Shoulder": (f"clavicle.{s}", f"clavicle.{s}"), f"{S}Arm": (f"upperarm01.{s}", f"upperarm02.{s}"),
        f"{S}ForeArm": (f"lowerarm01.{s}", f"lowerarm02.{s}"),
    })
HEAD_UP_DEG = 12
# MakeHuman 몸이 CMU 배우보다 엉덩이·옷이 두꺼워 팔을 그대로 옮기면 손이 허벅지 앞을 지난다. 어깨에서 팔을 살짝 벌린다
ARM_OUT_DEG = 7
ARM_CHAIN = ("upperarm01", "upperarm02", "lowerarm01", "lowerarm02", "wrist")  # CMU BVH는 고개가 살짝 숙여져 있다 (README: 10~15° 들어 주면 자연스럽다)


def _q(m: Matrix) -> Quaternion:
    return m.to_3x3().to_quaternion()


def retarget_walk(rig, bvh: Path, fps: int = 30) -> dict:
    """rig에 'walk' 동작을 만든다. 돌려주는 값: 한 주기 길이(초)·한 주기에 가는 거리(m)·자연 빠르기."""
    before = set(bpy.data.objects)
    bpy.ops.import_anim.bvh(filepath=str(bvh), global_scale=1.0, use_fps_scale=False, rotate_mode="NATIVE",
                            axis_forward="-Z", axis_up="Y")
    src = next(o for o in bpy.data.objects if o not in before and o.type == "ARMATURE")
    act = src.animation_data.action
    n_last = int(act.frame_range[1])
    with open(bvh) as f:
        src_fps = next(round(1.0 / float(ln.split(":")[1])) for ln in f if ln.strip().startswith("Frame Time"))
    sc = bpy.context.scene
    names = sorted(set(MAP.values()) | {"LeftToeBase", "RightToeBase"})

    def sample(fr: float):
        sc.frame_set(int(math.floor(fr)), subframe=fr - math.floor(fr))
        W = src.matrix_world
        out = {}
        for n in names:
            pb = src.pose.bones[n]
            m = W @ pb.matrix
            out[n] = (m.to_translation().copy(), _q(m), (W @ pb.tail).copy())
        return out

    ref = sample(1)  # T자
    frames = list(range(2, n_last + 1))
    S = [sample(f) for f in frames]
    P = lambda n: np.array([[*s[n][0]] for s in S])  # noqa: E731
    root, lf, rf = P("Hips"), P("LeftFoot"), P("RightFoot")
    a, b = pick_cycle(root, lf, rf, src_fps)
    T = (b - a) / src_fps

    # 크기: 사람 다리 길이 / BVH 다리 길이
    tb = rig.data.bones
    leg_t = (tb["upperleg01.L"].head_local - tb["lowerleg02.L"].tail_local).length
    leg_s = (ref["LeftUpLeg"][0] - ref["LeftFoot"][0]).length
    k = leg_t / leg_s

    # 걷는 쪽을 사람 정면(-Y)으로 돌리는 회전, T자가 보는 쪽을 -Y로 돌리는 회전
    def yaw_to_negy(v: Vector) -> Quaternion:
        ang = math.atan2(v.x, -v.y)  # -Y에서 v까지 각
        return Quaternion((0, 0, 1), -ang)
    travel = Vector(root[b] - root[a]); travel.z = 0
    fix = yaw_to_negy(travel)
    left = ref["LeftUpLeg"][0] - ref["RightUpLeg"][0]; left.z = 0
    fwd_ref = left.cross(Vector((0, 0, 1)))
    ref_fix = yaw_to_negy(fwd_ref)

    # 사람 쉬는 자세(월드 회전)와 팔·다리 T자 맞춤
    rest_w = {n: _q(tb[n].matrix_local) for n in MAP}
    align = {}
    for sb, (b0, b1) in ALIGN.items():
        d_t = (tb[b1].tail_local - tb[b0].head_local).normalized()
        d_s = (ref_fix @ (ref[sb][2] - ref[sb][0])).normalized()
        align[sb] = d_t.rotation_difference(d_s)
    for S in ("Left", "Right"):  # 손은 아래팔과 같이 맞춘다 (안 그러면 손목이 A자 각도만큼 꺾인다)
        align[f"{S}Hand"] = align[f"{S}ForeArm"]
    arm_out = {"L": Quaternion((0, 1, 0), -math.radians(ARM_OUT_DEG)), "R": Quaternion((0, 1, 0), math.radians(ARM_OUT_DEG))}
    head_up = Quaternion((1, 0, 0), math.radians(HEAD_UP_DEG))

    # 30 fps로 다시 찍을 BVH 프레임 (주기 끝 = 처음과 같은 자세라 마지막은 처음으로 닫는다)
    K = max(8, round(T * fps))
    picks = [frames[0] + a + (b - a) * i / K for i in range(K + 1)]
    root_src = np.array([[*sample(fr)["Hips"][0]] for fr in picks])
    local, trav = detrend_root(root_src)
    stride = float(np.linalg.norm(trav[:2])) * k
    rot_local = np.array([[*(fix @ Vector(v))] for v in local]) * k
    rot_local[:, 2] += (root_src[0, 2] - ref["Hips"][0].z) * k  # T자에 비해 걸을 때 골반이 낮은 만큼
    rot_local = close_loop(rot_local, blend=max(2, K // 6))

    pbs = rig.pose.bones
    order = [pb for pb in pbs if pb.name in MAP or pb.name.startswith("finger")]
    curl = {pb.name: pb.rotation_quaternion.copy() for pb in pbs}  # build_person가 정해 둔 손가락 굽힘

    keys = {n: [] for n in MAP}
    for i, fr in enumerate(picks):
        s = sample(fr)
        want = {}
        for n, sb in MAP.items():
            d = fix @ s[sb][1] @ (ref_fix @ ref[sb][1]).inverted()
            q = d @ align.get(sb, Quaternion()) @ rest_w[n]
            if n == "head":
                q = q @ head_up
            elif n.split(".")[0] in ARM_CHAIN:
                q = arm_out[n[-1]] @ q
            want[n] = q
        # 월드 회전 → 뼈 로컬 회전 (부모 쪽부터)
        posed = {}
        for pb in order:
            n = pb.name
            if n not in MAP:
                continue
            bw = Matrix(tb[n].matrix_local)
            if pb.parent is None:
                parent_w = Matrix()
                rest_rel = bw
            else:
                parent_w = posed[pb.parent.name]
                rest_rel = tb[pb.parent.name].matrix_local.inverted() @ bw
            base = parent_w @ rest_rel
            local_q = _q(base).inverted() @ want[n]
            posed[n] = base @ local_q.to_matrix().to_4x4()
            keys[n].append(local_q)
        # 골반 이동 (뼈 로컬 축)
        keys.setdefault("_root_loc", []).append(Vector(rot_local[i]))

    # 이음매: 쿼터니언 끝을 처음 쪽으로 (부호 맞춘 뒤 같은 close_loop)
    rig.animation_data_create()
    walk = bpy.data.actions.new("walk")
    walk.use_fake_user = True
    rig.animation_data.action = walk
    m_root = tb["root"].matrix_local.to_3x3()
    for n, qs in keys.items():
        if n == "_root_loc":
            continue
        arr = np.array([[*q] for q in qs])
        for i in range(1, len(arr)):
            if np.dot(arr[i], arr[i - 1]) < 0:
                arr[i] = -arr[i]
        if np.dot(arr[-1], arr[0]) < 0:
            arr[-1] = -arr[-1]
        arr = close_loop(arr, blend=max(2, K // 6))
        arr /= np.linalg.norm(arr, axis=1, keepdims=True)
        keys[n] = arr
    for i in range(K + 1):
        for pb in pbs:
            pb.rotation_mode = "QUATERNION"
            if pb.name in keys:
                pb.rotation_quaternion = Quaternion(keys[pb.name][i])
            else:
                pb.rotation_quaternion = curl[pb.name]
            pb.location = Vector()
        pbs["root"].location = m_root.inverted() @ keys["_root_loc"][i]
        for pb in pbs:
            pb.keyframe_insert("rotation_quaternion", frame=i)
            if pb.name == "root":
                pb.keyframe_insert("location", frame=i)
    track = rig.animation_data.nla_tracks.new()
    track.name = "walk"
    track.strips.new("walk", 0, walk)
    rig.animation_data.action = None
    bpy.data.objects.remove(src, do_unlink=True)
    bpy.data.actions.remove(act)  # BVH 동작은 glb에 넣지 않는다
    return {"cycle_s": K / fps, "frames": K, "stride_m": stride, "speed_mps": stride / (K / fps), "src": bvh.name,
            "src_frames": [frames[0] + a, frames[0] + b]}


def plant_feet(rig, shoes, frames: int, action_name: str = "walk") -> list[float]:
    """걸을 때는 늘 한 발이 바닥에 있다: 프레임마다 신발 맨 아래가 바닥(z=0)에 닿게 골반 높이를 고친다.
    돌려주는 값: 프레임별로 고친 높이(m, 확인용)"""
    act = bpy.data.actions[action_name]
    rig.animation_data.action = act
    sc = bpy.context.scene
    low = []
    for fr in range(frames + 1):
        sc.frame_set(fr)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = shoes.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        low.append(min((mw @ v.co).z for v in me.vertices))
        ev.to_mesh_clear()
    z = np.array(low)
    z = np.convolve(np.r_[z[-2:-1], z, z[1:2]], np.ones(3) / 3, mode="valid")  # 한 프레임 튐만 누그러뜨린다 (고리라 양 끝을 이어 붙임)
    z[-1] = z[0]
    m_inv = rig.data.bones["root"].matrix_local.to_3x3().inverted()
    fcs = {}
    for fc in _fcurves(act):
        if fc.data_path == 'pose.bones["root"].location':
            fcs[fc.array_index] = fc
    for fr in range(frames + 1):
        d = m_inv @ Vector((0, 0, -float(z[fr])))
        for i in range(3):
            kp = next(k for k in fcs[i].keyframe_points if round(k.co.x) == fr)
            kp.co.y += d[i]
            kp.handle_left.y += d[i]
            kp.handle_right.y += d[i]
    for fc in fcs.values():
        fc.update()
    rig.animation_data.action = None
    return [float(v) for v in z]


def _fcurves(act):
    """Blender 4.4+ 레이어 동작과 예전 동작 둘 다"""
    if hasattr(act, "fcurves") and len(act.fcurves):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out
