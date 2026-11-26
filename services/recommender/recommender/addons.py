"""꾸며 놓은 집을 보고 '여기에 이걸 더하면 좋아요'를 고르는 규칙.

집에 있는 것(놓은 가구·LG 가전, 치우지 않은 스캔 가구)의 종류만 보고 고른다. 자리 잡기와 제품 고르기는 Service가 한다.
숫자·성능은 말하지 않는다. 왜 좋은지 한 문장만.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class Addon:
    id: str
    text: str                          # 고객에게 보일 한 문장
    when: tuple[str, ...]              # 이 가운데 하나라도 있으면
    unless: tuple[str, ...]            # 이 가운데 하나라도 있으면 권하지 않는다
    sku: Optional[str] = None          # 꾸미기 가구 (decor:*)
    kind: Optional[str] = None         # 가구 이름을 찾을 때 쓰는 종류 (nightstand는 서랍장을 작게)
    category: Optional[str] = None     # LG 가전 종류. 제품은 Service가 이 집에 맞는 것으로 고른다
    role: str = "wall"                 # 기준 가구에 대한 자리 (recommender.layout 역할)
    min_items: int = 1                 # 놓은 것이 이만큼은 있어야 권한다

    @property
    def lg(self) -> bool:
        return self.category is not None


RULES: tuple[Addon, ...] = (
    Addon("hood", "인덕션 위에 후드를 달면 요리 냄새가 덜 퍼져요", ("cooktop_bare",), ("never",), sku="decor:hood", kind="hood"),
    Addon("deskchair", "책상 앞에 의자를 두면 바로 앉아 쓸 수 있어요", ("desk",), ("chair",), sku="decor:chair", kind="chair",
          role="desk_chair"),
    Addon("nightstand", "침대 옆에 협탁을 두면 자기 전 물건 둘 자리가 생겨요", ("bed",), ("nightstand",), sku="decor:dresser",
          kind="nightstand", role="pair"),
    Addon("coffee", "소파 앞에 테이블을 두면 거실 쓰기가 편해져요", ("sofa",), ("coffee", "table"), sku="decor:coffee", kind="coffee",
          role="front"),
    Addon("dryer", "세탁기 곁에 건조기를 두면 빨래 널 자리가 필요 없어요", ("washer",), ("dryer", "wash_tower", "washer_dryer"),
          category="dryer"),
    Addon("water_purifier", "조리대에 정수기를 두면 물 마시기와 요리가 편해져요",
          ("refrigerator", "cooktop", "basecab", "island", "sink", "dishwasher"), ("water_purifier",), category="water_purifier"),
    Addon("dishwasher", "조리대 곁에 식기세척기를 두면 설거지가 가벼워져요", ("cooktop", "basecab", "sink", "island"), ("dishwasher",),
          category="dishwasher"),
    Addon("rug", "러그를 깔면 공간이 한결 아늑해 보여요", ("sofa", "bed"), ("rug",), sku="decor:rug", kind="rug", role="rug"),
    Addon("tvstand", "소파 맞은편에 거실장을 두면 거실 중심이 잡혀요", ("sofa",), ("tvstand", "tv"), sku="decor:tvstand", kind="tvstand",
          role="facing"),
    Addon("air_purifier", "쉬는 자리 가까이에 공기청정기를 두면 좋아요", ("bed", "sofa"), ("air_purifier",), category="air_purifier"),
    Addon("styler", "장롱 곁에 스타일러를 두면 매일 입는 옷 관리가 쉬워요", ("wardrobe",), ("styler",), category="styler"),
    Addon("lamp", "조명을 하나 두면 저녁 분위기가 부드러워져요", ("bed", "sofa", "desk"), ("lamp",), sku="decor:lamp", kind="lamp",
          role="corner"),
    Addon("plant", "빈 구석에 식물을 두면 집에 생기가 돌아요", ("*",), ("plant",), sku="decor:plant", kind="plant", role="corner",
          min_items=3),
)
BY_ID = {a.id: a for a in RULES}


def pick_addons(have: Iterable[str], placed: Optional[int] = None) -> list[Addon]:
    """have: 집에 있는 것의 종류(가구 kind, LG 가전 category, 'cooktop_bare' = 후드 없는 인덕션). placed: 직접 놓은 개수.
    권할 만한 것을 중요한 순서로. 아무것도 없으면 빈 목록."""
    got = set(have)
    n = len(list(have)) if placed is None else placed
    if not got:
        return []
    out = []
    for a in RULES:
        if n < a.min_items or got & set(a.unless):
            continue
        if "*" in a.when or got & set(a.when):
            out.append(a)
    return out


def shortlist(cands: list[Addon], limit: int = 3) -> list[Addon]:
    """앞에서부터 limit개. 다만 LG 가전 제안이 있는데 하나도 안 들어갔으면 마지막 자리를 LG 가전에 준다."""
    top = cands[:limit]
    if len(cands) > limit and not any(a.lg for a in top):
        lg = next((a for a in cands[limit:] if a.lg), None)
        if lg:
            top[-1] = lg
    return top
