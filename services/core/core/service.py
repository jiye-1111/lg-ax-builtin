"""서비스 계층 — 웹 API와 MCP 도구가 똑같이 이 함수를 호출한다.

그래서 Claude·Codex에서 바꾼 상태가 웹 화면에 그대로 보인다 (기획 §6.2 "채팅과 웹 화면을 같은 프로젝트 상태로").
"""
from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import re
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from recommender.cmf import rank_cmf
from recommender.finishes import TEXTURE_KO, load_finishes, rank_finishes
from recommender.fit import FitConfig, check_fit
from recommender.install import install_checklist
from recommender.gaps import fill_width, measure as measure_gaps
from recommender.pose import SURFACE_MAX_M as PRODUCT_SURFACE_MAX_M, FLOOR_FIRST, HOOD_GAP_M, ISLAND_HOOD, MOUNT_SKUS, _clear, product_size, WALL_HOOD, floats, is_hood, WALL_LIKE, can_sit, needs_counter, settle_on, surface_under, Pose, check_pose, find_spot, snap_door, snap_to_wall, against_wall
from sim.regions import REGIONS
from recommender.mount import REACH_M as MOUNT_REACH_M, WALL, hang, mount_kind
from recommender.geometry import point_segment_distance
from recommender.slot import DOOR_BACK_M as SLOT_HOSTS, cover as slot_cover, slot_in, slotable
from recommender.finder import Conditions, find_products
from recommender import reference
from recommender.recommend import recommend_zone
from recommender.variants import families, shape_key

from . import config
from .ai_products import chat_message, interpret_products
from .ai_style import interpret_style
from .accounts import Accounts, Forbidden, is_approved_tech
from .decor import MAX_MM as MAX_DECOR_MM, TOP_COLOUR_SKUS, decor_product, is_decor, is_flat
from .models import MeasuredDims, Product, Room, Zone
from .service_addons import AddonMixin
from .service_combos import ComboMixin
from .service_life import LifeMixin
from .service_photoreal import PhotorealMixin
from .store import Store

KST = timezone(timedelta(hours=9))
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
MATERIAL_TARGETS = ("wall", "floor", "door", "window", "object")


HOME_NAME_MAX = 40


class NotFound(KeyError):
    pass


class Invalid(ValueError):
    pass


def now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


# ---------------- 카탈로그 ----------------
class Catalog:
    def __init__(self, paths: list[Path], lineup: Path | None = None):
        self.products: list[Product] = []
        for p in paths:
            if not p.exists():
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            items = data["products"] if isinstance(data, dict) else data
            self.products += [Product.model_validate(x) for x in items]
        # 내놓는 모델 목록이 있으면 거기 적힌 것만 목록·추천에 나온다. 나머지는 전에 놓아 둔 집을 열 수 있게 남겨만 둔다
        if lineup and lineup.exists():
            models = json.loads(lineup.read_text(encoding="utf-8"))["models"]
            for p in self.products:
                m = models.get(p.sku)
                p.listed = p.demo_only or m is not None
                if m:
                    p.lineup_family, p.lineup_note = m.get("family_id"), m.get("note")

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

    def families(self) -> list[dict]:
        """같은 모델(종류·치수·도면 모양이 같음)의 색·재질 다른 SKU를 묶는다."""
        if not hasattr(self, "_families"):
            shapes = {}
            for p in self.products:
                f = config.ROOT / "data" / "drawings" / f"{p.sku}.json"
                shapes[p.sku] = shape_key(json.loads(f.read_text(encoding="utf-8"))) if f.exists() else None
                if p.lineup_family:  # 전달받은 묶음은 그쪽 제품군대로 묶는다 (치수가 같아도 모양이 다른 모델이 있다)
                    shapes[p.sku] = "lineup:" + p.lineup_family
            self._families = families([p.model_dump() for p in self.products], shapes)
            # 제품 사진: 우리 3D 모델을 Blender로 렌더한 것 (웹 기준 상대 경로, 없으면 None)
            photos = config.ROOT / "apps" / "web" / "img" / "products"
            for f in self._families:
                for v in f["variants"]:
                    v["tabletop"] = can_sit(self.get(v["sku"]))  # 식탁·아일랜드 위에 올려 둘 수 있는 가전
                    v["slot"] = slotable(self.get(v["sku"]))  # 하부장·키큰장 칸에 끼워 넣는 빌트인
                    v["mount"] = mount_kind(self.get(v["sku"]))  # 벽에 걸거나(wall) 붙여(flush·builtin) 설치하는 제품
                    v["thumb"] = f"img/products/{v['sku']}.webp" if (photos / f"{v['sku']}.webp").exists() else None
        return self._families

    def family_of(self, sku: str) -> dict:
        self.get(sku)
        return next(f for f in self.families() if any(v["sku"] == sku for v in f["variants"]))


