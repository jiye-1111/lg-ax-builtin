"""조합 추천: 고객이 고른 가전 종류 + 목표 가격 + 분위기 → 가구·가전·벽지·바닥재가 다 들어간 조합 2~3개.

생성형 AI(OpenAI 또는 Claude)는 '컨셉'만 만든다: 이름, 이 집에 왜 맞는지, 실제로 쓸 만한 팁,
색·재질, 어떤 가구를 어떤 역할(중심·양옆·앞·마주·벽·구석)로 둘지, 가격 성격(목표·아끼기·한 단계 위).
제품 고르기·자리 잡기·가격 합계는 코드가 한다 (recommender.layout, cmf, finishes). CLAUDE.md: 계산은 코드.
키가 없거나 호출이 실패하면 분위기별 규칙 템플릿으로 같은 모양의 컨셉을 만든다.
"""
from __future__ import annotations

import base64
import binascii
import logging
import math
import os
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .ai_products import CATEGORY_KO, Category
from .ai_style import HEX, MODEL, OPENAI_MODEL, TextureName, openai_extra, pick_provider
from .decor import DECOR

log = logging.getLogger(__name__)

DecorKind = Literal["sofa", "table", "chair", "coffee", "bed", "desk", "storage", "shelf", "dresser", "basecab",
                    "island", "tvstand", "rug", "lamp", "plant", "nightstand"]
SlotRole = Literal["anchor", "pair", "front", "rug", "facing", "wall", "corner", "desk_chair"]
Purpose = Literal["bedroom", "living", "kitchen", "study"]
PricePlan = Literal["target", "save", "upgrade"]
PLAN_FACTOR = {"target": 1.0, "save": 0.75, "upgrade": 1.25}
# 가전을 안 골랐을 때 그 공간에 흔히 두는 LG 가전 (하나 둘만. 나열하지 않는다)
PURPOSE_CATS = {"kitchen": ["refrigerator", "water_purifier"], "bedroom": ["air_conditioner", "air_purifier"],
                "living": ["tv", "air_conditioner"], "study": ["air_purifier"]}
PLAN_KO = {"target": "목표 가격에 맞춤", "save": "아끼는 조합", "upgrade": "한 단계 위"}
PURPOSE_KO = {"bedroom": "침실", "living": "거실", "kitchen": "주방", "study": "서재"}
# 협탁은 서랍장 모델을 작게 쓴다 (판정·3D 모두 크기만 다름)
NIGHTSTAND_M = (0.45, 0.55, 0.40)


class Slot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: DecorKind = Field(description="가구 종류. nightstand = 침대 옆 협탁")
    role: SlotRole = Field(description="anchor 중심 가구(방에 하나) · pair 중심 가구 양옆 대칭 · front 중심 가구 바로 앞 · "
                                       "rug 중심 가구 앞 러그 · facing 중심 가구를 마주 보는 벽 · wall 남는 벽 · corner 구석 · desk_chair 책상 앞 의자")


