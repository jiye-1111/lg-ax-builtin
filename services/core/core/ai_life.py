"""생활 이야기("맞벌이 4인 가족, 장은 주말에 몰아서, 아기")에서 사실만 뽑는다.

AI는 사실(가족 수·아기·장보기·김치·맞벌이·반려동물)만 옮기고, 용량 계산은 recommender.lifestyle이 LGE.COM 가이드 숫자로 한다.
키가 없거나 실패하면 같은 사실을 규칙으로 읽는다.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from recommender.lifestyle import Life

from .ai_style import OPENAI_MODEL, openai_extra, pick_provider

log = logging.getLogger(__name__)


class LifeFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    people: Optional[int] = Field(description="함께 사는 사람 수(아기 포함). 말하지 않았으면 null", ge=1, le=12)
    baby: bool = Field(description="아기·영유아가 있거나 곧 태어나면 true")
    lots_of_food: bool = Field(description="장을 몰아서 보거나 식재료를 많이 사 두면 true")
    kimchi: Optional[Literal["none", "small", "lots"]] = Field(description="김치·김장: 안 먹음 none, 조금 small, 김장 많이 lots. 말 없으면 null")
    dual_income: bool = Field(description="맞벌이면 true")
    pet: bool = Field(description="반려동물(강아지·고양이 등)과 살면 true")


SYSTEM = """고객이 자기 집 생활을 이야기한다. 적힌 사실만 옮겨라. 짐작하지 마라.
가족 수는 아기를 포함한 함께 사는 사람 수. '신혼'은 2명, '혼자·자취'는 1명. 숫자가 없으면 null.
제품·용량·가격은 말하지 마라."""

_NUM = {"한": 1, "혼자": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4, "다섯": 5, "여섯": 6, "일곱": 7}
_LIFE_WORDS = re.compile(r"\d+\s*인|둘이|셋이|넷이|[한두세네]\s*식구|다섯\s*식구|여섯\s*식구|가족|혼자|자취|신혼|부부|맞벌이|반려|강아지|고양이|아기|육아|신생아|출산|"
                         r"장(을|은|는)?\s*(주말에\s*)?(몰아|한꺼번에|한 번에)|김장|김치")
# 용량·가격을 직접 정했거나 꾸미기 이야기면 생활 이야기로 보지 않는다 (그쪽 길이 따로 있음)
_PRODUCT_ASK = re.compile(r"\d+\s*(L|리터|kg|키로|만\s*원)|꾸며|꾸미|느낌|분위기|인테리어")


def is_life_story(text: str) -> bool:
    """가족·생활 이야기인지 (꾸미기 말이나 조건을 정한 제품 찾기가 아니라)."""
    t = text or ""
    return bool(_LIFE_WORDS.search(t)) and not _PRODUCT_ASK.search(t)


def rule_life(text: str) -> LifeFacts:
    t = text or ""
    people = None
    if m := re.search(r"(\d+)\s*(인|명|식구)", t):
        people = int(m.group(1))
    elif m := re.search(r"(한|두|세|네|다섯|여섯|일곱)\s*(식구|명)", t):
        people = _NUM[m.group(1)]
    elif re.search(r"혼자|자취|1인", t):
        people = 1
    elif re.search(r"신혼|둘이|부부\s*(둘|만)", t):
        people = 2
    kimchi = None
    if re.search(r"김치\S*\s*(안|않|못)\s*먹", t):
        kimchi = "none"
    elif re.search(r"김장\S*\s*(많이|크게|매년|해마다)|김장(을|도)?\s*해", t):
        kimchi = "lots"
    elif re.search(r"김치|김장", t):
        kimchi = "small"
    return LifeFacts(people=people if people and 1 <= people <= 12 else None,
                     baby=bool(re.search(r"아기|육아|신생아|출산|돌\s*전|영유아", t)),
                     lots_of_food=bool(re.search(r"(몰아|한꺼번에|한 번에)\s*(서\s*)?(장|사|봐|보)|장(을|은|는)?\s*(주말에\s*)?(몰아|한꺼번에)|대량|코스트코|창고형", t)),
                     kimchi=kimchi, dual_income="맞벌이" in t,
                     pet=bool(re.search(r"반려|강아지|고양이|댕댕|냥이", t)))


def to_life(f: LifeFacts) -> Life:
    return Life(people=f.people, baby=f.baby, lots_of_food=f.lots_of_food, kimchi=f.kimchi, dual_income=f.dual_income, pet=f.pet)


def read_life(text: str, *, client=None) -> tuple[Life, str]:
    """(사실, engine). engine = openai | rules"""
    if client is None and pick_provider() != "openai":
        return to_life(rule_life(text)), "rules"
    try:
        if client is None:
            import openai
            client = openai.OpenAI(timeout=float(os.getenv("STYLE_AI_TIMEOUT_S", "40")), max_retries=1)
        r = client.chat.completions.parse(model=OPENAI_MODEL, response_format=LifeFacts, **openai_extra(),
                                          messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}])
        msg = r.choices[0].message
        if getattr(msg, "refusal", None) or msg.parsed is None:
            return to_life(rule_life(text)), "rules"
        return to_life(msg.parsed), "openai"
    except Exception as e:  # noqa: BLE001 - 키·네트워크·한도: 규칙으로 계속
        log.warning("생활 이야기 해석 실패 → 규칙: %s", e)
        return to_life(rule_life(text)), "rules"
