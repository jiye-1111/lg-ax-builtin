"""MCP 서버 — Claude(Code·앱)와 Codex(CLI·IDE·데스크톱)가 같은 도구를 쓴다 (기획 §6.2).

실행:
  stdio:  python -m mcp_server              (Claude Code .mcp.json, Codex config.toml 기본)
  HTTP:   python -m mcp_server --http       (Streamable HTTP, /mcp, Authorization: Bearer $MCP_HTTP_TOKEN 필수)

원칙: 판정·점수는 서버 코드가 계산하고, 모델은 해석·설명만 한다. 임의 코드 실행 도구는 없다.
"""
from __future__ import annotations

import argparse
import hmac
import os
import sys
from typing import Annotated, Literal, Optional

from pydantic import Field

from mcp.server.mcpserver import Image, MCPServer

from core.service import Invalid, NotFound, Service

INSTRUCTIONS = """LG 빌트인 가상 리모델링 도구입니다. 고객이 LiDAR로 스캔한 집(project)에 LG 제품을 골라 놓아 보고
(place_at·move_product), 어울리는 색상·재질(CMF)을 찾고, 채광·와이파이·동선(daylight·wifi_coverage·flow_routes)을 확인합니다.
규칙:
1) 치수 적합 판정(fit/conditional/no_fit/unknown)과 점수는 반드시 check_fit·recommend 결과를 그대로 전하세요. 직접 계산하거나 추정하지 마세요.
2) 카탈로그에 없는 제품·치수를 만들지 마세요. null 값은 "공개 정보 없음"으로 말하세요.
3) 스타일 요청(예: "화이트 우드 톤 미니멀")은 대표색 3~5개(#RRGGBB)와 재질 키워드(wood, matte, glass, metal, stone...)로 바꿔 set_style로 저장한 뒤 recommend를 호출하세요.
4) 판정 이유(reasons)를 그대로 전하세요. 스캔값 기반이라 오차가 있을 수 있고, 줄자 실측은 선택입니다.
6) 채광·와이파이·동선은 참고용 근사입니다. 결과의 assumptions를 함께 말하세요. 채광은 set_site로 북쪽 방향이 필요합니다.
5) demo_only=true 제품은 시연용 가상 데이터임을 밝히세요.
결과는 고객 웹 화면(customer_url)에도 실시간으로 반영됩니다."""

mcp = MCPServer(name="lg-builtin", title="LG 빌트인 공간 설계", instructions=INSTRUCTIONS, version="0.1.0")

_svc: Service | None = None


def svc() -> Service:
    global _svc
    if _svc is None:
        _svc = Service()
    return _svc


def _pid(project_id: Optional[str]) -> str:
    if project_id:
        return project_id
    env = os.getenv("MCP_DEFAULT_PROJECT")
    if env:
        return env
    projects = svc().list_projects()
    if not projects:
        raise Invalid("등록된 프로젝트가 없습니다. 기사 화면에서 스캔을 먼저 업로드하세요.")
    return projects[-1]["project_id"]


PID = Annotated[Optional[str], Field(description="프로젝트 ID (예: p_001). 생략하면 가장 최근 프로젝트")]
ZID = Annotated[str, Field(description="영역 ID (list_zones로 확인, 예: z_001)")]
HEX = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$", description="#RRGGBB")]


def _wrap(fn):
    """서비스 오류를 모델이 읽을 수 있는 메시지로."""
    def inner(*a, **kw):
        try:
            return fn(*a, **kw)
        except (NotFound, KeyError) as e:
            raise ValueError(f"찾을 수 없음: {e}") from e
        except Invalid as e:
            raise ValueError(str(e)) from e
    inner.__name__, inner.__doc__, inner.__annotations__ = fn.__name__, fn.__doc__, fn.__annotations__
    inner.__wrapped__ = fn
    return inner


def _brief_room(room) -> dict:
    return {
        "walls": [{"wall_id": w.wall_id, "length_m": w.scanned.length_m, "height_m": w.scanned.height_m,
                   "measured": w.measured.model_dump(exclude_none=True) if w.measured else None,
                   "start": w.start, "end": w.end} for w in room.walls],
        "openings": [o.model_dump() for o in room.openings],
        "objects": [{"object_id": o.object_id, "category": o.category, "bbox_m": o.bbox_m.model_dump(),
                     "position": o.position} for o in room.objects],
    }


@mcp.tool()
@_wrap
def list_projects() -> list[dict]:
    """등록된 스캔 프로젝트 목록(ID, 상태, 고객 링크)."""
    return [{"project_id": p["project_id"], "status": p["status"], "created_at": p["created_at"],
             "style": p["style"].get("prompt")} for p in svc().list_projects()]


