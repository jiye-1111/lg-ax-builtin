"""웹앱 설치(PWA) 파일이 제대로 서빙되는지. 서비스 워커가 캐시하는 파일이 실제로 있는지도 본다."""
import json
import re

from fastapi.testclient import TestClient

from api import main

client = TestClient(main.app)


def test_manifest_served_with_icons():
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")
    m = json.loads(r.text)
    assert m["display"] == "standalone" and m["lang"] == "ko"
    sizes = {i["sizes"] for i in m["icons"]}
    assert {"192x192", "512x512"} <= sizes
    for icon in m["icons"]:
        assert client.get("/" + icon["src"]).status_code == 200


def test_index_links_manifest_and_icons():
    html = client.get("/").text
    assert 'rel="manifest"' in html and 'rel="apple-touch-icon"' in html
    assert client.get("/icons/apple-touch-icon.png").status_code == 200


def test_js_modules_have_js_mime():
    for path in ("/app.js", "/js/remodel.js", "/sw.js"):
        r = client.get(path)
        assert r.status_code == 200
        assert "javascript" in r.headers["content-type"]


def test_service_worker_shell_files_exist_and_api_not_cached():
    sw = client.get("/sw.js").text
    shell = re.search(r"const SHELL = \[(.*?)\];", sw, re.S).group(1)
    for path in re.findall(r'"\./([^"]*)"', shell):
        assert client.get("/" + path).status_code == 200, path
    assert 'startsWith("/api/")' in sw


def test_remodel_has_undo_and_install_check():
    WEB = main.config.ROOT / "apps" / "web"
    remodel = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    pages = (WEB / "js" / "pages.js").read_text(encoding="utf-8")
    # 되돌리기: 버튼과 Ctrl+Z 둘 다
    assert 'id="undo"' in remodel and "e.ctrlKey || e.metaKey" in remodel and "undo()" in remodel
    # 설치 전 확인: 고객 화면(놓은 제품 탭)과 기사 화면 둘 다 같은 목록을 쓴다
    assert "export async function installCheck" in pages and "/install-check" in pages
    assert 'id="icBox"' in remodel and 'id="icBox"' in pages


def test_remodel_has_install_request_and_before_view():
    WEB = main.config.ROOT / "apps" / "web"
    remodel = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    pages = (WEB / "js" / "pages.js").read_text(encoding="utf-8")
    assert "export function installRequestBox" in pages and "/install-request" in pages
    assert 'id="irBox"' in remodel
    # 처음 모습: 스캔 그대로의 장면을 따로 받아 겹쳐 보여 준다
    assert 'id="beforeBtn"' in remodel and "/files/before.glb" in remodel
