"""서버 배포(Lightsail 백엔드 + Cloudflare Pages 웹) 설정이 맞는지.

웹과 API가 다른 주소에 있어도 동작해야 한다:
- 웹은 config.js의 LGB_API로 API 주소를 받는다 (비우면 같은 서버, 팀 PC 시연 그대로)
- API는 CORS_ORIGINS에 적힌 웹 주소만 허용한다
"""
import importlib
import os
import re
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps" / "web"


def _app_with(monkeypatch, origins: str | None):
    if origins is None:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("CORS_ORIGINS", origins)
    from api import main
    return TestClient(importlib.reload(main).app)


def _preflight(c, origin):
    return c.options("/api/catalog", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})


def test_cors_allows_only_listed_web_origin(monkeypatch):
    c = _app_with(monkeypatch, "https://lgbuiltin.axworks.site, https://lgbuiltin.pages.dev")
    ok = _preflight(c, "https://lgbuiltin.axworks.site")
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == "https://lgbuiltin.axworks.site"
    assert _preflight(c, "https://lgbuiltin.pages.dev").headers["access-control-allow-origin"] == "https://lgbuiltin.pages.dev"
    bad = _preflight(c, "https://evil.example.com")
    assert "access-control-allow-origin" not in bad.headers
    # 실제 GET 응답(3D 파일 등)에도 허용 헤더가 붙어야 three.js가 읽을 수 있다
    r = c.get("/api/health", headers={"Origin": "https://lgbuiltin.axworks.site"})
    assert r.headers["access-control-allow-origin"] == "https://lgbuiltin.axworks.site"


def test_no_cors_header_when_unset(monkeypatch):
    c = _app_with(monkeypatch, None)
    r = c.get("/api/health", headers={"Origin": "https://lgbuiltin.axworks.site"})
    assert "access-control-allow-origin" not in r.headers
    importlib.reload(importlib.import_module("api.main"))


def test_index_loads_config_before_app():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert '<script src="config.js"></script>' in html
    assert html.index("config.js") < html.index('src="app.js"')
    cfg = (WEB / "config.js").read_text(encoding="utf-8")
    assert "LGB_API" in cfg and '""' in cfg  # 기본은 같은 서버


def test_all_api_urls_go_through_api_base():
    """'/api/...' 주소는 core.js의 api()/post()/put()/apiUrl()로만 만든다. 다른 서버에 API가 있어도 끊기지 않게."""
    core = (WEB / "js" / "core.js").read_text(encoding="utf-8")
    assert "window.LGB_API" in core and "export const apiUrl" in core
    bad = []
    for f in sorted((WEB / "js").glob("*.js")) + [WEB / "app.js"]:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for m in re.finditer(r"[\"`]/api/", line):
                before = line[: m.start()].rstrip()
                if not re.search(r"(api|post|put|apiUrl)\($", before) and not (f.name == "core.js"):
                    bad.append(f"{f.name}:{n}: {line.strip()[:90]}")
    assert not bad, "API 주소를 apiUrl()로 감싸지 않은 곳:\n" + "\n".join(bad)


def test_service_worker_never_caches_api_even_cross_origin():
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    assert 'url.pathname.startsWith("/api/")) return' in sw
    assert "url.origin === location.origin && url.pathname.startsWith(\"/api/\")" not in sw
    assert '"./config.js"' in sw


def test_pages_build_writes_api_base(tmp_path):
    out = tmp_path / "config.js"
    env = {**os.environ, "API_BASE": "https://api-lgbuiltin.axworks.site/", "CONFIG_OUT": str(out)}
    subprocess.run(["bash", str(ROOT / "deploy" / "pages-build.sh")], check=True, env=env, cwd=ROOT)
    assert out.read_text(encoding="utf-8").strip() == 'window.LGB_API = "https://api-lgbuiltin.axworks.site";'


def test_deploy_files_have_no_hardcoded_secrets():
    for name in ["lgb-api.service", "Caddyfile", "setup-server.sh", "update-server.sh"]:
        text = (ROOT / "deploy" / name).read_text(encoding="utf-8")
        assert "MCP_HTTP_TOKEN=" not in text.replace("MCP_HTTP_TOKEN=\n", "")
    svc = (ROOT / "deploy" / "lgb-api.service").read_text(encoding="utf-8")
    assert "127.0.0.1" in svc  # API는 Caddy 뒤에서만 열린다
