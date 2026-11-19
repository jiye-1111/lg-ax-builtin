"""FastAPI 백엔드 (기획 §6.1 api). 웹 정적 파일도 함께 서빙한다 (plan.md ADR-8)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core import config
from core.service import Invalid, NotFound, Service

WEB_DIR = config.ROOT / "apps" / "web"
MAX_UPLOAD = int(os.getenv("MAX_UPLOAD_MB", 200)) * 1024 * 1024


@lru_cache
def get_service() -> Service:
    return Service()


app = FastAPI(title="LG 빌트인 공간 설계 (시연)", version="0.1.0")


@app.exception_handler(NotFound)
async def _nf(_, e):
    return JSONResponse({"detail": str(e).strip("'")}, status_code=404)


@app.exception_handler(Invalid)
async def _inv(_, e):
    return JSONResponse({"detail": str(e)}, status_code=422)


@app.exception_handler(KeyError)
async def _ke(_, e):
    return JSONResponse({"detail": f"찾을 수 없음: {e}"}, status_code=404)


S = Depends(get_service)


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


class PoseIn(BaseModel):
    model_config = {"extra": "forbid"}
    sku: str
    center_xz: list[float] = Field(min_length=2, max_length=2)
    yaw_rad: float = 0.0
    snap: bool = True
    placement_id: Optional[str] = None


class MoveIn(BaseModel):
    model_config = {"extra": "forbid"}
    center_xz: Optional[list[float]] = Field(None, min_length=2, max_length=2)
    yaw_rad: Optional[float] = None
    snap: bool = True
    color: Optional[str] = None


class HiddenIn(BaseModel):
    hidden: bool = True


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
def list_requests(s: Service = S):
    return s.list_requests()


@app.post("/api/projects", status_code=201)
async def upload_scan(file: UploadFile = File(...), request_id: Optional[str] = Form(None),
                      scanned_by: str = Form("technician"), s: Service = S):
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "파일이 너무 큽니다")
    if not data:
        raise HTTPException(422, "빈 파일")
    return s.create_project_from_usdz(data, file.filename or "room.usdz", request_id or None, scanned_by)


@app.get("/api/projects")
def list_projects(s: Service = S):
    return s.list_projects()


@app.get("/api/projects/{pid}")
def get_project(pid: str, s: Service = S):
    return s.get_project(pid)


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


@app.post("/api/projects/{pid}/materials")
def apply_material(pid: str, body: MaterialIn, s: Service = S):
    return s.apply_material(pid, body.target, body.hex_color, body.finish, body.wall_id)


@app.post("/api/projects/{pid}/placements")
def place(pid: str, body: PlaceIn, s: Service = S):
    if body.center_xz is not None:
        return s.place_at(pid, body.sku, body.center_xz, body.yaw_rad, body.snap, body.color)
    if body.zone_id is None:
        raise HTTPException(422, "zone_id 또는 center_xz가 필요합니다")
    return s.place_product(pid, body.zone_id, body.sku, body.color)


@app.post("/api/projects/{pid}/pose-check")
def pose_check(pid: str, body: PoseIn, s: Service = S):
    return s.pose_check(pid, body.sku, body.center_xz, body.yaw_rad, body.snap, body.placement_id)


@app.patch("/api/projects/{pid}/placements/{plid}")
def move(pid: str, plid: str, body: MoveIn, s: Service = S):
    return s.move_placement(pid, plid, body.center_xz, body.yaw_rad, body.snap, body.color)


@app.delete("/api/projects/{pid}/placements/{plid}")
def delete_placement(pid: str, plid: str, s: Service = S):
    return s.delete_placement(pid, plid)


@app.put("/api/projects/{pid}/objects/{oid}/hidden")
def hide_object(pid: str, oid: str, body: HiddenIn, s: Service = S):
    return s.set_object_hidden(pid, oid, body.hidden)


@app.delete("/api/projects/{pid}/placements/{zid}/{sku}")
def unplace(pid: str, zid: str, sku: str, s: Service = S):
    return s.remove_product(pid, zid, sku)


@app.post("/api/projects/{pid}/render")
def render(pid: str, s: Service = S):
    return s.render(pid)


@app.get("/api/projects/{pid}/zones/{zid}/recommendations")
def recommend(pid: str, zid: str, category: Optional[str] = None, s: Service = S):
    return s.recommend(pid, zid, category)


@app.get("/api/projects/{pid}/results")
def results(pid: str, s: Service = S):
    return s.results(pid)


@app.post("/api/projects/{pid}/floorplan", status_code=201)
async def upload_floorplan(pid: str, file: UploadFile = File(...), s: Service = S):
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "파일이 너무 큽니다")
    return s.set_floorplan(pid, data, file.filename or "floorplan.png")


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
    allowed = {"scene.glb": "scene/scene.glb", "render.png": "scene/render.png", "room.json": "scan/room.json"}
    if name not in allowed:
        raise HTTPException(404)
    p = s.pdir(pid) / allowed[name]
    if not p.exists():
        raise HTTPException(404, "아직 생성되지 않음")
    return FileResponse(p, headers={"Cache-Control": "no-store"})


@app.get("/api/catalog")
def catalog(category: Optional[str] = None, zone: Optional[str] = None, q: Optional[str] = None, s: Service = S):
    return [p.model_dump() for p in s.catalog.search(category, zone, q)]


SAMPLES = {"synthetic_room.usdz", "ugscan_2026-11-18.usdz"}


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
