"""FastAPI 백엔드 (기획 §6.1 api). 웹 정적 파일도 함께 서빙한다 (plan.md ADR-8)."""
from __future__ import annotations

import mimetypes
import os
import time
from collections import defaultdict, deque
from functools import lru_cache
from typing import Annotated, Literal, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from core import config
from core.decor import decor_items
from core.accounts import AuthError, Conflict, Forbidden, is_approved_tech
from core.service import Invalid, NotFound, Service
from core.photoreal import Unavailable
from core.service_photoreal import TooMany
from recommender.finder import Conditions

WEB_DIR = config.ROOT / "apps" / "web"
# Windows 레지스트리에 따라 .js가 text/plain으로 잡히면 모듈 스크립트가 안 뜬다. 웹앱 매니페스트도 함께 지정.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("application/manifest+json", ".webmanifest")
MAX_UPLOAD = int(os.getenv("MAX_UPLOAD_MB", 200)) * 1024 * 1024


@lru_cache
def get_service() -> Service:
    return Service()


app = FastAPI(title="LG 빌트인 공간 설계 (시연)", version="0.1.0")


def cors_origins() -> list[str]:
    """웹을 다른 주소(Cloudflare Pages 등)에 올렸을 때 API를 불러도 되는 웹 주소. 쉼표로 구분, 비우면 CORS 안 씀."""
    return [o.strip().rstrip("/") for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]


if cors_origins():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["content-type", "authorization"],
        max_age=600,
    )


@app.exception_handler(NotFound)
async def _nf(_, e):
    return JSONResponse({"detail": str(e).strip("'")}, status_code=404)


@app.exception_handler(Invalid)
async def _inv(_, e):
    return JSONResponse({"detail": str(e)}, status_code=422)


@app.exception_handler(KeyError)
async def _ke(_, e):
    return JSONResponse({"detail": f"찾을 수 없음: {e}"}, status_code=404)


@app.exception_handler(AuthError)
async def _auth(_, e):
    return JSONResponse({"detail": str(e) or "로그인이 필요합니다"}, status_code=401,
                        headers={"WWW-Authenticate": "Bearer"})


@app.exception_handler(Forbidden)
async def _forbidden(_, e):
    return JSONResponse({"detail": str(e) or "권한이 없습니다"}, status_code=403)


@app.exception_handler(Unavailable)
async def _unavail(_, e):
    return JSONResponse({"detail": str(e)}, status_code=503)


@app.exception_handler(TooMany)
async def _toomany(_, e):
    return JSONResponse({"detail": str(e)}, status_code=429)


@app.exception_handler(Conflict)
async def _conflict(_, e):
    return JSONResponse({"detail": str(e)}, status_code=409)


S = Depends(get_service)


# ---------- 로그인 ----------
# 웹(housetwin.pages.dev)과 API가 다른 사이트라서 쿠키 대신 Authorization: Bearer 토큰을 쓴다.
def _bearer(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def optional_user(authorization: Optional[str] = Header(None), s: Service = S) -> Optional[dict]:
    return s.accounts.user_for_token(_bearer(authorization))


def current_user(u: Optional[dict] = Depends(optional_user)) -> dict:
    if u is None:
        raise AuthError("로그인이 필요합니다")
    return u


def technician_user(u: dict = Depends(current_user)) -> dict:
    if not is_approved_tech(u):
        raise Forbidden("승인된 기사 계정만 볼 수 있어요" if u["role"] == "technician" else "기사 전용 화면입니다")
    return u


def admin_user(u: dict = Depends(current_user)) -> dict:
    if u["role"] != "admin":
        raise Forbidden("관리자만 할 수 있어요")
    return u


ME, ME_OPT, TECH, ADMIN = Depends(current_user), Depends(optional_user), Depends(technician_user), Depends(admin_user)

# 비밀번호 대입 막기: 10분 동안 같은 이메일로 5번, 같은 IP에서 20번 틀리면 잠깐 막는다
# (강의실처럼 여러 명이 같은 공유기를 쓰면 IP가 같아서 IP 쪽은 넉넉하게)
LOGIN_WINDOW_S = 600
LOGIN_MAX_FAILS = {"e": 5, "ip": 20}
_fails: dict[str, deque] = defaultdict(deque)


def reset_login_limits() -> None:
    _fails.clear()


def _limited(keys: list[str]) -> bool:
    cut = time.monotonic() - LOGIN_WINDOW_S
    for k in keys:
        q = _fails[k]
        while q and q[0] < cut:
            q.popleft()
        if len(q) >= LOGIN_MAX_FAILS[k.split(":", 1)[0]]:
            return True
    return False


class SignupIn(BaseModel):
    model_config = {"extra": "forbid"}
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=40)
    role: str = Field(pattern=r"^(customer|technician)$")
    phone: Optional[str] = Field(None, max_length=30)
    center: Optional[str] = Field(None, max_length=60)
    employee_no: Optional[str] = Field(None, max_length=30)


