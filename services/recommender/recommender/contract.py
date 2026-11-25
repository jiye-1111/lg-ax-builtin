"""전달받은 모델 묶음의 설치 계약(data/lg-library/contracts/<모델명>.json) 읽기.

계약은 제품 설명서에서 옮긴 설치 조건이다. 여기서는 세 가지만 한다.
- 설명서에 수치로 적힌 환기 이격·타공·개구 치수를 꺼낸다 (카탈로그에 넣어 판정에 쓴다)
- 현장 값이 있어야 알 수 있는 조건(급수 압력, 콘센트, 지지면 높이 …)을 설치 전 확인 목록의 줄로 바꾼다
- 설명서에 수치가 없는 것(문 열림 경로, 정비·사용·통행 공간)은 확인된 것으로 치지 않고 그대로 남긴다

출처가 공식·실측·프로젝트 기준이 아닌 규칙은 쓰지 않는다. 순수 Python, 입력은 계약 dict.
"""
from __future__ import annotations

import re

TRUSTED = ("official", "measured", "project_defined")
UNIT = {"_mm": "mm", "_c": "℃", "_mpa": "MPa", "_v": "V"}
WORD = {"gte": "이상", "lte": "이하", "gt": "초과", "lt": "미만", "eq": ""}
# 계약의 이름이 문장으로 옮기기 어려운 것만 다시 적는다
LABEL = {
    "drain_hose_length_mm": "배수 호스 길이",
    "drain_outlet_height_mm": "배수 호스 끝 높이",
    "supply_voltage_v": "전원",
    "door_front_space_mm": "문 앞 공간",
    "model_plinth_configuration_mm": "걸레받이 높이",
    "cutout_width": "상판 타공 폭",
    "cutout_depth": "상판 타공 깊이",
    "wall_left_mm": "왼쪽 벽과 거리",
    "wall_right_mm": "오른쪽 벽과 거리",
    "wall_rear_mm": "뒤쪽 벽과 거리",
    "wall_front_mm": "앞쪽 벽과 거리",
}
_TAIL_NUM = re.compile(r"\s*(최소|최대|하한|상한|초과|미만)\s*$")  # 수치 조건: 방향은 값 뒤에 다시 적는다
_TAIL_BOOL = re.compile(r"\s*(여부|금지)\s*$")  # 예·아니오 조건: "… 금지"가 아니오면 "… 안 됨"


def _trusted(rule: dict) -> bool:
    s = rule.get("source") or {}
    return bool(s.get("reference")) and s.get("status") in TRUSTED


def _num(v: float) -> str:
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:g}"


def _label(rule: dict) -> str:
    key = rule.get("fact_key", "")
    if key in LABEL:
        return LABEL[key]
    s = re.sub(r"\([^)]*\)", "", rule["label"]).strip()
    tail = _TAIL_BOOL if isinstance(rule.get("value"), bool) else _TAIL_NUM
    while tail.search(s):
        s = tail.sub("", s)
    return s


def _unit(rule: dict) -> str:
    key = rule.get("fact_key", "")
    if key in ("cutout_width", "cutout_depth"):
        return "mm"
    return next((u for suffix, u in UNIT.items() if key.endswith(suffix)), "")


def _box_rules(contract: dict, prefix: str) -> dict[str, dict]:
    return {r["id"]: r for r in contract.get("rules", [])
            if r.get("kind") == "volume" and r["id"].startswith(prefix) and r.get("boxes") and _trusted(r)}


def clearances(contract: dict) -> dict[str, float]:
    """설명서의 환기 이격(mm): side(양옆 각각)·back·top. 적힌 것만 돌려준다."""
    rules, out = _box_rules(contract, "clearance_"), {}
    sides = [rules[k]["boxes"][0]["size_mm"][0] for k in ("clearance_left", "clearance_right") if k in rules]
    if len(sides) == 2:
        out["side"] = max(sides)
    if "clearance_rear" in rules:
        out["back"] = rules["clearance_rear"]["boxes"][0]["size_mm"][2]
    if "clearance_top" in rules:
        out["top"] = rules["clearance_top"]["boxes"][0]["size_mm"][1]
    return out


def _facts(contract: dict) -> list[dict]:
    return [r for r in contract.get("rules", []) if r.get("kind") == "fact" and _trusted(r)]


def _fact_value(contract: dict, key: str, op: str) -> float | None:
    for r in _facts(contract):
        if r["fact_key"] == key and r.get("operator") == op and isinstance(r.get("value"), (int, float)) and not isinstance(r["value"], bool):
            return r["value"]
    return None


def cutout(contract: dict) -> dict[str, float]:
    """인덕션 상판 타공(mm). 폭·깊이가 둘 다 적혀 있을 때만."""
    w, d = _fact_value(contract, "cutout_width", "eq"), _fact_value(contract, "cutout_depth", "eq")
    return {"w": w, "d": d} if w is not None and d is not None else {}


def opening(contract: dict) -> dict[str, float]:
    """빌트인 제품이 들어갈 장 개구의 최소 치수(mm). 폭·높이·깊이가 모두 적혀 있을 때만."""
    got = {k: _fact_value(contract, f"opening_{name}_mm", "gte") for k, name in (("w", "width"), ("h", "height"), ("d", "depth"))}
    return got if None not in got.values() else {}


def _phrase(rules: list[dict]) -> str | None:
    """같은 현장 값에 걸린 규칙 한두 개 → 한 마디. 문장으로 못 옮기는 것은 None."""
    first, label, unit = rules[0], _label(rules[0]), _unit(rules[0])
    v = first.get("value")
    if isinstance(v, bool):
        return label if v else f"{label} 안 됨"
    nums = {r["operator"]: r["value"] for r in rules if isinstance(r.get("value"), (int, float)) and r.get("operator") in WORD}
    if not nums:
        return None
    u = f" {unit}" if unit else ""
    lo = nums.get("gte", nums.get("gt"))
    hi = nums.get("lte", nums.get("lt"))
    if lo is not None and hi is not None:
        return f"{label} {_num(lo)}~{_num(hi)}{u}"
    op, val = next(iter(nums.items()))
    return f"{label} {_num(val)}{u} {WORD[op]}".rstrip()


def site_lines(contract: dict) -> list[dict]:
    """설치 전 확인 목록에 넣을 줄. 모두 '현장 확인'(site)이다: 설명서 조건은 현장 값이 있어야 맞는지 알 수 있다."""
    groups: dict[tuple, list[dict]] = {}
    unknown: list[str] = []
    for r in contract.get("rules", []):
        if r.get("applicable") is False or r.get("id") == "closed_envelope":
            continue
        if r.get("kind") == "fact":
            if r.get("value") is None:
                unknown.append(_label(r))
            elif _trusted(r):
                groups.setdefault((r["fact_key"], str(r.get("when"))), []).append(r)
        elif r.get("motion") is None and not r.get("boxes"):
            unknown.append(_label(r))
    said = list(dict.fromkeys(p for p in (_phrase(rs) for rs in groups.values()) if p))
    out = []
    if said:
        out.append({"code": "manual", "label": "설치 설명서 조건", "status": "site", "detail": " · ".join(said)})
    if unknown:
        out.append({"code": "unknown", "label": "설명서에 수치가 없어 현장에서 볼 것", "status": "site",
                    "detail": " · ".join(dict.fromkeys(unknown))})
    return out
