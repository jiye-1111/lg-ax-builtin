"""빌트인 주방 맞춤장: 장 배치·부재 수정·가전 넣기·마감 (docs/specs/builtin-kitchen.md).

장은 꾸미기 가구 배치(decor:cab_<종류>)이고, 외경은 size_m, 부재·모드·실측·마감은 배치의 cab에 둔다.
장에 넣은 LG 가전은 보통 배치와 같지만 in_cab에 장 id를 적는다. 자리는 장 안쪽 빈 공간에서 계산하고(장을 옮기면 같이 간다),
판정은 장 안쪽 치수와 LGE.COM 공식 설치 기준(recommender.cabinet_fit)으로 한다. 가전 모델 크기는 바꾸지 않는다.
"""
from __future__ import annotations

import copy
import math

from recommender.cabinet import KINDS, cavity_floor_mm, kinds_list, normalize, palette, suggest
from recommender.cabinet_fit import judge, load_rules

from .decor import PREFIX, cab_kind

SIDE_TOUCH_M = 0.012   # 옆 장과 이만큼 안이면 붙어 있다고 본다 (좌우 고정면·싱크 옆 안내)
SAME_YAW_RAD = math.radians(5)
SINKS = frozenset({"decor:cab_sink", "decor:sink"})


def _uf(yaw: float):
    """폭 축(정면에서 봤을 때 오른쪽)과 정면 방향."""
    return (math.cos(yaw - math.pi / 2), math.sin(yaw - math.pi / 2)), (math.cos(yaw), math.sin(yaw))


