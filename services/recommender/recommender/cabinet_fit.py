"""맞춤장 안에 넣은 LG 가전을 LGE.COM 공식 설치 기준과 견준다 (docs/specs/builtin-kitchen.md).

- 기준은 data/catalog/install_rules.json에 모델별로 적힌 것만 쓴다. 같은 카테고리의 다른 모델 값으로 채우지 않는다.
- 장 안쪽 치수(cabinet.interior)만 본다. 측판·뒷판 두께는 거기서 이미 빠졌다.
- 결과 네 가지: fit 적합 · conditional 조건부 · no_fit 불가 · unknown 판정 불가.
  공식 기준이 없거나 필요한 실측값이 없으면 외형 비교는 보여 주되 판정 불가. '적합'은 검사한 범위 기준이다.
- 3D 문 열림 간섭(근사)은 여기서 보지 않는다. 화면이 따로 계산해 따로 보여 준다 (apps/web/js/cabinet.js).
"""
from __future__ import annotations

import json
from pathlib import Path

from core.models import Product

from .cabinet import interior

RULES_PATH = Path(__file__).resolve().parents[3] / "data" / "catalog" / "install_rules.json"
AXES = {"w": "폭", "h": "높이", "d": "깊이"}
SOURCE_KO = {"designed": "설계값", "measured": "실측값", "scanned": "스캔값"}
VERDICT_KO = {"fit": "적합", "conditional": "조건부", "no_fit": "불가", "unknown": "판정 불가"}
_RANK = {"fit": 0, "conditional": 1, "unknown": 2, "no_fit": 3}
FLUSH_MM = 1  # 이 안이면 정면이 장과 맞는다


class Rules:
    def __init__(self, data: dict):
        self._rules = data["rules"]
        self._by_sku = {}
        for r in self._rules:
            for sku in r["applies_to"]:
                if sku in self._by_sku:
                    raise ValueError(f"{sku}에 기준이 둘: {self._by_sku[sku]['id']}, {r['id']}")
                self._by_sku[sku] = r

    def get(self, sku: str | None) -> dict | None:
        return self._by_sku.get(sku or "")

    def all(self) -> list[dict]:
        return list(self._rules)


def load_rules(path: Path = RULES_PATH) -> Rules:
    return Rules(json.loads(Path(path).read_text(encoding="utf-8")))


def _r(v: float | None):
    return None if v is None else int(round(v))


def _worst(vs) -> str:
    return max(vs, key=_RANK.get, default="fit")


def _axis(a: str, spec: dict, have, source: str) -> dict:
    ok = [b for b in spec["bands"] if b["verdict"] != "no_fit"]
    lo = min(b["lo"] for b in ok)
    his = [b.get("hi") for b in ok]
    hi = None if any(h is None for h in his) else max(his)
    need_text = f"{_r(lo):,}~{_r(hi):,}" if hi is not None else f"{_r(lo):,} 이상"
    out = {"axis": a, "label": AXES[a], "need_mm": _r(lo), "need_text": need_text, "recommend_mm": _r(spec.get("recommend")),
           "have_mm": _r(have), "short_mm": 0, "over_mm": 0, "source": source, "source_ko": SOURCE_KO[source], "basis": spec["basis"],
           "note": ""}
    if have is None:
        return {**out, "verdict": "unknown", "short_mm": None, "note": f"{AXES[a]} 실측값이 없어요"}
    band = next((b for b in spec["bands"] if b["lo"] <= have and (b.get("hi") is None or have < b["hi"])), None)
    if band:
        return {**out, "verdict": band["verdict"], "note": band.get("note", ""),
                "over_mm": _r(have - band["lo"]) if band["verdict"] == "no_fit" and hi is not None else 0}
    if have < lo:
        return {**out, "verdict": "no_fit", "short_mm": _r(lo - have), "note": f"{AXES[a]}이 {_r(lo - have):,} mm 부족해요"}
    return {**out, "verdict": "no_fit", "over_mm": _r(have - hi), "note": f"{AXES[a]}이 {_r(have - hi):,} mm 넘쳐요"}


def _check(c: dict, cab: dict, rule: dict, nb: dict) -> dict:
    out = {"code": c["code"], "label": c["label"], "detail": c["detail"]}
    p = cab["parts"]
    if c["status"] == "rule":
        return {**out, "status": "ok"}
    if c["status"] in ("none", "site"):
        if c["code"] == "water" and nb.get("sink"):
            out["detail"] = "싱크 하부장이 옆에 있지만 " + c["detail"]
        return {**out, "status": c["status"]}
    if c["code"] == "side_fix":
        left = p.get("side_l", 0) > 0 or nb.get("left")
        right = p.get("side_r", 0) > 0 or nb.get("right")
        if left and right:
            return {**out, "status": "ok"}
        miss = "왼쪽" if not left else "오른쪽"
        return {**out, "status": "blocked", "detail": f"{miss}에 나사로 고정할 면이 없어요 (측판이나 옆 장이 필요해요)"}
    if c["code"] == "toe_kick":
        toe, over = p.get("toe_kick"), (rule.get("toe_kick_mm") or {}).get("over")
        if toe is None or over is None:
            return {**out, "status": "none"}
        if toe > over:
            return {**out, "status": "ok", "detail": f"걸레받이 {_r(toe)} mm, 이 모델이 맞는 높이예요"}
        return {**out, "status": "check", "detail": f"걸레받이 {_r(toe)} mm는 {over} mm 이하라 낮은 걸레받이용 모델을 봐야 해요"}
    return {**out, "status": "none"}


