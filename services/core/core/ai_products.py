"""고객이 말로 적은 제품 조건 → 찾기 조건(종류·용량·색·가격·설치 공간).

생성형 AI는 말을 조건으로 '옮기는' 일만 한다. 어떤 제품이 맞고 들어가는지는
recommender(finder.py, fit.py)가 계산한다 (CLAUDE.md: 판정·점수는 코드가 계산).

키와 제공자는 ai_style.py와 같은 것을 쓴다. 키가 없거나 호출이 실패하면
정규식 규칙(rule_based_products)으로 읽고 engine="rules"로 알려 준다.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

from .ai_style import MODEL, OPENAI_MODEL, pick_provider

log = logging.getLogger(__name__)

# 긴 이름을 먼저 본다 (김치냉장고 → 냉장고 순)
CATEGORY_WORDS = [
    ("kimchi_refrigerator", "김치냉장고", ("김치냉장고", "김냉", "김치 냉장고")),
    ("wine_cellar", "와인셀러", ("와인셀러", "와인 셀러", "와인냉장고")),
    ("freezer", "냉동고", ("냉동고",)),
    ("refrigerator", "냉장고", ("냉장고",)),
    ("dishwasher", "식기세척기", ("식기세척기", "식세기")),
    ("wash_tower", "워시타워", ("워시타워", "워시 타워")),
    ("washer_dryer", "세탁건조기", ("세탁건조기", "워시콤보")),
    ("washer", "세탁기", ("세탁기",)),
    ("dryer", "건조기", ("건조기",)),
    ("styler", "스타일러", ("스타일러",)),
    ("shoe_care", "슈케어", ("슈케어", "슈케이스", "신발관리기")),
    ("microwave", "전자레인지", ("전자레인지", "광파오븐", "광파 오븐")),
    ("oven", "오븐", ("오븐",)),
    ("cooktop", "인덕션·전기레인지", ("인덕션", "쿡탑", "전기레인지", "하이라이트")),
    ("water_purifier", "정수기", ("정수기",)),
    ("air_purifier", "공기청정기", ("공기청정기", "공청기")),
    ("air_conditioner", "에어컨", ("에어컨",)),
    ("dehumidifier", "제습기", ("제습기",)),
    ("humidifier", "가습기", ("가습기",)),
    ("portable_tv", "이동식 TV", ("스탠바이미", "이동식 TV", "이동식 티비")),
    ("tv", "TV", ("TV", "tv", "티비", "텔레비전")),
    ("vacuum", "청소기", ("청소기",)),
    ("massage_chair", "안마의자", ("안마의자",)),
    ("plant_grower", "식물재배기", ("식물재배기", "틔운")),
]
CATEGORY_KO = {c: ko for c, ko, _ in CATEGORY_WORDS}
Category = Literal["refrigerator", "kimchi_refrigerator", "freezer", "wine_cellar", "dishwasher", "oven", "cooktop", "microwave",
                   "water_purifier", "washer", "dryer", "wash_tower", "washer_dryer", "styler", "shoe_care", "air_conditioner",
                   "air_purifier", "dehumidifier", "humidifier", "tv", "portable_tv", "vacuum", "massage_chair", "plant_grower"]
ColorGroup = Literal["화이트", "베이지", "실버·그레이", "블랙", "그린"]
_LIMITS = {"capacity_min": (1, 2000), "capacity_max": (1, 2000), "price_min": (10_000, 100_000_000),
           "price_max": (10_000, 100_000_000), "space_w": (50, 20000), "space_h": (50, 20000), "space_d": (50, 20000)}
CONDITION_KEYS = ("category", "install", "capacity_min", "capacity_max", "color", "price_min", "price_max",
                  "space_w", "space_h", "space_d")


class ProductIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wants_products: bool = Field(description="가전제품을 찾거나 추천해 달라는 말이면 true. 벽·바닥 분위기만 말하면 false")
    also_style: bool = Field(description="벽지·바닥재·집 분위기도 바꿔 달라는 말이 같이 있으면 true. 제품 색만 말한 것이면 false")
    category: Optional[Category] = Field(default=None, description="찾는 제품 종류. 말하지 않았으면 null")
    install: Optional[Literal["built_in", "freestanding"]] = Field(default=None, description="빌트인이면 built_in, 일반형이면 freestanding")
    capacity_min: Optional[float] = Field(default=None, description="용량 하한(L). '600L 이상', '대용량'처럼 말했을 때만")
    capacity_max: Optional[float] = Field(default=None, description="용량 상한(L)")
    color: Optional[ColorGroup] = Field(default=None, description="원하는 제품 색 묶음")
    price_min: Optional[int] = Field(default=None, description="가격 하한(원)")
    price_max: Optional[int] = Field(default=None, description="가격 상한(원). '300만 원 이하'면 3000000")
    space_w: Optional[float] = Field(default=None, description="제품을 놓을 자리의 폭(mm). 95cm면 950")
    space_h: Optional[float] = Field(default=None, description="놓을 자리의 높이(mm)")
    space_d: Optional[float] = Field(default=None, description="놓을 자리의 깊이(mm)")
    sort: Literal["recommended", "size", "price"] = Field(default="recommended", description="싼 순이면 price, 작은 순이면 size, 그 밖에는 recommended")
    _engine: str = PrivateAttr(default="claude")

    @field_validator(*_LIMITS)
    @classmethod
    def _sane(cls, v, info):
        lo, hi = _LIMITS[info.field_name]
        return v if v is not None and lo <= v <= hi else None

    @property
    def engine(self) -> str:
        return self._engine

    @engine.setter
    def engine(self, v: str) -> None:
        self._engine = v

    def conditions(self) -> dict:
        """말에서 읽은 조건만 (없는 값은 뺀다)."""
        d = self.model_dump()
        return {k: (int(d[k]) if isinstance(d[k], float) and d[k].is_integer() else d[k]) for k in CONDITION_KEYS if d[k] is not None}


SYSTEM = """너는 LG HouseTwin의 제품 조건 해석기다.
고객이 한국어로 한 말에서 LG 가전을 찾는 조건만 뽑아 정해진 칸에 옮긴다.
- 말에 없는 조건은 지어내지 않고 null로 둔다.
- 단위를 맞춘다: 용량은 L, 가격은 원, 놓을 자리 치수는 mm.
- 제품을 고르거나 추천하지 않는다. 어떤 제품이 맞는지는 프로그램이 카탈로그에서 계산한다."""


def interpret_products(prompt: str, client=None) -> ProductIntent:
    """서버에 있는 키로 해석 (ai_style과 같은 제공자). 키가 없거나 실패·거절이면 규칙 기반으로."""
    if client is None:
        provider = pick_provider()
        if provider is None:
            return rule_based_products(prompt)
        if provider == "openai":
            return interpret_products_with_openai(prompt)
        import anthropic
        client = anthropic.Anthropic(timeout=float(os.getenv("STYLE_AI_TIMEOUT_S", 40)), max_retries=1)
    try:
        r = client.beta.messages.parse(
            model=MODEL,
            max_tokens=1000,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=ProductIntent,
        )
        out = getattr(r, "parsed_output", None)
        if r.stop_reason == "refusal" or out is None:
            log.warning("제품 조건 해석 거절/빈 응답 → 규칙 기반 (stop_reason=%s)", r.stop_reason)
            return rule_based_products(prompt)
        out.engine = "claude"
        return out
    except Exception as e:
        log.warning("제품 조건 해석 실패 → 규칙 기반: %s", e)
        return rule_based_products(prompt)


def interpret_products_with_openai(prompt: str, client=None) -> ProductIntent:
    try:
        if client is None:
            import openai
            client = openai.OpenAI(timeout=float(os.getenv("STYLE_AI_TIMEOUT_S", 40)), max_retries=1)
        r = client.chat.completions.parse(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            response_format=ProductIntent,
        )
        msg = r.choices[0].message
        if getattr(msg, "refusal", None) or msg.parsed is None:
            log.warning("제품 조건 해석(OpenAI) 거절/빈 응답 → 규칙 기반")
            return rule_based_products(prompt)
        out = msg.parsed
        out.engine = "openai"
        return out
    except Exception as e:
        log.warning("제품 조건 해석(OpenAI) 실패 → 규칙 기반: %s", e)
        return rule_based_products(prompt)


# ---------------- 키 없이 쓰는 규칙 기반 ----------------
_NUM = r"(\d+(?:,\d{3})*(?:\.\d+)?)"
_MORE, _LESS = ("이상", "넘", "초과", "부터"), ("이하", "미만", "까지", "안", "밑", "아래", "이내")
_CAP = re.compile(_NUM + r"\s*(?:L|l|ℓ|리터)(?![a-zA-Z])\s*(\S{0,3})")
_PRICE = re.compile(_NUM + r"\s*(천만|백만|만)\s*원?\s*(대)?\s*(\S{0,3})")
_DIM_WORDS = {"폭": "space_w", "너비": "space_w", "가로": "space_w", "높이": "space_h", "깊이": "space_d"}
_UNIT = r"(mm|cm|m|밀리|센티|미터)?"
_DIM_A = re.compile(r"(폭|너비|가로|높이|깊이)\s*(?:은|는|이|가)?\s*" + _NUM + r"\s*" + _UNIT + r"(?![a-zA-Z])")
_DIM_B = re.compile(_NUM + r"\s*(mm|cm|m|밀리|센티|미터)\s*(폭|너비|가로|높이|깊이)")
_COLORS = [("베이지", ("베이지", "크림", "아이보리")), ("블랙", ("블랙", "검정", "검은", "까만")),
           ("실버·그레이", ("실버", "그레이", "회색", "스테인리스", "메탈")), ("그린", ("그린", "초록", "민트")),
           ("화이트", ("화이트", "흰색", "하얀", "흰 "))]
_STYLE_WORDS = ("분위기", "느낌", "무드", "꾸미", "꾸며", "인테리어", "벽지", "바닥", "우드", "나무", "원목", "대리석", "회벽", "린넨", "톤으로")


def _n(s: str) -> float:
    return float(s.replace(",", ""))


def _to_mm(v: float, unit: Optional[str]) -> float:
    if unit in ("cm", "센티"):
        return v * 10
    if unit in ("m", "미터"):
        return v * 1000
    if unit in ("mm", "밀리"):
        return v
    return v * 1000 if v < 10 else v * 10 if v < 300 else v   # 단위를 안 쓰면 크기로 짐작


def rule_based_products(prompt: str) -> ProductIntent:
    text = prompt or ""
    f: dict = {}
    f["category"] = next((c for c, _, words in CATEGORY_WORDS if any(w in text for w in words)), None)
    for num, tail in _CAP.findall(text):
        v = _n(num)
        if any(tail.startswith(w) for w in _MORE):
            f["capacity_min"] = v
        elif any(tail.startswith(w) for w in _LESS):
            f["capacity_max"] = v
        else:   # "800L 냉장고"는 그쯤 되는 크기
            f["capacity_min"], f["capacity_max"] = round(v * 0.9), round(v * 1.1)
    for num, unit, dae, tail in _PRICE.findall(text):
        won = int(_n(num) * {"만": 10_000, "백만": 1_000_000, "천만": 10_000_000}[unit])
        if dae:   # 200만원대 = 200만 ~ 300만, 250만원대 = 250만 ~ 260만
            step = 1_000_000 if won % 1_000_000 == 0 else 100_000
            f["price_min"], f["price_max"] = won, won + step
        elif any(tail.startswith(w) for w in _MORE):
            f["price_min"] = won
        else:     # 금액만 말하면 예산 상한
            f["price_max"] = won
    for num, unit, word in _DIM_B.findall(text):   # "60cm 폭". 아래 "폭 60cm" 꼴이 있으면 그쪽이 이긴다
        f[_DIM_WORDS[word]] = _to_mm(_n(num), unit)
    for word, num, unit in _DIM_A.findall(text):
        f[_DIM_WORDS[word]] = _to_mm(_n(num), unit or None)
    if "빌트인" in text:
        f["install"] = "built_in"
    elif any(w in text for w in ("일반형", "프리스탠딩", "단독형")):
        f["install"] = "freestanding"
    if any(w in text for w in ("싼", "저렴", "가격순", "가격 순")):
        f["sort"] = "price"
    elif any(w in text for w in ("작은 순", "크기순", "크기 순", "슬림")):
        f["sort"] = "size"
    wants = any(f.get(k) is not None for k in CONDITION_KEYS)
    if wants:
        f["color"] = next((g for g, words in _COLORS if any(w in text for w in words)), None)
    out = ProductIntent(wants_products=wants, also_style=wants and any(w in text for w in _STYLE_WORDS), **f)
    out.engine = "rules"
    return out


# ---------------- 대화에 보여 줄 말 (코드가 만든다) ----------------
def _won(v: int) -> str:
    return f"{v // 10_000:,}만 원" if v % 10_000 == 0 else f"{v:,}원"


def _range(lo, hi, fmt) -> Optional[str]:
    if lo is not None and hi is not None:
        return f"{fmt(lo)}~{fmt(hi)}"
    if lo is not None:
        return f"{fmt(lo)} 이상"
    return f"{fmt(hi)} 이하" if hi is not None else None


def condition_labels(c: dict) -> list[str]:
    out = [_range(c.get("capacity_min"), c.get("capacity_max"), lambda v: f"{v:g}L"), c.get("color"),
           {"built_in": "빌트인", "freestanding": "일반형"}.get(c.get("install"))]
    out += [f"{ko} {c[k]:g}mm 안" for k, ko in (("space_w", "폭"), ("space_h", "높이"), ("space_d", "깊이")) if k in c]
    out.append(_range(c.get("price_min"), c.get("price_max"), _won))
    return [x for x in out if x]


def chat_message(c: dict, total: int, shown: int, sort: str = "recommended") -> str:
    what = CATEGORY_KO.get(c.get("category"), "제품")
    labels = condition_labels(c)
    head = f"{' · '.join(labels)} {what}" if labels else what
    if total == 0:
        return f"{head} 조건에 맞는 제품이 없어요. 조건을 하나 풀어서 다시 말해 주세요."
    order = {"price": "가격이 낮은 순", "size": "폭이 좁은 순"}.get(sort, "공간에 잘 맞는 순")
    if total <= shown:
        return f"{head} {total}종을 찾았어요. {order}으로 보여 드려요."
    return f"{head} {total}종을 찾았어요. {order}으로 {shown}종 먼저 보여 드려요."
