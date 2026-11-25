"""생활 이야기로 가전 고르기를 Service에 붙이는 부분.

1) AI(또는 규칙)가 이야기에서 사실만 뽑고 (ai_life)
2) LGE.COM 가이드 숫자로 가전마다 용량 범위를 정하고 (recommender.lifestyle)
3) 이 집에 들어가는 제품 중 범위 안의 첫 번째를 고른다 (find 추천 순서).
"""
from __future__ import annotations

from recommender.finder import Conditions
from recommender.lifestyle import Life, needs, pick

from .ai_life import read_life
from .ai_products import CATEGORY_KO, CATEGORY_WORDS

SELLABLE = (None, "ACTIVE", "SOLD_OUT")
NEED_CATS = {"refrigerator", "kimchi_refrigerator", "washer", "washer_dryer"}


def _said_categories(text: str) -> set[str]:
    """이야기 안에 콕 집은 가전이 있으면 그것만 (예: '4인 가족인데 냉장고 추천해 줘')."""
    out = set()
    for cat, _, words in CATEGORY_WORDS:
        t = text.replace("김치냉장고", "") if cat == "refrigerator" else text  # '김치냉장고'만 말했으면 냉장고는 빼고
        if any(w in t for w in words):
            out.add(cat)
    if "washer" in out or "washer_dryer" in out:
        out |= {"washer", "washer_dryer"}  # 세탁기를 물었어도 맞벌이면 워시콤보로 고른다
    return out & NEED_CATS


def life_words(life: Life) -> str:
    bits = [f"{life.people}인" if life.people else None, "아기" if life.baby else None, "맞벌이" if life.dual_income else None,
            "장 몰아 보기" if life.lots_of_food else None,
            {"lots": "김장 많이", "small": "김치 조금", "none": None}.get(life.kimchi or "none")]
    return " · ".join(b for b in bits if b)


class LifeMixin:
    life_reader = staticmethod(read_life)  # (text) -> (Life, engine). 테스트에서 바꿔 끼운다

    def life_pick(self, pid: str, text: str) -> dict:
        life, engine = self.life_reader(text)
        want = _said_categories(text)
        todo = [n for n in needs(life) if not want or n.category in want]
        items, missing = [], []
        for n in todo:
            got = self.find(Conditions(category=n.category), pid)["items"]
            sell = [it for it in got if (q := self.catalog.get(it["product"]["sku"])).listed and q.sale_status in SELLABLE]
            it = pick(n, sell, lambda x: x["product"].get("options") or {})
            if it is None:
                missing.append(CATEGORY_KO.get(n.category, n.category))
                continue
            items.append({**it, "need": {"category": n.category, "label": n.label(), "why": n.why, "quote": n.quote,
                                         "source_url": n.source_url}, "reasons": [n.why]})
        said = life_words(life)
        if not todo:
            msg = "가족 수나 생활(아기, 맞벌이, 장보기, 김장)을 조금 더 알려 주시면 맞는 용량으로 골라 드릴게요."
        elif not items:
            msg = f"{said} 생활에 맞는 용량 중 이 집에 들어가는 제품을 못 찾았어요."
        else:
            msg = f"{said} 생활에 맞춰 가전 {len(items)}개를 골랐어요. 용량은 LGE.COM 구매 가이드 기준이에요."
            if missing:
                msg += f" {'·'.join(missing)}는 맞는 용량 중 이 집에 들어가는 게 없었어요."
        return {"type": "life", "message": msg, "engine": engine, "life": life.__dict__, "items": items,
                "categories": [it["need"]["category"] for it in items]}
