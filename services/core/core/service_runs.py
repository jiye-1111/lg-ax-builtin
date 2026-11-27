"""벽면 맞춤가구 세트 (docs/specs/wall-run.md).

세트(run)는 한 벽을 따라 놓은 장들의 순서·틈·시작 위치만 적는다: scene_state.cab_runs.
장 하나하나는 그대로 맞춤장 배치(decor:cab_<종류>)이고 cab.run = {id, tier, idx}로 세트에 묶인다.
- 미리보기(preview)는 사본에만 적용하고 저장하지 않는다. 확정(confirm)만 저장한다. 취소는 아무것도 안 하면 된다.
- 장 하나를 패널에서 고치거나 지우면 세트를 다시 늘어놓는다 (_runs_sync). 3D에서 끌어 옮기면 세트에서 빠진다.
- 이미 놓은 가전을 장에 연결(app.id)하면 그 가전을 그대로 쓴다 (새로 만들지 않음, cab_made=False).
"""
from __future__ import annotations

import copy
import math

from recommender.cabinet import KINDS, normalize, suggest
from recommender.pose import _thick, room_center
from recommender.runs import TIERS, align_counter, layout, preset_cfg, presets

from .decor import PREFIX

WALL_SOURCE_KO = {"technician": "실측", "customer": "실측", "floorplan": "도면", "reference": "한 벽 실측으로 보정"}
# 가전 매입부·싱크의 전기·급배수·방열: 도면·스캔으로는 알 수 없으니 확정으로 보이지 않게 한다
UTILITY_NOTES = {
    "sink": [("water", "급수·배수", "급수·배수 위치는 현장에서 확인해야 해요")],
    "dishwasher": [("water", "급수·배수", "급수·배수 위치는 현장에서 확인해야 해요"), ("power", "전원", "콘센트 위치는 현장에서 확인해야 해요")],
    "fridge": [("power", "전원", "콘센트 위치는 현장에서 확인해야 해요")],
    "oven_tall": [("power", "전원", "전용 콘센트·차단기는 현장에서 확인해야 해요"), ("heat", "방열", "모델 설치 기준의 방열 여유를 확인해야 해요")],
    "cooktop_base": [("power", "전기", "인덕션 전용 전기 공사가 필요한지 현장에서 확인해야 해요")],
    "hood_cab": [("duct", "배기", "배기 덕트 위치는 현장에서 확인해야 해요")],
    "tvwall": [("power", "전원·배선", "TV 뒤 콘센트·배선 위치는 현장에서 확인해야 해요")],
}
CORNER_M = 0.35  # 벽 끝점이 이만큼 안이면 이어진 벽으로 본다
CORNER_GAP_M = 0.02  # 옆 벽 면과 띄우는 여유 (스캔 벽이 조금 기울어도 안 닿게)
HEAT_CODES = ("rear", "heat", "vent", "side_gap", "top_gap")