class LoginIn(BaseModel):
    model_config = {"extra": "forbid"}
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class TechStatusIn(BaseModel):
    model_config = {"extra": "forbid"}
    status: str = Field(pattern=r"^(pending|approved|suspended|rejected)$")


class ClaimIn(BaseModel):
    model_config = {"extra": "forbid"}
    share_token: str = Field(min_length=1, max_length=64)


class SaveIn(BaseModel):
    model_config = {"extra": "forbid"}
    kind: str = Field("manual", pattern=r"^(manual|auto)$")
    label: Optional[str] = Field(None, max_length=60)


@app.post("/api/auth/signup", status_code=201)
def signup(body: SignupIn, s: Service = S):
    try:
        token, user = s.accounts.signup(body.email, body.password, body.name, body.role, body.phone, body.center,
                                        body.employee_no)
    except (ValueError, TypeError) as e:
        raise HTTPException(422, str(e))
    return {"token": token, "user": user}


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request, s: Service = S):
    keys = [f"e:{body.email.strip().lower()}", f"ip:{request.client.host if request.client else '-'}"]
    if _limited(keys):
        raise HTTPException(429, "로그인 시도가 너무 많아요. 10분 뒤에 다시 해 주세요")
    try:
        token, user = s.accounts.login(body.email, body.password)
    except AuthError:
        for k in keys:
            _fails[k].append(time.monotonic())
        raise
    return {"token": token, "user": user}


@app.post("/api/auth/logout", status_code=204)
def logout(authorization: Optional[str] = Header(None), s: Service = S):
    tok = _bearer(authorization)
    if tok:
        s.accounts.logout(tok)


@app.get("/api/auth/me")
def me(u: dict = ME):
    return u


@app.get("/api/me/projects")
def my_projects(u: dict = ME, s: Service = S):
    return s.my_projects(u)


@app.get("/api/admin/technicians")
def admin_technicians(_: dict = ADMIN, s: Service = S):
    return s.accounts.technicians()


@app.patch("/api/admin/technicians/{uid}")
def admin_set_technician(uid: str, body: TechStatusIn, _: dict = ADMIN, s: Service = S):
    return s.accounts.set_technician_status(uid, body.status)


@app.post("/api/projects/{pid}/claim")
def claim_project(pid: str, body: ClaimIn, u: dict = ME, s: Service = S):
    return s.claim_project(pid, u, body.share_token)


@app.get("/api/projects/{pid}/saves")
def list_saves(pid: str, u: dict = ME, s: Service = S):
    return s.list_saves(pid, u)


@app.post("/api/projects/{pid}/saves", status_code=201)
def save_project(pid: str, body: SaveIn, u: dict = ME, s: Service = S):
    return s.save_snapshot(pid, u, body.kind, body.label)


@app.post("/api/projects/{pid}/saves/{sid}/restore")
def restore_save(pid: str, sid: str, u: dict = ME, s: Service = S):
    return s.restore_save(pid, sid, u)


@app.delete("/api/projects/{pid}/saves/{sid}", status_code=204)
def delete_save(pid: str, sid: str, u: dict = ME, s: Service = S):
    s.delete_save(pid, sid, u)


# ---------- 입력 모델 ----------
class RequestIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    contact: str = Field(min_length=1, max_length=50)
    address: str = Field(min_length=1, max_length=200)
    preferred_at: Optional[str] = None


class MeasureIn(BaseModel):
    length_m: Optional[float] = None
    height_m: Optional[float] = None
    depth_m: Optional[float] = None
    by: str = "technician"


