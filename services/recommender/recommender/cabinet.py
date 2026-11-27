"""맞춤장(빌트인 주방) 모듈: 외경과 부재(측판·상판·뒷판·걸레받이·틈막이판·마감판)로 안쪽 빈 공간을 계산한다.

규칙은 docs/specs/builtin-kitchen.md. 단위 mm.
- 새 장 설계(mode="new"): 외경과 부재 두께로 안쪽 치수를 계산한다 (설계값, 현장 실측 아님).
- 기존 장에 넣기(mode="existing"): 줄자로 잰 안쪽 치수(measured_mm)를 그대로 쓴다. 제품을 바꿔도 장 크기는 그대로다.
- 판정은 이 안쪽 치수만 본다. 부재 두께는 여기서 이미 빠졌으니 판정에서 다시 빼지 않는다 (cabinet_fit.py).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

FINISHES_PATH = Path(__file__).resolve().parents[3] / "data" / "finishes" / "cabinet_finishes.json"

# 부재 이름 → (최소, 최대). 두께는 mm, 개수는 개, 켜고 끄는 것은 bool, 고르는 것은 ENUM
THICK = (0, 60)
ENUM = "enum"
PART_RANGE: dict[str, tuple] = {
    "side_l": THICK, "side_r": THICK,          # 좌우 측판 (0이면 옆 장 측판을 쓴다)
    "back": THICK,                             # 뒷판 (0 = 없음)
    "counter": THICK,                          # 상판 두께
    "filler_l": (0, 200), "filler_r": (0, 200),  # 벽과 장 사이 틈막이판
    "end_l": THICK, "end_r": THICK,            # 노출 측면 마감판
    "upper_h": (0, 1200),                      # 냉장고장·TV월 위 수납장 높이 (판 포함)
    "toe_kick": (0, 250),                      # 걸레받이 높이
    "toe_recess": (0, 150),                    # 걸레받이가 정면에서 들어간 깊이
    "shelves": (0, 8), "drawers": (0, 6), "doors": (0, 4),
    "kick_across": (False, True),              # 식기세척기 자리 앞까지 걸레받이를 이어 붙임
    "bowl": (False, True),                     # 싱크볼·수전
    "style": (ENUM, ("door", "drawer", "open", "pullout", "flap", "homecafe")),  # 문짝·서랍 유형
    "hinge": (ENUM, ("l", "r")),               # 한 짝 문이 열리는 쪽 (경첩 쪽)
    "niche_y": (0, 2000), "niche_h": (0, 1500),  # 키큰장 가운데 열린 칸·가전 칸 (밑면 높이, 높이)
    "leg_b": (300, 1500),                      # 코너장: 옆 벽을 따라 차지하는 길이
    "corner": (ENUM, ("l", "r")),              # 코너장: 꺾이는 쪽 (정면에서 봤을 때)
    "door_leg": (ENUM, ("a", "b")),            # 코너장: 문이 달린 쪽 (a = 이 벽, b = 옆 벽)
    "overhang": (0, 600),                      # 아일랜드 상판 돌출 (앉는 쪽)
    "storage": (ENUM, ("front", "back", "both")),  # 아일랜드 수납 방향
    "attach_wall": (False, True),              # 아일랜드 한쪽을 벽에 붙임 (반도형)
    "side_w": (0, 1200),                       # TV월 좌우 키큰 수납 폭
    "media_h": (0, 1200),                      # TV월 아래 미디어장 높이
    "cable": (False, True),                    # TV월 배선 통로
    "vent": (0, 200),                          # TV·가전 둘레 통풍 여유 (표시용)
    "cutout_w": (0, 1000), "cutout_d": (0, 700),  # 인덕션 상판 타공 (공식 타공 치수를 확인한 경우만)
}
# 종류마다 고를 수 있는 문짝·서랍 유형
STYLES = {"base": ("door", "drawer", "open", "pullout"), "wall": ("door", "flap", "open"),
          "tall": ("door", "pullout", "open", "homecafe"), "low": ("door", "drawer", "open"), "low_wall": ("door", "drawer", "open")}
FRAME = {"side_l": 18, "side_r": 18, "back": 0, "filler_l": 0, "filler_r": 0, "end_l": 0, "end_r": 0}
BASE = {**FRAME, "counter": 30, "toe_kick": 150, "toe_recess": 50}
# 벽면 맞춤가구 하부: 몸체 800 + 다리(걸레받이) 80 + 상판 30 (IKEA METOD 몸체·다리 구성을 시작값으로)
BASE2 = {**FRAME, "counter": 30, "toe_kick": 80, "toe_recess": 50}
DOOR = {"doors": 1, "hinge": "r"}

# 1단계 모듈과 다음 단계 모듈. 다음 단계도 같은 구조(외경 + 부재 + 마감)로 늘린다
# host: 가전을 넣는 장 (그 카테고리) · hang: 벽에 거는 장 (밑면 높이 base_mm) · band: 벽면에서 차지하는 높이 구간
# shape: 같은 상자가 아닌 것 (corner = ㄱ자, island = 바닥에 따로, tvwall = TV 칸이 빈 조합)
KINDS: dict[str, dict] = {
    "fridge": {"label": "냉장고·김치냉장고장", "stage": 1, "host": ("refrigerator", "kimchi_refrigerator", "freezer"), "band": "tall",
               "outer": (958, 2300, 720), "parts": {**FRAME, "upper_h": 400, "doors": 2}},
    "dishwasher": {"label": "식기세척기 자리", "stage": 1, "host": ("dishwasher",), "band": "base",
                   "outer": (636, 850, 600), "parts": {**FRAME, "counter": 30, "toe_kick": 150, "kick_across": False}},
    "sink": {"label": "싱크 하부장", "stage": 1, "band": "base", "outer": (900, 850, 600), "parts": {**BASE, "doors": 2, "bowl": True}},
    "drawer": {"label": "서랍형 하부장", "stage": 1, "band": "base", "outer": (600, 850, 600), "parts": {**BASE, "back": 9, "drawers": 3}},
    "base": {"label": "하부장", "stage": 1, "band": "base", "outer": (600, 910, 600),
             "parts": {**BASE2, "back": 9, "style": "door", **DOOR, "shelves": 1, "drawers": 3}},
    "wall": {"label": "상부장", "stage": 1, "hang": 1450, "band": "wall", "outer": (800, 700, 350),
             "parts": {**FRAME, "back": 9, "shelves": 2, "doors": 2, "style": "door", "hinge": "r"}},
    "pantry": {"label": "키큰 팬트리장", "stage": 1, "band": "tall", "outer": (600, 2100, 600), "parts": {**FRAME, "back": 9, "toe_kick": 100, "toe_recess": 50, "shelves": 4, "doors": 1}},
    "tall": {"label": "키큰장", "stage": 1, "band": "tall", "outer": (600, 2280, 600),
             "parts": {**FRAME, "back": 9, "toe_kick": 80, "toe_recess": 50, "style": "door", **DOOR, "shelves": 4, "drawers": 4,
                       "niche_y": 950, "niche_h": 550}},
    "glass_wall": {"label": "유리 상부장", "stage": 1, "hang": 1450, "band": "wall", "outer": (800, 700, 370), "glass": True,
                   "parts": {**FRAME, "back": 9, "shelves": 2, "doors": 2}},
    "glass_tall": {"label": "유리 키큰장", "stage": 1, "band": "tall", "outer": (600, 2080, 400), "glass": True,
                   "parts": {**FRAME, "back": 9, "toe_kick": 80, "toe_recess": 50, "shelves": 4, **DOOR}},
    "low": {"label": "낮은 수납장", "stage": 1, "band": "base", "outer": (1200, 380, 400),
            "parts": {**FRAME, "back": 9, "toe_kick": 0, "toe_recess": 0, "style": "door", "doors": 2, "hinge": "r", "drawers": 2, "shelves": 1}},
    "low_wall": {"label": "벽걸이 하부장", "stage": 1, "hang": 300, "band": "base", "outer": (1800, 380, 400),
                 "parts": {**FRAME, "back": 9, "style": "drawer", "doors": 2, "hinge": "r", "drawers": 3, "shelves": 0}},
    "corner": {"label": "코너장", "stage": 1, "band": "base", "shape": "corner", "outer": (900, 910, 600),
               "parts": {**BASE2, "back": 9, "leg_b": 900, "corner": "r", "door_leg": "a", "doors": 1, "shelves": 1}},
    "island_storage": {"label": "수납형 아일랜드", "stage": 1, "band": "floor", "shape": "island", "outer": (1800, 900, 900),
                       "parts": {**FRAME, "counter": 30, "toe_kick": 80, "toe_recess": 50, "overhang": 300, "storage": "front",
                                 "attach_wall": False, "drawers": 3}},
    "tvwall": {"label": "TV월", "stage": 1, "band": "tall", "shape": "tvwall", "host": ("tv",), "outer": (3000, 2400, 400),
               "parts": {**FRAME, "back": 9, "toe_kick": 0, "side_w": 600, "media_h": 450, "upper_h": 400, "cable": True, "vent": 50,
                         "shelves": 4, "doors": 1}},
    "oven_tall": {"label": "오븐·전자레인지 키큰장", "stage": 1, "band": "tall", "host": ("oven", "microwave"), "outer": (600, 2280, 600),
                  "parts": {**FRAME, "back": 0, "toe_kick": 80, "toe_recess": 50, "niche_y": 850, "niche_h": 600, "drawers": 2, "doors": 1}},
    "cooktop_base": {"label": "인덕션 하부장", "stage": 1, "band": "base", "host": ("cooktop",), "outer": (800, 910, 600),
                     "parts": {**BASE2, "back": 9, "drawers": 2, "cutout_w": 0, "cutout_d": 0}},
    "hood_cab": {"label": "후드 상부장", "stage": 1, "hang": 1600, "band": "wall", "outer": (600, 400, 350), "parts": {**FRAME, "back": 9, "doors": 1}},
    "counter": {"label": "연속 상판", "stage": 1, "outer": (1800, 30, 620), "base": 820, "parts": {}},
    "filler": {"label": "틈막이판", "stage": 1, "band": "base", "outer": (50, 850, 20), "parts": {}},
    "end_panel": {"label": "측면 마감판", "stage": 1, "band": "base", "outer": (20, 880, 620), "parts": {}},
}
# 가전을 넣는 장의 빈 공간 (부재 계산식이 다른 것)
HOSTS = {k for k, v in KINDS.items() if v.get("host")}
MODES = ("new", "existing")
FINISH_PARTS = {"front": "panel", "body": "panel", "top": "top", "handle": "handle"}
DEFAULT_FINISH = {"front": "warmwhite_matte", "body": "warmwhite_matte", "top": "stone_white", "handle": "steel"}
OUTER_RANGE = {"w": (10, 4000), "h": (10, 3000), "d": (10, 1500)}

_palette: dict | None = None


def palette() -> dict:
    """마감 목록 (data/finishes/cabinet_finishes.json). LG 가전 색과 따로 관리한다."""
    global _palette
    if _palette is None:
        _palette = json.loads(FINISHES_PATH.read_text(encoding="utf-8"))
    return _palette


def _ids(group: str) -> set[str]:
    return {f["id"] for f in palette()[group]}


def _num(v, name: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"{name}는 숫자여야 해요")
    return float(v)


def _int_if(v: float):
    return int(v) if float(v).is_integer() else round(v, 1)


def normalize(cfg: dict) -> dict:
    """장 설정을 검사하고 빠진 값은 기본값으로 채운다. 잘못된 값이면 ValueError."""
    kind = cfg.get("kind")
    if kind not in KINDS:
        raise ValueError(f"없는 장 종류: {kind}")
    spec = KINDS[kind]
    if spec["stage"] != 1:
        raise ValueError(f"{spec['label']}은 다음 단계에서 열어요")
    mode = cfg.get("mode", "new")
    if mode not in MODES:
        raise ValueError("mode는 new(새 장 설계) 또는 existing(기존 장에 넣기)")
    outer_in = cfg.get("outer_mm") or {}
    outer = {}
    for i, a in enumerate("whd"):
        v = _num(outer_in.get(a, spec["outer"][i]), f"외경 {a}")
        lo, hi = OUTER_RANGE[a]
        if not lo <= v <= hi:
            raise ValueError(f"외경 {a}는 {lo}~{hi} mm")
        outer[a] = _int_if(v)
    parts = dict(spec["parts"])
    for k, v in (cfg.get("parts") or {}).items():
        if k not in spec["parts"]:
            raise ValueError(f"{spec['label']}에는 {k} 부재가 없어요")
        lo, hi = PART_RANGE[k]
        if lo == ENUM:
            allowed = STYLES.get(kind, hi) if k == "style" else hi
            if v not in allowed:
                raise ValueError(f"{k}는 {', '.join(allowed)} 중 하나예요")
            parts[k] = v
            continue
        if isinstance(lo, bool):
            if not isinstance(v, bool):
                raise ValueError(f"{k}는 켜고 끄는 값이에요")
            parts[k] = v
            continue
        v = _num(v, k)
        if not lo <= v <= hi:
            raise ValueError(f"{k}는 {lo}~{hi} 사이여야 해요")
        parts[k] = int(v) if k in ("shelves", "drawers", "doors") else _int_if(v)
    out = {"kind": kind, "mode": mode, "outer_mm": outer, "parts": parts}
    if mode == "existing":
        m = cfg.get("measured_mm") or {}
        out["measured_mm"] = {a: (None if m.get(a) is None else _int_if(_num(m[a], f"실측 {a}"))) for a in "whd"}
        for a, v in out["measured_mm"].items():
            if v is not None and not 1 <= v <= OUTER_RANGE[a][1]:
                raise ValueError(f"실측 {a}가 너무 작거나 커요")
    finish = {**DEFAULT_FINISH}
    for k, v in (cfg.get("finish") or {}).items():
        if k not in FINISH_PARTS:
            raise ValueError(f"마감을 바꿀 수 없는 부위: {k}")
        if v not in _ids(FINISH_PARTS[k]):
            raise ValueError(f"{k}에 쓸 수 없는 마감: {v}")
        finish[k] = v
    out["finish"] = finish
    if spec.get("glass"):
        g = cfg.get("glass", "clear")
        if g not in _ids("glass"):
            raise ValueError(f"없는 유리: {g}")
        out["glass"] = g
    if cfg.get("appliance"):
        out["appliance"] = str(cfg["appliance"])
    if "base_mm" in cfg or spec.get("hang") or spec.get("base"):
        out["base_mm"] = _int_if(_num(cfg.get("base_mm", spec.get("hang") or spec.get("base") or 0), "밑면 높이"))
    inside = _designed(out)
    if any(v <= 0 for v in inside.values()) and kind not in ("counter", "filler", "end_panel", "cooktop_base"):
        raise ValueError("부재가 장보다 두꺼워 안쪽 공간이 없어요")
    if cfg.get("preset"):
        out["preset"] = str(cfg["preset"])
    if cfg.get("dims_by") == "user":  # 프리셋 값을 손으로 바꾼 장 (치수 출처 표시)
        out["dims_by"] = "user"
    if isinstance(cfg.get("run"), dict):  # 벽면 세트에 묶인 장
        out["run"] = copy.deepcopy(cfg["run"])
    return out


def _side_total(p: dict) -> float:
    return sum(p.get(k, 0) for k in ("side_l", "side_r", "filler_l", "filler_r", "end_l", "end_r"))


def _designed(c: dict) -> dict:
    o, p, kind = c["outer_mm"], c["parts"], c["kind"]
    w = o["w"] - _side_total(p)
    d = o["d"] - p.get("back", 0)
    if kind == "fridge":
        h = o["h"] - p.get("upper_h", 0)
    elif kind == "dishwasher":
        h = o["h"] - p.get("counter", 0)
    elif kind == "oven_tall":  # 가전 칸: 그 칸 높이만
        h = p.get("niche_h", 0)
    elif kind == "tvwall":  # TV 칸: 좌우 키큰 수납을 뺀 가운데, 미디어장 위 · 위 수납장 아래
        w = o["w"] - 2 * p.get("side_w", 0)
        h = o["h"] - p.get("upper_h", 0) - p.get("media_h", 0)
    elif kind == "cooktop_base":  # 상판 타공 (공식 치수를 넣지 않았으면 0 = 모름)
        return {"w": _int_if(p.get("cutout_w", 0)), "h": _int_if(o["h"]), "d": _int_if(p.get("cutout_d", 0))}
    else:  # 수납장: 상판·걸레받이를 뺀 몸통 안
        h = o["h"] - p.get("counter", 0) - p.get("toe_kick", 0)
    return {"w": _int_if(w), "h": _int_if(h), "d": _int_if(d)}


def cavity_floor_mm(c: dict) -> float:
    """장 안 가전이 놓이는 바닥 높이 (장 밑면 기준, mm). 냉장고·식기세척기는 바닥, 오븐 칸·TV 칸은 그 칸 밑, 인덕션은 상판 위."""
    kind, p, o = c["kind"], c["parts"], c["outer_mm"]
    if kind == "oven_tall":
        return p.get("niche_y", 0)
    if kind == "tvwall":
        return p.get("media_h", 0)
    if kind == "cooktop_base":
        return o["h"] - p.get("counter", 0)
    return 0.0


def interior(cfg: dict) -> dict:
    """가전이 들어가는 안쪽 유효 폭·높이·깊이 (mm)와 그 값의 출처.
    source: designed(새 장 설계값) | measured(기존 장 실측값)."""
    if cfg.get("mode") == "existing":
        return {**cfg["measured_mm"], "source": "measured"}
    return {**_designed(cfg), "source": "designed"}


def suggest(kind: str, rule: dict | None, base: dict | None = None) -> dict | None:
    """새 장 설계: 공식 기준이 있는 모델만 안쪽 권장 치수를 내고, 그만큼 들어가게 외경을 정한다. 기준이 없으면 None."""
    if not rule:
        return None
    cfg = normalize({**(base or {}), "kind": kind, "mode": "new"})
    want = {a: rule["axes"][a]["recommend"] for a in "whd"}
    p = cfg["parts"]
    cfg["outer_mm"] = {
        "w": _int_if(want["w"] + _side_total(p)),
        "h": _int_if(want["h"] + (p.get("upper_h", 0) if kind == "fridge" else p.get("counter", 0))),
        "d": _int_if(want["d"] + p.get("back", 0)),
    }
    return normalize(cfg)


def kinds_list() -> list[dict]:
    """웹 목록용: 종류·이름·단계·기본 크기·부재 기본값."""
    return [{"kind": k, "label": v["label"], "stage": v["stage"], "host": list(v.get("host", ())),
             "outer_mm": dict(zip("whd", v["outer"])), "parts": copy.deepcopy(v["parts"]), "glass": bool(v.get("glass")),
             "hang_mm": v.get("hang"), "base_mm": v.get("base"), "band": v.get("band"), "shape": v.get("shape"),
             "styles": list(STYLES.get(k, ()))} for k, v in KINDS.items()]