class RunMixin:
    # ---- 데이터 ----
    def cabinet_presets(self) -> dict:
        d = presets()
        return {"note": d["note"], "sources": d["sources"], "presets": d["presets"], "starters": d["starters"]}

    @staticmethod
    def _runs(p: dict) -> list[dict]:
        return p["scene_state"].setdefault("cab_runs", [])

    def _wall_info(self, room, wall_id: str) -> dict:
        try:
            w = room.wall(wall_id)
        except KeyError:
            raise self._invalid(f"없는 벽: {wall_id}") from None
        # 벽 길이는 가운데 선이라, 이어진 옆 벽 안쪽 면까지는 장을 놓을 수 없다 (스캔 벽은 끝점이 딱 맞지 않아 투영해서 잰다)
        L = math.dist(w.start, w.end) or 1e-9
        u = ((w.end[0] - w.start[0]) / L, (w.end[1] - w.start[1]) / L)

        def inset(p, sign):
            best = 0.0
            for o in room.walls:
                if o is w:
                    continue
                q = min((tuple(o.start), tuple(o.end)), key=lambda e: math.dist(p, e))
                if math.dist(p, q) > CORNER_M:
                    continue
                along = sign * ((q[0] - p[0]) * u[0] + (q[1] - p[1]) * u[1])  # 끝점에서 안쪽으로 얼마나 들어와 있나
                best = max(best, along + _thick(o) / 2 + CORNER_GAP_M)
            return best
        return {"wall_id": w.wall_id, "start": tuple(w.start), "end": tuple(w.end), "thickness_m": _thick(w),
                "inset_start_m": inset(tuple(w.start), 1), "inset_end_m": inset(tuple(w.end), -1),
                "inward_hint": room_center(room), "openings": [o.model_dump() for o in room.openings],
                "source": WALL_SOURCE_KO.get(w.measured.by if w.measured and w.measured.length_m else None, "스캔")}

    # ---- 모듈 설정 ----
    def _run_cfg(self, spec: dict, old: dict | None) -> dict:
        """요청 모듈 → 장 설정. 같은 장이면 지금 설정 위에, 프리셋을 바꾸면(교체) 새 프리셋에 마감만 이어 받는다."""
        pre = spec.get("preset")
        if old is not None and (not pre or pre == old["cab"].get("preset")):
            cur = copy.deepcopy(old["cab"])
            cur.pop("run", None)
        elif pre:
            try:
                cur = preset_cfg(pre)
            except ValueError as e:
                raise self._invalid(str(e)) from None
            if old is not None:
                cur["finish"] = old["cab"]["finish"]
        elif spec.get("kind"):
            cur = {"kind": spec["kind"]}
        else:
            raise self._invalid("모듈에 preset이나 kind가 있어야 해요")
        for k in ("outer_mm", "parts", "finish", "measured_mm"):
            if spec.get(k):
                cur[k] = {**(cur.get(k) or {}), **spec[k]}
        for k in ("mode", "glass", "base_mm"):
            if spec.get(k) is not None:
                cur[k] = spec[k]
        if cur.get("mode") == "existing" and "measured_mm" not in cur:
            cur["measured_mm"] = {a: None for a in "whd"}
        if cur.get("mode", "new") == "new":
            cur.pop("measured_mm", None)
        cfg = self._cab_cfg(cur)
        app = spec.get("app") or {}
        if app.get("sku") and cfg["mode"] == "new" and not spec.get("outer_mm") and KINDS[cfg["kind"]].get("host"):
            self._cab_category_ok(cfg["kind"], app["sku"])
            cfg = suggest(cfg["kind"], self.cab_rules.get(app["sku"]), cfg) or cfg  # 공식 기준이 있는 모델만 그 치수로
            if pre:
                cfg["preset"] = pre
        if spec.get("dims_by"):
            cfg["dims_by"] = spec["dims_by"]
        return cfg

    # ---- 세트 적용 ----
    def _run_apply(self, room, p: dict, spec: dict, commit: bool) -> dict:
        runs = self._runs(p)
        rid = spec.get("run_id")
        old_run = next((r for r in runs if r["run_id"] == rid), None) if rid else None
        if rid and old_run is None:
            raise self._invalid(f"없는 세트: {rid}")
        if not rid:
            rid = self.db.next_id("run") if commit else "run_new"
        wall = self._wall_info(room, spec["wall_id"])
        pls = p["scene_state"]["placements"]
        mine = {x["placement_id"]: x for x in pls if (x.get("cab") or {}).get("run", {}).get("id") == rid}
        cfgs, rows, apps, n = {}, {t: [] for t in TIERS}, {}, 0
        for tier in TIERS:
            for m in (spec.get("rows") or {}).get(tier, []):
                old = mine.get(m.get("id")) if m.get("id") else None
                cfg = self._run_cfg(m, old)
                if old is not None:
                    mid = old["placement_id"]
                else:
                    n += 1
                    mid = self.db.next_id("pl") if commit else f"new{n}"
                cfgs[mid] = cfg
                rows[tier].append({"id": mid, "gap_mm": max(0, round(float(m.get("gap_mm", 0) or 0)))})
                if "app" in m:
                    apps[mid] = m["app"]
        notes = []
        if spec.get("align"):
            ids = [r["id"] for r in rows["base"]]
            fixed, notes = align_counter([cfgs[i] for i in ids])
            cfgs.update(zip(ids, fixed))
        run = {"run_id": rid, "wall_id": wall["wall_id"], "room": spec.get("room") or (old_run or {}).get("room"),
               "start_mm": {t: max(-2000, min(20000, round(float((spec.get("start_mm") or {}).get(t, 0) or 0)))) for t in TIERS},
               "rows": rows}
        # 빠진 장은 지운다. 그 장에 연결만 한 가전은 남기고, 장과 같이 만든 가전만 같이 뺀다
        keep = set(cfgs)
        gone = {i for i in mine if i not in keep}
        self._drop_cabs(p, gone)
        if old_run is not None:
            runs.remove(old_run)
        runs.append(run)
        self._run_place(room, p, run, cfgs, wall)
        for mid, app in apps.items():
            self._run_link(p, mid, app)
        self._rejudge_all(room, p)
        return self._run_report(room, p, run, wall, notes)

    def _drop_cabs(self, p: dict, ids: set[str]) -> None:
        if not ids:
            return
        pls = p["scene_state"]["placements"]
        for y in pls:
            if y.get("in_cab") in ids and not y.get("cab_made", True):
                y.pop("in_cab")
        p["scene_state"]["placements"] = [y for y in pls if y["placement_id"] not in ids
                                          and not (y.get("in_cab") in ids and y.get("cab_made", True))]

    def _run_place(self, room, p: dict, run: dict, cfgs: dict, wall: dict | None = None) -> dict:
        """세트 순서대로 장 자리를 다시 잡는다 (없는 장은 만든다)."""
        wall = wall or self._wall_info(room, run["wall_id"])
        lay = layout(wall, run, cfgs)
        pls = p["scene_state"]["placements"]
        by = {x["placement_id"]: x for x in pls}
        for m in lay["modules"]:
            cfg = copy.deepcopy(cfgs[m["id"]])
            cfg["run"] = {"id": run["run_id"], "tier": m["tier"], "idx": m["idx"]}
            kind = cfg["kind"]
            x = by.get(m["id"])
            if x is None:
                x = {"placement_id": m["id"], "zone_id": None, "color": None, "hex": None, "verdict": "unknown", "reasons": [],
                     "on": None, "tabletop": False, "kind": "decor"}
                pls.append(x)
                by[m["id"]] = x
            x["sku"] = f"{PREFIX}cab_{kind}"
            x["center_xz"], x["yaw_rad"], x["wall_id"] = m["center_xz"], m["yaw_rad"], run["wall_id"]
            x["size_m"] = [cfg["outer_mm"][a] / 1000 for a in "whd"]
            x["cab"] = cfg
            if KINDS[kind].get("hang") or m["tier"] == "wall":
                x["base_m"], x["hung"] = m["y0"] / 1000, True
            else:
                x["base_m"] = 0.0
                x.pop("hung", None)
        return lay

    def _run_link(self, p: dict, cab_id: str, app: dict | None) -> None:
        """장에 가전: {id} = 이미 놓은 가전을 연결, {sku} = 그 모델을 새로 넣기, None = 빼기."""
        pls = p["scene_state"]["placements"]
        cab = next(x for x in pls if x["placement_id"] == cab_id)
        cur = next((y for y in pls if y.get("in_cab") == cab_id), None)
        if app and app.get("id"):
            if cur is not None and cur["placement_id"] == app["id"]:
                return
            y = next((y for y in pls if y["placement_id"] == app["id"]), None)
            if y is None or y.get("cab") or str(y.get("sku", "")).startswith(PREFIX):
                raise self._invalid("연결할 가전이 없어요")
            self._cab_category_ok(cab["cab"]["kind"], y["sku"])
            self._unlink_app(p, cur)
            y["in_cab"], y["cab_made"] = cab_id, False
            return
        if app and app.get("sku"):
            if cur is not None and cur["sku"] == app["sku"]:
                return
            prod = self._cab_category_ok(cab["cab"]["kind"], app["sku"])
            d = prod.product_dims_mm
            if d.w is None or d.h is None or d.d is None:
                raise self._invalid("제품 치수 정보가 없어 넣을 수 없어요")
            self._unlink_app(p, cur)
            opt = self._color_option(prod, None)
            size = [d.w / 1000, d.h / 1000, d.d / 1000]
            c, yaw = self._cab_slot(cab, size)
            pls.append({"placement_id": self.db.next_id("pl") if not cab_id.startswith("new") else f"{cab_id}_app", "sku": app["sku"],
                        "zone_id": None, "center_xz": c, "yaw_rad": yaw, "size_m": size, "wall_id": None,
                        "color": opt.color if opt else None, "hex": opt.hex_approx if opt else None, "verdict": "unknown",
                        "reasons": [], "base_m": 0.0, "on": None, "tabletop": False, "in_cab": cab_id, "cab_made": True})
            return
        self._unlink_app(p, cur)

    @staticmethod
    def _unlink_app(p: dict, y: dict | None) -> None:
        if y is None:
            return
        if y.get("cab_made", True):
            p["scene_state"]["placements"].remove(y)
        else:
            y.pop("in_cab", None)

    def _runs_sync(self, room, p: dict) -> None:
        """패널에서 장을 고치거나 지운 뒤: 남은 장으로 세트를 다시 늘어놓는다."""
        runs = p["scene_state"].get("cab_runs")
        if not runs:
            return
        by = {x["placement_id"]: x for x in p["scene_state"]["placements"] if x.get("cab")}
        for run in list(runs):
            for t in TIERS:
                run["rows"][t] = [r for r in run["rows"][t] if r["id"] in by and (by[r["id"]]["cab"].get("run") or {}).get("id") == run["run_id"]]
            if not any(run["rows"][t] for t in TIERS):
                runs.remove(run)
                continue
            try:
                self._run_place(room, p, run, {r["id"]: by[r["id"]]["cab"] for t in TIERS for r in run["rows"][t]})
            except Exception:  # 벽이 없어진 집(다시 스캔 등): 세트만 풀고 장은 그 자리에 둔다
                for t in TIERS:
                    for r in run["rows"][t]:
                        by[r["id"]]["cab"].pop("run", None)
                runs.remove(run)

    def _run_detach(self, p: dict, x: dict) -> None:
        """3D에서 끌어 옮긴 장은 세트에서 뺀다 (다시 늘어놓을 때 제자리로 끌려가지 않게)."""
        r = (x.get("cab") or {}).pop("run", None)
        if not r:
            return
        for run in self._runs(p):
            if run["run_id"] == r["id"]:
                for t in TIERS:
                    run["rows"][t] = [m for m in run["rows"][t] if m["id"] != x["placement_id"]]

    # ---- 결과 ----
    def _run_report(self, room, p: dict, run: dict, wall: dict, notes: list[str]) -> dict:
        pls = p["scene_state"]["placements"]
        by = {x["placement_id"]: x for x in pls}
        cfgs = {r["id"]: by[r["id"]]["cab"] for t in TIERS for r in run["rows"][t]}
        lay = layout(wall, run, cfgs)
        mods, fit, util = [], [], []
        pre = presets()["by_id"]
        for m in lay["modules"]:
            x = by[m["id"]]
            c = x["cab"]
            app = next((y for y in pls if y.get("in_cab") == x["placement_id"]), None)
            src = "실측" if c["mode"] == "existing" else ("입력값" if c.get("dims_by") == "user" else "프리셋")
            label = pre.get(c.get("preset"), {}).get("label") or KINDS[c["kind"]]["label"]
            mods.append({**m, "label": label, "kind": c["kind"], "dims_src": src, "verdict": x.get("verdict"),
                         "reasons": x.get("reasons", []), "app": app and {"id": app["placement_id"], "sku": app["sku"],
                                                                         "cab_made": app.get("cab_made", True)}})
            if KINDS[c["kind"]].get("host"):
                chk = x.get("cab_check")
                if chk:
                    fit.append({"id": m["id"], "label": label, "verdict": chk["verdict"], "verdict_ko": chk["verdict_ko"],
                                "summary": chk["summary"], "rule_id": chk.get("rule_id")})
                else:
                    fit.append({"id": m["id"], "label": label, "verdict": "unknown", "verdict_ko": "확인 필요",
                                "summary": "넣을 가전 모델을 고르거나, 빈 공간 치수를 실측으로 넣어 주세요. 설치 기준 확인 필요", "rule_id": None})
                for chk_line in (chk or {}).get("checks", []):
                    if chk_line["code"] in HEAT_CODES:
                        util.append({"id": m["id"], "label": f"{label} · {chk_line['label']}", "status": chk_line["status"],
                                     "detail": chk_line["detail"]})
            for code, what, detail in UTILITY_NOTES.get(c["kind"], ()):
                util.append({"id": m["id"], "label": f"{label} · {what}", "status": "site", "detail": detail, "code": code})
            if c["kind"] == "tvwall":
                pp = c["parts"]
                util.append({"id": m["id"], "label": f"{label} · 배선 통로", "status": "ok" if pp.get("cable") else "check",
                             "detail": "TV 칸 뒤에 배선 통로를 둬요" if pp.get("cable") else "배선 통로가 없어요. 선이 앞으로 드러날 수 있어요"})
                util.append({"id": m["id"], "label": f"{label} · 통풍", "status": "ok" if pp.get("vent", 0) >= 50 else "check",
                             "detail": f"TV 둘레 통풍 여유 {pp.get('vent', 0)} mm (TV 모델 설명서 값과 견줘 보세요)"})
        issues = list(lay["issues"])
        for mm in mods:  # 세트 밖 물건(가구·스캔 물건·벽)과 겹침은 배치 판정이 알려 준다
            for r in mm["reasons"]:
                if r.get("code") in ("overlaps_object", "overlaps_placement", "hits_wall", "outside_room", "door_blocked", "ceiling_low"):
                    issues.append({"code": r["code"], "level": "no" if mm["verdict"] == "no_fit" else "check", "id": mm["id"],
                                   "tier": mm["tier"], "s_mm": round(mm["s0"]), "label": f"{mm['label']}: {r['label']}"})
        sim = all(m["dims_src"] == "프리셋" for m in mods) and wall["source"] == "스캔"
        return {"run": run, "wall": {"wall_id": wall["wall_id"], "length_mm": lay["length_mm"], "source": wall["source"]},
                "modules": mods, "usage": lay["usage"], "issues": issues, "openings": lay["openings"], "fit": fit,
                "utilities": util, "notes": notes, "simulation": sim}

    def preview_run(self, pid: str, spec: dict) -> dict:
        """저장하지 않고 세트를 놓아 본다. 사본 장면(scene_state)도 같이 돌려줘 화면이 그대로 그린다."""
        room, p = self.get_room(pid), copy.deepcopy(self.get_project(pid))
        out = self._run_apply(room, p, spec, commit=False)
        out["scene_state"] = p["scene_state"]
        out["preview"] = True
        return out

    def confirm_run(self, pid: str, spec: dict) -> dict:
        room, p = self.get_room(pid), self.get_project(pid)
        rep = self._run_apply(room, p, spec, commit=True)
        self._save_project(p)
        out = self._rebuild(pid)
        out["run"] = rep
        return out

    def delete_run(self, pid: str, run_id: str) -> dict:
        room, p = self.get_room(pid), self.get_project(pid)
        run = next((r for r in self._runs(p) if r["run_id"] == run_id), None)
        if run is None:
            raise self._invalid(f"없는 세트: {run_id}")
        self._drop_cabs(p, {r["id"] for t in TIERS for r in run["rows"][t]})
        self._runs(p).remove(run)
        self._rejudge_all(room, p)
        self._save_project(p)
        return self._rebuild(pid)

    def get_run(self, pid: str, run_id: str) -> dict:
        room, p = self.get_room(pid), self.get_project(pid)
        run = next((r for r in self._runs(p) if r["run_id"] == run_id), None)
        if run is None:
            raise self._invalid(f"없는 세트: {run_id}")
        return self._run_report(room, p, run, self._wall_info(room, run["wall_id"]), [])