class ZoneIn(BaseModel):
    purpose: str = Field(pattern=r"^[a-z_]{2,30}$")
    polygon_m: list[tuple[float, float]] = Field(min_length=3, max_length=64)
    wall_ids: Optional[list[str]] = None
    name: Optional[str] = None


class ZonePatch(BaseModel):
    purpose: Optional[str] = None
    polygon_m: Optional[list[tuple[float, float]]] = None
    wall_ids: Optional[list[str]] = None
    name: Optional[str] = None


class StyleIn(BaseModel):
    prompt: Optional[str] = None
    palette: Optional[list[str]] = None
    materials: Optional[list[str]] = None
    zone_id: Optional[str] = None


class MaterialIn(BaseModel):
    target: str
    hex_color: str
    finish: Optional[str] = None
    wall_id: Optional[str] = None


class PlaceIn(BaseModel):
    """zone_id를 주면 영역 안 자동 배치, center_xz를 주면 그 자리에 놓기."""
    model_config = {"extra": "forbid"}
    sku: str
    zone_id: Optional[str] = None
    center_xz: Optional[list[float]] = Field(None, min_length=2, max_length=2)
    yaw_rad: float = 0.0
    snap: bool = True
    color: Optional[str] = None
    size_m: Optional[list[float]] = Field(None, min_length=3, max_length=3, description="꾸미기 가구 크기 (m, 폭·높이·깊이)")
    base_m: Optional[float] = Field(None, ge=0, le=10, description="벽걸이 제품을 거는 높이 (바닥에서 밑면까지, m)")
    slot: bool = Field(True, description="빌트인을 가까운 장 줄에 끼워 넣기 (겹친 장은 칸을 내준다)")


class PoseIn(BaseModel):
    model_config = {"extra": "forbid"}
    sku: str
    center_xz: list[float] = Field(min_length=2, max_length=2)
    yaw_rad: float = 0.0
    snap: bool = True
    placement_id: Optional[str] = None
    size_m: Optional[list[float]] = Field(None, min_length=3, max_length=3, description="꾸미기 가구 크기 (m, 폭·높이·깊이)")
    base_m: Optional[float] = Field(None, ge=0, le=10, description="벽걸이 제품을 거는 높이 (바닥에서 밑면까지, m)")
    slot: bool = Field(True, description="빌트인을 가까운 장 줄에 끼워 넣기 (겹친 장은 칸을 내준다)")


class MoveIn(BaseModel):
    model_config = {"extra": "forbid"}
    center_xz: Optional[list[float]] = Field(None, min_length=2, max_length=2)
    yaw_rad: Optional[float] = None
    snap: bool = True
    color: Optional[str] = None
    sku: Optional[str] = Field(None, description="같은 모델의 다른 색·재질 SKU")
    hex: Optional[str] = Field(None, pattern=r"^(#[0-9A-Fa-f]{6})?$", description="꾸미기 가구 색. 빈 글자면 원래 색으로")
    size_m: Optional[list[float]] = Field(None, min_length=3, max_length=3, description="꾸미기 가구 크기 (m, 폭·높이·깊이)")
    base_m: Optional[float] = Field(None, ge=0, le=10, description="벽걸이 제품을 거는 높이 (바닥에서 밑면까지, m)")
    slot: bool = Field(True, description="빌트인을 가까운 장 줄에 끼워 넣기 (겹친 장은 칸을 내준다)")


class SiteIn(BaseModel):
    model_config = {"extra": "forbid"}
    north_deg: Optional[float] = None
    region: Optional[str] = None
    address: Optional[str] = Field(default=None, max_length=200)
    auto_north: bool = False


class RouterIn(BaseModel):
    model_config = {"extra": "forbid"}
    center_xz: list[float] = Field(min_length=2, max_length=2)
    band: str = "5"
    yaw_rad: float | None = None


class HiddenIn(BaseModel):
    hidden: bool = True


class ObjectPoseIn(BaseModel):
    model_config = {"extra": "forbid"}
    center_xz: list[float] = Field(..., min_length=2, max_length=2)
    yaw_rad: float = 0.0


class HiddenManyIn(BaseModel):
    """object_ids가 없으면 스캔 가구 전부"""
    model_config = {"extra": "forbid"}
    hidden: bool = True
    object_ids: Optional[list[str]] = Field(None, max_length=500)