_CHECK_VERDICT = {"blocked": "no_fit", "check": "conditional"}


def judge(product: Product, cab: dict, rule: dict | None, neighbours: dict | None = None) -> dict:
    """장(cabinet.normalize 결과) 안에 product를 넣었을 때의 공식 기준 판정.
    neighbours: {"left": 옆에 붙은 장이 있음, "right": …, "sink": 옆에 싱크 하부장} — 좌우 고정면·배관 안내에만 쓴다."""
    nb = neighbours or {}
    inside = interior(cab)
    src = inside["source"]
    dims = product.product_dims_mm
    pd = {"w": dims.w, "h": dims.h, "d": dims.d}
    outline = {a: {"product_mm": _r(pd[a]), "have_mm": _r(inside[a]),
                   "fits": None if pd[a] is None or inside[a] is None else inside[a] >= pd[a]} for a in "whd"}
    front = None
    if pd["d"] is not None and inside["d"] is not None:
        off = _r(pd["d"] - inside["d"])
        front = {"offset_mm": off, "state": "flush" if abs(off) <= FLUSH_MM else "protrudes" if off > 0 else "recessed"}
    base = {"sku": product.sku, "mode": cab["mode"], "inside_mm": inside, "outline": outline, "front": front}
    if rule is None:
        return {**base, "verdict": "unknown", "verdict_ko": VERDICT_KO["unknown"], "rule_id": None, "axes": [], "checks": [],
                "source_url": product.source_url, "scope": "LG 공식 설치 기준이 없는 모델이라 제품 외형과 장 안쪽만 견줬어요",
                "summary": "공식 설치 기준이 없어 외형만 견줬어요. 공식 설치 여부는 판정 불가예요"}
    axes = [_axis(a, rule["axes"][a], inside[a], src) for a in "whd"]
    checks = [_check(c, cab, rule, nb) for c in rule.get("checks", [])]
    verdict = _worst([x["verdict"] for x in axes] + [_CHECK_VERDICT[c["status"]] for c in checks if c["status"] in _CHECK_VERDICT])
    looked = ["장 안쪽 폭·높이·깊이"] + [c["label"] for c in checks if c["status"] in ("ok", "blocked", "check")]
    scope = f"검사한 범위: {', '.join(looked)} ({SOURCE_KO[src]} 기준)"
    if src == "designed":
        scope += ". 새 장 설계값이라 현장 실측이 아니에요"
    site = [c["label"] for c in checks if c["status"] == "site"]
    if site:
        scope += f". {'·'.join(site)}은 현장 확인"
    if verdict == "no_fit":
        bad = next((x for x in axes if x["verdict"] == "no_fit"), None)
        if bad:
            summary = bad["note"] if bad["short_mm"] or bad["over_mm"] else f"{bad['label']}: {bad['note']}"
            if bad["short_mm"]:
                summary = f"{bad['label']}이 {bad['short_mm']:,} mm 부족해요"
            elif bad["over_mm"]:
                summary = f"{bad['label']}이 {bad['over_mm']:,} mm 넘쳐요. {bad['note']}".rstrip(". ")
        else:
            summary = next(c["detail"] for c in checks if c["status"] == "blocked")
    elif verdict == "unknown":
        summary = "실측값이 없는 치수가 있어 판정 불가예요"
    elif verdict == "conditional":
        x = next((x for x in axes if x["verdict"] == "conditional"), None)
        summary = (f"{x['label']}: {x['note']}" if x else next(c["detail"] for c in checks if c["status"] == "check"))
    else:
        summary = "LG 공식 기준 안에 들어가요 (검사한 범위 기준)"
    # 3D 근사 검사용 식기세척기 문 밑 높이: 가이드의 걸레받이 기준(150)에 다리를 올린 만큼 (가이드: 올린 만큼 기준이 바뀐다)
    kick = (rule.get("toe_kick_mm") or {}).get("nominal")
    if kick is not None:
        lift = 0 if inside["h"] is None or pd["h"] is None else min(max(inside["h"] - pd["h"], 0), rule.get("leg_adjust_max_mm", 0))
        base["door_bottom_mm"] = _r(kick + lift)
    return {**base, "verdict": verdict, "verdict_ko": VERDICT_KO[verdict], "rule_id": rule["id"], "rule_title": rule["title"],
            "axes": axes, "checks": checks, "source_url": rule["source_url"], "source_title": rule["source_title"],
            "checked_at": rule["checked_at"], "scope": scope, "summary": summary}