@mcp.tool()
@_wrap
def get_room(project_id: PID = None) -> dict:
    """방 구조: 벽(스캔 길이·높이, 기사 실측값), 문·창문, 기존 가구. 단위 m."""
    pid = _pid(project_id)
    p = svc().get_project(pid)
    return {"project_id": pid, "customer_url": p["customer_url"], **_brief_room(svc().get_room(pid))}


@mcp.tool()
@_wrap
def list_zones(project_id: PID = None) -> list[dict]:
    """영역 목록(용도, 다각형 m, 벽, 스타일 팔레트·재질)."""
    return svc().list_zones(_pid(project_id))


@mcp.tool()
@_wrap
def create_zone(
    purpose: Annotated[str, Field(pattern=r"^[a-z_]{2,30}$", description="kitchen | living | bedroom ...")],
    polygon_m: Annotated[list[tuple[float, float]], Field(min_length=3, description="평면 꼭짓점 [[x, y], ...] (m)")],
    project_id: PID = None,
    name: Optional[str] = None,
) -> dict:
    """평면도 위에 영역을 만든다. 보통은 고객이 웹에서 그리지만 대화로도 만들 수 있다."""
    return svc().create_zone(_pid(project_id), purpose, polygon_m, None, name)


@mcp.tool()
@_wrap
def set_style(
    palette: Annotated[list[HEX], Field(min_length=1, max_length=8, description="대표색 3~5개")],
    materials: Annotated[list[str], Field(max_length=10, description="재질·마감 키워드: wood, matte, glossy, glass, metal, stone, fabric")],
    prompt: Annotated[Optional[str], Field(description="고객이 쓴 원문 스타일 요청")] = None,
    zone_id: Annotated[Optional[str], Field(description="특정 영역에만 적용. 생략 시 프로젝트 전체")] = None,
    project_id: PID = None,
) -> dict:
    """고객 스타일을 팔레트·재질 키워드로 저장한다(CMF 추천 입력). 이미지가 첨부되면 이미지에서 대표색을 골라 넣는다."""
    r = svc().set_style(_pid(project_id), prompt, palette, materials, zone_id)
    return {"saved": True, "project_style": r["project_style"],
            "zones": [{"zone_id": z["zone_id"], "style_tags": z["style_tags"]} for z in r["zones"]]}


@mcp.tool()
@_wrap
def search_catalog(
    category: Annotated[Optional[str], Field(description="refrigerator | kimchi_refrigerator | dishwasher | oven | cooktop | water_purifier | ...")] = None,
    zone: Annotated[Optional[str], Field(description="kitchen | living ...")] = None,
    query: Optional[str] = None,
) -> list[dict]:
    """LG 제품 카탈로그 검색. 치수(mm)·이격·색상 옵션·출처 URL 포함. null은 공개 정보 없음."""
    return [p.model_dump() for p in svc().catalog.search(category, zone, query)]


@mcp.tool()
@_wrap
def check_fit(zone_id: ZID, sku: str, project_id: PID = None) -> dict:
    """한 제품이 영역에 설치 가능한지 규칙 기반 판정. 폭·높이·깊이별 가용/필요 치수(mm), 여유, 사용한 값(scanned/measured)."""
    return svc().check_fit(_pid(project_id), zone_id, sku)


@mcp.tool()
@_wrap
def recommend(zone_id: ZID, category: Optional[str] = None, project_id: PID = None) -> dict:
    """영역에 맞는 제품 후보: 적합 판정 + 스타일에 맞는 색상·재질 상위 3개와 점수 근거. 설명은 reasons를 벗어나지 말 것."""
    r = svc().recommend(_pid(project_id), zone_id, category)
    items = [{
        "sku": i["product"]["sku"], "name": i["product"]["name"], "category": i["product"]["category"],
        "demo_only": i["product"]["demo_only"], "source_url": i["product"]["source_url"],
        "fit": i["fit"], "cmf_top": i["cmf"],
    } for i in r["items"]]
    return {"zone_id": zone_id, "style_tags": r["zone"]["style_tags"], "margins_mm": r["margins_mm"], "items": items}