# ---------- 엔드포인트 ----------
@app.get("/api/health")
def health(s: Service = S):
    from worker.runner import blender_bin
    return {"ok": True, "blender": blender_bin(), "catalog_size": len(s.catalog.products),
            "catalog_demo_only": sum(p.demo_only for p in s.catalog.products)}


@app.post("/api/requests", status_code=201)
def create_request(body: RequestIn, s: Service = S):
    return s.create_request(body.name, body.contact, body.address, body.preferred_at)


@app.get("/api/requests")
def list_requests(_: dict = TECH, s: Service = S):
    """고객 이름·연락처·주소가 있어서 승인된 기사와 관리자만 본다."""
    return s.list_requests()


@app.post("/api/projects", status_code=201)
async def upload_scan(file: UploadFile = File(...), request_id: Optional[str] = Form(None),
                      scanned_by: str = Form("technician"), name: Optional[str] = Form(None),
                      u: Optional[dict] = ME_OPT, s: Service = S):
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "파일이 너무 큽니다")
    if not data:
        raise HTTPException(422, "빈 파일")
    return s.create_project_from_usdz(data, file.filename or "room.usdz", request_id or None, scanned_by, user=u, name=name)


MAX_PLAN_UPLOAD = 20 * 1024 * 1024  # 도면 한 장. 이보다 크면 읽는 쪽에서 받지 않는다


@app.post("/api/projects/from-plan", status_code=201)
async def upload_plan_as_home(file: UploadFile = File(...), name: Optional[str] = Form(None),
                              u: Optional[dict] = ME_OPT, s: Service = S):
    """스캔 없이 도면만으로 집을 만든다."""
    data = await file.read()
    if len(data) > MAX_PLAN_UPLOAD:
        raise HTTPException(413, "도면 파일이 너무 커요. 20MB 아래로 올려 주세요")
    if not data:
        raise HTTPException(422, "빈 파일")
    return await run_in_threadpool(s.create_project_from_plan, data, file.filename or "floorplan.png", user=u, name=name)


@app.get("/api/projects")
def list_projects(u: Optional[dict] = ME_OPT, s: Service = S):
    return s.visible_projects(u)


@app.delete("/api/projects/{pid}", status_code=204)
def delete_project(pid: str, t: Optional[str] = None, u: Optional[dict] = ME_OPT, s: Service = S):
    s.delete_project(pid, u, t)


@app.get("/api/projects/{pid}")
def get_project(pid: str, s: Service = S):
    return s.project_view(pid)


@app.get("/api/projects/{pid}/version")
def get_version(pid: str, s: Service = S):
    """웹이 폴링: 채팅(MCP)에서 상태가 바뀌면 version이 오른다."""
    return {"version": s.get_project(pid)["version"]}


@app.get("/api/projects/{pid}/room")
def get_room(pid: str, s: Service = S):
    return s.get_room(pid).model_dump()


@app.put("/api/projects/{pid}/walls/{wid}/measured")
def set_measured(pid: str, wid: str, body: MeasureIn, s: Service = S):
    return s.set_measurement(pid, wid, body.length_m, body.height_m, body.depth_m, body.by)


@app.delete("/api/projects/{pid}/walls/{wid}/measured")
def clear_measured(pid: str, wid: str, s: Service = S):
    return s.clear_measurement(pid, wid)


@app.get("/api/projects/{pid}/zones")
def list_zones(pid: str, s: Service = S):
    return s.list_zones(pid)


@app.post("/api/projects/{pid}/zones", status_code=201)
def create_zone(pid: str, body: ZoneIn, s: Service = S):
    return s.create_zone(pid, body.purpose, body.polygon_m, body.wall_ids, body.name)


@app.patch("/api/projects/{pid}/zones/{zid}")
def patch_zone(pid: str, zid: str, body: ZonePatch, s: Service = S):
    return s.update_zone(pid, zid, **body.model_dump())


@app.delete("/api/projects/{pid}/zones/{zid}", status_code=204)
def delete_zone(pid: str, zid: str, s: Service = S):
    s.delete_zone(pid, zid)


@app.put("/api/projects/{pid}/style")
def set_style(pid: str, body: StyleIn, s: Service = S):
    return s.set_style(pid, body.prompt, body.palette, body.materials, body.zone_id)


class FinishIn(BaseModel):
    finish_id: str = Field(min_length=1, max_length=64)
    tone: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class AiStyleIn(BaseModel):
    prompt: str = Field(max_length=500)
    zone_id: Optional[str] = None
    apply_finishes: bool = True


