"""조합 추천을 Service에 붙이는 부분 (combos.py 컨셉 + recommender.layout 자리 + 카탈로그 제품 고르기).

조합은 만들기만 하고 저장하지 않은 상태로 보여 준다(scene_state["combos"]에 마지막 결과만 둔다).
고객이 하나를 고르면 그 조합의 가구·가전·벽지·바닥재가 한 번에 들어가고, 전에 넣은 조합 것은 빠진다.
"""
from __future__ import annotations

import math
from statistics import median
from typing import Optional

from recommender.cmf import rank_cmf
from recommender.finishes import rank_finishes
from recommender.layout import Item, arrange
from recommender.lifestyle import Life, in_range, needs
from recommender.pose import Pose, can_sit, check_pose, needs_counter

from .ai_life import is_life_story, rule_life
from .ai_products import CATEGORY_KO, categories_named, rule_based_products
from .combos import (PLAN_KO, PURPOSE_CATS, PURPOSE_KO, Idea, ask_ideas, detect_purpose, label_of, parse_photo, room_brief,
                     rule_ideas, slot_sku)
from .decor import decor_product, is_decor
from .models import Product, StyleTags

MAX_CATEGORIES = 6
TRIES = 4          # 가전 하나당 자리를 찾아볼 후보 수
SELLABLE = (None, "ACTIVE", "SOLD_OUT")
# 예산을 말했으면 어느 조합도 그 금액을 넘기지 않는다: 맞춤은 조금 남기고, 아끼기는 더 남기고, 한 단계 위는 꽉 채운다
BUDGET_FACTOR = {"target": 0.9, "save": 0.7, "upgrade": 1.0}
FLOOR_CATS = frozenset({"air_purifier", "wine_cellar", "refrigerator"})  # 올릴 수는 있어도 바닥 자리부터 찾는 가전 (식탁 위 공기청정기는 어색하다)
HUG = {"dishwasher": 2.0, "refrigerator": 0.6, "kimchi_refrigerator": 0.6}  # 조리대 옆에 붙이는 정도


def won(v: int) -> str:
    return f"{round(v / 10000):,}만 원"