@mcp.tool()
@_wrap
def apply_material(
    target: Literal["wall", "floor", "door", "window", "object"],
    hex_color: HEX,
    finish: Optional[Literal["matte", "glossy", "satin"]] = None,
    wall_id: Annotated[Optional[str], Field(description="특정 벽만 칠할 때 (target=wall)")] = None,
    project_id: PID = None,
) -> dict:
    """3D 씬의 벽·바닥 등 색과 마감을 바꾼다. 웹 3D 뷰어에 바로 반영."""
    r = svc().apply_material(_pid(project_id), target, hex_color, finish, wall_id)
    return {"applied": True, "scene_state": r["scene_state"], "engine": r["scene"]["engine"]}


@mcp.tool()
@_wrap
def place_product(zone_id: ZID, sku: str, color: Annotated[Optional[str], Field(description="제품 색상 옵션명. 생략 시 CMF 1순위")] = None,
                  project_id: PID = None) -> dict:
    """제품을 영역의 가장 알맞은 벽 앞에 치수 박스로 배치(배치 미리보기). 판정 결과도 함께 돌려준다."""
    r = svc().place_product(_pid(project_id), zone_id, sku, color)
    return {"placed": True, "fit": r["fit"], "placements": r["scene_state"]["placements"]}


@mcp.tool()
@_wrap
def remove_product(zone_id: ZID, sku: str, project_id: PID = None) -> dict:
    """배치 미리보기에서 제품을 뺀다."""
    r = svc().remove_product(_pid(project_id), zone_id, sku)
    return {"removed": True, "placements": r["scene_state"]["placements"]}


XZ = Annotated[list[float], Field(min_length=2, max_length=2, description="바닥 평면 좌표 [x, z] (m). get_room의 벽 좌표와 같은 좌표계")]
YAW = Annotated[float, Field(description="회전(라디안). 0이면 제품 등이 -z 쪽")]
SNAP = Annotated[bool, Field(description="0.3 m 안의 벽이 있으면 등을 벽에 붙인다")]


def _placed(r: dict) -> dict:
    return {"placement": r.get("placement"), "placements": r["scene_state"]["placements"]}


@mcp.tool()
@_wrap
def place_at(sku: str, center_xz: XZ, yaw_rad: YAW = 0.0, snap: SNAP = True,
             color: Annotated[Optional[str], Field(description="제품 색상 옵션명. 생략 시 첫 옵션")] = None,
             project_id: PID = None) -> dict:
    """제품을 지정한 자리·방향에 놓고 판정(적합/조건부/불가)과 이유를 돌려준다."""
    return _placed(svc().place_at(_pid(project_id), sku, center_xz, yaw_rad, snap, color))


@mcp.tool()
@_wrap
def move_product(placement_id: Annotated[str, Field(description="list_placements의 배치 ID (예: pl_001)")],
                 center_xz: Optional[XZ] = None, yaw_rad: Optional[float] = None, snap: SNAP = True,
                 color: Optional[str] = None, project_id: PID = None) -> dict:
    """놓은 제품을 옮기거나 돌리거나 색을 바꾸고 다시 판정한다."""
    return _placed(svc().move_placement(_pid(project_id), placement_id, center_xz, yaw_rad, snap, color))


@mcp.tool()
@_wrap
def list_placements(project_id: PID = None) -> list[dict]:
    """지금 놓여 있는 제품 목록(위치, 방향, 색, 판정, 이유)."""
    return svc().get_project(_pid(project_id))["scene_state"]["placements"]


@mcp.tool()
@_wrap
def hide_object(object_id: Annotated[str, Field(description="get_room의 기존 가구 ID (예: o3)")],
                hidden: bool = True, project_id: PID = None) -> dict:
    """스캔된 기존 가구를 치운다(hidden=false면 되돌림). 치운 가구는 판정·3D에서 빠진다."""
    r = svc().set_object_hidden(_pid(project_id), object_id, hidden)
    return {"hidden_objects": r["scene_state"].get("hidden_objects", []), "placements": r["scene_state"]["placements"]}


@mcp.tool()
@_wrap
def set_site(north_deg: Annotated[Optional[float], Field(ge=0, lt=360, description="평면도 위쪽에서 북쪽까지 시계 방향 각도")] = None,
             region: Annotated[Optional[str], Field(description="시·도 (예: 서울, 부산, 경기)")] = None,
             project_id: PID = None) -> dict:
    """집의 북쪽 방향과 지역을 저장한다 (채광 계산용)."""
    return svc().set_site(_pid(project_id), north_deg, region)["site"]