@app.get("/api/finishes")
def finishes(s: Service = S):
    return {"finishes": [f.model_dump() for f in s.finishes]}


@app.post("/api/projects/{pid}/finishes")
def apply_finish(pid: str, body: FinishIn, s: Service = S):
    return s.apply_finish(pid, body.finish_id, body.tone)


@app.post("/api/projects/{pid}/style/ai")
def ai_style(pid: str, body: AiStyleIn, s: Service = S):
    return s.ai_style(pid, body.prompt, body.zone_id, body.apply_finishes)


class CombosIn(BaseModel):
    categories: list[str] = Field(default_factory=list, max_length=6)
    budget: Optional[int] = Field(default=None, ge=100_000, le=100_000_000)
    prompt: str = Field(default="", max_length=500)
    zone_id: Optional[str] = None


@app.post("/api/projects/{pid}/combos")
def make_combos(pid: str, body: CombosIn, s: Service = S):
    return s.make_combos(pid, body.categories, body.budget, body.prompt, body.zone_id)


class LifeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    people: Optional[int] = Field(None, ge=1, le=12)
    baby: bool = False
    lots_of_food: bool = False
    kimchi: Optional[Literal["none", "small", "lots"]] = None
    dual_income: bool = False


class AssistIn(BaseModel):
    prompt: str = Field("", max_length=500)
    image: Optional[str] = Field(None, max_length=7_500_000)  # 하우니에 붙인 사진 (data URL, 5MB 안). 저장하지 않는다
    # 생활 이야기로 고른 가전으로 이어서 배치 추천할 때
    categories: Optional[list[Literal["refrigerator", "kimchi_refrigerator", "washer", "washer_dryer"]]] = Field(None, max_length=4)
    life: Optional[LifeIn] = None  # 그때 읽은 생활 사실 (용량 범위를 조합에서도 지키려고)


@app.post("/api/projects/{pid}/assist")
def assist(pid: str, body: AssistIn, s: Service = S):
    return s.assist(pid, body.prompt, body.image, body.categories, body.life.model_dump() if body.life else None)


@app.delete("/api/projects/{pid}/combos/applied")
def clear_combo(pid: str, s: Service = S):
    return s.clear_combo(pid)


@app.post("/api/projects/{pid}/combos/{combo_id}/apply")
def apply_combo(pid: str, combo_id: str, s: Service = S):
    return s.apply_combo(pid, combo_id)


@app.post("/api/projects/{pid}/materials")
def apply_material(pid: str, body: MaterialIn, s: Service = S):
    return s.apply_material(pid, body.target, body.hex_color, body.finish, body.wall_id)


@app.post("/api/projects/{pid}/placements")
def place(pid: str, body: PlaceIn, s: Service = S):
    if body.center_xz is not None:
        return s.place_at(pid, body.sku, body.center_xz, body.yaw_rad, body.snap, body.color, size_m=body.size_m, base_m=body.base_m, slot=body.slot)
    if body.zone_id is None:
        raise HTTPException(422, "zone_id 또는 center_xz가 필요합니다")
    return s.place_product(pid, body.zone_id, body.sku, body.color)


class AutoPlaceIn(BaseModel):
    model_config = {"extra": "forbid"}
    sku: str
    color: Optional[str] = None
    size_m: Optional[list[float]] = Field(None, min_length=3, max_length=3, description="꾸미기 가구 크기 (m, 폭·높이·깊이)")


@app.post("/api/projects/{pid}/auto-place")
def auto_place(pid: str, body: AutoPlaceIn, s: Service = S):
    return s.auto_place(pid, body.sku, body.color, body.size_m)


@app.post("/api/projects/{pid}/placements/{plid}/copy")
def copy_placement(pid: str, plid: str, s: Service = S):
    return s.copy_placement(pid, plid)


@app.get("/api/decor")
def decor_list():
    """공간 꾸미기 라이브러리 (일반 가구·수납·소품·가벽, 모양만)."""
    return {"items": decor_items()}


@app.put("/api/projects/{pid}/walls/{wid}/hidden")
def hide_wall(pid: str, wid: str, body: HiddenIn, s: Service = S):
    return s.set_wall_hidden(pid, wid, body.hidden)


