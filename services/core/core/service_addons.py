"""'여기에 이걸 더하면 좋아요': 꾸며 놓은 집을 보고 하우니가 먼저 권하는 것.

무엇을 권할지는 recommender.addons 규칙, 어디에 놓을지는 recommender.layout(기준 가구 곁) 또는 auto_place와 같은 자리 찾기,
LG 가전은 이 집에 실제로 들어가는 판매 중 제품 가운데 가격이 가운데쯤인 것. AI를 부르지 않는다 (놓을 때마다 바로 떠야 해서).
"""
from __future__ import annotations

from statistics import median

from recommender.addons import BY_ID, Addon, pick_addons, shortlist
from recommender.layout import Item, arrange_near
from recommender.pose import Pose

from .ai_products import CATEGORY_KO
from .combos import NIGHTSTAND_M, label_of
from .decor import decor_product, is_decor

NIGHTSTAND_MAX_W = 0.6   # 이보다 좁은 서랍장은 협탁으로 본다
LG_TRIES = 4
LIMIT = 3


class AddonMixin:
    def _addon_have(self, room, p: dict) -> tuple[list[str], list[dict]]:
        """집에 있는 것의 종류, 직접 놓은 것."""
        mine = [x for x in p["scene_state"]["placements"] if x.get("size_m") and not x.get("host_of") and not x.get("over")]
        have = []
        for x in mine:
            if is_decor(x["sku"]):
                kind = x["sku"].split(":", 1)[1]
                have.append("nightstand" if kind == "dresser" and x["size_m"][0] <= NIGHTSTAND_MAX_W else kind)
            else:
                try:
                    have.append(self.catalog.get(x["sku"]).category)
                except KeyError:
                    continue
        gone = set(p["scene_state"].get("hidden_objects") or [])
        have += [o.category for o in room.objects if o.object_id not in gone]
        if self._hoodless(p) is not None:
            have.append("cooktop_bare")
        return have, mine

    def _addon_anchor(self, p: dict, mine: list[dict], rule: Addon):
        """이 제안의 기준이 되는 가구 (직접 놓은 것만: 스캔 가구는 앞뒤를 모른다)."""
        for x in mine:
            if is_decor(x["sku"]) and x["sku"].split(":", 1)[1] in rule.when:
                return x
        return None

    def _addon_spots(self, room, p: dict, mine: list[dict], rule: Addon) -> list[dict] | None:
        """가구 제안이 들어갈 자리들. 자리가 없으면 None."""
        size = NIGHTSTAND_M if rule.kind == "nightstand" else None
        prod = decor_product(rule.sku, size)
        if rule.id == "hood":
            return [{"auto": True}]
        anchor = self._addon_anchor(p, mine, rule)
        if anchor is not None and rule.role != "wall":
            a_size = anchor["size_m"] if is_decor(anchor["sku"]) else None
            a_item = Item(key="anchor", sku=anchor["sku"], product=self._item(anchor["sku"], a_size), role="anchor",
                          size_m=tuple(a_size) if a_size else None)
            seat = (a_item, Pose(tuple(anchor["center_xz"]), anchor["yaw_rad"], anchor.get("wall_id")), tuple(anchor["size_m"]))
            others = [x for x in self._others(p) if x["placement_id"] != anchor["placement_id"]]
            got = arrange_near(room, Item(key=rule.id, sku=rule.sku, product=prod, role=rule.role, size_m=size), seat,
                               self.fit_cfg, others, self._blocked_off(p), self._counters(room, p))
            if got:
                return [{"center_xz": [round(v, 4) for v in x.pose.center_xz], "yaw_rad": round(x.pose.yaw_rad, 6),
                         "wall_id": x.pose.wall_id} for x in got]
            if rule.role in ("pair", "front", "desk_chair"):
                return None   # 바로 곁에 못 두면 권하지 않는다 (엉뚱한 벽에 놓인 협탁은 도움이 안 된다)
        r = self._auto_spot(room, p, prod)
        if r is None:
            return None
        return [{"center_xz": list(r.pose.center_xz), "yaw_rad": r.pose.yaw_rad, "wall_id": r.pose.wall_id}]

    def _addon_lg(self, room, p: dict, rule: Addon):
        """이 종류에서 이 집에 들어가는 판매 중 제품 하나 (가격이 가운데쯤인 것부터 놓아 본다)."""
        pool = [x for x in self._combo_pool(room, rule.category) if not x.demo_only]
        if not pool:
            return None
        mid = median(x.price_krw for x in pool)
        for prod in sorted(pool, key=lambda x: (abs(x.price_krw - mid), x.sku))[:LG_TRIES]:
            if self._auto_spot(room, p, prod) is not None:
                return prod
        return None

    def _addon_row(self, room, p: dict, mine: list[dict], rule: Addon) -> dict | None:
        if rule.lg:
            prod = self._addon_lg(room, p, rule)
            if prod is None:
                return None
            return {"id": rule.id, "kind": "lg", "sku": prod.sku, "name": prod.name, "category": rule.category,
                    "category_label": CATEGORY_KO.get(rule.category, ""), "price": prod.price_krw, "text": rule.text,
                    "spots": [{"auto": True}], "size_m": None}
        spots = self._addon_spots(room, p, mine, rule)
        if not spots:
            return None
        return {"id": rule.id, "kind": "decor", "sku": rule.sku, "name": label_of(rule.kind), "category": None,
                "category_label": None, "price": None, "text": rule.text, "spots": spots,
                "size_m": list(NIGHTSTAND_M) if rule.kind == "nightstand" else None}

    def addons(self, pid: str, limit: int = LIMIT) -> dict:
        """지금 꾸민 상태에서 더하면 좋은 것 최대 3개. 직접 놓은 것이 없으면 권하지 않는다."""
        room, p = self.get_room(pid), self.get_project(pid)
        have, mine = self._addon_have(room, p)
        if not mine:
            return {"items": []}
        rows, cands = [], pick_addons(have, placed=len(mine))
        want = shortlist(cands, limit)
        for rule in want + [a for a in cands if a not in want]:   # 자리가 없어 빠진 만큼 다음 것으로 채운다
            if len(rows) >= limit:
                break
            row = self._addon_row(room, p, mine, rule)
            if row:
                rows.append(row)
        return {"items": rows}

    def apply_addon(self, pid: str, addon_id: str) -> dict:
        """제안 하나를 그 자리에 더한다. 그사이 집이 바뀌었으면 지금 상태로 다시 계산한 자리에 놓는다."""
        from .service import Invalid, NotFound

        rule = BY_ID.get(addon_id)
        if rule is None:
            raise NotFound("모르는 제안이에요")
        room, p = self.get_room(pid), self.get_project(pid)
        have, mine = self._addon_have(room, p)
        if not mine or rule not in pick_addons(have, placed=len(mine)):
            raise Invalid("지금 집에는 이미 있거나 필요 없는 제안이에요")
        row = self._addon_row(room, p, mine, rule)
        if row is None:
            raise Invalid("지금은 들어갈 자리가 없어요. 가구를 조금 옮긴 뒤 다시 눌러 주세요")
        before = {x["placement_id"] for x in p["scene_state"]["placements"]}
        out = None
        for s in row["spots"]:
            try:
                if s.get("auto"):
                    out = self.auto_place(pid, row["sku"], size_m=row["size_m"])
                else:
                    out = self.place_at(pid, row["sku"], s["center_xz"], s["yaw_rad"], snap=False, wall_id=s.get("wall_id"),
                                        size_m=row["size_m"])
            except Invalid:
                continue
        if out is None:
            raise Invalid("지금은 들어갈 자리가 없어요. 가구를 조금 옮긴 뒤 다시 눌러 주세요")
        out.pop("placement", None)
        out["added"] = [x["placement_id"] for x in out["scene_state"]["placements"] if x["placement_id"] not in before]
        out["addon"] = {"id": rule.id, "name": row["name"]}
        return out
