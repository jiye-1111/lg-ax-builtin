"""서비스 계층 — 웹 API와 MCP 도구가 똑같이 이 함수를 호출한다.

그래서 Claude·Codex에서 바꾼 상태가 웹 화면에 그대로 보인다 (기획 §6.2 "채팅과 웹 화면을 같은 프로젝트 상태로").
"""
from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from recommender.cmf import rank_cmf
from recommender.fit import FitConfig, check_fit
from recommender.pose import Pose, check_pose, snap_to_wall
from sim.regions import REGIONS
from recommender.recommend import recommend_zone

from . import config
from .models import MeasuredDims, Product, Room, StyleTags, Zone
from .store import Store

KST = timezone(timedelta(hours=9))
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
MATERIAL_TARGETS = ("wall", "floor", "door", "window", "object")


class NotFound(KeyError):
    pass


class Invalid(ValueError):
    pass


def now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


# ---------------- 카탈로그 ----------------
class Catalog:
    def __init__(self, paths: list[Path]):
        self.products: list[Product] = []
        for p in paths:
            if not p.exists():
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            items = data["products"] if isinstance(data, dict) else data
            self.products += [Product.model_validate(x) for x in items]

    def get(self, sku: str) -> Product:
        for p in self.products:
            if p.sku == sku:
                return p
        raise NotFound(f"카탈로그에 없는 제품: {sku}")

    def search(self, category: str | None = None, zone: str | None = None, query: str | None = None,
               install_type: str | None = None) -> list[Product]:
        out = self.products
        if category:
            out = [p for p in out if p.category == category]
        if zone:
            out = [p for p in out if zone in p.zone_fit]
        if install_type:
            out = [p for p in out if p.install_type == install_type]
        if query:
            q = query.lower()
            out = [p for p in out if q in p.name.lower() or q in p.sku.lower() or q in p.category]
        return out