class ObjectColorIn(BaseModel):
    model_config = {"extra": "forbid"}
    hex: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="없으면 원래 색으로")


@app.put("/api/projects/{pid}/objects/{oid}/color")
def color_object(pid: str, oid: str, body: ObjectColorIn, s: Service = S):
    return s.set_object_color(pid, oid, body.hex)


@app.put("/api/projects/{pid}/openings/{oid}/hidden")
def hide_opening(pid: str, oid: str, body: HiddenIn, s: Service = S):
    return s.set_opening_hidden(pid, oid, body.hidden)


@app.post("/api/projects/{pid}/placements/{plid}/auto-align")
def auto_align(pid: str, plid: str, s: Service = S):
    return s.auto_align(pid, plid)


@app.post("/api/projects/{pid}/placements/{plid}/fit-gap")
def fit_gap(pid: str, plid: str, s: Service = S):
    return s.fit_gap(pid, plid)


class SuggestIn(BaseModel):
    model_config = {"extra": "forbid"}
    skus: list[str] = Field(max_length=60)
    limit: int = Field(default=3, ge=1, le=10)


@app.post("/api/projects/{pid}/suggest")
def suggest(pid: str, body: SuggestIn, s: Service = S):
    return s.suggest(pid, body.skus, body.limit)


@app.post("/api/projects/{pid}/pose-check")
def pose_check(pid: str, body: PoseIn, s: Service = S):
    return s.pose_check(pid, body.sku, body.center_xz, body.yaw_rad, body.snap, body.placement_id, body.size_m, body.base_m, body.slot)


@app.patch("/api/projects/{pid}/placements/{plid}")
def move(pid: str, plid: str, body: MoveIn, s: Service = S):
    return s.move_placement(pid, plid, body.center_xz, body.yaw_rad, body.snap, body.color, body.sku, body.size_m, body.hex, body.base_m, body.slot)


@app.delete("/api/projects/{pid}/placements/{plid}")
def delete_placement(pid: str, plid: str, s: Service = S):
    return s.delete_placement(pid, plid)


@app.put("/api/projects/{pid}/site")
def set_site(pid: str, body: SiteIn, s: Service = S):
    return s.set_site(pid, body.north_deg, body.region, body.address, body.auto_north)


@app.get("/api/projects/{pid}/sim/daylight")
def daylight(pid: str, date: str, time: Optional[str] = None, heatmap: bool = True, path: bool = False, s: Service = S):
    return s.daylight(pid, date, time, heatmap, path)


@app.put("/api/projects/{pid}/router")
def set_router(pid: str, body: RouterIn, s: Service = S):
    return s.set_router(pid, body.center_xz, body.band, body.yaw_rad)


@app.get("/api/projects/{pid}/sim/wifi")
def wifi(pid: str, band: Optional[str] = None, s: Service = S):
    return s.wifi(pid, band)


@app.get("/api/projects/{pid}/sim/wifi/best")
def wifi_best(pid: str, band: str = "5", s: Service = S):
    if band not in ("2.4", "5"):
        raise HTTPException(422, "band는 2.4 또는 5")
    return s.wifi_best(pid, band)


class MarkIn(BaseModel):
    model_config = {"extra": "forbid"}
    center_xz: list[float] = Field(min_length=2, max_length=2)


@app.put("/api/projects/{pid}/marks/{name}")
def set_mark(pid: str, name: str, body: MarkIn, s: Service = S):
    return s.set_mark(pid, name, body.center_xz)


@app.delete("/api/projects/{pid}/marks/{name}")
def del_mark(pid: str, name: str, s: Service = S):
    return s.set_mark(pid, name, None)


@app.get("/api/projects/{pid}/life-check")
def life_check(pid: str, date: Optional[str] = None, s: Service = S):
    return s.life_check(pid, date)


@app.get("/api/projects/{pid}/sim/flow")
def flow(pid: str, s: Service = S):
    return s.flow(pid)


@app.get("/api/regions")
def regions():
    from sim.regions import REGIONS
    return REGIONS


@app.put("/api/projects/{pid}/objects/hidden")
def hide_objects(pid: str, body: HiddenManyIn, s: Service = S):
    return s.set_objects_hidden(pid, body.hidden, body.object_ids)


