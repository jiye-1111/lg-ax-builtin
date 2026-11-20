"""생활 이야기 → 가전마다 필요한 용량.

숫자는 LGE.COM·LG베스트샵 구매 가이드에 적힌 것만 쓴다 (docs/specs/lifestyle.md에 인용·주소).
가이드에 그 경우의 숫자가 없으면 용량 조건을 두지 않는다 (지어내지 않음). AI는 이야기에서 사실(Life)만 뽑는다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional

CHECKED = "2026-11-20"
FRIDGE_URL = "https://bestshop.lge.co.kr/story/insight/detail/IN10025001"
FRIDGE4_URL = "https://bestshop.lge.co.kr/story/insight/detail/IN10037000"
KIMCHI_URL = "https://bestshop.lge.co.kr/story/insight/detail/IN10038000"
WASH_URL = "https://www.lge.co.kr/story/useful-tip/lg-washing-machines-guide"
WASH34_URL = "https://www.lge.co.kr/story/home-curation/washer-dryer-capacity-guide"
BABY_URL = "https://www.lge.co.kr/story/home-curation/washing-machine-guide-for-baby-laundry"

Kimchi = Literal["none", "small", "lots"]


@dataclass(frozen=True)
class Life:
    """이야기에서 읽은 사실만. 모르면 None/False."""
    people: Optional[int] = None
    baby: bool = False
    lots_of_food: bool = False      # 장을 몰아서 보거나 식재료를 많이 두는 집
    kimchi: Optional[Kimchi] = None
    dual_income: bool = False


@dataclass(frozen=True)
class Need:
    category: str
    key: Optional[str]              # 제품 options 안의 값 이름 (capacity_l, wash_kg)
    min: Optional[float]
    max: Optional[float]
    unit: str
    why: str                        # 고객에게 보일 한 줄
    quote: Optional[str]            # 가이드 원문 (짧게)
    source_url: Optional[str]

    def label(self) -> str:
        if self.min is None and self.max is None:
            return ""
        if self.max is None:
            return f"{self.min:g}{self.unit} 이상"
        if self.min is None:
            return f"{self.max:g}{self.unit} 이하"
        return f"{self.min:g}~{self.max:g}{self.unit}"


def _fridge(life: Life) -> Need:
    p = life.people
    if life.lots_of_food and p == 4:
        return Need("refrigerator", "capacity_l", 600, 699, "L", "식재료가 많은 4인 가족이라 600L대",
                    "식재료가 많은 4인 가구라면 서랍처럼 여는 600L대", FRIDGE4_URL)
    if life.lots_of_food and (p is None or p >= 5):
        return Need("refrigerator", "capacity_l", 800, None, "L", "식재료를 많이 두는 집이라 800L대",
                    "보관하는 식재료가 많은 집은 800L대 대용량부터", FRIDGE_URL)
    if p is not None and p <= 2:
        return Need("refrigerator", "capacity_l", 300, 500, "L", f"{p}인 가구라 300~500L",
                    "1~2인 실속 구성은 300~500L대부터 보면 돼요", FRIDGE_URL)
    return Need("refrigerator", None, None, None, "L", "용량 기준이 따로 없어 이 집에 들어가는 것으로", None, None)


def _kimchi(life: Life) -> Optional[Need]:
    if life.kimchi in (None, "none"):
        return None
    p = life.people
    if life.kimchi == "lots":
        return Need("kimchi_refrigerator", "capacity_l", 480, 499, "L", "김장을 많이 해서 4도어 480~490L대",
                    "김장을 많이 한다면 4도어 490L 전후", KIMCHI_URL)
    if p is not None and p <= 2:
        return Need("kimchi_refrigerator", "capacity_l", 200, 299, "L", "김치를 조금 먹는 1~2인이라 200L대",
                    "1~2인 | 김치 소량 | 뚜껑형 | 200L대", KIMCHI_URL)
    if p == 3:
        return Need("kimchi_refrigerator", "capacity_l", 300, 399, "L", "김장을 조금 하는 2~3인이라 300L대",
                    "김장 소량 + 식재료 보관 | 스탠드형 3도어 | 300L대", KIMCHI_URL)
    return Need("kimchi_refrigerator", "capacity_l", 300, 499, "L", "김장을 조금 하는 3~4인이라 300~400L대",
                "김장을 조금 하고 식재료를 함께 보관한다면 스탠드형 300~400L대", KIMCHI_URL)


def _wash(life: Life) -> Optional[Need]:
    p = life.people
    if life.dual_income and (p is None or p >= 3):
        return Need("washer_dryer", "wash_kg", 25, None, "kg", "맞벌이라 빨래·건조를 한 번에 하는 워시콤보",
                    "육아와 업무로 24시간이 모자란 맞벌이 부부에게는 워시콤보를 추천합니다", WASH34_URL)
    if life.baby:
        return Need("washer", "wash_kg", 21, 24, "kg", "어른·아기 빨래를 한 번에 돌리는 21~24kg",
                    "어른과 아기의 빨랫감을 함께 관리할 수 있는 넉넉한 용량", BABY_URL)
    if p is not None and p >= 3:
        return Need("washer", "wash_kg", 25, None, "kg", f"{p}인 가족 빨래라 25kg 대용량",
                    "대용량의 세탁기가 필요한 4인 이상 가구인 경우", WASH_URL)
    return None


def needs(life: Life) -> list[Need]:
    """이 생활에 고를 가전과 용량 범위. 사람 수도 생활 단서도 없으면 빈 목록."""
    if life.people is None and not (life.baby or life.lots_of_food or life.kimchi or life.dual_income):
        return []
    return [n for n in (_fridge(life), _kimchi(life), _wash(life)) if n is not None]


def in_range(need: Need, options: dict) -> bool:
    if need.key is None:
        return True
    v = options.get(need.key)
    if not isinstance(v, (int, float)):
        return False
    return (need.min is None or v >= need.min) and (need.max is None or v <= need.max)


def pick(need: Need, items: list[dict], options_of: Callable[[dict], dict]) -> Optional[dict]:
    """추천 순서대로 받은 후보 중 범위 안이고 이 집에 안 들어가는 게 아닌 첫 제품."""
    for it in items:
        if (it.get("fit") or {}).get("verdict") == "no_fit":
            continue
        if in_range(need, options_of(it)):
            return it
    return None