# ---------------- 서비스 ----------------
class Service:
    def __init__(self, storage: Path | None = None, catalog: Catalog | None = None, fit_cfg: FitConfig | None = None):
        self.root = Path(storage or config.storage_dir())
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = Store(self.root / "app.sqlite3")
        self.catalog = catalog or Catalog(config.catalog_paths())
        self.fit_cfg = fit_cfg or FitConfig.from_env()

    # ---- 경로 ----
    def pdir(self, pid: str) -> Path:
        return self.root / "projects" / pid

    # ---- F1 상담 요청 (목업) ----
    def create_request(self, name: str, contact: str, address: str, preferred_at: str | None) -> dict:
        rid = self.db.next_id("r")
        req = {"request_id": rid, "customer": {"name": name, "contact": contact}, "address": address,
               "preferred_at": preferred_at, "status": "requested", "created_at": now()}
        return self.db.put("request", rid, req)

    def list_requests(self) -> list[dict]:
        return self.db.list("request")

    def get_request(self, rid: str) -> dict:
        r = self.db.get("request", rid)
        if r is None:
            raise NotFound(rid)
        return r

    def _set_request_status(self, rid: str | None, status: str) -> None:
        if not rid:
            return
        r = self.db.get("request", rid)
        if r:
            r["status"] = status
            self.db.put("request", rid, r)

    # ---- F2·F4 스캔 등록 ----
    def create_project_from_usdz(self, data: bytes, filename: str = "room.usdz", request_id: str | None = None,
                                 scanned_by: str = "technician") -> dict:
        from worker.runner import process_scan  # 지연 import: pxr 로딩 비용

        if request_id:
            self.get_request(request_id)
        if scanned_by not in ("technician", "customer"):
            raise Invalid("scanned_by는 technician 또는 customer")
        pid = self.db.next_id("p")
        d = self.pdir(pid)
        (d / "scan").mkdir(parents=True, exist_ok=True)
        ext = Path(filename).suffix.lower() or ".usdz"
        if ext not in (".usdz", ".usda", ".usdc", ".usd"):
            raise Invalid("USDZ(USD) 파일만 업로드할 수 있습니다")
        usdz = d / "scan" / f"room{ext}"
        usdz.write_bytes(data)
        try:
            process_scan(usdz, d / "scan")
        except Exception as e:  # 변환 실패 이유를 화면에 그대로 보여 준다
            raise Invalid(f"스캔 변환 실패: {e}") from e
        proj = {
            "project_id": pid, "request_id": request_id, "created_at": now(), "status": "scanned",
            "scan": {"source": "ugscan_roomplan_usdz", "usdz": str(usdz.relative_to(self.root)),
                     "room_json": str((d / "scan" / "room.json").relative_to(self.root)), "scanned_by": scanned_by},
            "scene": {"glb": None, "png": None, "engine": None},
            "scene_state": {"materials": {}, "finish": None, "placements": []},
            "style": {"prompt": None, "reference_image": None, "palette": [], "materials": []},
            "share_token": secrets.token_urlsafe(8), "version": 0,
        }
        self.db.put("project", pid, proj)
        self._set_request_status(request_id, "scanned")
        self._rebuild(pid)
        return self.get_project(pid)

    def list_projects(self) -> list[dict]:
        return self.db.list("project")

    def get_project(self, pid: str) -> dict:
        p = self.db.get("project", pid)
        if p is None:
            raise NotFound(f"프로젝트 없음: {pid}")
        p["customer_url"] = f"{config.public_base_url()}/#/c/{pid}?t={p['share_token']}"
        p["technician_url"] = f"{config.public_base_url()}/#/t/{pid}"
        return p

    def _save_project(self, p: dict) -> dict:
        p = {k: v for k, v in p.items() if k not in ("customer_url", "technician_url")}
        p["version"] = int(p.get("version", 0)) + 1
        p["updated_at"] = now()
        self.db.put("project", p["project_id"], p)
        return p

    # ---- room ----
    def get_room(self, pid: str) -> Room:
        p = self.get_project(pid)
        return Room.model_validate_json((self.root / p["scan"]["room_json"]).read_text(encoding="utf-8"))

    def _save_room(self, pid: str, room: Room) -> None:
        p = self.get_project(pid)
        (self.root / p["scan"]["room_json"]).write_text(room.model_dump_json(indent=2), encoding="utf-8")

    # ---- F3 실측 보정 ----
    def set_measurement(self, pid: str, wall_id: str, length_m: float | None = None, height_m: float | None = None,
                        depth_m: float | None = None, by: str = "technician") -> dict:
        p = self.get_project(pid)
        if by not in ("technician", "customer"):
            raise Invalid("by는 technician 또는 customer")
        for name, v in (("length_m", length_m), ("height_m", height_m), ("depth_m", depth_m)):
            if v is not None and not (0.05 <= v <= 30):
                raise Invalid(f"{name} 값이 범위를 벗어남: {v}")
        room = self.get_room(pid)
        try:
            w = room.wall(wall_id)
        except KeyError:
            raise NotFound(f"벽 없음: {wall_id}")
        old = w.measured or MeasuredDims()
        w.measured = MeasuredDims(
            length_m=length_m if length_m is not None else old.length_m,
            height_m=height_m if height_m is not None else old.height_m,
            depth_m=depth_m if depth_m is not None else old.depth_m,
            by=by, at=now(),
        )
        self._save_room(pid, room)
        self._save_project(p)
        return w.model_dump()

    # ---- 도면 (선택) ----
    FLOORPLAN_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                       ".webp": "image/webp", ".pdf": "application/pdf"}

    def set_floorplan(self, pid: str, data: bytes, filename: str) -> dict:
        """고객이 가진 도면(이미지·PDF)을 참고 자료로 붙인다. 판정에는 쓰지 않는다."""
        p = self.get_project(pid)
        ext = Path(filename).suffix.lower()
        if ext not in self.FLOORPLAN_TYPES:
            raise Invalid("도면은 PNG·JPG·WEBP·PDF만 올릴 수 있습니다")
        if not data:
            raise Invalid("빈 파일")
        d = self.pdir(pid) / "plan"
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("floorplan.*"):
            old.unlink()
        path = d / f"floorplan{ext}"
        path.write_bytes(data)
        p["floorplan"] = {"file": str(path.relative_to(self.root)), "name": Path(filename).name,
                          "content_type": self.FLOORPLAN_TYPES[ext], "uploaded_at": now()}
        return self._save_project(p)

    def clear_floorplan(self, pid: str) -> dict:
        p = self.get_project(pid)
        fp = p.pop("floorplan", None)
        if fp:
            (self.root / fp["file"]).unlink(missing_ok=True)
        return self._save_project(p)

    def floorplan_path(self, pid: str) -> tuple[Path, str] | None:
        fp = self.get_project(pid).get("floorplan")
        if not fp:
            return None
        path = self.root / fp["file"]
        return (path, fp["content_type"]) if path.exists() else None

    def clear_measurement(self, pid: str, wall_id: str) -> dict:
        room = self.get_room(pid)
        w = room.wall(wall_id)
        w.measured = None
        self._save_room(pid, room)
        self._save_project(self.get_project(pid))
        return w.model_dump()

    # ---- F5 영역 ----
    def create_zone(self, pid: str, purpose: str, polygon_m: list, wall_ids: list[str] | None = None,
                    name: str | None = None) -> dict:
        self.get_project(pid)
        if len(polygon_m) < 3:
            raise Invalid("영역 다각형은 꼭짓점 3개 이상")
        room = self.get_room(pid)
        for wid in wall_ids or []:
            room.wall(wid)
        zid = self.db.next_id("z")
        z = Zone(zone_id=zid, purpose=purpose, polygon_m=[tuple(map(float, pt)) for pt in polygon_m],
                 wall_ids=wall_ids or [])
        body = {**z.model_dump(), "project_id": pid, "name": name or purpose}
        if not z.wall_ids:  # 자동 감지 결과를 보여 준다
            from recommender.fit import zone_walls
            body["auto_wall_ids"] = [w.wall_id for w in zone_walls(room, z, self.fit_cfg)]
        self.db.put("zone", zid, body, parent=pid)
        self._apply_project_style_to_new_zone(pid, zid)
        self._save_project(self.get_project(pid))
        return self.get_zone(pid, zid)

    def _apply_project_style_to_new_zone(self, pid: str, zid: str) -> None:
        st = self.get_project(pid)["style"]
        z = self.db.get("zone", zid)
        if st.get("palette") or st.get("materials"):
            if not (z["style_tags"]["palette"] or z["style_tags"]["materials"]):
                z["style_tags"] = {"palette": st["palette"], "materials": st["materials"]}
                self.db.put("zone", zid, z, parent=pid)

    def list_zones(self, pid: str) -> list[dict]:
        self.get_project(pid)
        return self.db.list("zone", parent=pid)

    def get_zone(self, pid: str, zid: str) -> dict:
        z = self.db.get("zone", zid)
        if z is None or z["project_id"] != pid:
            raise NotFound(f"영역 없음: {zid}")
        return z

    def update_zone(self, pid: str, zid: str, **fields) -> dict:
        z = self.get_zone(pid, zid)
        for k in ("purpose", "polygon_m", "wall_ids", "name"):
            if fields.get(k) is not None:
                z[k] = fields[k]
        Zone.model_validate({k: z[k] for k in Zone.model_fields if k in z})
        self.db.put("zone", zid, z, parent=pid)
        self._save_project(self.get_project(pid))
        return z

    def delete_zone(self, pid: str, zid: str) -> None:
        self.get_zone(pid, zid)
        self.db.delete("zone", zid)
        p = self.get_project(pid)
        p["scene_state"]["placements"] = [x for x in p["scene_state"]["placements"] if x.get("zone_id") != zid]
        self._save_project(p)
        self._rebuild(pid)

    def _zone_model(self, pid: str, zid: str) -> Zone:
        z = self.get_zone(pid, zid)
        return Zone.model_validate({k: z[k] for k in Zone.model_fields if k in z})

    # ---- F6 스타일 ----
    def set_style(self, pid: str, prompt: str | None = None, palette: list[str] | None = None,
                  materials: list[str] | None = None, zone_id: str | None = None,
                  reference_image: str | None = None) -> dict:
        """LLM이 프롬프트·이미지를 해석해 팔레트(hex)와 재질 키워드로 저장. zone_id가 없으면 프로젝트 전체."""
        for h in palette or []:
            if not HEX_RE.match(h):
                raise Invalid(f"팔레트 색은 #RRGGBB 형식: {h}")
        if palette is not None and not (0 < len(palette) <= 8):
            raise Invalid("팔레트는 1~8색")
        p = self.get_project(pid)
        tags = {"palette": [h.upper() for h in palette or []], "materials": [m.lower() for m in materials or []]}
        if zone_id:
            z = self.get_zone(pid, zone_id)
            z["style_tags"] = tags
            z["inherits_style"] = False
            if prompt:
                z["style_prompt"] = prompt
            self.db.put("zone", zone_id, z, parent=pid)
        else:
            p["style"] = {"prompt": prompt, "reference_image": reference_image, **tags}
            for z in self.list_zones(pid):  # 영역별 스타일이 없는 영역에 전파
                if z.get("inherits_style", True):
                    z["style_tags"] = tags
                    z["inherits_style"] = True
                    self.db.put("zone", z["zone_id"], z, parent=pid)
        p["status"] = "designed"
        self._save_project(p)
        self._set_request_status(p.get("request_id"), "designed")
        return {"project_style": self.get_project(pid)["style"], "zones": self.list_zones(pid)}

    # ---- F7 디자인 조작 ----
    def apply_material(self, pid: str, target: str, hex_color: str, finish: str | None = None,
                       wall_id: str | None = None) -> dict:
        if target not in MATERIAL_TARGETS:
            raise Invalid(f"target은 {MATERIAL_TARGETS} 중 하나")
        if not HEX_RE.match(hex_color):
            raise Invalid("색은 #RRGGBB 형식")
        if finish is not None and finish not in ("matte", "glossy", "satin"):
            raise Invalid("finish는 matte | glossy | satin")
        p = self.get_project(pid)
        st = p["scene_state"]
        if wall_id:
            self.get_room(pid).wall(wall_id)
            st.setdefault("wall_colors", {})[wall_id] = hex_color.upper()
        else:
            st["materials"][target] = hex_color.upper()
        if finish:
            st["finish"] = finish
        self._save_project(p)
        return self._rebuild(pid)

    def place_product(self, pid: str, zone_id: str, sku: str, color: str | None = None) -> dict:
        prod = self.catalog.get(sku)
        room, zone = self.get_room(pid), self._zone_model(pid, zone_id)
        fit = check_fit(room, zone, prod, self.fit_cfg)
        if fit.placement is None:
            raise Invalid(f"배치할 수 없습니다: {fit.verdict.label} ({', '.join(fit.notes) or '치수 부족'})")
        opt = None
        if color:
            opt = next((o for o in prod.cmf_options if o.color == color), None)
            if opt is None:
                raise Invalid(f"제품 색상 옵션에 없음: {color}")
        else:
            ranked = rank_cmf(prod, zone.style_tags, 1)
            opt = ranked[0].option if ranked else None
        p = self.get_project(pid)
        pl = [x for x in p["scene_state"]["placements"] if not (x["sku"] == sku and x.get("zone_id") == zone_id)]
        pl.append({"placement_id": self.db.next_id("pl"), "sku": sku, "zone_id": zone_id, **fit.placement,
                   "color": opt.color if opt else None, "hex": opt.hex_approx if opt else None,
                   "verdict": fit.verdict.value, "wall_id": fit.wall_id, "reasons": []})
        p["scene_state"]["placements"] = pl
        self._save_project(p)
        out = self._rebuild(pid)
        out["fit"] = fit.to_dict()
        return out

    # ---- 자유 배치 (plans/virtual-remodel.md S2~S4) ----
    def _color_option(self, prod: Product, color: str | None):
        if color is None:
            return prod.cmf_options[0] if prod.cmf_options else None
        opt = next((o for o in prod.cmf_options if o.color == color), None)
        if opt is None:
            raise Invalid(f"제품 색상 옵션에 없음: {color}")
        return opt

    def _hidden(self, p: dict) -> list[str]:
        return p["scene_state"].setdefault("hidden_objects", [])

    def _pose(self, room: Room, prod: Product, center_xz, yaw_rad: float, snap: bool) -> Pose:
        if len(center_xz) != 2:
            raise Invalid("center_xz는 [x, z]")
        pose = Pose((float(center_xz[0]), float(center_xz[1])), float(yaw_rad))
        return snap_to_wall(room, prod, pose, self.fit_cfg) if snap else pose

    def _judge(self, room: Room, p: dict, prod: Product, pose: Pose, exclude: str | None = None):
        others = [x for x in p["scene_state"]["placements"] if x.get("placement_id") != exclude and x.get("size_m")]
        return check_pose(room, prod, pose, self.fit_cfg, others=others, hidden=self._hidden(p))

    def _rejudge_all(self, room: Room, p: dict) -> None:
        """한 제품이 움직이거나 가구를 치우면 나머지 배치도 다시 판정한다 (자유 배치만)."""
        for x in p["scene_state"]["placements"]:
            if x.get("zone_id"):
                continue
            try:
                prod = self.catalog.get(x["sku"])
            except KeyError:
                continue
            r = self._judge(room, p, prod, Pose(tuple(x["center_xz"]), x["yaw_rad"], x.get("wall_id")), x["placement_id"])
            x["verdict"], x["reasons"] = r.verdict.value, r.reasons

    def pose_check(self, pid: str, sku: str, center_xz, yaw_rad: float = 0.0, snap: bool = True,
                   placement_id: str | None = None) -> dict:
        """저장하지 않고 판정만 (끌어서 옮기는 중 미리 보기)."""
        prod, room, p = self.catalog.get(sku), self.get_room(pid), self.get_project(pid)
        return self._judge(room, p, prod, self._pose(room, prod, center_xz, yaw_rad, snap), placement_id).to_dict()

    def place_at(self, pid: str, sku: str, center_xz, yaw_rad: float = 0.0, snap: bool = True,
                 color: str | None = None) -> dict:
        prod, room, p = self.catalog.get(sku), self.get_room(pid), self.get_project(pid)
        opt = self._color_option(prod, color)
        pose = self._pose(room, prod, center_xz, yaw_rad, snap)
        r = self._judge(room, p, prod, pose)
        if r.size_m is None:
            raise Invalid("제품 치수 정보가 없어 놓을 수 없습니다")
        x = {"placement_id": self.db.next_id("pl"), "sku": sku, "zone_id": None,
             "center_xz": list(pose.center_xz), "yaw_rad": pose.yaw_rad, "size_m": list(r.size_m),
             "wall_id": pose.wall_id, "color": opt.color if opt else None, "hex": opt.hex_approx if opt else None,
             "verdict": r.verdict.value, "reasons": r.reasons}
        p["scene_state"]["placements"].append(x)
        self._rejudge_all(room, p)
        self._save_project(p)
        out = self._rebuild(pid)
        out["placement"] = next(y for y in out["scene_state"]["placements"] if y["placement_id"] == x["placement_id"])
        return out

    def _find_placement(self, p: dict, placement_id: str) -> dict:
        x = next((y for y in p["scene_state"]["placements"] if y.get("placement_id") == placement_id), None)
        if x is None:
            raise NotFound(f"배치 없음: {placement_id}")
        return x

    def move_placement(self, pid: str, placement_id: str, center_xz=None, yaw_rad: float | None = None,
                       snap: bool = True, color: str | None = None) -> dict:
        room, p = self.get_room(pid), self.get_project(pid)
        x = self._find_placement(p, placement_id)
        prod = self.catalog.get(x["sku"])
        if color is not None:
            opt = self._color_option(prod, color)
            x["color"], x["hex"] = opt.color, opt.hex_approx
        if center_xz is not None or yaw_rad is not None:
            pose = self._pose(room, prod, center_xz if center_xz is not None else x["center_xz"],
                              yaw_rad if yaw_rad is not None else x["yaw_rad"], snap)
            x["center_xz"], x["yaw_rad"], x["wall_id"] = list(pose.center_xz), pose.yaw_rad, pose.wall_id
            x["zone_id"] = None  # 옮긴 순간부터 자유 배치
        self._rejudge_all(room, p)
        self._save_project(p)
        out = self._rebuild(pid)
        out["placement"] = self._find_placement(out_p := self.get_project(pid), placement_id)
        out["scene_state"] = out_p["scene_state"]
        return out

    def delete_placement(self, pid: str, placement_id: str) -> dict:
        room, p = self.get_room(pid), self.get_project(pid)
        self._find_placement(p, placement_id)
        p["scene_state"]["placements"] = [y for y in p["scene_state"]["placements"] if y.get("placement_id") != placement_id]
        self._rejudge_all(room, p)
        self._save_project(p)
        return self._rebuild(pid)

    def set_object_hidden(self, pid: str, object_id: str, hidden: bool = True) -> dict:
        room, p = self.get_room(pid), self.get_project(pid)
        if not any(o.object_id == object_id for o in room.objects):
            raise NotFound(f"가구 없음: {object_id}")
        hs = self._hidden(p)
        if hidden and object_id not in hs:
            hs.append(object_id)
        if not hidden and object_id in hs:
            hs.remove(object_id)
        self._rejudge_all(room, p)
        self._save_project(p)
        return self._rebuild(pid)

    # ---- 살아 보기: 집 위치·방향 (S6~S8) ----
    def set_site(self, pid: str, north_deg: float | None = None, region: str | None = None) -> dict:
        """north_deg: 평면도 위쪽에서 북쪽까지 시계 방향 각도. region: 시·도 (채광용 위도·경도)."""
        p = self.get_project(pid)
        site = dict(p.get("site") or {"region": "서울", **REGIONS["서울"]})
        if north_deg is not None:
            if not 0 <= north_deg < 360:
                raise Invalid("north_deg는 0 이상 360 미만")
            site["north_deg"] = float(north_deg)
        if region is not None:
            if region not in REGIONS:
                raise Invalid(f"지역은 {', '.join(REGIONS)} 중 하나")
            site.update(region=region, **REGIONS[region])
        p["site"] = site
        return self._save_project(p)

    def daylight(self, pid: str, day: str, time: str | None = None) -> dict:
        import math
        from datetime import date as _date, datetime as _dt

        from sim.daylight import KST, Site, daily_sun_hours, sun_patches
        from sim.solar import sun_position

        p = self.get_project(pid)
        site = p.get("site") or {}
        if site.get("north_deg") is None:
            raise Invalid("채광을 보려면 먼저 평면도에서 북쪽 방향을 지정하세요")
        try:
            d = _date.fromisoformat(day)
            hh, mm = (int(x) for x in (time or "12:00").split(":"))
            when = _dt(d.year, d.month, d.day, hh, mm, tzinfo=KST)
        except ValueError as e:
            raise Invalid(f"날짜·시간 형식 오류 (YYYY-MM-DD, HH:MM): {e}") from e
        th = math.radians(site["north_deg"])
        s = Site(lat=site["lat"], lon=site["lon"], north_rad=math.atan2(-math.cos(th), math.sin(th)))
        room = self.get_room(pid)
        pts = {x["placement_id"]: tuple(x["center_xz"]) for x in p["scene_state"]["placements"] if x.get("placement_id")}
        alt, az = sun_position(s.lat, s.lon, when)
        daily = daily_sun_hours(room, s, d, points=pts)
        return {"site": site, "date": d.isoformat(), "time": when.strftime("%H:%M"),
                "sun": {"altitude_deg": round(alt, 2), "azimuth_deg": round(az, 2)},
                "patches": [{**x, "polygon": [[round(a, 3), round(b, 3)] for a, b in x["polygon"]]} for x in sun_patches(room, s, when)],
                "daily": daily, "assumptions": daily.pop("assumptions") + [f"위치: {site['region']} (위도 {site['lat']}, 경도 {site['lon']})"]}

    def remove_product(self, pid: str, zone_id: str, sku: str) -> dict:
        p = self.get_project(pid)
        p["scene_state"]["placements"] = [x for x in p["scene_state"]["placements"]
                                          if not (x["sku"] == sku and x.get("zone_id") == zone_id)]
        self._save_project(p)
        return self._rebuild(pid)

    def render(self, pid: str) -> dict:
        return self._rebuild(pid, render=True)

    def _rebuild(self, pid: str, render: bool = False) -> dict:
        from worker.runner import build_scene

        p = self.get_project(pid)
        room = self.get_room(pid)
        hidden = set(p["scene_state"].get("hidden_objects") or [])
        if hidden:  # 치운 가구는 3D·렌더에서 뺀다
            room = room.model_copy(update={"objects": [o for o in room.objects if o.object_id not in hidden]})
        usdz = self.root / p["scan"]["usdz"]
        state = {**p["scene_state"], "title": f"{pid} · {p['style'].get('prompt') or ''}".strip(" ·")}
        res = build_scene(room, usdz, state, self.pdir(pid) / "scene", render=render)
        p = self.db.get("project", pid)
        p["scene"] = {"glb": str(res["glb"].relative_to(self.root)),
                      "png": str(res["png"].relative_to(self.root)) if res.get("png") else (p.get("scene") or {}).get("png"),
                      "engine": res["engine"], "built_at": now()}
        self._save_project(p)
        return {"project_id": pid, "scene": p["scene"], "scene_state": p["scene_state"],
                "png_path": str(self.root / p["scene"]["png"]) if p["scene"].get("png") else None}

    # ---- F8·F9 추천 ----
    def check_fit(self, pid: str, zone_id: str, sku: str) -> dict:
        return check_fit(self.get_room(pid), self._zone_model(pid, zone_id), self.catalog.get(sku), self.fit_cfg).to_dict()

    def recommend(self, pid: str, zone_id: str, category: str | None = None, include_no_fit: bool = True) -> dict:
        zone = self._zone_model(pid, zone_id)
        prods = self.catalog.search(category=category)
        items = recommend_zone(self.get_room(pid), zone, prods, self.fit_cfg, include_no_fit=include_no_fit)
        return {"zone": self.get_zone(pid, zone_id), "items": items,
                "margins_mm": {"scanned": self.fit_cfg.margin_scanned_mm, "measured": self.fit_cfg.margin_measured_mm}}

    def results(self, pid: str) -> dict:
        """F10 결과 화면 데이터 한 번에."""
        return {"project": self.get_project(pid), "room": self.get_room(pid).model_dump(),
                "zones": [{**z, "recommendation": self.recommend(pid, z["zone_id"])["items"]} for z in self.list_zones(pid)]}
