"""생활 이야기로 가전 고르기를 Service에 붙이는 부분.

1) AI(또는 규칙)가 이야기에서 사실만 뽑고 (ai_life)
2) LGE.COM 가이드 숫자로 가전마다 용량 범위를 정하고 (recommender.lifestyle)
3) 이 집에 들어가는 제품 중 범위 안의 첫 번째를 고른다 (find 추천 순서).
"""
from __future__ import annotations

from recommender.finder import Conditions
from recommender.lifestyle import Life, extras, in_range, needs, pick

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


def _won(v: int) -> str:
    return f"{round(v / 10000):,}만 원"


def life_words(life: Life) -> str:
    bits = [f"{life.people}인" if life.people else None, "아기" if life.baby else None, "맞벌이" if life.dual_income else None,
            "장 몰아 보기" if life.lots_of_food else None, "반려동물" if life.pet else None,
            {"lots": "김장 많이", "small": "김치 조금", "none": None}.get(life.kimchi or "none")]
    return " · ".join(b for b in bits if b)


class LifeMixin:
    life_reader = staticmethod(read_life)  # (text) -> (Life, engine). 테스트에서 바꿔 끼운다

    def _life_cands(self, pid: str, n) -> list[dict]:
        """이 용량 범위 안이고 이 집에 들어가는 판매 중 제품 (추천 순서)."""
        got = self.find(Conditions(category=n.category), pid)["items"]
        return [it for it in got
                if (q := self.catalog.get(it["product"]["sku"])).listed and q.sale_status in SELLABLE
                and (it.get("fit") or {}).get("verdict") != "no_fit" and in_range(n, it["product"].get("options") or {})]

    @staticmethod
    def _life_row(it: dict, n) -> dict:
        return {**it, "need": {"category": n.category, "label": n.label(), "why": n.why, "quote": n.quote,
                               "source_url": n.source_url}, "reasons": [n.why]}

    @staticmethod
    def _to_budget(picks: list[dict], pools: list[list[dict]], budget: int) -> list[dict]:
        """합계가 예산을 넘으면 가장 비싼 가전부터 같은 용량 범위 안의 더 싼 것으로 바꾼다."""
        price = lambda it: it["product"].get("price_krw") or 0  # noqa: E731
        picks = list(picks)
        for _ in range(60):
            if sum(price(x) for x in picks) <= budget:
                break
            swaps = []
            for i, cur in enumerate(picks):
                cheaper = [x for x in pools[i] if 0 < price(x) < price(cur)]
                if cheaper:
                    swaps.append((price(cur), i, max(cheaper, key=price)))
            if not swaps:
                break
            _, i, nxt = max(swaps, key=lambda t: (t[0], -t[1]))
            picks[i] = nxt
        return picks

    def life_pick(self, pid: str, text: str, budget: int | None = None) -> dict:
        life, engine = self.life_reader(text)
        want = _said_categories(text)
        todo = [n for n in needs(life) if not want or n.category in want]
        picked, pools, missing = [], [], []
        for n in todo:
            cands = self._life_cands(pid, n)
            if not cands:
                missing.append(CATEGORY_KO.get(n.category, n.category))
                continue
            picked.append((n, cands[0]))
            pools.append(cands)
        if budget and picked:
            best = self._to_budget([it for _, it in picked], pools, budget)
            picked = [(n, it) for (n, _), it in zip(picked, best)]
        items = [self._life_row(it, n) for n, it in picked]
        more = []
        if not want:  # 가전을 콕 집어 물었으면 그것만
            for n in extras(life):
                if n.category in {x["need"]["category"] for x in items}:
                    continue
                cands = self._life_cands(pid, n)
                if cands:
                    more.append(self._life_row(cands[0], n))
        total = sum(it["product"].get("price_krw") or 0 for it in items)
        said = life_words(life)
        if not todo and not more:
            msg = "가족 수나 생활(아기, 맞벌이, 반려동물, 장보기, 김장)을 조금 더 알려 주시면 맞는 가전을 골라 드릴게요."
        elif not items and not more:
            msg = f"{said} 생활에 맞는 용량 중 이 집에 들어가는 제품을 못 찾았어요."
        else:
            msg = (f"{said} 생활에 맞춰 가전 {len(items)}개를 골랐어요. 용량은 LGE.COM 구매 가이드 기준이에요." if items
                   else f"{said} 생활이면 이런 가전을 함께 보시면 좋아요.")
            if missing:
                msg += f" {'·'.join(missing)}는 맞는 용량 중 이 집에 들어가는 게 없었어요."
            if budget and items:
                msg += (f" 합계 {_won(total)}으로 예산 {_won(budget)} 안이에요." if total <= budget
                        else f" 이 용량에서 가장 낮은 가격으로 골라도 합계 {_won(total)}이라 예산 {_won(budget)}을 넘어요.")
        return {"type": "life", "message": msg, "engine": engine, "life": life.__dict__, "items": items, "extras": more[:3],
                "categories": [it["need"]["category"] for it in items], "budget": budget, "total": total}
