"""고객이 말로 적은 취향 → 스타일(팔레트·재질 키워드·선호 질감).

생성형 AI(Claude)는 말을 스타일로 '옮기는' 일만 한다. 어떤 벽지·바닥재·가전 색이 맞는지
점수는 recommender(finishes.py, cmf.py)가 계산한다 (CLAUDE.md: 판정·점수는 코드가 계산).

API 키는 서버 .env에만 둔다. ANTHROPIC_API_KEY가 있으면 Claude, OPENAI_API_KEY만 있으면 OpenAI를 쓴다
(둘 다 있으면 STYLE_AI_PROVIDER=claude|openai로 고른다). 키가 없거나 호출이 실패하면
키워드 규칙(rule_based_style)으로 대신 해석하고 engine="rules"로 알려 준다.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

log = logging.getLogger(__name__)

MODEL = os.getenv("STYLE_AI_MODEL", "claude-opus-5-5")
OPENAI_MODEL = os.getenv("STYLE_AI_OPENAI_MODEL", "gpt-5-mini")
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
TextureName = Literal["plaster", "fabric", "stone", "wood", "paint"]


class StyleIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    palette: list[str] = Field(description="공간 전체 색 2~5개, #RRGGBB. 밝은 바탕색부터")
    materials: list[str] = Field(description="재질·마감·색 키워드(영어 소문자): wood, oak, stone, marble, plaster, fabric, "
                                             "linen, paint, matte, glossy, metal, glass, white, beige, gray, black, brown, green, navy, natural, minimal, warm")
    summary: str = Field(description="고객에게 보여 줄 한두 문장 한국어 설명. 숫자·점수·제품명 없이 분위기만")
    wall_texture: Optional[TextureName] = Field(default=None, description="벽에 어울리는 질감")
    floor_texture: Optional[TextureName] = Field(default=None, description="바닥에 어울리는 질감 (wood 또는 stone)")
    _engine: str = PrivateAttr(default="claude")

    @field_validator("palette")
    @classmethod
    def _hex(cls, v: list[str]) -> list[str]:
        if not v or len(v) > 6:
            raise ValueError("팔레트는 1~6색")
        for h in v:
            if not HEX.match(h):
                raise ValueError(f"#RRGGBB 형식이어야 함: {h}")
        return [h.upper() for h in v]

    @field_validator("materials")
    @classmethod
    def _lower(cls, v: list[str]) -> list[str]:
        return [m.strip().lower() for m in v if m.strip()][:10]

    @property
    def engine(self) -> str:
        return self._engine

    @engine.setter
    def engine(self, v: str) -> None:
        self._engine = v


SYSTEM = """너는 LG HouseTwin의 인테리어 스타일 해석기다.
고객이 집을 어떻게 꾸미고 싶은지 한국어로 말하면, 그 말을 공간 스타일로 옮긴다.
- palette: 벽·바닥·가구·가전에 쓸 대표색. 고객 말에 없는 강한 색은 넣지 않는다.
- materials: 정해진 영어 키워드만 쓴다.
- wall_texture / floor_texture: 아래 카탈로그에 있는 질감 중 고른다.
- summary: 고객이 읽을 짧은 설명. 점수·치수·제품명은 쓰지 않는다 (제품 추천과 점수는 프로그램이 따로 계산한다).
지금 고를 수 있는 실제 벽지·바닥재 (2026 트렌드 조사):
{catalog}"""


def pick_provider() -> Optional[str]:
    has = {"claude": bool(os.getenv("ANTHROPIC_API_KEY")), "openai": bool(os.getenv("OPENAI_API_KEY"))}
    want = (os.getenv("STYLE_AI_PROVIDER") or "").strip().lower()
    if want in has and has[want]:
        return want
    return "claude" if has["claude"] else "openai" if has["openai"] else None


def interpret_style(prompt: str, catalog_brief: str = "", client=None) -> StyleIntent:
    """서버에 있는 키로 해석 (Claude 우선, 없으면 OpenAI). 키가 없거나 실패·거절이면 규칙 기반으로."""
    if client is None:
        provider = pick_provider()
        if provider is None:
            return rule_based_style(prompt)
        if provider == "openai":
            return interpret_with_openai(prompt, catalog_brief)
        import anthropic
        client = anthropic.Anthropic(timeout=float(os.getenv("STYLE_AI_TIMEOUT_S", 40)), max_retries=1)
    try:
        r = client.beta.messages.parse(
            model=MODEL,
            max_tokens=2000,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM.format(catalog=catalog_brief or "(없음)"),
            messages=[{"role": "user", "content": prompt}],
            output_format=StyleIntent,
        )
        out = getattr(r, "parsed_output", None)
        if r.stop_reason == "refusal" or out is None:
            log.warning("스타일 해석 거절/빈 응답 → 규칙 기반 (stop_reason=%s)", r.stop_reason)
            return rule_based_style(prompt)
        out.engine = "claude"
        return out
    except Exception as e:  # 네트워크·키·한도 문제여도 시연은 계속된다
        log.warning("스타일 해석 실패 → 규칙 기반: %s", e)
        return rule_based_style(prompt)


def interpret_with_openai(prompt: str, catalog_brief: str = "", client=None) -> StyleIntent:
    """OpenAI structured output으로 같은 StyleIntent를 받는다. 실패·거절이면 규칙 기반으로."""
    try:
        if client is None:
            import openai
            client = openai.OpenAI(timeout=float(os.getenv("STYLE_AI_TIMEOUT_S", 40)), max_retries=1)
        r = client.chat.completions.parse(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": SYSTEM.format(catalog=catalog_brief or "(없음)")},
                      {"role": "user", "content": prompt}],
            response_format=StyleIntent,
        )
        msg = r.choices[0].message
        if getattr(msg, "refusal", None) or msg.parsed is None:
            log.warning("스타일 해석(OpenAI) 거절/빈 응답 → 규칙 기반")
            return rule_based_style(prompt)
        out = msg.parsed
        out.engine = "openai"
        return out
    except Exception as e:
        log.warning("스타일 해석(OpenAI) 실패 → 규칙 기반: %s", e)
        return rule_based_style(prompt)


# ---------------- 키 없이 쓰는 규칙 기반 ----------------
# (키워드들, 팔레트 색, 재질 키워드, 벽 질감, 바닥 질감, 설명 조각)
_RULES = [
    (("우드", "나무", "원목", "오크", "내추럴", "따뜻"), ["#F0EEE9", "#D5B48C", "#B08A62"], ["wood", "natural", "warm"], None, "wood", "따뜻한 나무 결"),
    (("대리석", "마블", "스톤", "돌", "호텔"), ["#E6E3DE", "#B9B6B0"], ["stone"], "stone", "stone", "대리석 같은 돌 질감"),
    (("회벽", "미장", "석회", "질감"), ["#ECE8E1", "#CFC9C0"], ["plaster", "matte"], "plaster", None, "손으로 바른 듯한 회벽"),
    (("린넨", "패브릭", "직물", "포근", "아늑"), ["#E6DFD3", "#D6CBB9"], ["fabric", "warm"], "fabric", None, "포근한 직물 느낌"),
    (("화이트", "하얀", "밝", "깨끗", "미니멀", "심플"), ["#F0EEE9", "#E8E4DC"], ["white", "minimal", "matte"], "paint", None, "밝고 깔끔한 화이트"),
    (("어둡", "다크", "블랙", "검정", "무드", "시크", "모던"), ["#2B2B2B", "#4E4643", "#8D8D8A"], ["black", "matte"], None, "stone", "차분하고 어두운 무드"),
    (("브라운", "갈색", "카라멜", "초콜릿", "테라코타", "어스"), ["#C19C78", "#8B5E3C", "#C08E73"], ["brown", "warm"], None, "wood", "흙빛 브라운 톤"),
    (("그린", "초록", "식물", "자연"), ["#9DA388", "#E9E1D2"], ["green", "natural"], "fabric", None, "편안한 그린 포인트"),
    (("블루", "파랑", "네이비", "청"), ["#AEB9C2", "#3B4A5A"], ["navy"], "fabric", None, "차분한 블루 그레이"),
    (("그레이", "회색", "그레이지"), ["#CFCAC2", "#9A9893"], ["gray"], "plaster", None, "부드러운 그레이"),
    (("베이지", "크림", "아이보리"), ["#EDE7DC", "#E3D9CB"], ["beige"], "plaster", None, "크림빛 베이지"),
]
_NEUTRAL = (["#F0EEE9", "#D5B48C", "#CFC9C0"], ["natural", "matte"], "plaster", "wood")


def rule_based_style(prompt: str) -> StyleIntent:
    text = prompt or ""
    palette: list[str] = []
    materials: list[str] = []
    wall = floor = None
    bits: list[str] = []
    for words, pal, mats, w, f, bit in _RULES:
        if any(k in text for k in words):
            palette += [h for h in pal if h not in palette]
            materials += [m for m in mats if m not in materials]
            wall, floor = wall or w, floor or f
            bits.append(bit)
    if not palette:
        palette, materials, wall, floor = list(_NEUTRAL[0]), list(_NEUTRAL[1]), _NEUTRAL[2], _NEUTRAL[3]
        summary = "말씀에서 특정 취향을 찾지 못해, 요즘 많이 쓰는 밝은 화이트와 내추럴 오크로 시작해 볼게요."
    else:
        summary = f"{', '.join(bits)}을 살린 공간으로 맞춰 볼게요."
    s = StyleIntent(palette=palette[:6], materials=materials, summary=summary,
                    wall_texture=wall, floor_texture=floor or "wood")
    s.engine = "rules"
    return s