class ComboMixin:
    ideator = staticmethod(ask_ideas)  # (brief, image=None) -> Ideas | None. 테스트에서 바꿔 끼운다

    # ---- 후보 ----
    def _combo_pool(self, room, category: str) -> list[Product]:
        """이 집에 들어갈 수 있는 크기이고 가격이 있는 제품. 같은 모델 색 다른 것은 하나만."""
        longest = max((math.dist(w.start, w.end) for w in room.walls), default=0)
        tall = max((w.scanned.height_m for w in room.walls), default=2.3)
        seen, out = set(), []
        for p in self.catalog.products:
            d = p.product_dims_mm
            if p.category != category or p.price_krw is None or None in (d.w, d.h, d.d):
                continue
            if not p.demo_only and (not p.listed or p.sale_status not in SELLABLE):
                continue
            if d.w / 1000 > longest or d.h / 1000 > tall:
                continue
            key = (p.name, d.w, d.h, d.d)
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
        return out

    @staticmethod
    def _keep(pool: list[Product], keep, category: str) -> list[Product]:
        if not keep or category not in keep:
            return pool
        return [p for p in pool if keep[category](p.options)] or pool  # 범위 안이 하나도 없으면 원래대로

    @staticmethod
    def _color_score(p: Product, tags: StyleTags):
        if not p.cmf_options or p.cmf_options[0].color is None:
            return 0.5, None  # LGE.COM에 색 정보가 없는 모델(TV 등): 색으로 고르지도, 색을 말하지도 않는다
        r = rank_cmf(p, tags, 1)
        return (r[0].score, r[0].option) if r else (0.0, None)

    def _pick_order(self, pool: list[Product], tags: StyleTags, target: Optional[float], plan: str) -> list[Product]:
        """목표 가격(이 가전 몫)에 가까울수록, 조합 색과 맞을수록 앞."""
        if not pool:
            return []
        prices = sorted(p.price_krw for p in pool)
        if target is None:  # 예산이 없으면 아끼기=아래 4분위, 한 단계 위=위 4분위, 그 밖=가운데
            q = {"save": 0.25, "upgrade": 0.75}.get(plan, 0.5)
            target = prices[min(len(prices) - 1, int(q * (len(prices) - 1)))]
        capped = plan is None  # 예산이 있을 때: 몫을 넘지 않는 것부터
        return sorted(pool, key=lambda p: (capped and p.price_krw > target,
                                           abs(p.price_krw - target) / max(target, 1) + (1 - self._color_score(p, tags)[0]) * 0.4,
                                           p.sku))

    @staticmethod
    def _within(order: dict, pools: dict, cap: Optional[float]) -> None:
        """첫 후보 합계가 예산을 넘으면 가장 비싼 종류부터 한 칸씩 싼 것으로 바꾼다."""
        if not cap:
            return
        for _ in range(40):
            if sum(c[0].price_krw for c in order.values() if c) <= cap:
                return
            swaps = []
            for cat, cands in order.items():
                cheaper = [x for x in pools[cat] if cands and x.price_krw < cands[0].price_krw]
                if cheaper:
                    swaps.append((cands[0].price_krw, cat, max(cheaper, key=lambda x: (x.price_krw, x.sku))))
            if not swaps:
                return
            _, cat, nxt = max(swaps, key=lambda x: (x[0], x[1]))
            order[cat] = [nxt] + [x for x in order[cat] if x is not nxt][:TRIES - 1]

    # ---- 만들기 ----
    def make_combos(self, pid: str, categories: list[str] | None = None, budget: int | None = None, prompt: str = "",
                    zone_id: str | None = None, image: tuple[str, str] | None = None, said=None, keep=None) -> dict:
        """keep: {종류: (제품 options) -> bool}. 생활 이야기로 정한 용량 범위를 조합에서도 지키게 한다."""
        from .service import Invalid

        prompt = (prompt or "").strip()
        if len(prompt) > 500:
            raise Invalid("500자 안으로 적어 주세요")
        cats = list(dict.fromkeys(categories or []))
        bad = [c for c in cats if c not in CATEGORY_KO]
        if bad:
            raise Invalid(f"모르는 가전 종류: {', '.join(bad)}")
        if prompt:
            said = said or self.product_reader(prompt)  # 하우니가 이미 읽었으면 다시 부르지 않는다 (AI 한 번 아끼기)
            for c in categories_named(prompt) + ([said.category] if said.category else []):  # 말한 가전은 빠짐없이
                if c not in cats:
                    cats.append(c)
            budget = budget or said.price_max
            cats = cats[:MAX_CATEGORIES] if len(cats) > MAX_CATEGORIES and not categories else cats
        if len(cats) > MAX_CATEGORIES:
            raise Invalid(f"가전 종류는 {MAX_CATEGORIES}개까지 골라 주세요")
        if budget is not None and not (100_000 <= budget <= 100_000_000):
            raise Invalid("목표 가격은 10만 원 ~ 1억 원 사이로 적어 주세요")
        p = self.get_project(pid)
        room = self._standing(self.get_room(pid), p)
        zones = self.list_zones(pid)
        pools = {c: self._keep(self._combo_pool(room, c), keep, c) for c in cats}
        stock = {c: (len(v), min((x.price_krw for x in v), default=None), max((x.price_krw for x in v), default=None))
                 for c, v in pools.items()}
        purpose = detect_purpose(prompt, cats, zones)
        brief = room_brief(room, zones, cats, budget, prompt, stock)
        ideas = self.ideator(brief, image=image) if image else self.ideator(brief)
        if image and ideas and ideas.not_a_room:
            return {"engine": "ai", "not_a_room": True, "combos": []}
        engine, seen = "ai", (ideas.seen if image and ideas else None)
        if not ideas or not ideas.ideas:
            ideas, engine = rule_ideas(prompt, purpose), "rules"
        auto = not cats  # 가전을 안 골랐으면 그 공간에 흔히 두는 LG 가전을 넣는다 (가구만 주지 않게)
        if auto:
            cats = list(PURPOSE_CATS.get(ideas.purpose, []))
            pools = {c: self._keep(self._combo_pool(room, c), keep, c) for c in cats}
        others = [x for x in p["scene_state"]["placements"] if not x.get("combo") and x.get("size_m")]
        meds = {c: median(x.price_krw for x in v) for c, v in pools.items() if v}
        combos = [self._one_combo(room, p, others, idea, pools, meds, budget, i) for i, idea in enumerate(ideas.ideas[:3])]
        p["scene_state"]["combos"] = combos
        self._save_project(p)
        return {"engine": engine, "purpose": ideas.purpose, "purpose_label": PURPOSE_KO.get(ideas.purpose, ""),
                "budget": budget, "categories": cats, "auto_categories": auto, "combos": combos, "seen": seen}

    def _one_combo(self, room, p: dict, others: list[dict], idea: Idea, pools: dict, meds: dict, budget, idx: int) -> dict:
        tags = StyleTags(palette=idea.palette, materials=idea.materials)
        cap = budget * BUDGET_FACTOR[idea.price_plan] if budget else None
        share_tot = sum(meds.values()) or 1
        targets = {c: (cap * meds[c] / share_tot if cap else None) for c in meds}
        items: list[Item] = []
        for n, s in enumerate(idea.furniture):
            sku, size = slot_sku(s.kind)
            items.append(Item(key=f"d{n}-{s.kind}", sku=sku, product=decor_product(sku, size), role=s.role, size_m=size))
        order = {c: self._pick_order(pools[c], tags, targets.get(c), None if cap else idea.price_plan)[:TRIES] for c in pools}
        self._within(order, pools, cap)
        mine = {x["placement_id"] for x in p["scene_state"]["placements"] if x.get("combo")}  # 전에 넣은 조합 것은 곧 빠진다
        tops = {flag: [t for t in self._surfaces(room, p, counters=flag) if t["id"] not in mine] for flag in (True, False)}
        counter_cats = [c for c, cands in order.items() if cands and needs_counter(cands[0])]
        if counter_cats and not tops[True] and not any(s.kind in ("basecab", "island") for s in idea.furniture):
            items.append(Item(key=f"d{len(items)}-basecab", sku="decor:basecab", product=decor_product("decor:basecab", None),
                              role="wall"))  # 인덕션을 넣을 조리대가 없으면 하부장을 같이
        for c, cands in order.items():  # 바닥에 서는 가전은 가구와 함께 자리를 잡는다. 올려 두는 가전은 그다음에
            if cands and not self._tops_first(cands[0]):
                items.append(self._lg_item(c, cands[0], tags))
        hidden = self._blocked_off(p)
        counters = [(tuple(t["center_xz"]), t["w"] / 2) for t in tops[True]]
        placed = arrange(room, items, self.fit_cfg, others, hidden, counters)
        got = {x.item.key for x in placed}
        spent = sum(x.item.product.price_krw or 0 for x in placed if x.item.role == "appliance")
        missing = []
        for c, cands in order.items():  # 올려 두는 가전, 그리고 첫 후보가 안 들어간 가전: 놓인 것 사이에 넣어 본다
            if f"lg-{c}" in got:
                continue
            ok = False
            for prod in (cands if cands and (self._tops_first(cands[0]) or can_sit(cands[0])) else cands[1:]):
                if cap and spent + prod.price_krw > cap:
                    continue
                it = self._lg_item(c, prod, tags)
                now = others + [x.as_placement(f"pl-{i}") for i, x in enumerate(placed) if x.item.role != "rug"]
                top = self._combo_on_top(room, it, placed, tops[needs_counter(prod)], now, hidden) if can_sit(prod) else None
                more = [top] if top else [] if needs_counter(prod) else arrange(room, [it], self.fit_cfg, now, hidden, counters)
                if more:
                    placed += more
                    spent += prod.price_krw
                    ok = True
                    break
            if not ok:
                missing.append(CATEGORY_KO.get(c, c))
        finishes = {}
        for k in ("wall", "floor"):
            r = rank_finishes(self.finishes, k, idea.palette, idea.materials,
                              idea.wall_texture if k == "wall" else idea.floor_texture, top_k=1)
            if r and r[0].score > 0:
                finishes[k] = {"id": r[0].finish.id, "tone": r[0].tone.hex, "name": r[0].tone.name}  # 색 이름만 (브랜드 없이)
        out_items = [self._combo_row(x, targets, tags, idea.price_plan) for x in placed]
        total = sum(x["price"] or 0 for x in out_items if x["kind"] == "lg")
        return {"combo_id": f"c{idx + 1}", "name": idea.name, "why": idea.why, "tips": idea.tips[:3],
                "plan": idea.price_plan, "plan_label": PLAN_KO[idea.price_plan], "appliance_point": idea.appliance_point,
                "palette": idea.palette, "finishes": finishes, "items": out_items, "lg_total": total,
                "budget_diff": (total - budget) if budget else None, "missing": missing}

    @staticmethod
    def _tops_first(prod: Product) -> bool:
        """가구 위부터 찾는 가전인지. 공기청정기·미니 냉장고는 바닥에 설 자리가 없을 때만 올린다."""
        return bool(can_sit(prod)) and prod.category not in FLOOR_CATS

    def _lg_item(self, category: str, prod: Product, tags: StyleTags) -> Item:
        _, opt = self._color_score(prod, tags)
        return Item(key=f"lg-{category}", sku=prod.sku, product=prod, role="appliance",
                    color=opt.color if opt else None, hex=opt.hex_approx if opt else None,
                    hug=HUG.get(category, 0.0) if prod.install_type == "built_in" or category != "dishwasher" else 0.0)

    def _combo_on_top(self, room, it: Item, placed: list, tops: list[dict], now: list[dict], hidden: list[str]):
        """올려 두는 가전(인덕션·전자레인지·정수기)을 이 조합의 가구나 원래 있던 가구 윗면에 놓는다. 자리가 없으면 None."""
        from recommender.layout import Placed

        counter = needs_counter(it.product)
        hosts = self.CABINETS if counter else self.HOSTS
        mine = [{"id": f"pl-{i}", "center_xz": tuple(x.pose.center_xz), "yaw_rad": x.pose.yaw_rad - math.pi / 2,
                 "w": x.size[0], "d": x.size[2], "top_m": x.size[1]}
                for i, x in enumerate(placed) if x.item.sku in hosts and x.item.role != "rug"]
        for s in sorted(mine + tops, key=lambda q: -q["w"] * q["d"]):
            ux, uz = math.cos(s["yaw_rad"]), math.sin(s["yaw_rad"])
            n = max(0, int(s["w"] / 2 / 0.1))
            for i in sorted(range(-n, n + 1), key=abs):
                c = (s["center_xz"][0] + ux * i * 0.1, s["center_xz"][1] + uz * i * 0.1)
                for yaw in (s["yaw_rad"] + math.pi / 2, s["yaw_rad"] - math.pi / 2):
                    r = check_pose(room, it.product, Pose(c, yaw), self.fit_cfg, others=now, hidden=hidden, host=s)
                    if r.verdict.value != "no_fit" and r.size_m:
                        return Placed(it, r.pose, r.size_m, r.verdict.value, r.reasons, base_m=round(r.base_m, 3))
        return None

    def _combo_row(self, x, targets: dict, tags: StyleTags, plan: str) -> dict:
        it = x.item
        base = {"sku": it.sku, "center_xz": [round(v, 4) for v in x.pose.center_xz], "yaw_rad": round(x.pose.yaw_rad, 6),
                "size_m": [round(v, 4) for v in x.size], "wall_id": x.pose.wall_id, "verdict": x.verdict,
                "base_m": x.base_m}  # 미리보기 그림에서 조리대 위 가전이 바닥에 떨어져 보이지 않게
        if is_decor(it.sku):
            kind = it.key.split("-", 1)[1]
            return {**base, "kind": "decor", "name": label_of(kind), "price": None, "color": None, "hex": None, "why": None,
                    "resize": it.size_m is not None}
        prod = it.product
        why = []
        if x.verdict == "fit":
            why.append("설치 여유까지 지키는 자리에 들어가요")
        score, _ = self._color_score(prod, tags)
        if it.color and score >= 0.6:
            why.append(f"{it.color} 색이 이 조합 벽·바닥 톤과 잘 어울려요")
        if plan != "target":
            why.append("같은 종류에서 가격을 낮춘 선택이에요" if plan == "save" else "같은 종류에서 한 단계 위 제품이에요")
        elif targets.get(prod.category):
            why.append("예산 안에서 고른 가격이에요")
        return {**base, "kind": "lg", "name": prod.name, "category": prod.category, "category_label": CATEGORY_KO.get(prod.category),
                "price": prod.price_krw, "color": it.color, "hex": it.hex, "why": why[:2]}

    # ---- 하우니 대화 ----
    DECOR_WORDS = ("꾸미", "꾸며", "분위기", "느낌", "무드", "인테리어", "침대", "소파", "책상", "식탁", "호텔", "리조트",
                   "컨셉", "콘셉")

    def assist(self, pid: str, prompt: str, image: str | None = None, categories: list[str] | None = None,
               life: dict | None = None, budget: int | None = None) -> dict:
        """하우니 한 번. 꾸미기·분위기를 말하거나 사진을 붙이면 조합 2~3개, 제품만 물으면 이 집에 맞는 하나 + 대안 둘.
        사진은 AI에 한 번 보내고 버린다 (저장하지 않음)."""
        from .service import Invalid

        prompt = (prompt or "").strip()
        photo = None
        if image:
            try:
                photo = parse_photo(image)
            except ValueError as e:
                raise Invalid(str(e)) from None
        if not prompt and not photo:
            raise Invalid("원하는 것을 적거나 사진을 붙여 주세요")
        if categories:  # 생활 이야기로 고른 가전 그대로 배치 추천까지
            got = {n.category: n for n in needs(Life(**life))} if life else {}
            keep = {c: (lambda o, n=n: in_range(n, o)) for c, n in got.items()}
            out = self.make_combos(pid, list(categories)[:MAX_CATEGORIES], budget, prompt, keep=keep)
            n = len(out["combos"])
            msg = (f"고른 가전으로 {n}가지 배치를 만들어 봤어요. 마음에 드는 조합을 누르면 가구·가전·벽지까지 한 번에 들어가요." if n
                   else "이 집 구조로는 조합을 못 만들었어요. 가구를 치우거나 다른 분위기로 말해 주세요.")
            return {"type": "combos", "message": msg, **out}
        named = categories_named(prompt)
        if not photo and len(named) >= 2:  # "냉장고랑 식기세척기, 예산 600" → 말한 가전 그대로, 예산 안에서 조합
            return self._named_combos(pid, prompt, named[:MAX_CATEGORIES])
        if not photo and is_life_story(prompt):  # "맞벌이 4인 가족, 장은 몰아서" → 가전마다 맞는 용량으로 하나씩
            return self.life_pick(pid, prompt, budget)
        want = self.product_reader(prompt) if prompt else None
        decor = photo is not None or any(w in prompt for w in self.DECOR_WORDS)
        if want and want.wants_products and want.category and not decor:
            got = self._chat_products(pid, None, want)
            items = got["items"][:3]
            head = CATEGORY_KO.get(want.category, "제품")
            if not items:
                msg = got["message"]
            else:
                msg = f"이 집에는 ‘{items[0]['family_name']}’ 제품이 가장 잘 맞아요."
                if len(items) > 1:
                    msg += f" 비교해 볼 {head} {len(items) - 1}개도 같이 둘게요."
            return {"type": "products", "message": msg, "items": items, "engine": got["engine"]}
        out = self.make_combos(pid, [want.category] if want and want.category else [], want.price_max if want else None,
                               prompt, image=photo, said=want)
        if out.get("not_a_room"):
            return {"type": "message", "message": "방 사진이 아닌 것 같아요. 이런 느낌으로 살고 싶은 방 사진을 붙여 주세요.", "engine": "ai"}
        n = len(out["combos"])
        if not n:
            msg = "이 집 구조로는 조합을 못 만들었어요. 가구를 치우거나 다른 분위기로 말해 주세요."
        elif photo and out["seen"]:
            msg = f"사진에서 읽은 느낌: {out['seen']}. 이 집에 맞춰 {n}가지로 꾸며 봤어요. 마음에 드는 조합을 누르면 가구·가전·벽지까지 한 번에 들어가요."
        elif photo:
            msg = f"사진을 읽지 못해서 {'적어 준 말로' if prompt else '기본 분위기로'} {n}가지를 꾸며 봤어요. 마음에 드는 조합을 누르면 한 번에 들어가요."
        else:
            msg = f"{out['purpose_label'] or '이 공간'}을 {n}가지로 꾸며 봤어요. 마음에 드는 조합을 누르면 가구·가전·벽지까지 한 번에 들어가요."
        if n and out.get("auto_categories") and out["categories"]:
            msg += f" 가전은 이 공간에 흔히 두는 {'·'.join(CATEGORY_KO[c] for c in out['categories'])}로 넣었어요."
        return {"type": "combos", "message": msg, **out}

    def _named_combos(self, pid: str, prompt: str, named: list[str]) -> dict:
        """가전을 둘 이상 콕 집어 말했을 때. 종류·예산·가족 수는 말에서 코드가 읽는다 (AI는 분위기 컨셉만)."""
        said = rule_based_products(prompt)
        got = {n.category: n for n in needs(Life(**rule_life(prompt).model_dump()))}
        keep = {c: (lambda o, n=n: in_range(n, o)) for c, n in got.items() if c in named}
        out = self.make_combos(pid, named, said.price_max, prompt, said=said, keep=keep)
        n, names = len(out["combos"]), "·".join(CATEGORY_KO[c] for c in named)
        if not n:
            msg = "이 집 구조로는 조합을 못 만들었어요. 가구를 치우거나 다른 분위기로 말해 주세요."
        else:
            msg = f"말씀하신 {names}로 {n}가지를 꾸며 봤어요. 마음에 드는 조합을 누르면 가구·가전·벽지까지 한 번에 들어가요."
            if out["budget"] and all(c["lg_total"] <= out["budget"] for c in out["combos"]):
                msg += f" 가전 합계는 모두 예산 {won(out['budget'])} 안이에요."
            lost = sorted({m for c in out["combos"] for m in c["missing"]})
            if lost:
                msg += f" {'·'.join(lost)}는 예산이나 자리가 맞지 않아 빠진 조합이 있어요."
        return {"type": "combos", "message": msg, **out}

    def clear_combo(self, pid: str) -> dict:
        p = self.get_project(pid)
        p["scene_state"]["placements"] = [x for x in p["scene_state"]["placements"] if not x.get("combo")]
        self._rejudge_all(self.get_room(pid), p)
        self._save_project(p)
        return self._rebuild(pid)

    # ---- 적용 ----
    def apply_combo(self, pid: str, combo_id: str) -> dict:
        from .service import Invalid, NotFound

        p = self.get_project(pid)
        combo = next((c for c in p["scene_state"].get("combos") or [] if c["combo_id"] == combo_id), None)
        if combo is None:
            raise NotFound("조합을 다시 만들어 주세요")
        room = self.get_room(pid)
        keep = [x for x in p["scene_state"]["placements"] if not x.get("combo")]
        p["scene_state"]["placements"] = keep
        added, skipped = 0, []
        for it in combo["items"]:
            size = it["size_m"] if it["kind"] == "decor" else None
            try:
                prod = self._item(it["sku"], size)
            except Exception:  # 카탈로그에서 빠진 제품은 건너뛴다
                continue
            pose = Pose(tuple(it["center_xz"]), it["yaw_rad"], it.get("wall_id"))
            r = self._judge(room, p, prod, pose)
            if r.verdict.value == "no_fit" or r.size_m is None:
                skipped.append(it["name"])
                continue
            x = {"placement_id": self.db.next_id("pl"), "sku": it["sku"], "zone_id": None, "center_xz": list(pose.center_xz),
                 "yaw_rad": pose.yaw_rad, "size_m": list(r.size_m), "wall_id": pose.wall_id, "color": it.get("color"),
                 "hex": it.get("hex"), "verdict": r.verdict.value, "reasons": r.reasons, "combo": combo_id}
            if it["kind"] == "decor":
                x["kind"] = "decor"
            p["scene_state"]["placements"].append(x)
            if self._undersink(it["sku"]):
                self._add_sink_cabinet(room, p, x)
            added += 1
        if not added:
            raise Invalid("지금 집 상태에서는 이 조합이 들어가지 않아요. 조합을 다시 만들어 주세요")
        self._rejudge_all(room, p)
        self._save_project(p)
        for k in ("wall", "floor"):
            f = combo["finishes"].get(k)
            if f:
                self.apply_finish(pid, f["id"], f["tone"])
        out = self._rebuild(pid)
        out["combo"] = {"combo_id": combo_id, "name": combo["name"], "added": added, "skipped": skipped}
        return out