class Idea(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(description="조합 이름, 한국어 12자 안. 예: 호텔 스위트")
    why: str = Field(description="이 집·이 고객에게 왜 맞는지 한두 문장. 제품명·가격·치수 숫자 없이")
    tips: list[str] = Field(description="이 분위기를 살리는 실제 조언 2~3개 (조명 색, 패브릭, 배치 요령). 한 문장씩")
    palette: list[str] = Field(description="#RRGGBB 2~4개, 밝은 바탕색부터")
    materials: list[str] = Field(description="영어 소문자 재질 키워드: wood, oak, stone, marble, plaster, fabric, linen, matte, "
                                             "glossy, metal, glass, white, beige, gray, black, brown, green, navy, natural, minimal, warm")
    wall_texture: Optional[TextureName] = None
    floor_texture: Optional[TextureName] = None
    furniture: list[Slot] = Field(description="놓을 가구 3~8개. anchor는 하나만, 맨 앞에")
    price_plan: PricePlan = Field(description="target 목표 가격에 맞춤 · save 아끼기 · upgrade 한 단계 위. 세 조합이 서로 달라야 함")
    appliance_point: str = Field(description="이 컨셉에서 가전을 고를 때 볼 점 한 문장 (색·크기·소음 등). 제품명·숫자 없이")

    @field_validator("name")
    @classmethod
    def _plain_name(cls, v: str) -> str:  # AI가 이름 끝에 붙이는 '(target)' 같은 말 빼기
        return re.sub(r"\s*[(\[]?\b(target|save|upgrade)\b[)\]]?\s*$", "", v, flags=re.I).strip() or v

    @field_validator("palette")
    @classmethod
    def _hex(cls, v: list[str]) -> list[str]:
        out = [h.upper() for h in v if HEX.match(h)][:4]
        if not out:
            raise ValueError("팔레트 색이 없음")
        return out

    @field_validator("furniture")
    @classmethod
    def _one_anchor(cls, v: list[Slot]) -> list[Slot]:
        seen, out = False, []
        for s in v[:8]:
            if s.role == "anchor":
                if seen:
                    s = Slot(kind=s.kind, role="wall")
                seen = True
            out.append(s)
        return out


class Ideas(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: Purpose = Field(description="이 공간 용도")
    ideas: list[Idea] = Field(description="성격이 다른 조합 2~3개")
    seen: Optional[str] = Field(None, description="사진이 있을 때만: 사진에서 읽은 느낌 한 줄, 30자 안. "
                                                  "예: 짙은 호두나무 · 베이지 리넨 · 따뜻한 간접조명. 사진이 없으면 null")
    not_a_room: bool = Field(False, description="사진이 실내 공간 사진이 아니면 true (그때 ideas는 비워도 됨)")

    @field_validator("seen")
    @classmethod
    def _short_seen(cls, v: Optional[str]) -> Optional[str]:
        v = (v or "").strip().rstrip(".") or None
        if v is None or len(v) <= SEEN_MAX:
            return v
        cut = max(v.rfind(c, 0, SEEN_MAX) for c in ("·", ",", "/"))  # 끊기 좋은 자리에서 자른다 (말줄임표 없이)
        return v[:cut if cut > 10 else SEEN_MAX].rstrip(" ,·/")


SYSTEM = """너는 LG전자 매장의 인테리어 컨설턴트다. 고객의 실제 집(스캔)과 고른 가전, 목표 가격을 보고
고객이 '이렇게 살고 싶다'고 느낄 조합 2~3개의 컨셉을 만든다.
지켜야 할 것:
- 세 조합은 성격이 달라야 한다: price_plan을 target, save, upgrade로 하나씩.
- 가구는 아래 목록 안에서만 고른다. 중심 가구(anchor)는 하나. 방 크기에 비해 너무 많이 넣지 않는다.
- 배치 원칙(인테리어 연구): 중심 가구를 정하고 양옆을 대칭으로, 정면 앞은 비워 동선을 지킨다.
- 제품 이름, 가격, 치수 숫자를 지어내지 않는다. 어떤 제품이 들어가는지와 가격은 프로그램이 계산한다.
- why와 tips는 고객에게 바로 도움이 되는 말로. 막연한 칭찬 대신 무엇을 어떻게 하면 되는지.
고를 수 있는 가구: {kinds}"""


PHOTO_RULES = """
고객이 사진을 한 장 붙였다. 사진은 '이런 느낌으로 살고 싶다'는 참고일 뿐이다.
- 사진에서는 분위기, 주요 색(palette), 재질(materials), 벽·바닥 질감, 보이는 가구 종류, 공간 용도만 읽는다.
- 사진 속 가구·가전의 브랜드나 제품명을 추측하지 않는다. 사람 얼굴·글자·개인 정보는 무시한다.
- seen에는 사진에서 읽은 느낌을 짧은 말 세 개로, '·'로 잇는다. 예: 짙은 호두나무 · 베이지 리넨 · 따뜻한 간접조명
- 세 조합 모두 사진 느낌을 따르되 price_plan만 다르게.
- name, why, tips, seen은 모두 한국어로 쓴다 (영어 이름 금지).
- 실내 공간 사진이 아니면 not_a_room을 true로."""

SEEN_MAX = 40
PHOTO_TYPES = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG", "image/webp": b"RIFF"}
PHOTO_MAX_BYTES = 5 * 1024 * 1024
_DATA_URL = re.compile(r"^data:(image/[a-z]+);base64,([A-Za-z0-9+/=\s]+)$")


def parse_photo(data_url: str) -> tuple[str, str]:
    """하우니에 붙인 사진(data URL)을 (형식, base64)로. 형식·실제 바이트·크기를 확인한다. 저장하지 않는다."""
    m = _DATA_URL.match(data_url or "")
    if not m or m.group(1) not in PHOTO_TYPES:
        raise ValueError("jpg, png, webp 사진만 붙일 수 있어요")
    b64 = re.sub(r"\s", "", m.group(2))
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("사진을 읽을 수 없어요") from None
    if len(raw) > PHOTO_MAX_BYTES:
        raise ValueError("사진은 5MB 안으로 붙여 주세요")
    if not raw.startswith(PHOTO_TYPES[m.group(1)]):
        raise ValueError("사진 파일이 아닌 것 같아요")
    return m.group(1), b64


def room_brief(room, zones: list[dict], categories: list[str], budget: Optional[int], prompt: str, stock: dict) -> str:
    """LLM에 넘길 집 요약 (코드가 만든다)."""
    xs = [c for w in room.walls for c in (w.start[0], w.end[0])]
    zs = [c for w in room.walls for c in (w.start[1], w.end[1])]
    W, D = max(xs) - min(xs), max(zs) - min(zs)
    doors = sum(1 for o in room.openings if o.type != "window")
    wins = sum(1 for o in room.openings if o.type == "window")
    longest = max((math.dist(w.start, w.end) for w in room.walls), default=0)
    objs = ", ".join(sorted({o.category for o in room.objects})) or "없음"
    lines = [f"고객 말: {prompt or '(없음)'}",
             f"공간: 약 {W:.1f} x {D:.1f} m, 가장 긴 벽 {longest:.1f} m, 문 {doors}개, 창 {wins}개, 스캔된 가구: {objs}",
             f"그려 둔 영역 용도: {', '.join(z.get('purpose', '') for z in zones) or '없음'}",
             f"목표 가격(LG 가전 합계): {f'{budget // 10000:,}만 원' if budget else '정하지 않음'}"]
    for c in categories:
        n, lo, hi = stock.get(c, (0, None, None))
        rng = f", {lo // 10000:,}~{hi // 10000:,}만 원" if lo and hi else ""
        lines.append(f"고른 가전: {CATEGORY_KO.get(c, c)} (이 집에 들어가는 {n}종{rng})")
    return "\n".join(lines)


def ask_ideas(brief: str, image: Optional[tuple[str, str]] = None, *, client=None) -> Optional[Ideas]:
    """image = (형식, base64). 있으면 사진을 같이 보내 분위기·색만 읽게 한다."""
    provider = pick_provider() if client is None else "given"
    if provider is None:
        return None
    system = SYSTEM.format(kinds=", ".join(k for k in DecorKind.__args__)) + (PHOTO_RULES if image else "")
    try:
        if provider == "openai" or (client is not None and hasattr(client, "chat")):
            if client is None:
                import openai
                client = openai.OpenAI(timeout=float(os.getenv("STYLE_AI_TIMEOUT_S", 40)), max_retries=1)
            user = brief if not image else [{"type": "text", "text": brief},
                                            {"type": "image_url", "image_url": {"url": f"data:{image[0]};base64,{image[1]}", "detail": "low"}}]
            r = client.chat.completions.parse(model=OPENAI_MODEL, response_format=Ideas, **openai_extra(),
                                              messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
            msg = r.choices[0].message
            return None if getattr(msg, "refusal", None) else msg.parsed
        if client is None:
            import anthropic
            client = anthropic.Anthropic(timeout=float(os.getenv("STYLE_AI_TIMEOUT_S", 40)), max_retries=1)
        r = client.beta.messages.parse(model=MODEL, max_tokens=3000, output_config={"effort": "low"},
                                       betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                                       system=system, output_format=Ideas,
                                       messages=[{"role": "user", "content": brief if not image else [
                                           {"type": "image", "source": {"type": "base64", "media_type": image[0], "data": image[1]}},
                                           {"type": "text", "text": brief}]}])
        return None if r.stop_reason == "refusal" else getattr(r, "parsed_output", None)
    except Exception as e:  # 키·네트워크·한도 문제여도 규칙 템플릿으로 계속
        log.warning("조합 컨셉 생성 실패 → 규칙 템플릿: %s", e)
        return None


# ---------------- 키 없이 쓰는 규칙 템플릿 ----------------
def _s(*pairs: tuple[str, str]) -> list[Slot]:
    return [Slot(kind=k, role=r) for k, r in pairs]


_SETS = {
    "bedroom": {"full": _s(("bed", "anchor"), ("nightstand", "pair"), ("rug", "rug"), ("dresser", "wall"), ("lamp", "corner")),
                "lean": _s(("bed", "anchor"), ("nightstand", "pair"), ("lamp", "corner")),
                "plus": _s(("bed", "anchor"), ("nightstand", "pair"), ("rug", "rug"), ("dresser", "wall"), ("chair", "corner"),
                           ("plant", "corner"))},
    "living": {"full": _s(("sofa", "anchor"), ("coffee", "front"), ("rug", "rug"), ("tvstand", "facing"), ("lamp", "corner")),
               "lean": _s(("sofa", "anchor"), ("coffee", "front"), ("tvstand", "facing")),
               "plus": _s(("sofa", "anchor"), ("coffee", "front"), ("rug", "rug"), ("tvstand", "facing"), ("shelf", "wall"),
                          ("lamp", "corner"), ("plant", "corner"))},
    "kitchen": {"full": _s(("basecab", "anchor"), ("table", "wall"), ("plant", "corner")),
                "lean": _s(("basecab", "anchor"), ("table", "wall")),
                "plus": _s(("basecab", "anchor"), ("island", "front"), ("table", "wall"), ("shelf", "wall"), ("plant", "corner"))},
    "study": {"full": _s(("desk", "anchor"), ("chair", "desk_chair"), ("shelf", "wall"), ("lamp", "corner")),
              "lean": _s(("desk", "anchor"), ("chair", "desk_chair"), ("shelf", "wall")),
              "plus": _s(("desk", "anchor"), ("chair", "desk_chair"), ("shelf", "wall"), ("storage", "wall"), ("rug", "rug"),
                         ("plant", "corner"))},
}

# (키워드, 이름 3개, why, tips, palette, materials, wall, floor, 가전 볼 점)
_MOODS = [
    (("호텔", "스위트", "럭셔리", "고급", "리조트"), ("호텔 스위트", "비즈니스 호텔", "리조트 스위트"),
     "중심 가구를 벽 가운데 두고 양옆을 똑같이 맞춰 호텔 객실처럼 정돈된 느낌을 내요.",
     ["양옆 협탁과 조명을 같은 것으로 맞추면 대칭이 살아나요.", "조명은 따뜻한 전구색으로 낮게, 천장 등은 줄여 보세요.",
      "침구·커튼은 베이지와 브라운 두세 가지 톤으로만 맞춰요."],
     ["#EEE8DF", "#B9A58C", "#5B4B3E"], ["fabric", "stone", "warm"], "fabric", "wood", "벽지 톤에 가까운 차분한 색, 튀지 않는 매끈한 면"),
    (("우드", "나무", "원목", "내추럴", "따뜻"), ("내추럴 우드", "작은 숲 같은 방", "북유럽 원목"),
     "나무 결 바닥과 밝은 벽으로 오래 머물러도 편한 방을 만들어요.",
     ["바닥과 가구 나무 색은 한 단계만 차이 나게 맞춰요.", "식물을 창가 구석에 두면 나무 톤이 더 살아나요."],
     ["#F0EEE9", "#D5B48C", "#8A6A4A"], ["wood", "natural", "warm"], "plaster", "wood", "베이지·크림처럼 나무와 어울리는 따뜻한 색"),
    (("모던", "다크", "블랙", "시크", "무드"), ("모던 다크", "미니멀 블랙", "갤러리 무드"),
     "어두운 바탕에 선이 단순한 가구로 무게감 있는 공간을 만들어요.",
     ["어두운 벽에는 간접 조명을 벽 쪽으로 비춰 깊이를 만들어요.", "금속·유리 소품은 한두 개만 포인트로."],
     ["#E5E2DE", "#4E4643", "#2B2B2B"], ["black", "matte", "stone"], "paint", "stone", "블랙·그레이처럼 어두운 무광"),
    (("화이트", "밝", "미니멀", "깔끔", "심플"), ("밝은 미니멀", "화이트 스튜디오", "갤러리 화이트"),
     "밝은 벽과 낮은 가구로 방을 넓어 보이게 해요.",
     ["가구 높이를 낮게 맞추면 천장이 높아 보여요.", "수납은 문 달린 장으로 물건을 가려요."],
     ["#F4F2EE", "#E3DED6", "#A9A39A"], ["white", "minimal", "matte"], "paint", "wood", "화이트·실버처럼 밝은 색"),
]


def detect_purpose(prompt: str, categories: list[str], zones: list[dict]) -> Purpose:
    t = prompt or ""
    if any(w in t for w in ("침실", "침대", "안방", "잠", "호텔")):
        return "bedroom"
    if any(w in t for w in ("서재", "책상", "공부", "작업")):
        return "study"
    if any(w in t for w in ("주방", "부엌", "키친")):
        return "kitchen"
    if any(w in t for w in ("거실", "소파", "티비", "TV")):
        return "living"
    kitchen = {"refrigerator", "kimchi_refrigerator", "dishwasher", "oven", "cooktop", "microwave", "water_purifier", "wine_cellar"}
    if categories and all(c in kitchen for c in categories):
        return "kitchen"
    z = next((x.get("purpose") for x in zones if x.get("purpose") in PURPOSE_KO), None)
    return z or "living"


def rule_ideas(prompt: str, purpose: Purpose) -> Ideas:
    mood = next((m for m in _MOODS if any(w in (prompt or "") for w in m[0])), _MOODS[1])
    _, names, why, tips, pal, mats, wall, floor, point = mood
    sets = _SETS[purpose]
    ideas = [Idea(name=names[i], why=why, tips=tips, palette=pal, materials=mats, wall_texture=wall, floor_texture=floor,
                  furniture=sets[s], price_plan=plan, appliance_point=point)
             for i, (s, plan) in enumerate((("full", "target"), ("lean", "save"), ("plus", "upgrade")))]
    return Ideas(purpose=purpose, ideas=ideas)


def slot_sku(kind: str) -> tuple[str, Optional[tuple[float, float, float]]]:
    if kind == "nightstand":
        return "decor:dresser", NIGHTSTAND_M
    if kind not in DECOR:
        raise KeyError(kind)
    return f"decor:{kind}", None


def label_of(kind: str) -> str:
    return "협탁" if kind == "nightstand" else DECOR[kind]["label"]


__all__ = ["Category", "Idea", "Ideas", "PLAN_FACTOR", "PLAN_KO", "PURPOSE_KO", "Slot", "ask_ideas", "detect_purpose",
           "label_of", "room_brief", "rule_ideas", "slot_sku"]