# ---------------- 서비스 ----------------
class Service(ComboMixin, PhotorealMixin, LifeMixin, AddonMixin):
    def __init__(self, storage: Path | None = None, catalog: Catalog | None = None, fit_cfg: FitConfig | None = None,
                 stylist=None, product_reader=None):
        self.root = Path(storage or config.storage_dir())
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = Store(self.root / "app.sqlite3")
        self.catalog = catalog or Catalog(config.catalog_paths(), config.catalog_lineup())
        self.fit_cfg = fit_cfg or FitConfig.from_env()
        self.finishes = load_finishes(config.ROOT / "data" / "finishes" / "finishes.json")
        self.stylist = stylist or interpret_style  # (prompt, catalog_brief) -> StyleIntent
        self.product_reader = product_reader or interpret_products  # (prompt) -> ProductIntent
        self.accounts = Accounts(self.db)

    # ---- 경로 ----
    def pdir(self, pid: str) -> Path:
        return self.root / "projects" / pid

    # ---- F1 상담 요청 (목업) ----
    def create_request(self, name: str, contact: str, address: str, preferred_at: str | None) -> dict:
        rid = self.db.next_id("r")
        req = {"request_id": rid, "customer": {"name": name, "contact": contact}, "address": address,
               "preferred_at": preferred_at, "status": "requested", "created_at": now()}
        return self.db.put("request", rid, req)

    def create_install_request(self, pid: str, name: str, contact: str, address: str, preferred_at: str | None) -> dict:
        """놓아 본 제품 그대로 방문 설치 상담을 신청한다. 기사가 미리 볼 수 있게 제품과 설치 전 확인 결과를 같이 남긴다."""
        p, check = self.get_project(pid), self.install_check(pid)
        if not check["items"]:
            raise Invalid("놓은 제품이 없어요. 제품을 먼저 놓아 주세요")
        products = []
        for it in check["items"]:
            prod = self.catalog.get(it["sku"])
            products.append({"placement_id": it["placement_id"], "sku": it["sku"], "name": it["name"], "status": it["status"],
                             "open": [c["label"] for c in it["checks"] if c["status"] in ("check", "blocked")],
                             "source_url": prod.source_url})
        rid = self.db.next_id("r")
        req = {"request_id": rid, "kind": "install", "project_id": pid, "customer": {"name": name, "contact": contact},
               "address": address, "preferred_at": preferred_at, "status": "requested", "created_at": now(),
               "products": products, "summary": check["summary"]}
        self.db.put("request", rid, req)
        p["install_request_id"] = rid
        self._save_project(p)
        return req

    def before_glb(self, pid: str) -> Path:
        """스캔한 그대로의 집(가구 그대로, 마감·제품 없음). 지금 모습과 견줘 보는 용도라 한 번 만들어 두고 쓴다."""
        from worker.glb import room_to_glb

        self.get_project(pid)
        out, src = self.pdir(pid) / "scene" / "before.glb", self.pdir(pid) / "scan" / "room.json"
        if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
            out.parent.mkdir(parents=True, exist_ok=True)
            room_to_glb(self._load_room(pid), out, {"materials": {}, "finish": None, "placements": []})
        return out

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
                                 scanned_by: str = "technician", user: dict | None = None,
                                 name: str | None = None) -> dict:
        from worker.runner import process_scan  # 지연 import: pxr 로딩 비용

        if request_id:
            self.get_request(request_id)
        if scanned_by not in ("technician", "customer"):
            raise Invalid("scanned_by는 technician 또는 customer")
        name = (name or "").strip()
        if len(name) > HOME_NAME_MAX:
            raise Invalid(f"집 이름은 {HOME_NAME_MAX}자까지 쓸 수 있어요")
        name = name or Path(filename).stem.strip()[:HOME_NAME_MAX] or None  # 이름을 안 주면 올린 파일 이름
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
        scan = {"source": "ugscan_roomplan_usdz", "usdz": str(usdz.relative_to(self.root)),
                "room_json": str((d / "scan" / "room.json").relative_to(self.root)), "scanned_by": scanned_by}
        self.db.put("project", pid, self._new_project(pid, name, scan, user, request_id))
        self._set_request_status(request_id, "scanned")
        self._rebuild(pid)
        return self.get_project(pid)

    def _new_project(self, pid: str, name: str | None, scan: dict, user: dict | None, request_id: str | None = None) -> dict:
        return {
            "project_id": pid, "name": name, "request_id": request_id, "created_at": now(), "status": "scanned",
            "scan": scan,
            "scene": {"glb": None, "png": None, "engine": None},
            "scene_state": {"materials": {}, "finish": None, "placements": []},
            "style": {"prompt": None, "reference_image": None, "palette": [], "materials": []},
            "share_token": secrets.token_urlsafe(8), "version": 0,
            # 로그인한 채로 올리면 고객은 주인, 기사는 담당 기사가 된다
            "owner_id": user["user_id"] if user and user["role"] == "customer" else None,
            "technician_id": user["user_id"] if is_approved_tech(user) and user["role"] == "technician" else None,
        }

    def create_project_from_plan(self, data: bytes, filename: str, user: dict | None = None,
                                 name: str | None = None, reader=None) -> dict:
        """스캔 없이 도면(이미지·PDF)만으로 집을 만든다. 도면에서 벽·문·창을 읽어 room.json을 쓴다.

        가구는 없다(도면의 가구 그림은 읽지 않는다). 천장 높이는 도면에 없어서 2.4 m로 둔다.
        """
        from worker.plan_room import room_from_plan

        from .plan_read import PlanReadError, read_plan

        ext = Path(filename).suffix.lower()
        if ext not in self.FLOORPLAN_TYPES:
            raise Invalid("도면은 PNG·JPG·WEBP·PDF만 올릴 수 있습니다")
        if not data:
            raise Invalid("빈 파일")
        name = (name or "").strip()
        if len(name) > HOME_NAME_MAX:
            raise Invalid(f"집 이름은 {HOME_NAME_MAX}자까지 쓸 수 있어요")
        name = name or Path(filename).stem.strip()[:HOME_NAME_MAX] or None
        try:
            plan = (reader or self.plan_reader or read_plan)(data, self.FLOORPLAN_TYPES[ext], Path(filename).name)
            room = room_from_plan(plan)
        except (PlanReadError, ValueError) as e:
            raise Invalid(str(e)) from e
        pid = self.db.next_id("p")
        d = self.pdir(pid)
        (d / "scan").mkdir(parents=True, exist_ok=True)
        (d / "scan" / "room.json").write_text(room.model_dump_json(indent=1), encoding="utf-8")
        # scale_from: dimensions(도면 치수) | door_width(치수가 없어 방문 폭 90 cm로 어림)
        scan = {"source": "floorplan_image", "usdz": None, "scale_from": plan.scale_from,
                "room_json": str((d / "scan" / "room.json").relative_to(self.root)), "scanned_by": "customer"}
        self.db.put("project", pid, self._new_project(pid, name, scan, user))
        self.set_floorplan(pid, data, filename)  # 읽은 도면은 그대로 붙여 둔다 (도면·실측 창에서 다시 볼 수 있게)
        self._rebuild(pid)
        return self.get_project(pid)

    def list_projects(self) -> list[dict]:
        return self.db.list("project")

    def visible_projects(self, user: dict | None) -> list[dict]:
        """웹 목록용. 기사·관리자는 전부, 고객은 내 집만, 로그인 안 했으면 아무것도 안 보인다."""
        if is_approved_tech(user):
            return self.list_projects()
        return self.my_projects(user) if user else []

    def delete_project(self, pid: str, user: dict | None, share_token: str | None = None) -> None:
        """집 지우기. 주인 있는 집은 주인·관리자만, 주인 없는 집은 고객 링크를 가진 사람만."""
        p = self.get_project(pid)
        if p.get("owner_id"):
            if not user or not (user["role"] == "admin" or user["user_id"] == p["owner_id"]):
                raise Forbidden("이 집을 지울 권한이 없습니다")
        elif not (user and user["role"] == "admin") and not secrets.compare_digest(str(share_token or ""), str(p["share_token"])):
            raise Forbidden("이 집의 고객 링크가 아닙니다")
        for kind, key in (("save", "save_id"), ("zone", "zone_id")):
            for x in self.db.list(kind, parent=pid):
                self.db.delete(kind, x[key])
        self.db.delete("project", pid)
        shutil.rmtree(self.pdir(pid), ignore_errors=True)

    # ---- 내 집 · 저장 ----
    def my_projects(self, user: dict) -> list[dict]:
        uid = user["user_id"]
        return [p for p in self.db.list("project") if uid in (p.get("owner_id"), p.get("technician_id"))]

    def claim_project(self, pid: str, user: dict, share_token: str) -> dict:
        """로그인 전에 꾸미던 집을 내 계정으로 가져온다. 고객 링크의 토큰이 있어야 한다."""
        p = self.get_project(pid)
        if not secrets.compare_digest(str(share_token), str(p["share_token"])):
            raise Forbidden("이 집의 고객 링크가 아닙니다")
        if p.get("owner_id") == user["user_id"]:
            return p
        if p.get("owner_id"):
            raise Forbidden("이미 다른 계정에 저장된 집입니다")
        if user["role"] != "customer":
            raise Forbidden("집을 내 계정으로 가져오는 건 고객 계정만 됩니다")
        p["owner_id"] = user["user_id"]
        self._save_project(p)
        return self.get_project(pid)

    def _can_save(self, p: dict, user: dict) -> None:
        if user["role"] == "admin" or user["user_id"] in (p.get("owner_id"), p.get("technician_id")):
            return
        raise Forbidden("이 집을 저장할 권한이 없습니다. 내 계정으로 가져온 집만 저장돼요")

    # 저장본에 넣지 않는 것: 스캔 원본·3D 파일 경로·주인 정보처럼 되돌리면 안 되는 값
    _KEEP = ("project_id", "request_id", "created_at", "status", "scan", "scene", "share_token", "version",
             "updated_at", "owner_id", "technician_id", "floorplan", "customer_url", "technician_url", "install_request_id")

    def save_snapshot(self, pid: str, user: dict, kind: str = "manual", label: str | None = None) -> dict:
        if kind not in ("manual", "auto"):
            raise Invalid("kind는 manual 또는 auto")
        p = self.get_project(pid)
        self._can_save(p, user)
        room = self._load_room(pid)
        state = {"project": {k: v for k, v in p.items() if k not in self._KEEP},
                 "zones": self.list_zones(pid),
                 "measured": {w.wall_id: (w.measured.model_dump() if w.measured else None) for w in room.walls}}
        if kind == "auto":  # 자동 저장은 사람마다 한 칸을 계속 덮어쓴다
            sid = f"{pid}.auto.{user['user_id']}"
        else:
            manual = [x for x in self.db.list("save", parent=pid) if x["kind"] == "manual"]
            if len(manual) >= 30:
                raise Invalid("저장본은 집마다 30개까지예요. 안 쓰는 저장본을 지워 주세요")
            sid = self.db.next_id("s")
        body = {"save_id": sid, "project_id": pid, "kind": kind,
                "label": (label or "").strip()[:60] or ("자동 저장" if kind == "auto" else f"저장 {self.db.next_id('sv.' + pid).split('_')[-1].lstrip('0')}"),
                "by": user["user_id"], "by_name": user["name"], "saved_at": now(), "project_version": p["version"],
                "placements": len(p["scene_state"].get("placements") or []), "zones": len(state["zones"]),
                "state": state}
        self.db.put("save", sid, body, parent=pid)
        return {k: v for k, v in body.items() if k != "state"}

    def list_saves(self, pid: str, user: dict) -> list[dict]:
        self._can_save(self.get_project(pid), user)
        out = [{k: v for k, v in x.items() if k != "state"} for x in self.db.list("save", parent=pid)]
        return sorted(out, key=lambda x: x["saved_at"], reverse=True)

    def _get_save(self, pid: str, sid: str) -> dict:
        s = self.db.get("save", sid)
        if not s or s["project_id"] != pid:
            raise NotFound(f"저장본 없음: {sid}")
        return s

    def delete_save(self, pid: str, sid: str, user: dict) -> None:
        self._can_save(self.get_project(pid), user)
        self._get_save(pid, sid)
        self.db.delete("save", sid)

    def restore_save(self, pid: str, sid: str, user: dict) -> dict:
        p = self.get_project(pid)
        self._can_save(p, user)
        st = self._get_save(pid, sid)["state"]
        # 프로젝트 상태
        p = {k: v for k, v in p.items() if k in self._KEEP}
        p.update(st["project"])
        self._save_project(p)
        # 영역
        for z in self.db.list("zone", parent=pid):
            self.db.delete("zone", z["zone_id"])
        for z in st["zones"]:
            self.db.put("zone", z["zone_id"], z, parent=pid)
        # 벽 실측값
        room = self._load_room(pid)
        for w in room.walls:
            m = st["measured"].get(w.wall_id)
            w.measured = MeasuredDims.model_validate(m) if m else None
        self._save_room(pid, room)
        self._rebuild(pid)
        return self.get_project(pid)

    def get_project(self, pid: str) -> dict:
        p = self.db.get("project", pid)
        if p is None:
            raise NotFound(f"프로젝트 없음: {pid}")
        p["customer_url"] = f"{config.public_base_url()}/#/c/{pid}?t={p['share_token']}"
        p["technician_url"] = f"{config.public_base_url()}/#/t/{pid}"
        return p

    def _save_project(self, p: dict) -> dict:
        p = {k: v for k, v in p.items() if k not in ("customer_url", "technician_url")}
        rt = (p.get("scene_state") or {}).get("router")
        if rt and p.get("scan"):  # 책상을 치우거나 옮기면 그 위 공유기도 같이 내려온다
            rt["height_m"] = self._surface_top(p, tuple(rt["center_xz"]))
        p["version"] = int(p.get("version", 0)) + 1
        p["updated_at"] = now()
        self.db.put("project", p["project_id"], p)
        return p

    # ---- room ----
    def _load_room(self, pid: str) -> Room:
        """스캔 그대로(+실측). 저장할 때는 이걸 고쳐서 저장한다 (가구 옮긴 자리가 스캔에 섞이지 않게)."""
        from worker.tidy import tidy_openings

        p = self.get_project(pid)
        path = self.root / p["scan"]["room_json"]
        room = Room.model_validate_json(path.read_text(encoding="utf-8"))
        fixed = tidy_openings(room)
        if fixed is not room:
            # 예전에 만든 집: 벽이 가로지르는 문, 겹친 문을 바로잡아 다시 써 두고 3D도 새로 만든다
            path.write_text(fixed.model_dump_json(indent=2), encoding="utf-8")
            if p.get("scene"):
                self._rebuild(pid)
        return fixed

    def get_room(self, pid: str) -> Room:
        """지금 집 모습: 스캔 + 옮긴 가구 자리(scene_state.object_poses)."""
        room, poses = self._load_room(pid), self.get_project(pid)["scene_state"].get("object_poses") or {}
        if not poses:
            return room
        objs = []
        for o in room.objects:
            q = poses.get(o.object_id)
            if q:
                o = o.model_copy(update={"position": (q["center_xz"][0], o.position[1], q["center_xz"][1]),
                                         "yaw_rad": q["yaw_rad"]})
            objs.append(o)
        return room.model_copy(update={"objects": objs})

    def _save_room(self, pid: str, room: Room) -> None:
        p = self.get_project(pid)
        (self.root / p["scan"]["room_json"]).write_text(room.model_dump_json(indent=2), encoding="utf-8")

    # ---- F3 실측 보정 ----
    @staticmethod
    def _reestimate(room: Room) -> None:
        """잰 벽을 기준으로 나머지 벽 길이를 다시 바로잡는다 (recommender.reference). 잰 벽이 없으면 바로잡은 값을 지운다.

        도면으로 만든 집은 그림에서 읽은 길이라 집 전체 배율이 크게 틀릴 수 있어서 도면용 기준을 쓴다.
        """
        est = reference.estimate(room.walls, plan=room.source == "floorplan_image")
        for w in room.walls:
            m = w.measured
            if m is not None and m.length_m is not None and m.by != reference.ESTIMATED_BY:
                continue
            length = est.lengths.get(w.wall_id)
            old = m or MeasuredDims()
            if length is not None:
                w.measured = MeasuredDims(length_m=length, height_m=old.height_m, depth_m=old.depth_m,
                                          by=reference.ESTIMATED_BY, at=now())
            elif m is not None and m.by == reference.ESTIMATED_BY:
                rest = m.model_copy(update={"length_m": None, "by": None, "at": None})
                w.measured = rest if (rest.height_m is not None or rest.depth_m is not None) else None

    def set_measurement(self, pid: str, wall_id: str, length_m: float | None = None, height_m: float | None = None,
                        depth_m: float | None = None, by: str = "technician") -> dict:
        p = self.get_project(pid)
        if by not in ("technician", "customer"):
            raise Invalid("by는 technician 또는 customer")
        for name, v in (("length_m", length_m), ("height_m", height_m), ("depth_m", depth_m)):
            if v is not None and not (0.05 <= v <= 30):
                raise Invalid(f"{name} 값이 범위를 벗어남: {v}")
        room = self._load_room(pid)
        try:
            w = room.wall(wall_id)
        except KeyError:
            raise NotFound(f"벽 없음: {wall_id}")
        old = w.measured or MeasuredDims()
        if length_m is not None:
            scan = w.scanned.length_m
            plan = room.source == "floorplan_image"
            if abs(length_m - scan) > reference.off_limit(scan, plan=plan):
                raise Invalid(f"{'도면에서 읽은' if plan else '스캔한'} 길이와 너무 달라요. 고른 벽과 넣은 값을 다시 확인해 주세요")
        elif old.by in ("floorplan", reference.ESTIMATED_BY):
            # 높이·깊이만 잰 벽: 길이는 여전히 도면·기준 벽에서 온 값이다
            w.measured = old.model_copy(update={"height_m": height_m if height_m is not None else old.height_m,
                                                "depth_m": depth_m if depth_m is not None else old.depth_m})
            self._save_room(pid, room)
            self._save_project(p)
            return w.model_dump()
        w.measured = MeasuredDims(
            length_m=length_m if length_m is not None else old.length_m,
            height_m=height_m if height_m is not None else old.height_m,
            depth_m=depth_m if depth_m is not None else old.depth_m,
            by=by, at=now(),
        )
        self._reestimate(room)
        self._save_room(pid, room)
        self._save_project(p)
        return w.model_dump()

    # ---- 도면 (선택) ----
    plan_reader = None  # 도면 읽는 함수를 바꿔 끼울 때 (테스트). 없으면 core.plan_read.read_plan
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

    def apply_floorplan(self, pid: str, reader=None) -> dict:
        """스캔으로 만든 집에 붙인 도면을 읽어, 길이가 맞는 벽을 도면 치수로 보정한다.

        줄자로 잰 값(기사·고객 실측)이 있는 벽은 건드리지 않는다. 도면을 못 읽어도 첨부는 그대로 두고 이유만 적는다.
        """
        from worker.plan_room import corrections, room_from_plan

        from .plan_read import PlanReadError, read_plan

        p = self.get_project(pid)
        fp = p.get("floorplan")
        if not fp or p["scan"].get("source") == "floorplan_image":
            return p
        try:
            plan = room_from_plan((reader or self.plan_reader or read_plan)((self.root / fp["file"]).read_bytes(), fp["content_type"], fp["name"]))
        except (PlanReadError, ValueError) as e:
            p["floorplan"] = {**fp, "applied": None, "note": str(e)}
            return self._save_project(p)
        room = self._load_room(pid)
        fixed = []
        for wall_id, length in corrections(room, plan).items():
            w = room.wall(wall_id)
            if w.measured and w.measured.length_m is not None and w.measured.by not in ("floorplan", reference.ESTIMATED_BY):
                continue
            old = w.measured or MeasuredDims()
            w.measured = MeasuredDims(length_m=length, height_m=old.height_m, depth_m=old.depth_m, by="floorplan", at=now())
            fixed.append(wall_id)
        self._reestimate(room)
        self._save_room(pid, room)
        p["floorplan"] = {**fp, "applied": {"walls": fixed, "at": now()}, "note": None}
        return self._save_project(p)

    def clear_floorplan(self, pid: str) -> dict:
        p = self.get_project(pid)
        fp = p.pop("floorplan", None)
        if fp:
            (self.root / fp["file"]).unlink(missing_ok=True)
            if fp.get("applied"):  # 도면으로 맞춘 길이도 같이 되돌린다
                room = self._load_room(pid)
                for w in room.walls:
                    if w.measured and w.measured.by == "floorplan":
                        rest = w.measured.model_copy(update={"length_m": None, "by": None, "at": None})
                        w.measured = rest if (rest.height_m is not None or rest.depth_m is not None) else None
                self._reestimate(room)
                self._save_room(pid, room)
        return self._save_project(p)

    def floorplan_path(self, pid: str) -> tuple[Path, str] | None:
        fp = self.get_project(pid).get("floorplan")
        if not fp:
            return None
        path = self.root / fp["file"]
        return (path, fp["content_type"]) if path.exists() else None

    def clear_measurement(self, pid: str, wall_id: str) -> dict:
        room = self._load_room(pid)
        w = room.wall(wall_id)
        w.measured = None
        self._reestimate(room)
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

    # ---- 벽지·바닥재 (data/finishes) ----
    def get_finish(self, finish_id: str):
        for f in self.finishes:
            if f.id == finish_id:
                return f
        raise NotFound(f"마감재 없음: {finish_id}")

    def apply_finish(self, pid: str, finish_id: str, tone: str | None = None) -> dict:
        """실제 벽지·바닥재를 벽 전체 또는 바닥에 적용. 3D 색은 그 톤(근사색), 질감은 웹이 finish_ids로 그린다."""
        f = self.get_finish(finish_id)
        try:
            t = f.tone(tone)
        except ValueError as e:
            raise Invalid(str(e)) from None
        p = self.get_project(pid)
        st = p["scene_state"]
        st.setdefault("finish_ids", {})[f.kind] = {"id": f.id, "tone": t.hex}
        st["materials"][f.kind] = t.hex
        if f.kind == "wall":
            st.pop("wall_colors", None)  # 벽마다 칠한 색보다 벽지가 우선
        self._save_project(p)
        return self._rebuild(pid)

    def finishes_brief(self) -> str:
        return "\n".join(f"- [{'벽' if f.kind == 'wall' else '바닥'}] {f.brand} {f.name} ({TEXTURE_KO[f.texture]}): {f.trend or ''}"
                         for f in self.finishes)

    def ai_style(self, pid: str, prompt: str, zone_id: str | None = None, apply_finishes: bool = True) -> dict:
        """고객의 말 → 스타일 저장 → 코드가 벽지·바닥재 순위 계산 → (선택) 1순위 적용. 가전 색 추천도 이 스타일을 따른다.

        제품 조건(종류·용량·색·가격·놓을 자리)을 말하면 카탈로그에서 맞는 제품도 찾아 products에 담는다.
        제품만 물었으면 벽지·바닥재와 저장된 스타일은 건드리지 않는다."""
        prompt = (prompt or "").strip()
        if not prompt:
            raise Invalid("원하는 분위기를 적어 주세요")
        if len(prompt) > 500:
            raise Invalid("500자 안으로 적어 주세요")
        self.get_project(pid)
        with ThreadPoolExecutor(max_workers=2) as pool:   # 두 해석을 같이 보내 기다리는 시간을 줄인다
            want_f = pool.submit(self.product_reader, prompt)
            style_f = pool.submit(self.stylist, prompt, catalog_brief=self.finishes_brief())
            want, intent = want_f.result(), style_f.result()
        products = self._chat_products(pid, zone_id, want) if want.wants_products else None
        if products and not want.also_style:
            st = self.get_project(pid)["style"]
            return {"engine": want.engine, "summary": products["message"], "style": st,
                    "intent": {"wall_texture": None, "floor_texture": None},
                    "finishes": {"wall": [], "floor": []}, "applied": {}, "products": products}
        style = self.set_style(pid, prompt, intent.palette, intent.materials, zone_id)
        ranked = {k: rank_finishes(self.finishes, k, intent.palette, intent.materials,
                                   intent.wall_texture if k == "wall" else intent.floor_texture, top_k=3)
                  for k in ("wall", "floor")}
        applied = {}
        if apply_finishes:
            for k, r in ranked.items():
                if r and r[0].score > 0:
                    self.apply_finish(pid, r[0].finish.id, r[0].tone.hex)
                    applied[k] = r[0].to_dict()
        summary = f"{intent.summary} {products['message']}" if products else intent.summary
        p = self.get_project(pid)
        p["style"]["summary"] = intent.summary
        p["style"]["engine"] = intent.engine
        self._save_project(p)
        return {"engine": intent.engine, "summary": summary,
                "style": {**style["project_style"], "summary": intent.summary, "engine": intent.engine},
                "intent": {"wall_texture": intent.wall_texture, "floor_texture": intent.floor_texture},
                "finishes": {k: [m.to_dict() for m in r] for k, r in ranked.items()}, "applied": applied,
                "products": products}

    CHAT_PRODUCTS = 5

    def _chat_products(self, pid: str, zone_id: str | None, want) -> dict:
        """대화에서 읽은 조건으로 찾기. 놓을 자리 치수를 말했으면 거기 들어가는 것만 고른다."""
        conds = want.conditions()
        typed = any(k in conds for k in ("space_w", "space_h", "space_d"))
        res = self.find(Conditions(**conds, fits_only=typed, sort=want.sort, limit=self.CHAT_PRODUCTS), pid, zone_id)
        return {"engine": want.engine, "conditions": conds, "sort": want.sort, "items": res["items"], "total": res["total"],
                "zone_id": res["zone_id"], "message": chat_message(conds, res["total"], len(res["items"]), want.sort)}

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

    @staticmethod
    def _standing(room: Room, p: dict) -> Room:
        """철거한 벽(과 그 벽의 문·창)을 뺀 방. 동선·와이파이처럼 벽이 막는 계산에 쓴다."""
        gone = set(p["scene_state"].get("hidden_walls") or [])
        shut = set(p["scene_state"].get("hidden_openings") or [])  # 없앤 창
        if not gone and not shut:
            return room
        return room.model_copy(update={"walls": [w for w in room.walls if w.wall_id not in gone],
                                       "openings": [o for o in room.openings if o.wall_id not in gone and o.opening_id not in shut]})

    def _blocked_off(self, p: dict) -> list[str]:
        """판정에서 빼는 것: 치운 가구 + 철거한 벽."""
        return self._hidden(p) + list(p["scene_state"].get("hidden_walls") or [])

    def _item(self, sku: str, size_m=None) -> Product:
        """LG 제품은 카탈로그에서, 공간 꾸미기 가구(decor:)는 배치 크기로 판정용 Product를 만든다."""
        if is_decor(sku):
            try:
                return decor_product(sku, size_m)
            except KeyError:
                raise NotFound(f"없는 가구: {sku}") from None
            except ValueError as e:
                raise Invalid(str(e)) from None
        return self.catalog.get(sku)

    def _others(self, p: dict, exclude: str | None = None) -> list[dict]:
        """겹침을 보는 다른 배치. 러그 같은 바닥 깔개는 위에 놓아도 되니 뺀다."""
        return [x for x in p["scene_state"]["placements"]
                if x.get("placement_id") != exclude and x.get("size_m") and not is_flat(x.get("sku"))]

    def _gap_others(self, p: dict, exclude: str | None = None) -> list[dict]:
        """틈을 잴 때 보는 다른 배치. 옆 가전이 요구하는 옆 여유(side_mm, LGE.COM 값)를 같이 넘긴다."""
        out = []
        for x in self._others(p, exclude):
            side = None
            if not is_decor(x.get("sku")):
                try:
                    side = self.catalog.get(x["sku"]).clearance_mm.side
                except KeyError:
                    side = None
            out.append({**x, "side_mm": side or 0})
        return out

    def _gaps(self, room: Room, p: dict, prod: Product, pose: Pose, exclude: str | None, base: float) -> dict:
        if is_flat(prod.sku):
            return {}
        others = self._gap_others(p, exclude)
        if self._undersink(prod.sku):  # 하부장 안에 들어간 정수기: 그 하부장은 옆 틈이 아니다
            others = [x for x in others if x.get("sku") not in self.CABINETS]
        elif prod.sku in self.CABINETS:
            others = [x for x in others if not self._inset(x.get("sku"))]
        return measure_gaps(room, prod, pose, self.fit_cfg, others=others, hidden=self._blocked_off(p), base=base)

    def _pose(self, room: Room, prod: Product, center_xz, yaw_rad: float, snap: bool, p: dict | None = None) -> Pose:
        if len(center_xz) != 2:
            raise Invalid("center_xz는 [x, z]")
        pose = Pose((float(center_xz[0]), float(center_xz[1])), float(yaw_rad))
        if not snap:
            return pose
        gone = set((p or {}).get("scene_state", {}).get("hidden_walls") or [])
        if prod.sku in MOUNT_SKUS:  # 문·창은 스캔 벽이나 가벽 가운데 줄에 단다
            return snap_door(self._wall_lines(room, p, gone), pose, prod.product_dims_mm.w / 1000)
        kind = WALL if prod.category == WALL_HOOD else mount_kind(prod)
        if kind == WALL:  # 벽걸이·벽 후드: 어디를 눌러도 가장 가까운 벽(가벽 포함)에 건다
            d = prod.product_dims_mm
            return hang(self._wall_faces(room, p, gone), pose, d.w / 1000, d.d / 1000) or pose if d.w and d.d else pose
        if gone:  # 철거한 벽에는 붙지 않는다
            room = room.model_copy(update={"walls": [w for w in room.walls if w.wall_id not in gone]})
        return snap_to_wall(room, prod, pose, self.fit_cfg, reach_m=MOUNT_REACH_M if kind else None)

    @staticmethod
    def _wall_faces(room: Room, p: dict | None, gone: set[str]) -> list[tuple]:
        """벽걸이 제품을 걸 수 있는 벽: 남아 있는 스캔 벽과 놓은 가벽 (시작, 끝, 두께, id)."""
        faces = [(tuple(w.start), tuple(w.end), w.thickness_m or 0.1, w.wall_id) for w in room.walls if w.wall_id not in gone]
        for x in (p or {}).get("scene_state", {}).get("placements", []):
            if x.get("sku") == "decor:wall" and x.get("size_m"):
                u, half = x["yaw_rad"] - math.pi / 2, x["size_m"][0] / 2
                (cx, cz), dx, dz = x["center_xz"], math.cos(u) * half, math.sin(u) * half
                faces.append(((cx - dx, cz - dz), (cx + dx, cz + dz), x["size_m"][2], x["placement_id"]))
        return faces

    @staticmethod
    def _wall_lines(room: Room, p: dict | None, gone: set[str]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        """문을 달 수 있는 선: 남아 있는 스캔 벽과 놓은 가벽·파티션의 가운데 줄."""
        import math as _m
        lines = [(tuple(w.start), tuple(w.end)) for w in room.walls if w.wall_id not in gone]
        for x in (p or {}).get("scene_state", {}).get("placements", []):
            if x.get("sku") in WALL_LIKE and x.get("size_m"):
                u, half = x["yaw_rad"] - _m.pi / 2, x["size_m"][0] / 2
                (cx, cz), dx, dz = x["center_xz"], _m.cos(u) * half, _m.sin(u) * half
                lines.append(((cx - dx, cz - dz), (cx + dx, cz + dz)))
        return lines

    def _settle(self, room: Room, p: dict, prod: Product, pose: Pose, exclude: str | None = None) -> Pose:
        """올려 두는 가전이 윗면 가장자리에 걸치면 다 올라오는 자리로 당긴다."""
        size = can_sit(prod) and prod.product_dims_mm
        host = surface_under(pose.center_xz, self._tops(room, p, prod, exclude)) if size else None
        if not host:
            return pose
        return Pose(settle_on(host, pose.center_xz, pose.yaw_rad, size.w / 1000, size.d / 1000), pose.yaw_rad, pose.wall_id)

    # ---- 장 칸에 끼워 넣기 (recommender/slot.py) ----
    SCAN_HOST_MAX_M = 1.0  # 스캔한 수납장 가운데 이보다 낮은 것(싱크대·하부장)은 칸을 내줄 수 있는 장으로 본다

    def _scan_hosts(self, room: Room, p: dict) -> list[dict]:
        """스캔한 낮은 수납장을 하부장처럼 다룬다. 스캔은 앞뒤를 모르니 벽에 가까운 쪽을 등으로 본다."""
        hidden, out = set(self._blocked_off(p)), []
        gone = set(p["scene_state"].get("hidden_walls") or [])
        walls = [w for w in room.walls if w.wall_id not in gone]
        for o in room.objects:
            top = o.position[1] + o.bbox_m.h / 2
            if o.category not in self.COUNTER_SCANNED or o.object_id in hidden or top > self.SCAN_HOST_MAX_M:
                continue
            c = (o.position[0], o.position[2])

            def off_wall(yaw: float) -> float:
                b = (c[0] - math.cos(yaw) * o.bbox_m.d / 2, c[1] - math.sin(yaw) * o.bbox_m.d / 2)
                return min((point_segment_distance(b, tuple(w.start), tuple(w.end)) for w in walls), default=0.0)

            yaw = min((o.yaw_rad, o.yaw_rad + math.pi), key=off_wall)
            out.append({"placement_id": o.object_id, "sku": "decor:basecab", "scanned": True, "door_m": 0.0, "center_xz": list(c),
                        "yaw_rad": yaw, "size_m": [o.bbox_m.w, round(top, 3), o.bbox_m.d], "hex": None})
        return out

    def _slot_hosts(self, room: Room, p: dict, exclude: str | None = None) -> list[dict]:
        return [x for x in p["scene_state"]["placements"]
                if x.get("sku") in SLOT_HOSTS and x.get("size_m") and x.get("placement_id") != exclude] + self._scan_hosts(room, p)

    def _slot(self, room: Room, p: dict, prod: Product, pose: Pose, exclude: str | None = None):
        """빌트인을 가까운 장 줄에 끼운 자리와 칸을 내줄 장들. 줄이 없으면 None."""
        if is_decor(prod.sku) or not slotable(prod) or product_size(prod) is None:
            return None
        side, back, _, _ = _clear(prod)
        # 고정한 장, 안에 정수기를 넣은 장은 자르지 않는다
        keep = set(p["scene_state"].get("locked") or []) | {x["placement_id"] for x in p["scene_state"]["placements"] if x.get("host_of")}
        return slot_in(product_size(prod), pose, self._slot_hosts(room, p, exclude), side, back, keep)

    def project_view(self, pid: str) -> dict:
        """웹이 받는 집 상태. 칸을 내줄 수 있는 스캔 장(scan_hosts)은 아직 아무것도 안 놓은 집에도 넣어 준다."""
        p = self.get_project(pid)
        if "scan_hosts" not in p["scene_state"]:
            hosts = self._scan_hosts(self.get_room(pid), p)
            p["scene_state"]["scan_hosts"] = [{k: c[k] for k in ("placement_id", "center_xz", "yaw_rad", "size_m")} for c in hosts]
        return p

    @staticmethod
    def _scratch(p: dict) -> dict:
        """저장하지 않고 칸을 내어 볼 때 쓰는 사본."""
        ss = p["scene_state"]
        return {**p, "scene_state": {**ss, "placements": [dict(x) for x in ss["placements"]], "hidden_objects": list(ss.get("hidden_objects") or [])}}

    def _apply_slot(self, room: Room, p: dict, slot, new_id=None) -> dict:
        """칸을 내준다: 겹친 장을 줄이거나 가르거나 없앤다. 되돌릴 때 쓸 바뀌기 전 값을 돌려준다.
        스캔한 장은 고칠 수 없으니 치우고, 남는 부분을 같은 크기 하부장으로 놓는다."""
        pls = p["scene_state"]["placements"]
        scans = {c["placement_id"]: c for c in self._scan_hosts(room, p)}
        mint = new_id or (lambda: self.db.next_id("pl"))
        ch = {"resized": [], "added": [], "removed": [], "hidden": []}
        for e in slot.edits:
            key = e.get("id") or e["like"]
            if key in scans:
                if key not in ch["hidden"]:
                    self._hidden(p).append(key)
                    ch["hidden"].append(key)
                if not e.get("remove"):
                    c = scans[key]
                    pls.append({"placement_id": mint(), "sku": "decor:basecab", "zone_id": None, "center_xz": list(e["center_xz"]),
                                "yaw_rad": c["yaw_rad"], "size_m": [e["w"], *c["size_m"][1:]], "wall_id": None, "color": None, "hex": None,
                                "verdict": "fit", "reasons": [], "base_m": 0.0, "on": None, "tabletop": False, "kind": "decor"})
                    ch["added"].append(pls[-1]["placement_id"])
                continue
            cab = next(x for x in pls if x["placement_id"] == key)
            if e.get("remove"):
                pls.remove(cab)
                ch["removed"].append({k: cab.get(k) for k in ("sku", "center_xz", "yaw_rad", "size_m", "color", "hex", "top_hex", "part_colors")})
            elif "id" in e:
                ch["resized"].append({"id": cab["placement_id"], "center_xz": list(cab["center_xz"]), "size_m": list(cab["size_m"])})
                cab["center_xz"], cab["size_m"] = list(e["center_xz"]), [e["w"], *cab["size_m"][1:]]
            else:
                # 갈라진 다른 쪽: 원래 장 크기는 resized에 남아 있다
                more = {**cab, "placement_id": mint(), "center_xz": list(e["center_xz"]), "size_m": [e["w"], *cab["size_m"][1:]]}
                pls.append(more)
                ch["added"].append(more["placement_id"])
        return ch

    def _slot_covers(self, room: Room, p: dict) -> None:
        """끼워 넣은 제품에 위를 덮는 상판·가림판 정보를 적는다 (웹 3D가 그린다. 그 위에 물건도 올릴 수 있다)."""
        hosts = self._slot_hosts(room, p)
        p["scene_state"]["scan_hosts"] = [{k: c[k] for k in ("placement_id", "center_xz", "yaw_rad", "size_m")} for c in hosts if c.get("scanned")]
        for x in p["scene_state"]["placements"]:
            x.pop("slot", None)
            if is_decor(x.get("sku")) or x.get("zone_id") or not x.get("size_m"):
                continue
            try:
                prod = self.catalog.get(x["sku"])
            except KeyError:
                continue
            if not slotable(prod):
                continue
            side, back, _, _ = _clear(prod)
            c = slot_cover(tuple(x["size_m"]), Pose(tuple(x["center_xz"]), x["yaw_rad"]), hosts, side, back)
            if c:
                x["slot"] = c

    CABINETS = frozenset({"decor:basecab", "decor:island", "decor:islandtable"})
    COUNTER_SCANNED = frozenset({"storage"})  # 스캔한 낮은 수납장(싱크대·하부장)은 조리대로 본다

    def _inset(self, sku: str | None) -> bool:
        """하부장과 한 몸으로 들어가는 제품: 빌트인 정수기(하부장 안), 인덕션(상판)."""
        if not sku or is_decor(sku):
            return False
        try:
            return self._undersink(sku) or needs_counter(self.catalog.get(sku))
        except KeyError:
            return False

    def _counters(self, room: Room, p: dict) -> list[tuple[tuple[float, float], float]]:
        """싱크대·하부장이 있는 자리 (가운데, 폭의 반). 식기세척기를 그 옆에 붙일 때 쓴다."""
        return [(tuple(s["center_xz"]), s["w"] / 2) for s in self._surfaces(room, p, counters=True)]

    def _undersink(self, sku: str | None) -> bool:
        """싱크대 하부장 안에 들어가는 빌트인 정수기 (출수 파이프만 상판 위로 나온다)."""
        if not sku or is_decor(sku):
            return False
        try:
            prod = self.catalog.get(sku)
        except KeyError:
            return False
        return prod.category == "water_purifier" and (prod.install_type == "built_in" or prod.install_form == "빌트인")

    def _judge(self, room: Room, p: dict, prod: Product, pose: Pose, exclude: str | None = None, base_m: float | None = None):
        # 창은 스캔·도면에서 창이 있던 벽에만 단다 (없앤 창이 있던 벽도 된다). 창을 하나도 못 찾은 집은 따지지 않는다
        window_walls = {o.wall_id for o in room.openings if o.type == "window" and o.wall_id} or None
        shut = set(p["scene_state"].get("hidden_openings") or [])
        if shut:  # 없앤 창은 가릴 일이 없다
            room = room.model_copy(update={"openings": [o for o in room.openings if o.opening_id not in shut]})
        if is_flat(prod.sku):  # 러그: 가구·제품과 겹쳐도 된다 (벽과 방 밖만 본다)
            return check_pose(room, prod, pose, self.fit_cfg, hidden=self._blocked_off(p) + [o.object_id for o in room.objects])
        others = self._others(p, exclude)
        # 빌트인 정수기는 하부장 안에 들어간다: 서로 겹쳐도 된다
        if self._undersink(prod.sku):
            others = [x for x in others if x.get("sku") not in self.CABINETS]
        elif prod.sku in self.CABINETS:
            others = [x for x in others if not self._inset(x.get("sku"))]
        host = surface_under(pose.center_xz, self._tops(room, p, prod, exclude)) if can_sit(prod) else None
        return check_pose(room, prod, pose, self.fit_cfg, others=others, hidden=self._blocked_off(p), host=host, base_m=base_m,
                          window_walls=window_walls)

    # 작은 가전을 올려 둘 수 있는 가구 (윗면이 SURFACE_MAX_M 이하일 때). 스캔 가구는 탁자·수납장
    HOSTS = frozenset({"decor:table", "decor:coffee", "decor:desk", "decor:dresser", "decor:basecab", "decor:island", "decor:islandtable",
                       "decor:tvstand"})

    def _tops(self, room: Room, p: dict, prod: Product, exclude: str | None = None) -> list[dict]:
        """이 제품을 올릴 수 있는 윗면. 인덕션은 조리대(하부장·아일랜드·스캔한 낮은 수납장)에만."""
        return self._surfaces(room, p, exclude, counters=needs_counter(prod))

    def _surfaces(self, room: Room, p: dict, exclude: str | None = None, counters: bool = False) -> list[dict]:
        """올려 둘 수 있는 윗면 목록 (놓은 가구 + 스캔한 탁자·수납장). yaw_rad는 폭 축 방향.
        counters=True면 조리대로 쓸 수 있는 것만."""
        out = []
        hosts = self.CABINETS if counters else self.HOSTS
        scanned = self.COUNTER_SCANNED if counters else self.SURFACE_SCANNED
        for x in p["scene_state"].get("placements", []):
            if x.get("sku") not in hosts or not x.get("size_m") or x.get("placement_id") == exclude:
                continue
            w, h, d = x["size_m"]
            if h <= PRODUCT_SURFACE_MAX_M:
                out.append({"id": x["placement_id"], "center_xz": tuple(x["center_xz"]),
                            "yaw_rad": x.get("yaw_rad", math.pi / 2) - math.pi / 2, "w": w, "d": d, "top_m": float(h)})
        for x in p["scene_state"].get("placements", []):  # 식기세척기 위로 이어진 상판
            c = x.get("slot")
            if not c or c["look"] == "tallcab" or x.get("placement_id") == exclude or c["top_m"] > PRODUCT_SURFACE_MAX_M:
                continue
            a, u = x["yaw_rad"] - math.pi / 2, (c["right_m"] - c["left_m"]) / 2
            out.append({"id": x["placement_id"], "yaw_rad": a, "w": x["size_m"][0] + c["left_m"] + c["right_m"], "d": c["depth_m"],
                        "top_m": float(c["top_m"]),
                        "center_xz": (x["center_xz"][0] + math.cos(a) * u + math.cos(x["yaw_rad"]) * c["off_m"],
                                      x["center_xz"][1] + math.sin(a) * u + math.sin(x["yaw_rad"]) * c["off_m"])})
        hidden = set(self._blocked_off(p))
        for o in room.objects:
            top = o.position[1] + o.bbox_m.h / 2
            if o.category in scanned and o.object_id not in hidden and top <= PRODUCT_SURFACE_MAX_M:
                out.append({"id": o.object_id, "center_xz": (o.position[0], o.position[2]), "yaw_rad": o.yaw_rad,
                            "w": o.bbox_m.w, "d": o.bbox_m.d, "top_m": round(top, 3)})
        return out

    @staticmethod
    def _seat(x: dict, r) -> None:
        """판정 결과의 높이를 배치에 적는다 (웹 3D·렌더·와이파이가 이 값을 쓴다)."""
        x["verdict"], x["reasons"] = r.verdict.value, r.reasons
        x["base_m"], x["on"] = round(r.base_m, 3), r.on

    def _on_top(self, room: Room, p: dict, prod: Product, exclude: str | None = None):
        """올려 두는 가전: 놓여 있는 가구 윗면에서 빈자리를 찾는다 (넓은 윗면부터, 가운데에서 가까운 곳). 없으면 None."""
        if not can_sit(prod):
            return None
        for s in sorted(self._tops(room, p, prod, exclude), key=lambda q: -q["w"] * q["d"]):
            ux, uz = math.cos(s["yaw_rad"]), math.sin(s["yaw_rad"])
            n = max(0, int(s["w"] / 2 / 0.1))
            for i in sorted(range(-n, n + 1), key=abs):
                c = (s["center_xz"][0] + ux * i * 0.1, s["center_xz"][1] + uz * i * 0.1)
                for yaw in (s["yaw_rad"] + math.pi / 2, s["yaw_rad"] - math.pi / 2):
                    r = self._judge(room, p, prod, Pose(c, yaw), exclude)
                    if r.on and r.verdict.value != "no_fit":
                        return r
        return None

    OFF_WALL_STEP_M = 0.05

    def _off_wall(self, room: Room, p: dict, prod: Product, pose: Pose, exclude: str | None = None) -> Pose:
        """벽에 붙여 둔 제품을 돌려서 모서리가 벽에 박히면, 박힌 벽에서 필요한 만큼만(5 cm씩) 방 안쪽으로 뗀다."""
        from recommender.pose import _inward

        def hit(q: Pose) -> list[str]:
            return [z["ref"] for z in self._judge(room, p, prod, q, exclude).reasons if z["code"] == "hits_wall" and z.get("ref")]

        walls = hit(pose)
        if not walls:
            return pose
        nx = sum(_inward(room, room.wall(w)).v_axis[0] for w in walls)
        nz = sum(_inward(room, room.wall(w)).v_axis[1] for w in walls)
        n = math.hypot(nx, nz) or 1.0
        dims = prod.product_dims_mm
        reach = max(1.0, max(dims.w or 0, dims.d or 0) / 2000 + 0.1)  # 긴 장을 돌리면 길이의 절반만큼은 떼야 한다
        for k in range(1, math.ceil(reach / self.OFF_WALL_STEP_M) + 1):
            d = self.OFF_WALL_STEP_M * k
            q = Pose((pose.center_xz[0] + nx / n * d, pose.center_xz[1] + nz / n * d), pose.yaw_rad, None)
            if not hit(q):
                return q
        return pose

    SINK_CABINET_M = (0.6, 0.85, 0.6)

    def _add_sink_cabinet(self, room: Room, p: dict, x: dict) -> None:
        """빌트인 정수기를 하부장 없이 놓으면 그 자리에 주방 하부장(600 x 850 x 600)을 같이 놓는다."""
        from recommender.pose import overlaps, rect
        mine = rect(tuple(x["center_xz"]), x["yaw_rad"] - math.pi / 2, x["size_m"][0], x["size_m"][2])
        for y in p["scene_state"]["placements"]:
            if y.get("sku") in self.CABINETS and y.get("size_m") and overlaps(
                    mine, rect(tuple(y["center_xz"]), y["yaw_rad"] - math.pi / 2, y["size_m"][0], y["size_m"][2])):
                return
        size = self.SINK_CABINET_M
        push = size[2] / 2 - x["size_m"][2] / 2   # 등을 정수기와 같은 벽에 맞춘다
        c = (x["center_xz"][0] + math.cos(x["yaw_rad"]) * push, x["center_xz"][1] + math.sin(x["yaw_rad"]) * push)
        prod = decor_product("decor:basecab", size)
        pose = Pose(c, x["yaw_rad"], x.get("wall_id"))
        r = self._judge(room, p, prod, pose)
        if r.verdict.value == "no_fit":
            return
        p["scene_state"]["placements"].append({
            "placement_id": self.db.next_id("pl"), "sku": "decor:basecab", "zone_id": None, "center_xz": list(c),
            "yaw_rad": x["yaw_rad"], "size_m": list(size), "wall_id": x.get("wall_id"), "color": None, "hex": None,
            "verdict": r.verdict.value, "reasons": r.reasons, "kind": "decor", "host_of": x["placement_id"],
            **({"combo": x["combo"]} if x.get("combo") else {})})

    def _rejudge_all(self, room: Room, p: dict) -> None:
        """한 제품이 움직이거나 가구를 치우면 나머지 배치도 다시 판정한다 (자유 배치만)."""
        self._slot_covers(room, p)
        # 먼저 높이부터: 받치던 가구가 빠졌으면 바닥으로 내려온 것으로 보고 서로 판정한다
        # 바닥에 있다가 방금 책상 위로 올라간 것도 여기서 높이를 적어야, 받친 책상이 "겹침"으로 잘못 나오지 않는다
        for x in p["scene_state"]["placements"]:
            if x.get("zone_id") or x.get("hung") or x.get("float"):
                continue
            if x.get("on"):
                host = surface_under(tuple(x["center_xz"]), self._surfaces(room, p, x["placement_id"], counters=self._inset(x["sku"])))
                x["base_m"], x["on"] = (host["top_m"], host["id"]) if host else (0.0, None)
                continue
            try:
                prod = self._item(x["sku"], x.get("size_m"))
            except KeyError:
                continue
            if can_sit(prod) and not floats(prod):
                host = surface_under(tuple(x["center_xz"]), self._tops(room, p, prod, x["placement_id"]))
                if host:
                    x["base_m"], x["on"] = host["top_m"], host["id"]
        for x in p["scene_state"]["placements"]:
            if x.get("zone_id"):
                continue
            try:
                prod = self._item(x["sku"], x.get("size_m"))
            except KeyError:
                continue
            up = floats(prod)
            r = self._judge(room, p, prod, Pose(tuple(x["center_xz"]), x["yaw_rad"], x.get("wall_id")), x["placement_id"],
                            base_m=x.get("base_m") if up and (x.get("hung") or x.get("float")) else None)
            self._seat(x, r)
            x["tabletop"] = can_sit(prod)
            if up:
                x["float" if prod.category == ISLAND_HOOD else "hung"] = True  # 걸거나 매단 것: base_m이 고른 높이
        self._sync_hoods(room, p)

    # ---- 인덕션 위 후드 (docs/specs/fit-rules.md '인덕션 위 후드') ----
    HOOD_WALL_REACH_M = 0.35          # 인덕션 가운데가 벽 후드 가운데에서 이 안이면 벽에 건다. 멀면 천장에서 내린다
    HOOD_WIDE_OVER_M = 0.62           # 인덕션이 이보다 넓으면 90 cm 후드
    HOOD_H_M = (0.62, 0.995)          # 벽 후드 높이 범위 (IKEA RYTMISK 60의 덕트 덮개를 가장 짧게·길게 뺐을 때)

    def _is_cooktop(self, x: dict) -> bool:
        return bool(x.get("size_m")) and x.get("on") and self._inset(x.get("sku")) and not self._undersink(x.get("sku"))

    def _hood_spec(self, room: Room, p: dict, x: dict, old: dict | None) -> dict:
        """이 인덕션 위에 달 후드의 종류·자리·크기. 뒤에 벽이 있으면 벽 후드, 없으면 천장에서 내려오는 아일랜드 후드."""
        from recommender.pose import _nearest_wall, _wall_height
        c, yaw = tuple(x["center_xz"]), x["yaw_rad"]
        ceiling = _wall_height(_nearest_wall(room, c)[0]) if room.walls else 2.4
        base = round(float(x.get("base_m") or 0) + x["size_m"][1] + HOOD_GAP_M, 3)
        wide = 0.9 if x["size_m"][0] > self.HOOD_WIDE_OVER_M else 0.6
        gone = set(p["scene_state"].get("hidden_walls") or [])
        back = None  # 인덕션 등 뒤의 벽 가운데 가장 가까운 것
        for a, b, t, wid in self._wall_faces(room, p, gone):
            L2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 or 1e-9
            k = min(max(((c[0] - a[0]) * (b[0] - a[0]) + (c[1] - a[1]) * (b[1] - a[1])) / L2, 0.0), 1.0)
            q = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
            dist = math.dist(c, q)
            if dist < 1e-6 or ((c[0] - q[0]) * math.cos(yaw) + (c[1] - q[1]) * math.sin(yaw)) / dist < 0.7:
                continue
            if back is None or dist < back[0]:
                back = (dist, (a, b, t, wid))
        w_m, _, d_m = (old["size_m"] if old and old["sku"] == "decor:hood" else (wide, 0, 0.471))
        w_m = max(w_m, wide) if not old else w_m
        at = hang([back[1]], Pose(c, yaw), w_m, d_m) if back else None
        if at and math.dist(at.center_xz, c) <= self.HOOD_WALL_REACH_M:
            lo, hi = self.HOOD_H_M
            base = min(base, ceiling - lo)
            return {"sku": "decor:hood", "center_xz": list(at.center_xz), "yaw_rad": at.yaw_rad, "wall_id": at.wall_id,
                    "size_m": [w_m, round(min(max(ceiling - base, lo), hi), 3), d_m], "base_m": base, "hung": True}
        w_m, _, d_m = (old["size_m"] if old and old["sku"] == "decor:islandhood" else (0.9, 0, 0.6))
        base = min(base, ceiling - 0.4)
        return {"sku": "decor:islandhood", "center_xz": list(c), "yaw_rad": yaw, "wall_id": None,
                "size_m": [w_m, round(ceiling - base, 3), d_m], "base_m": base, "float": True}

    def _sync_hoods(self, room: Room, p: dict) -> None:
        """인덕션마다 그 위 후드를 맞춘다: 없으면 달고, 인덕션이 움직였으면 따라가고, 인덕션이 빠졌으면 같이 뺀다.
        손으로 뗀 후드(no_hood)는 다시 달지 않는다. 이미 위에 다른 후드가 있으면 그대로 둔다."""
        from recommender.pose import overlaps, rect
        pls = p["scene_state"]["placements"]
        cooks = {x["placement_id"]: x for x in pls if self._is_cooktop(x)}
        pls[:] = [y for y in pls if not y.get("over") or (y["over"] in cooks and not cooks[y["over"]].get("no_hood"))]
        for cid, x in cooks.items():
            if x.get("no_hood"):
                continue
            old = next((y for y in pls if y.get("over") == cid), None)
            mine = rect(tuple(x["center_xz"]), x["yaw_rad"] - math.pi / 2, x["size_m"][0], x["size_m"][2])
            if old is None and any(y["sku"] in ("decor:hood", "decor:islandhood") and y.get("size_m") and overlaps(
                    mine, rect(tuple(y["center_xz"]), y["yaw_rad"] - math.pi / 2, y["size_m"][0], y["size_m"][2])) for y in pls):
                continue
            spec = self._hood_spec(room, p, x, old)
            hood = old or {"placement_id": self.db.next_id("pl"), "zone_id": None, "color": None, "hex": None, "kind": "decor",
                           "over": cid, "tabletop": False, "on": None}
            if old and old["sku"] != spec["sku"]:  # 벽 후드 ↔ 아일랜드 후드로 바뀌면 걸린 방식도 바뀐다
                old.pop("hung", None), old.pop("float", None)
            hood.update(spec)
            if x.get("combo"):
                hood["combo"] = x["combo"]
            r = self._judge(room, p, decor_product(hood["sku"], hood["size_m"]),
                            Pose(tuple(hood["center_xz"]), hood["yaw_rad"], hood["wall_id"]), hood["placement_id"], base_m=hood["base_m"])
            hood["verdict"], hood["reasons"] = r.verdict.value, r.reasons
            if old is None:
                if r.verdict.value == "no_fit":
                    continue  # 달 자리가 안 나오면 (키 큰 가구 아래 등) 억지로 달지 않는다
                pls.append(hood)

    def _hoodless(self, p: dict) -> dict | None:
        """후드가 안 달린 인덕션 (손으로 뗀 것 포함)."""
        pls = p["scene_state"]["placements"]
        have = {y.get("over") for y in pls}
        return next((x for x in pls if self._is_cooktop(x) and x["placement_id"] not in have), None)

    def pose_check(self, pid: str, sku: str, center_xz, yaw_rad: float = 0.0, snap: bool = True,
                   placement_id: str | None = None, size_m=None, base_m: float | None = None, slot: bool = True) -> dict:
        """저장하지 않고 판정만 (끌어서 옮기는 중 미리 보기)."""
        prod, room, p = self._item(sku, size_m), self.get_room(pid), self.get_project(pid)
        pose = self._settle(room, p, prod, self._pose(room, prod, center_xz, yaw_rad, snap, p), placement_id)
        cur = next((y for y in p["scene_state"]["placements"] if y.get("placement_id") == placement_id), None) if placement_id else None
        still = cur is not None and math.dist(pose.center_xz, cur["center_xz"]) < 1e-3  # 제자리 판정은 지금 자리 그대로
        bay = self._slot(room, p, prod, pose, placement_id) if slot and not still else None
        if bay:  # 장 칸에 끼운 모습으로 판정한다 (장은 저장할 때 자른다)
            pose = bay.pose
            p = self._scratch(p)
            self._apply_slot(room, p, bay, new_id=lambda: "preview")
        if base_m is None and cur:  # 걸어 둔 것을 옮겨 보는 중이면 지금 높이 그대로
            base_m = cur.get("base_m") if cur.get("hung") else None
        r = self._judge(room, p, prod, pose, placement_id, base_m=base_m)
        out = r.to_dict()
        out["gaps"] = self._gaps(room, p, prod, pose, placement_id, r.base_m)
        return out

    def place_at(self, pid: str, sku: str, center_xz, yaw_rad: float = 0.0, snap: bool = True,
                 color: str | None = None, wall_id: str | None = None, size_m=None, base_m: float | None = None,
                 slot: bool = True) -> dict:
        prod, room, p = self._item(sku, size_m), self.get_room(pid), self.get_project(pid)
        opt = self._color_option(prod, color)
        pose = self._settle(room, p, prod, self._pose(room, prod, center_xz, yaw_rad, snap, p))
        if wall_id and not pose.wall_id:
            pose = Pose(pose.center_xz, pose.yaw_rad, wall_id)
        bay = self._slot(room, p, prod, pose) if slot else None
        changes = None
        if bay:  # 빌트인: 가까운 장 줄에 끼우고, 겹친 장은 칸을 내준다
            pose, changes = bay.pose, self._apply_slot(room, p, bay)
        r = self._judge(room, p, prod, pose, base_m=base_m)
        if r.size_m is None:
            raise Invalid("제품 치수 정보가 없어 놓을 수 없습니다")
        x = {"placement_id": self.db.next_id("pl"), "sku": sku, "zone_id": None,
             "center_xz": list(pose.center_xz), "yaw_rad": pose.yaw_rad, "size_m": list(r.size_m),
             "wall_id": pose.wall_id, "color": opt.color if opt else None, "hex": opt.hex_approx if opt else None,
             "verdict": r.verdict.value, "reasons": r.reasons, "base_m": round(r.base_m, 3), "on": r.on,
             "tabletop": can_sit(prod)}
        if floats(prod):
            x["float" if prod.category == ISLAND_HOOD else "hung"] = True
        if is_decor(sku):
            x["kind"] = "decor"  # 꾸미기 가구: 주문·설치 신청에 넣지 않는다
        p["scene_state"]["placements"].append(x)
        if self._undersink(sku) or (needs_counter(prod) and not r.on):  # 인덕션을 조리대 없는 곳에 놓으면 하부장을 같이
            self._add_sink_cabinet(room, p, x)
        self._rejudge_all(room, p)
        self._save_project(p)
        out = self._rebuild(pid)
        out["placement"] = next(y for y in out["scene_state"]["placements"] if y["placement_id"] == x["placement_id"])
        if changes and any(changes.values()):
            out["slot_changes"] = changes
        return out

    def _spot(self, room: Room, p: dict, prod: Product, exclude: str | None = None, step_m: float = 0.1):
        if is_flat(prod.sku):
            return None
        near = self._counters(room, p) if prod.category == "dishwasher" and prod.install_type == "built_in" else ()
        return find_spot(room, prod, self.fit_cfg, others=self._others(p, exclude), hidden=self._blocked_off(p), step_m=step_m,
                         near=near)

    def _middle(self, room: Room, p: dict, prod: Product, exclude: str | None = None):
        """벽을 따라 자리가 없을 때(러그·큰 가구): 방 가운데 근처 빈자리. 못 찾으면 None."""
        from recommender.pose import inside_room
        xs = [c for w in room.walls for c in (w.start[0], w.end[0])]
        zs = [c for w in room.walls for c in (w.start[1], w.end[1])]
        cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
        cands = sorted(((cx + i * 0.25, cz + j * 0.25) for i in range(-12, 13) for j in range(-12, 13)),
                       key=lambda q: (q[0] - cx) ** 2 + (q[1] - cz) ** 2)
        for c in cands:
            if not inside_room(room, c):
                continue
            r = self._judge(room, p, prod, Pose(c, 0.0), exclude)
            if r.verdict.value != "no_fit":
                return r
        return None

    def _bay(self, room: Room, p: dict, prod: Product):
        """빌트인이 들어갈 장 칸: 넓은 장부터 양 끝을 내어 보고 들어가는 첫 자리. 없으면 None."""
        if is_decor(prod.sku) or not slotable(prod) or product_size(prod) is None:
            return None
        w = product_size(prod)[0]
        for cab in sorted(self._slot_hosts(room, p), key=lambda x: -x["size_m"][0]):
            a, half = cab["yaw_rad"] - math.pi / 2, cab["size_m"][0] / 2 - w / 2
            if half < 0:
                continue
            for u in (half, -half):
                pose = Pose((cab["center_xz"][0] + math.cos(a) * u, cab["center_xz"][1] + math.sin(a) * u), cab["yaw_rad"])
                bay = self._slot(room, p, prod, pose)
                if bay is None:
                    continue
                q = self._scratch(p)
                self._apply_slot(room, q, bay, new_id=lambda: "preview")
                r = self._judge(room, q, prod, bay.pose)
                if r.verdict.value != "no_fit":
                    return r
        return None

    def _auto_spot(self, room: Room, p: dict, prod: Product):
        """auto_place가 놓을 자리 (판정 결과). 어디에도 안 들어가면 None."""
        sku = prod.sku
        floor_first = prod.category in FLOOR_FIRST  # 미니 와인셀러·냉장고: 바닥 자리가 없을 때만 가구 위
        r = (self._spot(room, p, prod) if floor_first else None) or self._on_top(room, p, prod)
        if r is None and needs_counter(prod):  # 조리대가 없으면 하부장 자리를 찾아 그 위에 (place_at이 하부장을 같이 놓는다)
            r = self._spot(room, p, decor_product("decor:basecab", self.SINK_CABINET_M))
        r = r or self._spot(room, p, prod) or (self._middle(room, p, prod) if is_decor(sku) else None)
        if (r is None or self._slot(room, p, prod, r.pose) is None) and (bay := self._bay(room, p, prod)):
            r = bay  # 장 줄 옆에 빈자리가 없으면 장 한 칸을 내어 그 안에
        return r

    def auto_place(self, pid: str, sku: str, color: str | None = None, size_m=None) -> dict:
        """벽을 따라 가장 잘 들어가는 자리를 찾아 놓는다 (러그는 방 가운데). 어디에도 안 들어가면 Invalid."""
        prod, room, p = self._item(sku, size_m), self.get_room(pid), self.get_project(pid)
        if is_hood(prod):  # 후드: 후드 없는 인덕션이 있으면 그 위에 단다
            cook = self._hoodless(p)
            if cook is not None:
                cook.pop("no_hood", None)
                self._rejudge_all(room, p)
                hood = next((y for y in p["scene_state"]["placements"] if y.get("over") == cook["placement_id"]), None)
                if hood is None:
                    raise Invalid("인덕션 위에 후드를 달 자리가 없어요")
                self._save_project(p)
                out = self._rebuild(pid)
                out["placement"] = next(y for y in out["scene_state"]["placements"] if y["placement_id"] == hood["placement_id"])
                return out
        r = self._auto_spot(room, p, prod)
        if r is None:
            raise Invalid("이 집에서 들어가는 자리를 못 찾았어요. 가구를 치우거나 다른 크기를 골라 보세요")
        return self.place_at(pid, sku, list(r.pose.center_xz), r.pose.yaw_rad, snap=False, color=color,
                             wall_id=r.pose.wall_id, size_m=size_m)

    def copy_placement(self, pid: str, placement_id: str) -> dict:
        """복사: 같은 것(크기·색 그대로)을 옆 빈자리에 하나 더 놓는다."""
        room, p = self.get_room(pid), self.get_project(pid)
        x = self._find_placement(p, placement_id)
        size = x.get("size_m") if is_decor(x["sku"]) else None
        prod = self._item(x["sku"], size)
        cx, cz = x["center_xz"]
        w = x["size_m"][0] if x.get("size_m") else 1.0
        height = x.get("base_m") if x.get("hung") or x.get("float") else None  # 걸거나 매단 것은 같은 높이로
        best = None
        for k in range(1, 9):  # 옆으로 조금씩 밀면서 처음으로 들어가는 자리
            for sgn in (1, -1):
                ux, uz = math.cos(x["yaw_rad"] - math.pi / 2), math.sin(x["yaw_rad"] - math.pi / 2)
                c = (cx + sgn * ux * (w + 0.05) * k, cz + sgn * uz * (w + 0.05) * k)
                r = self._judge(room, p, prod, Pose(c, x["yaw_rad"], x.get("wall_id")), base_m=height)
                if r.verdict.value != "no_fit":
                    best = r
                    break
            if best:
                break
        best = best or self._spot(room, p, prod) or self._middle(room, p, prod)
        if best is None:
            raise Invalid("복사본을 놓을 빈자리가 없어요")
        r = self.place_at(pid, x["sku"], list(best.pose.center_xz), best.pose.yaw_rad, snap=False, color=x.get("color"),
                          wall_id=best.pose.wall_id, size_m=size, base_m=height)
        if is_decor(x["sku"]) and (x.get("hex") or x.get("part_colors") or x.get("top_hex")):  # 칠한 가구는 색도 그대로
            p = self.get_project(pid)
            twin = self._find_placement(p, r["placement"]["placement_id"])
            twin["hex"] = x.get("hex")
            if x.get("top_hex"):
                twin["top_hex"] = x["top_hex"]
            if x.get("part_colors"):
                twin["part_colors"] = dict(x["part_colors"])
            self._save_project(p)
            r["placement"] = twin
        return r

    def fit_gap(self, pid: str, placement_id: str) -> dict:
        """빈틈에 맞추기: 장·가벽의 폭을 양옆 벽·가전 사이에 꽉 차게 늘린다. 옆 가전이 요구하는 옆 여유는 남긴다."""
        room, p = self.get_room(pid), self.get_project(pid)
        x = self._find_placement(p, placement_id)
        if not is_decor(x["sku"]) or is_flat(x["sku"]):
            raise Invalid("빈틈에 맞추기는 장·가벽 같은 가구만 돼요")
        prod = self._item(x["sku"], x.get("size_m"))
        pose = Pose(tuple(x["center_xz"]), x["yaw_rad"], x.get("wall_id"))
        found = fill_width(room, prod, pose, self.fit_cfg, others=self._gap_others(p, placement_id),
                           hidden=self._blocked_off(p), base=float(x.get("base_m") or 0.0))
        if found is None:
            raise Invalid("양옆이 막힌 빈틈이 아니에요. 벽이나 가전 사이에 놓고 다시 눌러 보세요")
        center, w = found
        if w * 1000 > MAX_DECOR_MM:
            raise Invalid("빈틈이 너무 넓어요. 벽이나 가전 가까이에 놓고 다시 눌러 보세요")
        return self.move_placement(pid, placement_id, list(center), x["yaw_rad"], snap=False,
                                   size_m=[w, x["size_m"][1], x["size_m"][2]])

    def set_wall_hidden(self, pid: str, wall_id: str, hidden: bool = True) -> dict:
        """벽 철거(가상): 스캔한 벽을 3D·판정에서 뺀다. 되돌리면 다시 세운다."""
        room, p = self.get_room(pid), self.get_project(pid)
        if not any(w.wall_id == wall_id for w in room.walls):
            raise NotFound(f"벽 없음: {wall_id}")
        hs = p["scene_state"].setdefault("hidden_walls", [])
        if hidden and wall_id not in hs:
            hs.append(wall_id)
        if not hidden and wall_id in hs:
            hs.remove(wall_id)
        self._rejudge_all(room, p)
        self._save_project(p)
        return self._rebuild(pid)

    def set_opening_hidden(self, pid: str, opening_id: str, hidden: bool = True) -> dict:
        """스캔한 창을 없앤다(벽으로 메운다). 되돌리면 다시 생긴다. 문은 드나드는 길이라 없애지 않는다."""
        room, p = self.get_room(pid), self.get_project(pid)
        op = next((o for o in room.openings if o.opening_id == opening_id), None)
        if op is None:
            raise NotFound(f"창 없음: {opening_id}")
        if op.type != "window":
            raise Invalid("창문만 없앨 수 있어요")
        hs = p["scene_state"].setdefault("hidden_openings", [])
        if hidden and opening_id not in hs:
            hs.append(opening_id)
        if not hidden and opening_id in hs:
            hs.remove(opening_id)
        self._rejudge_all(room, p)
        self._save_project(p)
        return self._rebuild(pid)

    def auto_align(self, pid: str, placement_id: str) -> dict:
        """자동 정렬: 가까운 벽이 있으면 그 벽에 붙이고, 없거나 붙여도 안 들어가면 가장 잘 들어가는 자리로 옮긴다."""
        room, p = self.get_room(pid), self.get_project(pid)
        x = self._find_placement(p, placement_id)
        prod = self._item(x["sku"], x.get("size_m"))
        snapped = self._pose(room, prod, x["center_xz"], x["yaw_rad"], True, p)
        if snapped.wall_id and self._judge(room, p, prod, snapped, placement_id).verdict.value != "no_fit":
            return self.move_placement(pid, placement_id, list(snapped.center_xz), snapped.yaw_rad, snap=True)
        near = self._near_wall_spot(room, p, prod, tuple(x["center_xz"]), placement_id)
        if near:  # 멀리 떨어져 있어도 가장 가까운 벽으로 곧장 간다 (집 반대편의 '좋은 자리'로 보내지 않는다)
            return self.move_placement(pid, placement_id, list(near.center_xz), near.yaw_rad, snap=True)
        r = self._spot(room, p, prod, placement_id)
        if r is None:
            raise Invalid("이 집에서 들어가는 자리를 못 찾았어요. 가구를 치우거나 다른 크기를 골라 보세요")
        return self.move_placement(pid, placement_id, list(r.pose.center_xz), r.pose.yaw_rad, snap=True)

    ALIGN_SLIDE_M = 1.5  # 곧장 간 자리가 막혔으면 그 벽을 따라 이만큼까지 옆으로 비켜 본다

    def _near_wall_spot(self, room: Room, p: dict, prod: Product, at: tuple, exclude: str) -> Pose | None:
        """벽에 붙이기: 가까운 벽부터, 곧장 간 자리와 그 옆(10 cm씩)에서 처음으로 들어가는 자리."""
        if floats(prod) or prod.sku in MOUNT_SKUS or is_flat(prod.sku):
            return None
        gone = set(p["scene_state"].get("hidden_walls") or [])
        walls = sorted((w for w in room.walls if w.wall_id not in gone),
                       key=lambda w: point_segment_distance(at, tuple(w.start), tuple(w.end)))
        steps = [0.0] + [s * i * 0.1 for i in range(1, int(self.ALIGN_SLIDE_M / 0.1) + 1) for s in (1, -1)]
        for w in walls[:3]:
            for shift in steps:
                pose = against_wall(room, prod, w, at, self.fit_cfg, shift)
                if pose and self._judge(room, p, prod, pose, exclude).verdict.value != "no_fit":
                    return pose
        return None

    def suggest(self, pid: str, skus: list[str], limit: int = 3) -> dict:
        """후보 제품 가운데 이 집 벽을 따라 실제로 들어가는 자리가 있는 것만 골라 준다 (적합 먼저)."""
        room, p = self.get_room(pid), self.get_project(pid)
        others = [y for y in p["scene_state"]["placements"] if y.get("size_m")]
        rank = {"fit": 0, "conditional": 1, "unknown": 2}
        found = []
        for i, sku in enumerate(dict.fromkeys(skus)):
            try:
                prod = self.catalog.get(sku)
            except KeyError:
                continue
            r = find_spot(room, prod, self.fit_cfg, others=others, hidden=self._hidden(p), step_m=0.25)
            if r is None:
                continue
            found.append((rank.get(r.verdict.value, 3), i, {"sku": sku, "verdict": r.verdict.value, "wall_id": r.pose.wall_id}))
        found.sort(key=lambda t: t[:2])
        return {"items": [t[2] for t in found[:limit]]}

    def _find_placement(self, p: dict, placement_id: str) -> dict:
        x = next((y for y in p["scene_state"]["placements"] if y.get("placement_id") == placement_id), None)
        if x is None:
            raise NotFound(f"배치 없음: {placement_id}")
        return x

    def move_placement(self, pid: str, placement_id: str, center_xz=None, yaw_rad: float | None = None,
                       snap: bool = True, color: str | None = None, sku: str | None = None, size_m=None,
                       hex: str | None = None, base_m: float | None = None, slot: bool = True, top_hex: str | None = None,
                       part: str | None = None) -> dict:
        """part: 색을 바꿀 부위(상판·다리·쿠션 등). 없으면 가구의 대표 색(hex)."""
        room, p = self.get_room(pid), self.get_project(pid)
        x = self._find_placement(p, placement_id)
        changes = None
        if top_hex is not None:
            # 상판 색은 상판이 있는 가구만 (아일랜드 식탁·아일랜드·하부장·싱크대)
            if x["sku"] not in TOP_COLOUR_SKUS:
                raise Invalid("상판이 있는 가구만 상판 색을 고를 수 있어요")
            x["top_hex"] = top_hex.upper() or None  # 빈 글자 = 원래 상판
        if base_m is not None:  # 벽에 건 높이 (벽걸이 제품만. 천장·바닥을 넘는 값은 판정할 때 맞춘다)
            if x["sku"] == "decor:hood" or (not is_decor(x["sku"]) and mount_kind(self.catalog.get(x["sku"])) == WALL):
                x["base_m"], x["hung"] = float(base_m), True
                self._unlink_hood(p, x)
        if hex is not None:
            # 색을 마음대로 고르는 건 꾸미기 가구만 (LG 제품 색은 카탈로그에 있는 색만)
            if not is_decor(x["sku"]):
                raise Invalid("LG 제품은 제품에 있는 색만 고를 수 있어요")
            if part:  # 부위별 색은 part_colors에, 대표 색은 hex에 (예전에 칠한 가구와 같은 자리)
                parts = x.setdefault("part_colors", {})
                if hex:
                    parts[part] = hex.upper()
                else:
                    parts.pop(part, None)
            else:
                x["hex"] = hex.upper() or None  # 빈 글자 = 원래 색
        if size_m is not None:
            # 크기 조절은 꾸미기 가구만 (LG 제품 치수는 LGE.COM 값 그대로)
            if not is_decor(x["sku"]):
                raise Invalid("LG 제품은 크기를 바꿀 수 없어요")
            prod = self._item(x["sku"], size_m)
            d = prod.product_dims_mm
            x["size_m"] = [d.w / 1000, d.h / 1000, d.d / 1000]
        if sku is not None and sku != x["sku"] and is_decor(x["sku"]):
            raise Invalid("꾸미기 가구는 다른 것으로 바꿀 수 없어요")
        if sku is not None and sku != x["sku"]:
            # 색·재질 바꾸기 = 같은 모델 안의 다른 SKU로 바꾸기 (모양·치수가 같아서 자리는 그대로)
            if self.catalog.family_of(sku) is not self.catalog.family_of(x["sku"]):
                raise Invalid(f"{x['sku']}와 같은 모델이 아니라 바꿀 수 없음: {sku}")
            opt = self._color_option(self.catalog.get(sku), None)
            x["sku"] = sku
            x["color"], x["hex"] = (opt.color, opt.hex_approx) if opt else (None, None)
        prod = self._item(x["sku"], x.get("size_m"))
        if color is not None:
            opt = self._color_option(prod, color)
            x["color"], x["hex"] = opt.color, opt.hex_approx
        if center_xz is not None or yaw_rad is not None:
            pose = self._pose(room, prod, center_xz if center_xz is not None else x["center_xz"],
                              yaw_rad if yaw_rad is not None else x["yaw_rad"], snap, p)
            pose = self._settle(room, p, prod, pose, placement_id)
            self._unlink_hood(p, x)
            turned_only = center_xz is None or math.dist(pose.center_xz, x["center_xz"]) < 1e-3
            bay = self._slot(room, p, prod, pose, placement_id) if slot and not turned_only else None
            if bay:  # 빌트인을 장 줄로 옮겼으면 끼우고, 겹친 장은 칸을 내준다
                pose, changes = bay.pose, self._apply_slot(room, p, bay)
            elif floats(prod):
                pass  # 벽에 건 것은 벽에서 떼지 않는다
            elif turned_only:  # 제자리에서 돌리기만 했으면
                pose = self._off_wall(room, p, prod, pose, placement_id)
            self._carry(p, x, pose)
            x["center_xz"], x["yaw_rad"], x["wall_id"] = list(pose.center_xz), pose.yaw_rad, pose.wall_id
            x["zone_id"] = None  # 옮긴 순간부터 자유 배치
            if self._inset(x["sku"]):  # 같이 놓은 하부장도 따라온다
                p["scene_state"]["placements"] = [y for y in p["scene_state"]["placements"] if y.get("host_of") != placement_id]
                if self._undersink(x["sku"]) or not surface_under(pose.center_xz, self._tops(room, p, prod, placement_id)):
                    self._add_sink_cabinet(room, p, x)
        self._rejudge_all(room, p)
        self._save_project(p)
        out = self._rebuild(pid)
        out["placement"] = self._find_placement(out_p := self.get_project(pid), placement_id)
        out["scene_state"] = out_p["scene_state"]
        if changes and any(changes.values()):
            out["slot_changes"] = changes
        return out

    @staticmethod
    def _carry(p: dict, host: dict, pose: Pose) -> None:
        """식탁·아일랜드를 옮기거나 돌리면 그 위에 올려 둔 것도 같이 간다."""
        turn = pose.yaw_rad - host["yaw_rad"]
        c, n = math.cos(turn), math.sin(turn)
        for y in p["scene_state"]["placements"]:
            if y.get("on") != host["placement_id"]:
                continue
            dx, dz = y["center_xz"][0] - host["center_xz"][0], y["center_xz"][1] - host["center_xz"][1]
            y["center_xz"] = [pose.center_xz[0] + dx * c - dz * n, pose.center_xz[1] + dx * n + dz * c]
            y["yaw_rad"] = y["yaw_rad"] + turn
            y["wall_id"] = None

    @staticmethod
    def _unlink_hood(p: dict, hood: dict) -> None:
        """후드를 손으로 옮기거나 떼면 그때부터 인덕션을 따라가지 않는다 (인덕션에 다시 달리지도 않는다)."""
        cid = hood.pop("over", None)
        for y in p["scene_state"]["placements"]:
            if cid and y.get("placement_id") == cid:
                y["no_hood"] = True

    def delete_placement(self, pid: str, placement_id: str) -> dict:
        room, p = self.get_room(pid), self.get_project(pid)
        self._unlink_hood(p, self._find_placement(p, placement_id))
        # 빌트인 정수기와 같이 놓은 하부장도 같이 뺀다
        p["scene_state"]["placements"] = [y for y in p["scene_state"]["placements"]
                                          if y.get("placement_id") != placement_id and y.get("host_of") != placement_id]
        if "locked" in p["scene_state"]:  # 지운 물건은 고정 목록에서도 뺀다
            p["scene_state"]["locked"] = [i for i in p["scene_state"]["locked"] if i != placement_id]
        self._rejudge_all(room, p)
        self._save_project(p)
        return self._rebuild(pid)

    def set_locked(self, pid: str, item_id: str, locked: bool = True) -> dict:
        """고정: 놓은 물건이나 스캔 가구를 화면에서 끌어도 안 움직이게 한다. 목록만 적고 자리는 건드리지 않는다."""
        room, p = self.get_room(pid), self.get_project(pid)
        known = {y["placement_id"] for y in p["scene_state"]["placements"]} | {o.object_id for o in room.objects}
        if item_id not in known:
            raise NotFound(f"물건 없음: {item_id}")
        ids = [i for i in p["scene_state"].get("locked", []) if i != item_id and i in known]
        p["scene_state"]["locked"] = ids + [item_id] if locked else ids
        self._save_project(p)
        return self.get_project(pid)

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

    def set_object_color(self, pid: str, object_id: str, hex: str | None, part: str | None = None) -> dict:
        """스캔 가구 색 바꾸기. 스캔 파일은 그대로 두고 scene_state.object_colors에만 적는다. None이면 원래 색.
        part(상판·다리·쿠션 등)를 주면 그 부위 색만 scene_state.object_part_colors에 적는다."""
        room, p = self.get_room(pid), self.get_project(pid)
        if not any(o.object_id == object_id for o in room.objects):
            raise NotFound(f"가구 없음: {object_id}")
        if part:
            every = p["scene_state"].setdefault("object_part_colors", {})
            mine = every.setdefault(object_id, {})
            if hex is None:
                mine.pop(part, None)
            else:
                mine[part] = hex.upper()
            if not mine:
                every.pop(object_id, None)
            self._save_project(p)
            return self.get_project(pid)
        colors = p["scene_state"].setdefault("object_colors", {})
        if hex is None:
            colors.pop(object_id, None)
        else:
            colors[object_id] = hex.upper()
        self._save_project(p)
        return self.get_project(pid)

    def set_objects_hidden(self, pid: str, hidden: bool = True, object_ids: list[str] | None = None) -> dict:
        """스캔 가구를 한꺼번에 치우거나 되돌린다. object_ids가 없으면 전부."""
        room, p = self.get_room(pid), self.get_project(pid)
        known = [o.object_id for o in room.objects]
        ids = known if object_ids is None else object_ids
        missing = [i for i in ids if i not in known]
        if missing:
            raise NotFound(f"가구 없음: {', '.join(missing)}")
        hs = self._hidden(p)
        if hidden:
            hs.extend(i for i in ids if i not in hs)
        else:
            p["scene_state"]["hidden_objects"] = [i for i in hs if i not in ids]
        self._rejudge_all(room, p)
        self._save_project(p)
        return self._rebuild(pid)

    def move_object(self, pid: str, object_id: str, center_xz, yaw_rad: float) -> dict:
        """스캔 가구를 옮기거나 돌린다. 스캔 파일은 그대로 두고 scene_state.object_poses에만 적는다."""
        room, p = self._load_room(pid), self.get_project(pid)
        if not any(o.object_id == object_id for o in room.objects):
            raise NotFound(f"가구 없음: {object_id}")
        if len(center_xz) != 2:
            raise Invalid("center_xz는 [x, z]")
        poses = p["scene_state"].setdefault("object_poses", {})
        poses[object_id] = {"center_xz": [float(center_xz[0]), float(center_xz[1])], "yaw_rad": float(yaw_rad)}
        self._save_project(p)
        self._rejudge_all(self.get_room(pid), p)
        self._save_project(p)
        return self._rebuild(pid)

    def reset_object(self, pid: str, object_id: str) -> dict:
        room, p = self._load_room(pid), self.get_project(pid)
        if not any(o.object_id == object_id for o in room.objects):
            raise NotFound(f"가구 없음: {object_id}")
        (p["scene_state"].get("object_poses") or {}).pop(object_id, None)
        self._save_project(p)
        self._rejudge_all(self.get_room(pid), p)
        self._save_project(p)
        return self._rebuild(pid)

    # ---- 살아 보기: 집 위치·방향 (S6~S8) ----
    def set_site(self, pid: str, north_deg: float | None = None, region: str | None = None,
                 address: str | None = None, auto_north: bool = False) -> dict:
        """north_deg: 평면도 위쪽에서 북쪽까지 시계 방향 각도. region: 시·도 (채광용 위도·경도).
        address: 주소로 위도·경도를 찾고, 건물 외곽선이 있으면 그 방향으로 북쪽도 잡는다.
        auto_north: 북쪽을 추정한다 (가장 큰 창이 남쪽을 본다고 가정). 스캔에는 나침반 정보가 없다."""
        from sim.orientation import estimate_north

        p = self.get_project(pid)
        site = dict(p.get("site") or {"region": "서울", **REGIONS["서울"]})
        if region is not None:
            if region not in REGIONS:
                raise Invalid(f"지역은 {', '.join(REGIONS)} 중 하나")
            site.update(region=region, **REGIONS[region])
            site.pop("address", None)
            site.pop("approx", None)
            site.pop("area", None)
            site.pop("axis_deg", None)
        if address is not None:
            from sim.geocode import GeocodeError, geocode

            try:
                g = geocode(address)
            except GeocodeError as e:
                raise Invalid(str(e)) from e
            near = min(REGIONS, key=lambda k: (REGIONS[k]["lat"] - g["lat"]) ** 2 + (REGIONS[k]["lon"] - g["lon"]) ** 2)
            site.update(region=near, lat=g["lat"], lon=g["lon"], address=g["address"], axis_deg=g["axis_deg"], approx=g["approx"], area=g["area"])
            auto_north = True
        if auto_north and north_deg is None:
            est = estimate_north(self.get_room(pid), site.get("axis_deg"))
            if est:
                site.update(north_deg=est["north_deg"], north_basis=est["basis"])
        if north_deg is not None:
            if not 0 <= north_deg < 360:
                raise Invalid("north_deg는 0 이상 360 미만")
            site.update(north_deg=float(north_deg), north_basis="manual")
        p["site"] = site
        return self._save_project(p)

    def _sun_site(self, p: dict, day: str, time: str | None):
        """프로젝트 위치·북쪽 + 날짜·시각 → (Site, 날짜, 시각). 북쪽을 안 정했으면 Invalid."""
        import math
        from datetime import date as _date, datetime as _dt

        from sim.daylight import KST, Site

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
        return Site(lat=site["lat"], lon=site["lon"], north_rad=math.atan2(-math.cos(th), math.sin(th))), d, when

    def daylight(self, pid: str, day: str, time: str | None = None, heatmap: bool = True, path: bool = False) -> dict:
        """그 시각 해(3D 빛 방향·색·세기)와 볕 드는 자리. heatmap=False면 하루 직사광 격자를 건너뛴다(시간 슬라이더용).
        path=True면 하루 해 경로(5분 간격)도 준다: 화면이 시각 사이를 이어 그려 채광이 부드럽게 바뀐다."""
        from sim.daylight import daily_sun_hours, sun_light, sun_patches, sun_path
        from sim.orientation import window_facings

        p = self.get_project(pid)
        s, d, when = self._sun_site(p, day, time)
        site = p["site"]
        room = self.get_room(pid)
        pts = {x["placement_id"]: tuple(x["center_xz"]) for x in p["scene_state"]["placements"] if x.get("placement_id")}
        daily = daily_sun_hours(room, s, d, points=pts) if heatmap else None
        notes = daily.pop("assumptions") if daily else []
        return {"site": site, "date": d.isoformat(), "time": when.strftime("%H:%M"),
                "sun": sun_light(s, when),
                "patches": [{**x, "polygon": [[round(a, 3), round(b, 3)] for a, b in x["polygon"]]} for x in sun_patches(room, s, when)],
                "path": sun_path(s, d) if path else None,
                "facings": window_facings(room, site["north_deg"]),
                "daily": daily, "assumptions": notes + [f"위치: {site['region']} (위도 {site['lat']}, 경도 {site['lon']})"]}

    # ---- 제품 자리에서 살아 보기: 채광·와이파이를 결과 문장으로 ----
    SUN_SHY = ("refrigerator", "kimchi_refrigerator", "wine_cellar", "freezer")  # 직사광을 피해 설치하는 제품

    def life_check(self, pid: str, day: str | None = None) -> dict:
        """놓은 제품마다 그 자리의 하루 직사광 시간과 와이파이 세기. 북쪽·공유기를 안 정했으면 status=unknown."""
        from datetime import date as _date

        from sim.daylight import sun_hours_at
        from sim.wifi import WifiConfig, grade, rssi_at

        p, room = self.get_project(pid), self.get_room(pid)
        # 가구·가벽은 채광·와이파이 안내가 필요 없다 (LG 가전만)
        pls = [x for x in p["scene_state"]["placements"] if x.get("placement_id") and not is_decor(x["sku"])]
        items = {x["placement_id"]: {} for x in pls}
        day = day or _date.today().isoformat()
        estimated = False
        sp = p
        if (p.get("site") or {}).get("north_deg") is None:
            # 북쪽을 아직 안 정했으면 저장하지 않고 추정값으로 계산한다 (가장 큰 창이 남쪽을 본다고 가정)
            from sim.orientation import estimate_north
            est = estimate_north(room, (p.get("site") or {}).get("axis_deg"))
            if est:
                base = {"region": "서울", **REGIONS["서울"], **(p.get("site") or {})}
                sp, estimated = {**p, "site": {**base, "north_deg": est["north_deg"]}}, True
        try:
            site, d, _ = self._sun_site(sp, day, None)
        except Invalid as e:
            if "형식" in str(e):
                raise
            site = None
        hours = sun_hours_at(room, site, d, {x["placement_id"]: tuple(x["center_xz"]) for x in pls}) if site else {}
        rt = p["scene_state"].get("router")
        cfg = WifiConfig.from_env(rt.get("band", "5")) if rt else None
        for x in pls:
            k = x["placement_id"]
            try:
                cat = self.catalog.get(x["sku"]).category
            except KeyError:
                cat = ""
            if site is None:
                items[k]["daylight"] = {"status": "unknown", "hours": None, "label": "집 방향을 정하면 알려 드려요"}
            else:
                h = float(hours[k])
                shy = cat in self.SUN_SHY and h >= 1
                label = (f"하루 약 {h:.1f}시간 볕이 들어요" if h >= 0.5 else "직사광이 거의 안 들어요") + (" · 직사광은 피하는 게 좋아요" if shy else "")
                items[k]["daylight"] = {"status": "warn" if shy else "ok", "hours": round(h, 1), "estimated": estimated,
                                        "label": label + (" (집 방향은 큰 창 기준 추정)" if estimated else "")}
            if cfg is None:
                items[k]["wifi"] = {"status": "unknown", "grade": None, "dbm": None, "label": "공유기 자리를 정하면 알려 드려요"}
            else:
                # 공유기 높이(올려 둔 가구 윗면)와 제품 가운데 높이 사이로 잰다
                mid = (x.get("base_m") or 0.0) + (x["size_m"][1] / 2 if x.get("size_m") else 0.0)
                v = rssi_at(room, tuple(rt["center_xz"]), tuple(x["center_xz"]), cfg, blockers=self._metal_blockers(p, exclude=k),
                            tx_h=float(rt.get("height_m") or 0.0), rx_h=mid)
                g = grade(v, cfg)
                items[k]["wifi"] = {"status": "warn" if g == "weak" else "ok", "grade": g, "dbm": round(v, 1),
                                    "label": {"good": "연결이 잘 돼요", "ok": "연결돼요", "weak": "신호가 약해요"}[g]}
        return {"date": d.isoformat() if site else day, "items": items}

    # ---- 살아 보기: 와이파이 (S7) ----
    METAL = ("refrigerator", "kimchi_refrigerator")
    WIFI_RX_M = 1.0

    def _metal_blockers(self, p: dict, exclude: str | None = None) -> list:
        from recommender.pose import rect
        import math as _m
        out = []
        for x in p["scene_state"]["placements"]:
            if exclude and x.get("placement_id") == exclude:
                continue
            try:
                cat = self.catalog.get(x["sku"]).category
            except KeyError:
                continue
            if cat in self.METAL and x.get("size_m"):
                out.append((rect(tuple(x["center_xz"]), x["yaw_rad"] - _m.pi / 2, x["size_m"][0], x["size_m"][2]),
                            (x.get("base_m") or 0.0) + x["size_m"][1]))
        return out

    WIFI_BANDS = ("2.4", "5", "6")
    CHANNEL_MHZ = (20, 40, 80, 160)
    ENCLOSURES = ("open", "cabinet", "metal")
    # 웹 apps/web/js/wifi/materials.js의 MATERIALS와 같은 이름
    WALL_MATERIALS = ("drywall", "wood", "glass", "double_glass", "lowe_glass", "brick", "concrete", "reinforced_concrete", "bathroom", "metal")

    def set_router(self, pid: str, center_xz, band: str = "5", yaw_rad: float | None = None,
                   channel_mhz: int | None = None, enclosure: str | None = None) -> dict:
        if band not in self.WIFI_BANDS:
            raise Invalid("band는 2.4, 5, 6")
        if channel_mhz is not None and channel_mhz not in self.CHANNEL_MHZ:
            raise Invalid("채널 폭은 20, 40, 80, 160 MHz")
        if enclosure is not None and enclosure not in self.ENCLOSURES:
            raise Invalid("설치 상태는 open, cabinet, metal")
        if len(center_xz) != 2:
            raise Invalid("center_xz는 [x, z]")
        p = self.get_project(pid)
        prev = p["scene_state"].get("router") or {}
        # 방향은 화면 표시용 (신호 계산은 무지향). 자리만 옮기면 원래 방향을 그대로 둔다
        yaw = float(yaw_rad) if yaw_rad is not None else float(prev.get("yaw_rad", 0.0))
        xz = (float(center_xz[0]), float(center_xz[1]))
        rt = {"center_xz": list(xz), "band": band, "yaw_rad": yaw, "height_m": 0.0}  # 높이는 저장할 때 채운다
        for k, v in (("channel_mhz", channel_mhz), ("enclosure", enclosure)):  # 안 주면 전에 정한 값
            if v is not None or prev.get(k) is not None:
                rt[k] = v if v is not None else prev[k]
        p["scene_state"]["router"] = rt
        return self._save_project(p)

    def set_wall_material(self, pid: str, wall_id: str, material: str | None) -> dict:
        """와이파이 계산에 쓰는 벽 재질. 스캔으로는 알 수 없어서 고르지 않으면 바깥벽 철근콘크리트·안쪽 콘크리트로 본다."""
        room, p = self.get_room(pid), self.get_project(pid)
        added = {x["placement_id"] for x in p["scene_state"].get("placements", []) if x.get("sku") in ("decor:wall", "decor:partition")}
        if wall_id not in {w.wall_id for w in room.walls} | added:
            raise NotFound(f"벽 없음: {wall_id}")
        if material is not None and material not in self.WALL_MATERIALS:
            raise Invalid(f"모르는 벽 재질: {material}")
        wm = p["scene_state"].setdefault("wall_materials", {})
        if material is None:
            wm.pop(wall_id, None)
        else:
            wm[wall_id] = material
        return self._save_project(p)

    # 공유기를 올려 둘 수 있는 것: 놓은 것(가전·가구) 중 윗면이 2.2 m 이하인 것(웹 3D도 같은 규칙),
    # 스캔 가구 중 탁자·수납장. 가벽·파티션·러그는 빼고
    SURFACE_MAX_M = 2.2
    NOT_SURFACE = frozenset({"decor:wall", "decor:partition", "decor:rug", "decor:plant", "decor:lamp"})
    SURFACE_SCANNED = frozenset({"table", "storage"})

    def _surface_top(self, p: dict, xz: tuple[float, float]) -> float:
        """그 자리 아래 가구 윗면 높이(m). 아무것도 없으면 바닥(0). 겹치면 가장 높은 윗면."""
        return self._surface_under(p, xz)[0]

    def _surface_under(self, p: dict, xz: tuple[float, float]) -> tuple[float, str | None]:
        """그 자리 아래 가장 높은 윗면 (높이 m, 배치 id 또는 스캔 가구 id). 바닥이면 (0, None)."""
        def inside(c, yaw, w, d):
            dx, dz = xz[0] - c[0], xz[1] - c[1]
            u = dx * math.cos(yaw) + dz * math.sin(yaw)
            v = -dx * math.sin(yaw) + dz * math.cos(yaw)
            return abs(u) <= w / 2 and abs(v) <= d / 2

        tops: list[tuple[float, str | None]] = [(0.0, None)]
        for x in p["scene_state"].get("placements", []):
            if x["sku"] in self.NOT_SURFACE or not x.get("size_m"):
                continue
            w, h, d = x["size_m"]
            # 놓은 제품은 폭 방향이 yaw - 90° (웹 3D·동선과 같은 규칙)
            top = float(x.get("base_m") or 0.0) + h  # 식탁 위에 올려 둔 가전이면 그 가전 윗면
            if top <= self.SURFACE_MAX_M and inside(x["center_xz"], x.get("yaw_rad", math.pi / 2) - math.pi / 2, w, d):
                tops.append((top, x["placement_id"]))
        hidden = set(p["scene_state"].get("hidden_objects") or [])
        poses = p["scene_state"].get("object_poses") or {}  # 지금 저장하려는 자리 (DB의 옛 자리 말고)
        for o in self._load_room(p["project_id"]).objects:
            if o.category not in self.SURFACE_SCANNED or o.object_id in hidden:
                continue
            q = poses.get(o.object_id)
            c, yaw = ((q["center_xz"][0], q["center_xz"][1]), q["yaw_rad"]) if q else ((o.position[0], o.position[2]), o.yaw_rad)
            if inside(c, yaw, o.bbox_m.w, o.bbox_m.d):
                tops.append((o.position[1] + o.bbox_m.h / 2, o.object_id))
        top, ref = max(tops, key=lambda t: t[0])
        return round(top, 3), ref

    def wifi(self, pid: str, band: str | None = None) -> dict:
        from sim.wifi import WifiConfig, coverage, grade

        p = self.get_project(pid)
        rt = p["scene_state"].get("router")
        if not rt:
            raise Invalid("와이파이를 보려면 먼저 평면도에 공유기를 놓으세요 (또는 추천 자리 찾기)")
        cfg = WifiConfig.from_env(band or rt.get("band", "5"))
        room = self._standing(self.get_room(pid), p)
        # 받는 쪽은 손에 든 기기 높이(1 m)로 본다. 공유기를 선반 위에 올리면 냉장고 너머로도 닿는다
        g = coverage(room, tuple(rt["center_xz"]), cfg, blockers=self._metal_blockers(p),
                     tx_h=float(rt.get("height_m") or 0.0), rx_h=self.WIFI_RX_M)
        g["router_height_m"] = float(rt.get("height_m") or 0.0)
        from sim.daylight import _inside
        zones = []
        for z in self.list_zones(pid):
            vs = [g["values"][j][i] for j in range(g["ny"]) for i in range(g["nx"])
                  if g["values"][j][i] is not None and _inside((g["origin"][0] + (i + .5) * g["cell_m"], g["origin"][1] + (j + .5) * g["cell_m"]), z["polygon_m"])]
            share = {k: round(sum(1 for v in vs if grade(v, cfg) == k) / len(vs), 3) for k in ("good", "ok", "weak")} if vs else {}
            zones.append({"zone_id": z["zone_id"], "name": z.get("name") or z["purpose"], "share": share,
                          "min_dbm": min(vs) if vs else None})
        g["zones"] = zones
        g["band"] = cfg.band
        return g

    def wifi_best(self, pid: str, band: str = "5") -> dict:
        from sim.wifi import WifiConfig, best_router_spot

        p = self.get_project(pid)
        cfg = WifiConfig.from_env(band)
        spot, worst = best_router_spot(self.get_room(pid), cfg, cell_m=0.25, blockers=self._metal_blockers(p))
        return {"center_xz": [round(spot[0], 3), round(spot[1], 3)], "min_dbm": round(worst, 1), "band": band}

    # ---- 살아 보기: 동선 (S8) ----
    MARKS = {"sink": "싱크대", "entrance": "현관", "start": "출발"}
    DOOR, SINK = "decor:door", "decor:sink"
    DOOR_GAP_DEPTH_M = 0.5  # 문 자리에서 벽 두께를 넘겨 트는 깊이

    def set_mark(self, pid: str, name: str, center_xz=None) -> dict:
        if name not in self.MARKS:
            raise NotFound(f"표시 이름은 {', '.join(self.MARKS)}")
        p = self.get_project(pid)
        marks = p["scene_state"].setdefault("marks", {})
        if center_xz is None:
            marks.pop(name, None)
        else:
            if len(center_xz) != 2 or not all(math.isfinite(float(v)) for v in center_xz):
                raise Invalid("center_xz는 숫자 [x, z]")
            marks[name] = [float(center_xz[0]), float(center_xz[1])]
        return self._save_project(p)

    def flow(self, pid: str) -> dict:
        import math as _m

        from recommender.pose import rect
        from sim.flow import FlowConfig, plan_routes

        p = self.get_project(pid)
        room = self._standing(self.get_room(pid), p)
        marks = p["scene_state"].get("marks") or {}
        if "entrance" in marks:  # 고객이 현관을 직접 찍었으면 그 자리 가장 가까운 문을 현관으로
            ex, ey = marks["entrance"]
            doors = [o for o in room.openings if o.type in ("door", "opening") and o.wall_id]
            if doors:
                def dpos(o):
                    w = room.wall(o.wall_id)
                    L = _m.dist(w.start, w.end) or 1
                    u = (o.offset_m + o.width_m / 2) / L
                    return (w.start[0] + (w.end[0] - w.start[0]) * u, w.start[1] + (w.end[1] - w.start[1]) * u)
                keep = min(doors, key=lambda o: _m.dist(dpos(o), (ex, ey)))
                room = room.model_copy(update={"openings": [o for o in room.openings if o.type == "window" or o is keep]})
        targets, extra, gaps, names, cats, sink_at = {}, [], [], {}, {}, None
        for x in p["scene_state"]["placements"]:
            if not x.get("size_m") or not x.get("placement_id"):
                continue
            w, _, d = x["size_m"]
            yaw = x["yaw_rad"]
            if is_flat(x["sku"]):  # 러그는 밟고 지나간다
                continue
            if x["sku"] == self.DOOR and x.get("verdict") != "no_fit":  # 열리는 문은 벽에 난 길
                gaps.append(rect(tuple(x["center_xz"]), yaw - _m.pi / 2, w, max(d, self.DOOR_GAP_DEPTH_M)))
                continue
            extra.append(rect(tuple(x["center_xz"]), yaw - _m.pi / 2, w, d))
            reach = d / 2 + 0.35  # 제품 정면 앞에 서는 자리
            if x["sku"] == self.SINK:  # 놓은 싱크대 앞이 작업 삼각형의 싱크 자리
                sink_at = (x["center_xz"][0] + _m.cos(yaw) * reach, x["center_xz"][1] + _m.sin(yaw) * reach)
            if is_decor(x["sku"]):  # 가구·가벽은 피해 가기만, 걸어가는 목적지는 LG 가전
                continue
            targets[x["placement_id"]] = (x["center_xz"][0] + _m.cos(yaw) * reach, x["center_xz"][1] + _m.sin(yaw) * reach)
            try:
                prod = self._item(x["sku"], x.get("size_m"))
                names[x["placement_id"]], cats[x["placement_id"]] = prod.name, prod.category
            except KeyError:
                names[x["placement_id"]] = x["sku"]
        if sink_at or "sink" in marks:
            targets["sink"], names["sink"] = sink_at or tuple(marks["sink"]), self.MARKS["sink"]
        tri = None
        fr = next((k for k, c in cats.items() if c in ("refrigerator", "kimchi_refrigerator")), None)
        ck = next((k for k, c in cats.items() if c == "cooktop"), None)
        if fr and ck and "sink" in targets:
            tri = (fr, "sink", ck)
        out = plan_routes(room, targets, FlowConfig.from_env(), hidden=p["scene_state"].get("hidden_objects") or [],
                          extra=extra, triangle=tri, start=marks.get("start"), gaps=gaps)
        out["names"] = names
        out["cats"] = cats  # 웹이 "냉장고 앞까지 걸어가요"처럼 종류 이름으로 말하게
        out["marks"] = marks
        return out

    def remove_product(self, pid: str, zone_id: str, sku: str) -> dict:
        p = self.get_project(pid)
        p["scene_state"]["placements"] = [x for x in p["scene_state"]["placements"]
                                          if not (x["sku"] == sku and x.get("zone_id") == zone_id)]
        self._save_project(p)
        return self._rebuild(pid)

    def render(self, pid: str, day: str | None = None, time: str | None = None) -> dict:
        """렌더 이미지. 날짜·시각을 주고 북쪽이 정해져 있으면 채광과 같은 해로 비춘다."""
        sun = None
        if day:
            from sim.daylight import sun_light

            p = self.get_project(pid)
            if (p.get("site") or {}).get("north_deg") is not None:
                s, _, when = self._sun_site(p, day, time)
                sun = sun_light(s, when)
        return self._rebuild(pid, render=True, sun=sun)

    def surface_placements(self, placements: list[dict], find) -> list[dict]:
        """렌더가 재질대로 그리게, 재질을 아는 제품의 배치에 겉면 값(surface)을 붙인다. 저장된 상태는 건드리지 않는다"""
        from .surface import surface_for

        out = []
        for pl in placements:
            prod = find(pl.get("sku")) if not str(pl.get("sku") or "").startswith("decor:") else None
            look = surface_for(prod) if prod else None
            out.append({**pl, "surface": look} if look else pl)
        return out

    def _scene_inputs(self, pid: str, sun: dict | None = None):
        """지금 집 모습: (방, 스캔 파일, 장면 상태). 치운 가구와 철거한 벽은 빠져 있다"""
        p = self.get_project(pid)
        room = self.get_room(pid)
        hidden = set(p["scene_state"].get("hidden_objects") or [])
        if hidden:  # 치운 가구는 3D·렌더에서 뺀다
            room = room.model_copy(update={"objects": [o for o in room.objects if o.object_id not in hidden]})
        room = self._standing(room, p)  # 철거한 벽과 그 벽의 문·창도 뺀다
        usdz = self.root / p["scan"]["usdz"] if p["scan"].get("usdz") else None  # 도면으로 만든 집은 스캔 파일이 없다
        state = {**p["scene_state"], "title": f"{pid} · {p['style'].get('prompt') or ''}".strip(" ·")}
        state["placements"] = self.surface_placements(state.get("placements") or [], self.catalog.get)
        if sun:
            state["sun"] = sun
        return room, usdz, state

    def _rebuild(self, pid: str, render: bool = False, sun: dict | None = None) -> dict:
        from worker.runner import build_scene

        room, usdz, state = self._scene_inputs(pid, sun)
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

    def find(self, cond: Conditions, pid: str | None = None, zone_id: str | None = None) -> dict:
        """조건으로 제품 찾기. 같은 모델의 색만 다른 제품은 가장 앞선 것 하나로 묶는다.

        공간 판정은 직접 넣은 치수가 있으면 그 값, 없으면 그려 둔 영역(zone_id, 안 주면 제품 용도에 맞는 첫 영역) 기준."""
        zone_fit, used_zone = None, None
        typed = cond.space_w or cond.space_h or cond.space_d
        if pid and not typed:
            room = self.get_room(pid)
            zones = [self._zone_model(pid, zone_id)] if zone_id else \
                [self._zone_model(pid, z["zone_id"]) for z in self.list_zones(pid)]
            if zones:
                used_zone = zones[0].zone_id if zone_id or len(zones) == 1 else None

                def zone_fit(p: Product):
                    z = next((z for z in zones if z.purpose in p.zone_fit), None)
                    return check_fit(room, z, p, self.fit_cfg).to_dict() if z else None
        res = find_products(self.catalog.products, replace(cond, limit=None), self.fit_cfg, zone_fit)
        fam_of = {v["sku"]: (f, v) for f in self.catalog.families() for v in f["variants"]}
        seen, items = set(), []
        for it in res["items"]:
            f, v = fam_of[it["product"]["sku"]]
            if f["family_id"] in seen:
                continue
            seen.add(f["family_id"])
            items.append({**it, "family_id": f["family_id"], "family_name": f["name"], "variants": len(f["variants"]),
                          "thumb": v.get("thumb")})
        return {"items": items[:cond.limit] if cond.limit else items, "total": len(items), "facets": res["facets"],
                "zone_id": used_zone,
                "margins_mm": {"scanned": self.fit_cfg.margin_scanned_mm, "measured": self.fit_cfg.margin_measured_mm}}

    def install_check(self, pid: str) -> dict:
        """설치 전 확인 목록: 놓은 제품마다 자리·앞 공간·잴 벽·들여오는 길·현장 확인 항목."""
        p, room = self.get_project(pid), self.get_room(pid)
        # 꾸미기 가구는 사는 물건이 아니라 빼고 LG 제품만 본다
        pls = [x for x in p["scene_state"]["placements"] if not is_decor(x.get("sku"))]
        return install_checklist(room, pls, self.catalog.get)

    def results(self, pid: str) -> dict:
        """F10 결과 화면 데이터 한 번에."""
        return {"project": self.get_project(pid), "room": self.get_room(pid).model_dump(),
                "zones": [{**z, "recommendation": self.recommend(pid, z["zone_id"])["items"]} for z in self.list_zones(pid)]}
