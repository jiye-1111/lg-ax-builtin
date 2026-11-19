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
