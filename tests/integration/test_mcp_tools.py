"""MCP 도구 계약 테스트 — 인메모리 클라이언트로 실제 MCP 호출 경로를 통과시킨다."""
import json

import pytest
from mcp import Client

from core.service import Service
from mcp_server import server as srv

from core import config

USDZ = (config.ROOT / "data" / "samples" / "synthetic_room.usdz").read_bytes()
EXPECTED_TOOLS = {"list_projects", "get_room", "list_zones", "create_zone", "set_style", "search_catalog",
                  "check_fit", "recommend", "apply_material", "place_product", "remove_product", "render"}


@pytest.fixture()
def svc(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_BLENDER", "0")
    s = Service(storage=tmp_path)
    monkeypatch.setattr(srv, "_svc", s)
    p = s.create_project_from_usdz(USDZ)
    s.create_zone(p["project_id"], "kitchen", [[0, 0], [3, 0], [3, 1.6], [0, 1.6]])
    return s


def _data(res):
    assert not res.is_error, res.content
    if res.structured_content is not None:
        sc = res.structured_content
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    return json.loads(res.content[0].text)


@pytest.mark.anyio
async def test_tools_are_listed_with_schemas(svc):
    async with Client(srv.mcp) as c:
        tools = {t.name: t for t in (await c.list_tools()).tools}
    assert EXPECTED_TOOLS <= set(tools)
    assert "zone_id" in tools["check_fit"].input_schema["required"]
    assert all(t.description for t in tools.values())


@pytest.mark.anyio
async def test_chat_flow_updates_shared_state(svc):
    async with Client(srv.mcp) as c:
        room = _data(await c.call_tool("get_room", {}))
        assert len(room["walls"]) == 4
        zones = _data(await c.call_tool("list_zones", {}))
        zid = zones[0]["zone_id"]
        _data(await c.call_tool("set_style", {"palette": ["#F2EFEA", "#C8A27A"], "materials": ["wood", "matte"],
                                              "prompt": "화이트 우드 톤 미니멀"}))
        rec = _data(await c.call_tool("recommend", {"zone_id": zid}))
        assert rec["items"] and rec["items"][0]["fit"]["verdict"] in {"conditional", "fit"}
        fit = _data(await c.call_tool("check_fit", {"zone_id": zid, "sku": "DEMO-DW-01"}))
        assert fit["dims"]["width"]["source"] == "scanned"
        _data(await c.call_tool("apply_material", {"target": "floor", "hex_color": "#C8A27A"}))
        _data(await c.call_tool("place_product", {"zone_id": zid, "sku": "DEMO-RF-01"}))
        r = await c.call_tool("render", {})
        assert not r.is_error and any(getattr(x, "type", "") == "image" for x in r.content)
    # 웹이 읽는 같은 상태에 반영됐는지
    p = svc.list_projects()[-1]
    assert p["style"]["prompt"] == "화이트 우드 톤 미니멀"
    assert p["scene_state"]["materials"]["floor"] == "#C8A27A"
    assert p["scene_state"]["placements"][0]["sku"] == "DEMO-RF-01"


@pytest.mark.anyio
async def test_bad_input_is_tool_error(svc):
    async with Client(srv.mcp) as c:
        r = await c.call_tool("check_fit", {"zone_id": "z_999", "sku": "DEMO-RF-01"})
        assert r.is_error
        r = await c.call_tool("apply_material", {"target": "floor", "hex_color": "red"})
        assert r.is_error


@pytest.fixture
def anyio_backend():
    return "asyncio"