@mcp.tool()
@_wrap
def daylight(date: Annotated[str, Field(description="YYYY-MM-DD")], time: Annotated[Optional[str], Field(description="HH:MM (한국 시간)")] = None,
             project_id: PID = None) -> dict:
    """그 날 창으로 드는 직사광: 해 높이·방위, 볕 드는 창, 놓은 제품 자리별 하루 직사 시간. 참고용 근사."""
    d = svc().daylight(_pid(project_id), date, time)
    daily = d.pop("daily")
    vals = [v for row in daily["values"] for v in row if v is not None]
    d["sunlit_share"] = round(sum(1 for v in vals if v > 0) / len(vals), 3) if vals else 0
    d["max_hours"] = max(vals) if vals else 0
    d["placement_hours"] = daily["points"]
    d["patches"] = [x["opening_id"] for x in d["patches"]]
    return d


@mcp.tool()
@_wrap
def wifi_coverage(band: Annotated[str, Field(pattern=r"^(2\.4|5)$")] = "5",
                  router_xz: Annotated[Optional[list[float]], Field(min_length=2, max_length=2, description="공유기 위치 [x, z]. 생략 시 저장된 위치")] = None,
                  auto_place: Annotated[bool, Field(description="true면 가장 약한 곳이 제일 센 자리로 공유기를 옮긴다")] = False,
                  project_id: PID = None) -> dict:
    """와이파이 신호 요약(좋음·보통·약함 비율, 가장 약한 곳, 영역별). 참고용 근사."""
    pid = _pid(project_id)
    if auto_place:
        router_xz = svc().wifi_best(pid, band)["center_xz"]
    if router_xz is not None:
        svc().set_router(pid, router_xz, band)
    g = svc().wifi(pid, band)
    return {k: g[k] for k in ("router", "band", "share", "min_dbm", "zones", "assumptions")}


@mcp.tool()
@_wrap
def flow_routes(project_id: PID = None) -> dict:
    """현관에서 놓은 제품 앞까지 동선: 길이, 가장 좁은 통로 폭, 좁은 곳 개수, 주방 작업 삼각형. 참고용 근사."""
    f = svc().flow(_pid(project_id))
    routes = {k: {"name": f["names"].get(k, k), "reachable": r["reachable"], "length_m": r["length_m"],
                  "min_width_m": r["min_width_m"], "narrow_points": len(r["narrow"])} for k, r in f["routes"].items()}
    return {"entrance": f["entrance"], "routes": routes, "triangle": f.get("triangle"), "assumptions": f["assumptions"]}


@mcp.tool()
@_wrap
def render(project_id: PID = None) -> list:
    """현재 디자인(재질·배치)을 이미지로 렌더한다. Blender가 있으면 Blender, 없으면 미리보기 렌더."""
    pid = _pid(project_id)
    r = svc().render(pid)
    note = f"{pid} 렌더 완료 (engine={r['scene']['engine']}). 웹: {svc().get_project(pid)['customer_url']}"
    return [note, Image(path=r["png_path"])] if r.get("png_path") else [note]


# ---------------- 실행 ----------------
class BearerAuth:
    """Streamable HTTP용 고정 토큰 검사 (기획 §6.2 인증 통일)."""

    def __init__(self, app, token: str):
        self.app, self.token = app, token.encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers") or [])
            got = headers.get(b"authorization", b"")
            ok = got.startswith(b"Bearer ") and hmac.compare_digest(got[7:].strip(), self.token)
            if not ok:
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")]})
                await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
                return
        await self.app(scope, receive, send)


def http_app():
    token = os.getenv("MCP_HTTP_TOKEN")
    if not token or len(token) < 16:
        raise SystemExit("MCP_HTTP_TOKEN(16자 이상)을 .env에 설정하세요. 공개 주소에서는 토큰 없이 열지 않습니다.")
    from mcp.server.transport_security import TransportSecuritySettings

    hosts = [h.strip() for h in os.getenv("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    sec = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", *hosts],
        allowed_origins=["http://127.0.0.1:*", "http://localhost:*", *[f"https://{h}" for h in hosts]],
    )
    app = mcp.streamable_http_app(streamable_http_path="/mcp", transport_security=sec,
                                  stateless_http=os.getenv("MCP_STATELESS", "1") == "1", json_response=True)
    return BearerAuth(app, token)


def main(argv=None):
    ap = argparse.ArgumentParser(description="LG 빌트인 MCP 서버")
    ap.add_argument("--http", action="store_true", help="Streamable HTTP로 실행 (기본: stdio)")
    a = ap.parse_args(argv)
    if a.http:
        import uvicorn
        uvicorn.run(http_app(), host=os.getenv("MCP_HOST", "127.0.0.1"), port=int(os.getenv("MCP_PORT", 8765)))
    else:
        mcp.run("stdio")


if __name__ == "__main__":
    main(sys.argv[1:])
