"""벽지·바닥재 카탈로그와 스타일 기반 순위 (docs/specs/finishes.md).

점수는 CMF와 같은 규칙: 0.6 × 색 점수 + 0.4 × 재질 키워드 점수.
- 색 점수 = max(0, 1 − min ΔE00(톤, 팔레트) / 50). 마감재마다 가장 가까운 톤을 고른다.
- 키워드 점수 = 원하는 재질 키워드 중 마감재(키워드·질감·이름)에 들어 있는 비율.
- prefer_texture를 주면 그 질감을 원하는 키워드에 더한다.
스타일이 비어 있으면 0점, 카탈로그 순서 그대로.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .cmf import DE_SCALE, W_COLOR, W_MATERIAL, delta_e2000, hex_to_lab, material_keywords

Texture = Literal["plaster", "fabric", "stone", "wood", "paint"]
TEXTURE_KO = {"plaster": "회벽", "fabric": "직물", "stone": "스톤", "wood": "우드", "paint": "도장"}


class Tone(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    hex: str

    @field_validator("hex")
    @classmethod
    def _hex(cls, v: str) -> str:
        v = v.upper()
        if len(v) != 7 or v[0] != "#" or any(c not in "0123456789ABCDEF" for c in v[1:]):
            raise ValueError(f"#RRGGBB 형식이어야 함: {v}")
        return v


class Finish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: Literal["wall", "floor"]
    brand: str
    line: str
    pattern: Optional[str] = None
    name: str
    texture: Texture
    keywords: list[str] = Field(default_factory=list)
    trend: Optional[str] = None
    facts: list[str] = Field(default_factory=list)
    spec: dict = Field(default_factory=dict)
    tones: list[Tone]
    tone_basis: Literal["official", "approx"]
    source_url: str
    source_checked_at: str

    def tone(self, hex_: Optional[str] = None) -> Tone:
        if hex_ is None:
            return self.tones[0]
        for t in self.tones:
            if t.hex == hex_.upper():
                return t
        raise ValueError(f"{self.name}에 없는 톤: {hex_}")


def load_finishes(path: Path) -> list[Finish]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Finish.model_validate(x) for x in data["finishes"]]


@dataclass
class FinishMatch:
    finish: Finish
    tone: Tone
    score: float
    min_delta_e: Optional[float] = None
    matched: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"finish": self.finish.model_dump(), "tone": self.tone.model_dump(), "score": round(self.score, 3),
                "min_delta_e": None if self.min_delta_e is None else round(self.min_delta_e, 2),
                "matched": self.matched, "reasons": self.reasons,
                "approx_color": self.finish.tone_basis == "approx"}


def _score(f: Finish, labs: list, want: set[str]) -> FinishMatch:
    reasons: list[str] = []
    tone, color_score, min_de = f.tones[0], None, None
    if labs:
        best = min(((min(delta_e2000(hex_to_lab(t.hex), lab) for lab in labs), t) for t in f.tones), key=lambda x: x[0])
        min_de, tone = best
        color_score = max(0.0, 1 - min_de / DE_SCALE)
        reasons.append(f"{tone.name}이 원하는 색과 가까움 (ΔE00 {min_de:.1f}, 근사색 기준)")
    kw_score, matched = None, []
    if want:
        have = material_keywords(*f.keywords, f.texture, TEXTURE_KO[f.texture], f.name)
        matched = sorted(want & have)
        kw_score = len(matched) / len(want)
        if matched:
            reasons.append(f"재질 키워드 일치: {', '.join(matched)}")
    if color_score is not None and kw_score is not None:
        score = W_COLOR * color_score + W_MATERIAL * kw_score
    else:
        score = color_score if color_score is not None else (kw_score or 0.0)
    return FinishMatch(f, tone, score, min_de, matched, reasons)


def rank_finishes(items: list[Finish], kind: str, palette: list[str], materials: list[str],
                  prefer_texture: Optional[str] = None, top_k: Optional[int] = None) -> list[FinishMatch]:
    labs = [hex_to_lab(h) for h in palette]
    words = list(materials) + ([prefer_texture] if prefer_texture else [])
    want = {k for w in words for k in (material_keywords(w) or {w.lower()})}
    pool = [f for f in items if f.kind == kind]
    ranked = sorted((_score(f, labs, want) for f in pool), key=lambda m: -m.score)  # 안정 정렬: 동점은 카탈로그 순서
    return ranked[:top_k] if top_k else ranked