@app.put("/api/projects/{pid}/objects/{oid}/pose")
def move_object(pid: str, oid: str, body: ObjectPoseIn, s: Service = S):
    return s.move_object(pid, oid, body.center_xz, body.yaw_rad)


@app.delete("/api/projects/{pid}/objects/{oid}/pose")
def reset_object(pid: str, oid: str, s: Service = S):
    return s.reset_object(pid, oid)


class LockIn(BaseModel):
    model_config = {"extra": "forbid"}
    id: str = Field(min_length=1, max_length=64, description="놓은 물건 placement_id 또는 스캔 가구 object_id")
    locked: bool = True


@app.put("/api/projects/{pid}/locked")
def lock_item(pid: str, body: LockIn, s: Service = S):
    return s.set_locked(pid, body.id, body.locked)


@app.put("/api/projects/{pid}/objects/{oid}/hidden")
def hide_object(pid: str, oid: str, body: HiddenIn, s: Service = S):
    return s.set_object_hidden(pid, oid, body.hidden)


@app.delete("/api/projects/{pid}/placements/{zid}/{sku}")
def unplace(pid: str, zid: str, sku: str, s: Service = S):
    return s.remove_product(pid, zid, sku)


class RenderBody(BaseModel):
    date: Optional[str] = None  # 주면 채광과 같은 해로 렌더 (YYYY-MM-DD)
    time: Optional[str] = None  # HH:MM


@app.post("/api/projects/{pid}/render")
def render(pid: str, body: Optional[RenderBody] = None, s: Service = S):
    return s.render(pid, body.date if body else None, body.time if body else None)


Coord = Annotated[float, Field(ge=-1000, le=1000)]


class ViewCamera(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pos: Annotated[list[Coord], Field(min_length=3, max_length=3)]     # 웹 3D 좌표 (m, Y가 위)
    target: Annotated[list[Coord], Field(min_length=3, max_length=3)]
    fov: float = Field(ge=10, le=120)                                   # 세로 화각 (도)


class PhotorealIn(BaseModel):
    image: str = Field(max_length=12_000_000)  # 지금 3D 화면 (data URL)
    mask: str = Field(max_length=12_000_000)   # 같은 시점, LG 제품만 흰색
    spot: Optional[str] = Field(None, pattern=r"^[A-Za-z0-9_:-]{1,60}$")  # 둘러보기에서 들르는 곳 (곳마다 한 장씩 남긴다)
    camera: Optional[ViewCamera] = None  # 지금 시점. 이미지 AI를 못 쓸 때 서버의 Blender가 같은 자리에서 그린다


@app.post("/api/projects/{pid}/photoreal")
def photoreal(pid: str, body: PhotorealIn, s: Service = S):
    return s.photoreal(pid, body.image, body.mask, body.spot, body.camera.model_dump() if body.camera else None)


@app.get("/api/projects/{pid}/photoreal/spots")
def photoreal_spots(pid: str, s: Service = S):
    return s.photoreal_spots(pid)


@app.get("/api/projects/{pid}/photoreal/spots/{name}")
def photoreal_spot_file(pid: str, name: str, s: Service = S):
    p = s.photoreal_spot_path(pid, name)
    if p is None:
        raise HTTPException(404, "아직 생성되지 않음")
    return FileResponse(p, headers={"Cache-Control": "no-store"})


@app.get("/api/projects/{pid}/zones/{zid}/recommendations")
def recommend(pid: str, zid: str, category: Optional[str] = None, s: Service = S):
    return s.recommend(pid, zid, category)


@app.get("/api/projects/{pid}/results")
def results(pid: str, s: Service = S):
    return s.results(pid)


@app.post("/api/projects/{pid}/install-request", status_code=201)
def install_request(pid: str, body: RequestIn, s: Service = S):
    return s.create_install_request(pid, body.name, body.contact, body.address, body.preferred_at)


@app.get("/api/projects/{pid}/files/before.glb")
def before_file(pid: str, s: Service = S):
    return FileResponse(s.before_glb(pid), headers={"Cache-Control": "no-store"})


@app.get("/api/projects/{pid}/install-check")
def install_check(pid: str, s: Service = S):
    return s.install_check(pid)


@app.post("/api/projects/{pid}/floorplan", status_code=201)
async def upload_floorplan(pid: str, file: UploadFile = File(...), s: Service = S):
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "파일이 너무 큽니다")
    s.set_floorplan(pid, data, file.filename or "floorplan.png")
    return await run_in_threadpool(s.apply_floorplan, pid)  # 스캔한 집이면 도면 치수로 벽 길이를 맞춘다


