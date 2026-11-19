"""Streamable HTTP + Bearer 토큰 (기획 §6.2·§6.3)."""
import pytest
from starlette.testclient import TestClient

from mcp_server import server as srv

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
H = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


def test_refuses_to_start_without_token(monkeypatch):
    monkeypatch.delenv("MCP_HTTP_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        srv.http_app()


def test_bearer_required(monkeypatch):
    monkeypatch.setenv("MCP_HTTP_TOKEN", "x" * 24)
    with TestClient(srv.http_app(), base_url="http://127.0.0.1:8765") as c:
        assert c.post("/mcp", json=INIT, headers=H).status_code == 401
        assert c.post("/mcp", json=INIT, headers={**H, "authorization": "Bearer wrong"}).status_code == 401
        r = c.post("/mcp", json=INIT, headers={**H, "authorization": "Bearer " + "x" * 24})
        assert r.status_code == 200, r.text
        assert "lg-builtin" in r.text