class CabinetMixin:
    _rules = None

    @property
    def cab_rules(self):
        if CabinetMixin._rules is None:
            CabinetMixin._rules = load_rules()
        return CabinetMixin._rules

    def cabinet_kinds(self) -> dict:
        """장 종류·마감 목록·공식 기준이 있는 모델."""
        rules = [{"id": r["id"], "title": r["title"], "skus": r["applies_to"], "source_url": r["source_url"],
                  "recommend_mm": {a: r["axes"][a]["recommend"] for a in "whd"}} for r in self.cab_rules.all()]
        return {"kinds": kinds_list(), "finishes": palette(), "rules": rules}

    # ---- 장 안 가전 자리 ----
    @staticmethod
    def _cab_slot(cab: dict, size_m) -> tuple[list[float], float]:
        """장 안쪽 빈 공간 안의 가전 가운데 (바닥 기준). 옆은 좌우 부재 사이 가운데, 등은 안쪽 뒷면에 붙인다."""
        c = cab["cab"]
        p, o = c["parts"], c["outer_mm"]
        left = p.get("side_l", 0) + p.get("filler_l", 0) + p.get("end_l", 0)
        right = p.get("side_r", 0) + p.get("filler_r", 0) + p.get("end_r", 0)
        if c["kind"] == "tvwall":  # TV 칸은 좌우 키큰 수납 사이 가운데
            left = right = p.get("side_w", 0)
        du = (left - right) / 2 / 1000
        df = (-o["d"] / 2 + p.get("back", 0)) / 1000 + size_m[2] / 2
        u, f = _uf(cab["yaw_rad"])
        x, z = cab["center_xz"]
        return [x + u[0] * du + f[0] * df, z + u[1] * du + f[1] * df], cab["yaw_rad"]

    def _cab_neighbours(self, p: dict, cab: dict) -> dict:
        u, f = _uf(cab["yaw_rad"])
        out = {"left": False, "right": False, "sink": False}
        for y in p["scene_state"]["placements"]:
            if y is cab or not y.get("size_m") or not str(y.get("sku", "")).startswith(PREFIX) or y.get("in_cab"):
                continue
            if abs(((y["yaw_rad"] - cab["yaw_rad"] + math.pi) % (2 * math.pi)) - math.pi) > SAME_YAW_RAD:
                continue
            dx, dz = y["center_xz"][0] - cab["center_xz"][0], y["center_xz"][1] - cab["center_xz"][1]
            du, df = dx * u[0] + dz * u[1], dx * f[0] + dz * f[1]
            gap = abs(du) - (y["size_m"][0] + cab["size_m"][0]) / 2
            if gap > SIDE_TOUCH_M or abs(df) > (y["size_m"][2] + cab["size_m"][2]) / 2 or (y.get("base_m") or 0) > 0.3:
                continue
            out["right" if du > 0 else "left"] = True
            if y["sku"] in SINKS:
                out["sink"] = True
        return out

    def _cab_judge(self, p: dict, cab: dict) -> dict | None:
        c = cab["cab"]
        app = next((y for y in p["scene_state"]["placements"] if y.get("in_cab") == cab["placement_id"]), None)
        if app is None:
            return None
        prod = self.catalog.get(app["sku"])
        return judge(prod, c, self.cab_rules.get(prod.sku), self._cab_neighbours(p, cab))

    def _cabinets_sync(self, p: dict) -> None:
        """장 안 가전을 장 자리로 옮기고 장 판정을 다시 한다. 장이 없어진 가전은 끈을 푼다."""
        pls = p["scene_state"]["placements"]
        for x in pls:  # 목록에서 그냥 놓은 장(되돌리기·MCP)도 그 종류의 기본 부재로 장이 된다
            k = cab_kind(x.get("sku"))
            if k in KINDS and KINDS[k]["stage"] == 1 and not x.get("cab") and x.get("size_m"):
                x["cab"] = normalize({"kind": k, "outer_mm": {a: round(v * 1000) for a, v in zip("whd", x["size_m"])}})
        cabs = {x["placement_id"]: x for x in pls if x.get("cab")}
        for y in pls:
            host = cabs.get(y.get("in_cab"))
            if y.get("in_cab") and host is None:
                y.pop("in_cab", None)
                continue
            if host is not None:
                y["center_xz"], y["yaw_rad"] = self._cab_slot(host, y["size_m"])
                y["base_m"] = round((host.get("base_m") or 0) + cavity_floor_mm(host["cab"]) / 1000, 3)  # 오븐 칸·TV 칸은 그 칸 밑에
                y["on"], y["wall_id"], y["zone_id"] = None, None, None
                y.pop("slot", None)
        for cab in cabs.values():
            r = self._cab_judge(p, cab)
            cab["cab"].pop("appliance", None)
            if r is None:
                cab.pop("cab_check", None)
                continue
            cab["cab_check"] = r
            app = next(y for y in pls if y.get("in_cab") == cab["placement_id"])
            cab["cab"]["appliance"] = app["placement_id"]
            # 장 안 가전의 판정은 장 판정(공식 기준). 3D 문 열림 근사는 화면이 따로 본다
            app["verdict"] = r["verdict"]
            app["reasons"] = [{"code": "cabinet", "label": r["summary"], "ref": cab["placement_id"], "verdict": r["verdict"]}]

    def _cab_others_skip(self, p: dict, exclude: str | None) -> set[str]:
        """겹침을 볼 때 빼는 것: 장과 그 안 가전은 서로 겹쳐도 된다."""
        if not exclude:
            return set()
        me = next((x for x in p["scene_state"]["placements"] if x.get("placement_id") == exclude), None)
        skip = {x["placement_id"] for x in p["scene_state"]["placements"] if x.get("in_cab") == exclude}
        if me and me.get("in_cab"):
            skip.add(me["in_cab"])
        return skip

    # ---- 장 놓기·고치기 ----
    def _cab_category_ok(self, kind: str, sku: str):
        prod = self.catalog.get(sku)
        if prod.category not in KINDS[kind].get("host", ()):
            raise self._invalid(f"{KINDS[kind]['label']}에는 {prod.name}을 넣을 수 없어요")
        return prod

    @staticmethod
    def _invalid(msg: str):
        from .service import Invalid
        return Invalid(msg)

    def _cab_cfg(self, cfg: dict) -> dict:
        try:
            return normalize(cfg)
        except ValueError as e:
            raise self._invalid(str(e)) from None

    def add_cabinet(self, pid: str, kind: str, mode: str = "new", sku: str | None = None, center_xz=None, yaw_rad: float = 0.0,
                    outer_mm: dict | None = None, measured_mm: dict | None = None, parts: dict | None = None,
                    finish: dict | None = None, glass: str | None = None) -> dict:
        """맞춤장을 놓는다. 새 장 설계에 공식 기준이 있는 가전을 고르면 안쪽 권장 치수에 맞춰 외경을 정한다."""
        if kind not in KINDS or KINDS[kind]["stage"] != 1:
            raise self._invalid(f"놓을 수 없는 장: {kind}")
        if sku:
            self._cab_category_ok(kind, sku)
        base = {"kind": kind, "mode": mode, "parts": parts or {}, "finish": finish or {}}
        if outer_mm:
            base["outer_mm"] = outer_mm
        if measured_mm is not None:
            base["measured_mm"] = measured_mm
        if glass:
            base["glass"] = glass
        cfg = self._cab_cfg(base)
        if mode == "new" and sku and not outer_mm:
            cfg = suggest(kind, self.cab_rules.get(sku), cfg) or cfg
        size = [cfg["outer_mm"][a] / 1000 for a in "whd"]
        sku_cab = f"{PREFIX}cab_{kind}"
        base_m = cfg["base_mm"] / 1000 if "base_mm" in cfg else None
        if center_xz is None:
            out = self.auto_place(pid, sku_cab, size_m=size)
        else:
            out = self.place_at(pid, sku_cab, center_xz, yaw_rad, snap=True, size_m=size, base_m=base_m, slot=False)
        cab_id = out["placement"]["placement_id"]
        p = self.get_project(pid)
        x = self._find_placement(p, cab_id)
        x["cab"] = cfg
        if kind == "counter" and base_m is not None:
            x["base_m"], x["float"] = base_m, True
        self._save_project(p)
        if sku:
            return self.set_cabinet_appliance(pid, cab_id, sku, resize=False)
        return self._cab_done(pid, cab_id)

    def set_cabinet(self, pid: str, placement_id: str, patch: dict) -> dict:
        """부재·외경·모드·실측·마감·유리를 바꾼다. 새 장은 안쪽을 다시 계산하고, 기존 장은 실측값을 그대로 쓴다."""
        room, p = self.get_room(pid), self.get_project(pid)
        x = self._find_placement(p, placement_id)
        if not x.get("cab"):
            raise self._invalid("맞춤장이 아니에요")
        cur = copy.deepcopy(x["cab"])
        for k in ("outer_mm", "parts", "measured_mm", "finish"):
            if patch.get(k) is not None:
                cur[k] = {**(cur.get(k) or {}), **patch[k]}
        for k in ("mode", "glass", "base_mm"):
            if patch.get(k) is not None:
                cur[k] = patch[k]
        if cur.get("mode") == "existing" and "measured_mm" not in cur:
            cur["measured_mm"] = {a: None for a in "whd"}  # 기존 장으로 바꾸면 실측을 새로 넣는다
        if cur.get("mode") == "new":
            cur.pop("measured_mm", None)
        cfg = self._cab_cfg(cur)
        x["cab"] = cfg
        x["size_m"] = [cfg["outer_mm"][a] / 1000 for a in "whd"]
        if "base_mm" in cfg and x.get("hung"):
            x["base_m"] = cfg["base_mm"] / 1000
        self._rejudge_all(room, p)
        self._save_project(p)
        return self._cab_done(pid, placement_id)

    def set_cabinet_appliance(self, pid: str, placement_id: str, sku: str | None, resize: bool = False) -> dict:
        """장에 가전을 넣거나 바꾸거나 뺀다(sku=None). 기존 장은 크기를 그대로 두고,
        새 장은 resize=True일 때만 그 모델의 공식 권장 안쪽 치수로 다시 맞춘다 (기준이 없으면 그대로)."""
        room, p = self.get_room(pid), self.get_project(pid)
        cab = self._find_placement(p, placement_id)
        if not cab.get("cab"):
            raise self._invalid("맞춤장이 아니에요")
        kind = cab["cab"]["kind"]
        pls = p["scene_state"]["placements"]
        old = next((y for y in pls if y.get("in_cab") == placement_id), None)
        if old is not None:
            pls.remove(old)
        if sku:
            prod = self._cab_category_ok(kind, sku)
            if resize and cab["cab"]["mode"] == "new":
                cfg = suggest(kind, self.cab_rules.get(sku), cab["cab"])
                if cfg:
                    cab["cab"], cab["size_m"] = cfg, [cfg["outer_mm"][a] / 1000 for a in "whd"]
            d = prod.product_dims_mm
            if d.w is None or d.h is None or d.d is None:
                raise self._invalid("제품 치수 정보가 없어 넣을 수 없어요")
            opt = self._color_option(prod, None)
            size = [d.w / 1000, d.h / 1000, d.d / 1000]  # 가전 모델은 늘이거나 줄이지 않는다
            c, yaw = self._cab_slot(cab, size)
            pls.append({"placement_id": old["placement_id"] if old else self.db.next_id("pl"), "sku": sku, "zone_id": None,
                        "center_xz": c, "yaw_rad": yaw, "size_m": size, "wall_id": None,
                        "color": opt.color if opt else None, "hex": opt.hex_approx if opt else None,
                        "verdict": "unknown", "reasons": [], "base_m": 0.0, "on": None, "tabletop": False, "in_cab": placement_id})
        self._rejudge_all(room, p)
        self._save_project(p)
        return self._cab_done(pid, placement_id)

    def cabinet_finish(self, pid: str, ids: list[str], part: str, finish: str) -> dict:
        """고른 장 여러 개에 같은 마감을 한 번에."""
        room, p = self.get_room(pid), self.get_project(pid)
        cabs = [self._find_placement(p, i) for i in ids]
        if not cabs or any(not x.get("cab") for x in cabs):
            raise self._invalid("맞춤장만 마감을 한 번에 바꿀 수 있어요")
        for x in cabs:
            if part == "glass":
                x["cab"] = self._cab_cfg({**x["cab"], "glass": finish}) if "glass" in x["cab"] else x["cab"]
            else:
                x["cab"] = self._cab_cfg({**x["cab"], "finish": {**x["cab"]["finish"], part: finish}})
        self._save_project(p)
        out = self._rebuild(pid)
        out["placements"] = [self._find_placement(self.get_project(pid), i) for i in ids]
        return out

    def _cab_done(self, pid: str, placement_id: str) -> dict:
        out = self._rebuild(pid)
        q = self.get_project(pid)
        out["placement"] = self._find_placement(q, placement_id)
        out["scene_state"] = q["scene_state"]
        return out


def is_cab(sku: str | None) -> bool:
    return cab_kind(sku) is not None
