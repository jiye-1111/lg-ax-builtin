"""CMF(색상·재질·마감) 매칭 (기획 §9.2).

점수 = 0.6 × 색 점수 + 0.4 × 재질 점수
- 색 점수 = max(0, 1 − min ΔE2000(옵션색, 영역 팔레트) / 50)
- 재질 점수 = 영역 재질 키워드 중 옵션(재질·마감·색상명)에 포함된 비율
옵션 hex가 없으면(근사값 미확보) 재질 점수만 쓰고 'color_unknown' 표시.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional

from core.models import CmfOption, Product, StyleTags

W_COLOR, W_MATERIAL = 0.6, 0.4
DE_SCALE = 50.0

# 한국어·영어 표기를 같은 키워드로 묶는다
SYNONYMS = {
    "wood": ["wood", "우드", "원목", "나무", "오크", "월넛"],
    "matte": ["matte", "matt", "매트", "무광", "미스트"],
    "glossy": ["glossy", "gloss", "유광", "글로시"],
    "glass": ["glass", "글라스", "유리"],
    "metal": ["metal", "메탈", "스테인리스", "stainless", "스틸", "steel"],
    "stone": ["stone", "스톤", "대리석", "marble", "세라믹", "ceramic", "테라조", "terrazzo"],
    "plaster": ["plaster", "회벽", "미장", "석회", "스투코", "stucco"],
    "paint": ["paint", "페인트", "도장"],
    "fabric": ["fabric", "패브릭", "직물", "린넨", "linen"],
    "white": ["white", "화이트", "흰"],
    "beige": ["beige", "베이지"],
    "gray": ["gray", "grey", "그레이", "회색"],
    "black": ["black", "블랙", "검정"],
    "green": ["green", "그린"],
    "brown": ["brown", "브라운", "갈색", "에스프레소", "espresso", "초콜릿"],
    "pink": ["pink", "핑크"],
    "navy": ["navy", "네이비"],
    "silver": ["silver", "실버"],
    "minimal": ["minimal", "미니멀"],
    "natural": ["natural", "내추럴"],
}
_LOOKUP = [(syn.lower(), key) for key, syns in SYNONYMS.items() for syn in syns]


def material_keywords(*texts: Optional[str]) -> set[str]:
    out: set[str] = set()
    for t in texts:
        if not t:
            continue
        low = t.lower()
        for syn, key in _LOOKUP:
            if syn in low:
                out.add(key)
        out.update(w for w in re.split(r"[\s,/·]+", low) if w and w.isascii())
    return out


# ---------- 색 공간 ----------
def hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_lab(h: str) -> tuple[float, float, float]:
    r, g, b = (_lin(c) for c in hex_to_rgb(h))
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / 1.0
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e2000(lab1, lab2) -> float:
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbp = (h1p + h2p + 360) / 2
    else:
        hbp = (h1p + h2p - 360) / 2
    T = (1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    dtheta = 30 * math.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * dtheta)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


# ---------- 순위 ----------
@dataclass
class CmfMatch:
    option: CmfOption
    score: float
    color_score: Optional[float]
    material_score: Optional[float]
    min_delta_e: Optional[float] = None
    closest_palette: Optional[str] = None
    matched_materials: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "color": self.option.color, "material": self.option.material, "finish": self.option.finish,
            "hex_approx": self.option.hex_approx, "score": round(self.score, 3),
            "color_score": None if self.color_score is None else round(self.color_score, 3),
            "material_score": None if self.material_score is None else round(self.material_score, 3),
            "min_delta_e": None if self.min_delta_e is None else round(self.min_delta_e, 2),
            "closest_palette": self.closest_palette, "matched_materials": self.matched_materials,
            "flags": self.flags, "reasons": self.reasons,
        }


def score_option(opt: CmfOption, style: StyleTags) -> CmfMatch:
    flags, reasons = [], []
    color_score = min_de = closest = None
    if style.palette and opt.hex_approx:
        lab = hex_to_lab(opt.hex_approx)
        des = [(delta_e2000(lab, hex_to_lab(p)), p) for p in style.palette]
        min_de, closest = min(des)
        color_score = max(0.0, 1 - min_de / DE_SCALE)
        reasons.append(f"팔레트 {closest}와 색차 ΔE00 {min_de:.1f} (근사색 기준)")
    elif style.palette:
        flags.append("color_unknown")

    material_score = None
    matched: list[str] = []
    if style.materials:
        kw = material_keywords(opt.material, opt.finish, opt.color)
        want = {m for s in style.materials for m in (material_keywords(s) or {s.lower()})}
        matched = sorted(want & kw)
        material_score = len(matched) / len(want) if want else 0.0
        if matched:
            reasons.append(f"재질·마감 키워드 일치: {', '.join(matched)}")

    if color_score is not None and material_score is not None:
        score = W_COLOR * color_score + W_MATERIAL * material_score
    else:
        score = color_score if color_score is not None else (material_score or 0.0)
    return CmfMatch(opt, score, color_score, material_score, min_de, closest, matched, flags, reasons)


def rank_cmf(product: Product, style: StyleTags, top_k: int = 3) -> list[CmfMatch]:
    ranked = sorted((score_option(o, style) for o in product.cmf_options), key=lambda m: -m.score)
    return ranked[:top_k]