@app.delete("/api/projects/{pid}/floorplan")
def delete_floorplan(pid: str, s: Service = S):
    return s.clear_floorplan(pid)


@app.get("/api/projects/{pid}/files/floorplan")
def floorplan_file(pid: str, s: Service = S):
    hit = s.floorplan_path(pid)
    if hit is None:
        raise HTTPException(404, "도면 없음")
    return FileResponse(hit[0], media_type=hit[1], headers={"Cache-Control": "no-store"})


@app.get("/api/projects/{pid}/files/{name}")
def project_file(pid: str, name: str, s: Service = S):
    allowed = {"scene.glb": "scene/scene.glb", "render.png": "scene/render.png", "photoreal.png": "scene/photoreal.png",
               "room.json": "scan/room.json"}
    if name not in allowed:
        raise HTTPException(404)
    p = s.pdir(pid) / allowed[name]
    if not p.exists():
        raise HTTPException(404, "아직 생성되지 않음")
    return FileResponse(p, headers={"Cache-Control": "no-store"})


def find_conditions(
    category: Optional[str] = None,
    use: Optional[str] = Query(None, description="공간 용도 (kitchen, living, ...)"),
    install: Optional[Literal["built_in", "freestanding"]] = None,
    capacity_min: Optional[float] = Query(None, ge=0, description="용량 L 이상"),
    capacity_max: Optional[float] = Query(None, ge=0, description="용량 L 이하"),
    color: Optional[Literal["화이트", "베이지", "실버·그레이", "블랙", "그린", "기타"]] = None,
    price_min: Optional[int] = Query(None, ge=0, description="원"),
    price_max: Optional[int] = Query(None, ge=0, description="원"),
    space_w: Optional[float] = Query(None, gt=0, le=20000, description="설치 공간 폭 mm"),
    space_h: Optional[float] = Query(None, gt=0, le=20000, description="설치 공간 높이 mm"),
    space_d: Optional[float] = Query(None, gt=0, le=20000, description="설치 공간 깊이 mm"),
    fits_only: bool = False,
    sort: Literal["recommended", "size", "price"] = "recommended",
    limit: Optional[int] = Query(None, ge=1, le=500),
) -> Conditions:
    return Conditions(category=category, zone=use, install=install, capacity_min=capacity_min, capacity_max=capacity_max,
                      color=color, price_min=price_min, price_max=price_max, space_w=space_w, space_h=space_h,
                      space_d=space_d, fits_only=fits_only, sort=sort, limit=limit)


@app.get("/api/catalog/find")
def catalog_find(cond: Conditions = Depends(find_conditions), s: Service = S):
    """조건(종류·용량·색상·가격·설치 공간)으로 제품 찾기. 판정과 순서는 서버가 계산한다."""
    return s.find(cond)


@app.get("/api/projects/{pid}/find")
def project_find(pid: str, zone_id: Optional[str] = None, cond: Conditions = Depends(find_conditions), s: Service = S):
    """같은 조건 찾기를 우리 집 기준으로: 공간 치수를 안 넣으면 그려 둔 영역에 들어가는지로 판정한다."""
    return s.find(cond, pid, zone_id)


@app.get("/api/catalog/families")
def catalog_families(s: Service = S):
    return s.catalog.families()


@app.get("/api/catalog")
def catalog(category: Optional[str] = None, zone: Optional[str] = None, q: Optional[str] = None, s: Service = S):
    return [p.model_dump() for p in s.catalog.search(category, zone, q)]


SAMPLES = {"synthetic_room.usdz", "apt_living_kitchen.usdz", "studio_living.usdz", "ugscan_2026-11-18.usdz"}


@app.get("/api/samples/{name}")
def sample_scan(name: str):
    if name not in SAMPLES:
        raise HTTPException(404)
    return FileResponse(config.ROOT / "data" / "samples" / name, filename=name)


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


def run():
    import uvicorn
    uvicorn.run("api.main:app", host=os.getenv("API_HOST", "127.0.0.1"), port=int(os.getenv("API_PORT", 8000)))


if __name__ == "__main__":
    run()
