"""벽면 맞춤가구 세트: 한 벽을 따라 하부 줄·상부 줄로 장을 늘어놓는다 (docs/specs/wall-run.md).

순수 계산만 한다. 장 하나하나의 외경·부재는 cabinet.normalize가 검사한 설정을 그대로 받는다.
- 정면도 좌표 s(mm): 방 안에서 그 벽을 바라봤을 때 왼쪽 끝이 0, 오른쪽으로 커진다.
- 줄마다 시작 위치(start_mm)부터 [틈(gap_mm) + 장 폭]을 차례로 쌓는다. 겹치게 놓을 수는 없다.
- 사용 폭·남은 폭은 높이 구간(하부·상부)마다 따로 센다. 키큰장은 두 구간을 다 쓴다.
- 창문·문을 가리거나 벽 끝을 넘으면 자리와 까닭을 알린다. 장 크기를 몰래 줄이지 않는다.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

from .cabinet import KINDS

PRESETS_PATH = Path(__file__).resolve().parents[3] / "data" / "catalog" / "cabinet_presets.json"
TIERS = ("base", "wall")
FILLER_MAX_MM = 100      # 벽과 이 안으로 떨어지면 틈막이판으로 메우는 게 보통
WALL_GAP_MM = 5          # 벽 면과 장 등 사이 (스캔 벽이 반듯하지 않아 딱 붙이면 벽을 뚫는다)
LINE_TOL_MM = 2          # 앞선·상판선이 이만큼 안으로 다르면 맞는 것으로 본다

_presets: dict | None = None


def presets() -> dict:
    global _presets
    if _presets is None:
        _presets = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
        _presets["by_id"] = {x["id"]: x for x in _presets["presets"]}
    return _presets


def preset_cfg(preset_id: str) -> dict:
    """프리셋 → 장 설정 (normalize 전). 몸체 높이에 다리(걸레받이)·상판을 더해 외경을 만든다."""
    pr = presets()["by_id"].get(preset_id)
    if pr is None:
        raise ValueError(f"없는 프리셋: {preset_id}")
    kind = pr["kind"]
    spec = KINDS[kind]
    parts = {**spec["parts"], **pr.get("parts", {})}
    cfg = {"kind": kind, "parts": copy.deepcopy(pr.get("parts", {})), "preset": preset_id}
    if pr.get("outer_mm"):
        cfg["outer_mm"] = dict(pr["outer_mm"])
    elif pr.get("body_mm"):
        b = pr["body_mm"]
        cfg["outer_mm"] = {"w": b["w"], "d": b["d"], "h": b["h"] + parts.get("toe_kick", 0) + parts.get("counter", 0)}
    if "base_mm" in pr:
        cfg["base_mm"] = pr["base_mm"]
    return cfg


def body_h(cfg: dict) -> float:
    """몸체 높이 = 외경 − 다리 − 상판."""
    p = cfg["parts"]
    return cfg["outer_mm"]["h"] - p.get("toe_kick", 0) - p.get("counter", 0)


def band(cfg: dict) -> str:
    return KINDS[cfg["kind"]].get("band") or "base"


def wall_axes(start, end, inward_hint, thickness_m: float):
    """벽 → (원점, 오른쪽 방향 r, 안쪽 방향 v, 길이 m, 면까지 거리 m). 원점은 정면도 왼쪽 끝."""
    dx, dz = end[0] - start[0], end[1] - start[1]
    L = math.hypot(dx, dz) or 1e-9
    u = (dx / L, dz / L)
    v = (-u[1], u[0])
    mid = (start[0] + dx / 2, start[1] + dz / 2)
    if v[0] * (inward_hint[0] - mid[0]) + v[1] * (inward_hint[1] - mid[1]) < 0:
        v = (-v[0], -v[1])
    r = (v[1], -v[0])  # 벽을 바라봤을 때 오른쪽 (장 폭 축과 같은 방향)
    flip = u[0] * r[0] + u[1] * r[1] < 0
    origin = tuple(end) if flip else tuple(start)
    return origin, r, v, L, thickness_m / 2, flip


def openings_on_wall(openings, wall_id: str, L: float, flip: bool) -> list[dict]:
    """그 벽의 문·창을 정면도 좌표(mm)로."""
    out = []
    for o in openings:
        if o["wall_id"] != wall_id:
            continue
        a = o["offset_m"] * 1000
        b = a + o["width_m"] * 1000
        if flip:
            a, b = L * 1000 - b, L * 1000 - a
        y0 = 0.0 if o["type"] != "window" else o.get("sill_m", 0) * 1000
        out.append({"id": o["opening_id"], "type": o["type"], "s0": round(a), "s1": round(b),
                    "y0": round(y0), "y1": round(y0 + o["height_m"] * 1000)})
    return sorted(out, key=lambda x: x["s0"])


def _union(spans):
    tot, cur = 0.0, None
    for a, b in sorted(spans):
        if cur is None or a > cur[1]:
            if cur:
                tot += cur[1] - cur[0]
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    if cur:
        tot += cur[1] - cur[0]
    return tot


def _free(spans, L):
    """그 구간에서 비어 있는 폭들 (mm)."""
    out, x = [], 0.0
    for a, b in sorted(spans):
        a, b = max(0.0, a), min(L, b)
        if a > x + 1:
            out.append([round(x), round(a)])
        x = max(x, b)
    if L > x + 1:
        out.append([round(x), round(L)])
    return out


def _yrange(m: dict) -> tuple[float, float]:
    return m["y0"], m["y0"] + m["cfg"]["outer_mm"]["h"]


def layout(wall: dict, run: dict, cfgs: dict) -> dict:
    """벽 한 면의 세트 배치.

    wall: {wall_id, start, end, thickness_m, inward_hint, openings:[Opening dict], height_m?}
    run: {start_mm: {base, wall}, rows: {base: [{id, gap_mm}], wall: [...]}}
    cfgs: 모듈 id → normalize된 장 설정
    돌려줌: {length_mm, modules:[...], usage:{base, wall}, issues:[...], openings:[...]}
    """
    origin, r, v, L, face, flip = wall_axes(wall["start"], wall["end"], wall["inward_hint"], wall.get("thickness_m") or 0.1)
    # 이어진 옆 벽 두께 절반을 뺀 안쪽 면 길이. s = 0은 왼쪽 안쪽 모서리
    a0, a1 = wall.get("inset_start_m", 0.0), wall.get("inset_end_m", 0.0)
    left, right = (a1, a0) if flip else (a0, a1)
    origin = (origin[0] + r[0] * left, origin[1] + r[1] * left)
    L = max(0.01, L - left - right)
    Lmm = L * 1000
    yaw = math.atan2(v[1], v[0])
    modules = []
    for tier in TIERS:
        s = float((run.get("start_mm") or {}).get(tier, 0) or 0)
        for i, row in enumerate((run.get("rows") or {}).get(tier, [])):
            cfg = cfgs[row["id"]]
            s += float(row.get("gap_mm", 0) or 0)
            w, d = cfg["outer_mm"]["w"], cfg["outer_mm"]["d"]
            y0 = float(cfg.get("base_mm", 0) or 0) if (tier == "wall" or KINDS[cfg["kind"]].get("hang")) else 0.0
            cs = (s + w / 2) / 1000
            cv = face + (WALL_GAP_MM + d / 2) / 1000
            modules.append({"id": row["id"], "tier": tier, "idx": i, "s0": round(s, 1), "s1": round(s + w, 1), "y0": y0,
                            "band": band(cfg), "cfg": cfg, "yaw_rad": yaw,
                            "center_xz": [round(origin[0] + r[0] * cs + v[0] * cv, 4), round(origin[1] + r[1] * cs + v[1] * cv, 4)]})
            s += w
    ops = openings_on_wall(wall.get("openings", []), wall["wall_id"], L + left + right, flip)
    for o in ops:  # 안쪽 모서리 기준으로
        o["s0"], o["s1"] = round(o["s0"] - left * 1000), round(o["s1"] - left * 1000)
    issues = []

    def say(code, level, m, label, **kw):
        issues.append({"code": code, "level": level, "id": m["id"] if m else None, "tier": m["tier"] if m else None,
                       "s_mm": round(m["s0"]) if m else None, "label": label, **kw})

    def name(m):
        return KINDS[m["cfg"]["kind"]]["label"] if not m["cfg"].get("preset") else presets()["by_id"].get(m["cfg"]["preset"], {}).get("label", KINDS[m["cfg"]["kind"]]["label"])

    for m in modules:
        if m["s0"] < -0.5:
            say("past_wall", "no", m, f"{name(m)}이 벽 왼쪽 끝을 {round(-m['s0']):,} mm 넘어요")
        if m["s1"] > Lmm + 0.5:
            say("past_wall", "no", m, f"{name(m)}이 벽 오른쪽 끝을 {round(m['s1'] - Lmm):,} mm 넘어요")
        y0, y1 = _yrange(m)
        for o in ops:
            if min(m["s1"], o["s1"]) - max(m["s0"], o["s0"]) <= 0.5 or min(y1, o["y1"]) - max(y0, o["y0"]) <= 0.5:
                continue
            what = {"window": "창문을 가려요", "door": "문을 막아요"}.get(o["type"], "열린 통로를 막아요")
            say("blocks_" + o["type"], "no", m, f"{name(m)}이 {what}", opening=o["id"])
        if m["cfg"].get("preset") == "bench":
            under = [o for o in ops if o["type"] == "window" and min(m["s1"], o["s1"]) - max(m["s0"], o["s0"]) > 0.5]
            if under and y1 <= under[0]["y0"]:
                say("window_swing", "check", m, f"창틀까지 {round(under[0]['y0'] - y1):,} mm 남아요. 창문이 안쪽으로 열리면 열리는 자리를 현장에서 확인하세요")
    # 상부 줄이 하부 줄의 키큰장·장과 겹치는지 (높이까지 봄)
    for a in modules:
        for b in modules:
            if a["tier"] != "wall" or b["tier"] != "base":
                continue
            if min(a["s1"], b["s1"]) - max(a["s0"], b["s0"]) <= 0.5:
                continue
            ay, by = _yrange(a), _yrange(b)
            if min(ay[1], by[1]) - max(ay[0], by[0]) > 0.5:
                say("overlap", "no", a, f"{name(a)}이 아래 {name(b)}과 겹쳐요", other=b["id"])
    # 줄 안 이웃끼리 앞선·상판선·다리선 (알리기만, 맞추기는 따로 누른다)
    base_row = [m for m in modules if m["tier"] == "base"]
    for a, b in zip(base_row, base_row[1:]):
        if b["s0"] - a["s1"] > 0.5 or a["band"] != b["band"] or a["band"] not in ("base",):
            continue
        ca, cb = a["cfg"], b["cfg"]
        if abs(ca["outer_mm"]["d"] - cb["outer_mm"]["d"]) > LINE_TOL_MM:
            say("front_line", "info", b, f"{name(a)}과 {name(b)}의 앞선이 {abs(ca['outer_mm']['d'] - cb['outer_mm']['d']):,} mm 달라요")
        if "counter" in ca["parts"] and "counter" in cb["parts"] and abs(ca["outer_mm"]["h"] - cb["outer_mm"]["h"]) > LINE_TOL_MM:
            say("counter_line", "info", b, f"{name(a)}과 {name(b)}의 상판 높이가 {abs(ca['outer_mm']['h'] - cb['outer_mm']['h']):,} mm 달라요")
    # 마감판·틈막이판이 필요한 곳 (붙이지는 않고 알린다)
    for tier in TIERS:
        row = [m for m in modules if m["tier"] == tier]
        if not row:
            continue
        first, last = row[0], row[-1]
        gl, gr = first["s0"], Lmm - last["s1"]
        if 0.5 < gl <= FILLER_MAX_MM and not first["cfg"]["parts"].get("filler_l"):
            say("filler", "info", first, f"왼쪽 벽과 {round(gl)} mm 떠요. 틈막이판으로 메울 수 있어요", side="l", gap_mm=round(gl))
        elif gl > FILLER_MAX_MM and "end_l" in first["cfg"]["parts"] and not first["cfg"]["parts"].get("end_l"):
            say("end_panel", "info", first, f"{name(first)} 왼쪽 옆면이 드러나요. 측면 마감판을 붙일 수 있어요", side="l")
        if 0.5 < gr <= FILLER_MAX_MM and not last["cfg"]["parts"].get("filler_r"):
            say("filler", "info", last, f"오른쪽 벽과 {round(gr)} mm 떠요. 틈막이판으로 메울 수 있어요", side="r", gap_mm=round(gr))
        elif gr > FILLER_MAX_MM and "end_r" in last["cfg"]["parts"] and not last["cfg"]["parts"].get("end_r"):
            say("end_panel", "info", last, f"{name(last)} 오른쪽 옆면이 드러나요. 측면 마감판을 붙일 수 있어요", side="r")
        for a, b in zip(row, row[1:]):
            gap = b["s0"] - a["s1"]
            if gap > FILLER_MAX_MM and "end_r" in a["cfg"]["parts"] and not a["cfg"]["parts"].get("end_r"):
                say("end_panel", "info", a, f"{name(a)} 오른쪽 옆면이 드러나요. 측면 마감판을 붙일 수 있어요", side="r")
    for m in modules:
        k = m["cfg"]["kind"]
        if k == "corner":
            row = [x for x in modules if x["tier"] == m["tier"]]
            end_ok = (m["cfg"]["parts"]["corner"] == "r" and m is row[-1]) or (m["cfg"]["parts"]["corner"] == "l" and m is row[0])
            if not end_ok:
                say("corner_end", "check", m, "코너장은 꺾이는 쪽이 줄 끝에 있어야 해요")
    spans = {t: [] for t in TIERS}
    for m in modules:
        spans["base" if m["tier"] == "base" else "wall"].append((m["s0"], m["s1"]))
        if m["tier"] == "base" and m["band"] == "tall":
            spans["wall"].append((m["s0"], m["s1"]))
    usage = {}
    for t in TIERS:
        clipped = [(max(0.0, a), min(Lmm, b)) for a, b in spans[t] if b > 0 and a < Lmm]
        used = _union(clipped)
        usage[t] = {"used_mm": round(used), "left_mm": round(max(0.0, Lmm - used)), "free": _free(clipped, Lmm)}
    for m in modules:
        m.pop("cfg")
    return {"length_mm": round(Lmm), "flip": flip, "modules": modules, "usage": usage, "issues": issues, "openings": ops}


def align_counter(cfgs: list[dict]) -> tuple[list[dict], list[str]]:
    """'상판선 맞추기': 하부 장들의 상판 높이를 가장 많이 쓴 높이에 맞춘다. 몸체는 그대로 두고 다리 높이만 바꾼다.
    가전 매입부는 가전 공간이 바뀌니 건드리지 않고 알린다. 돌려줌: (바뀐 설정, 알림)."""
    cand = [c for c in cfgs if band(c) == "base" and "counter" in c["parts"] and "toe_kick" in c["parts"]]
    if not cand:
        return cfgs, []
    hs = [c["outer_mm"]["h"] for c in cand if not KINDS[c["kind"]].get("host")]
    if not hs:
        return cfgs, []
    target = max(set(hs), key=lambda h: (hs.count(h), -hs.index(h)))  # 같으면 왼쪽 것
    notes, out = [], []
    for c in cfgs:
        if c not in cand or c["outer_mm"]["h"] == target:
            out.append(c)
            continue
        label = KINDS[c["kind"]]["label"]
        if KINDS[c["kind"]].get("host"):
            notes.append(f"{label}은 가전 공간이 바뀌어 그대로 뒀어요 ({c['outer_mm']['h']:,} mm)")
            out.append(c)
            continue
        toe = c["parts"]["toe_kick"] + (target - c["outer_mm"]["h"])
        if not 0 <= toe <= 250:
            notes.append(f"{label}은 다리 높이로 맞출 수 없어 그대로 뒀어요")
            out.append(c)
            continue
        c = copy.deepcopy(c)
        c["parts"]["toe_kick"] = toe
        c["outer_mm"]["h"] = target
        out.append(c)
        notes.append(f"{label} 다리를 {toe:g} mm로 바꿔 상판을 {target:,} mm에 맞췄어요")
    return out, notes
