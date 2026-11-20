"""웹 화면 브랜드 기준 (docs/specs/web.md "디자인 기준").

LG 공식 색(Heritage Red #A50034, Warm Grey #F0ECE4), Pretendard 글꼴을 웹에 같이 넣어
인터넷 없이도 같은 화면이 나와야 하고, 첫 화면 배경은 Blender로 렌더한 실제 치수 주방 이미지다.
"""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "apps" / "web"


def css():
    return (WEB / "style.css").read_text(encoding="utf-8")


def test_lg_official_colors_are_tokens():
    root = re.search(r":root\s*{(.*?)}", css(), re.S).group(1).lower()
    assert "--lg: #a50034" in root
    assert "--warm-grey: #f0ece4" in root
    assert "--lg-active: #fd312e" in root


def test_pretendard_is_bundled_and_used():
    font = WEB / "vendor" / "fonts" / "PretendardVariable.woff2"
    assert font.exists() and font.stat().st_size > 100_000
    s = css()
    assert "@font-face" in s and "PretendardVariable.woff2" in s
    assert re.search(r"--font:\s*\"Pretendard", s)
    # 예전 Google Fonts 의존은 뺀다 (오프라인 시연)
    assert "fonts.googleapis.com" not in (WEB / "index.html").read_text(encoding="utf-8")


def test_hero_render_exists_and_is_light():
    for name, limit in (("hero-kitchen.webp", 450_000), ("hero-kitchen-m.webp", 220_000)):
        p = WEB / "img" / name
        assert p.exists(), name
        assert p.stat().st_size < limit, f"{name} {p.stat().st_size} bytes"


def test_app_name_is_housetwin():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert "<title>LG HouseTwin" in html
    assert "LG HouseTwin" in (WEB / "manifest.webmanifest").read_text(encoding="utf-8")


def test_service_worker_caches_brand_assets():
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    for f in ("./vendor/fonts/PretendardVariable.woff2", "./img/hero-kitchen.webp", "./img/hero-kitchen-m.webp"):
        assert f in sw


def test_home_keeps_upload_controls():
    js = (WEB / "js" / "pages.js").read_text(encoding="utf-8")
    for el in ('id="drop"', 'id="file"', 'id="fp"', 'id="sample"', 'id="projects"'):
        assert el in js


def test_remodel_is_simple():
    js = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    # 조작키는 버튼으로 여는 별도 창
    assert 'id="keysBtn"' in js and 'id="keysPop"' in js
    # 기호 대신 말로: 네모 영역 / 자유 영역
    assert "영역 □" not in js and "영역 ⬠" not in js
    assert "네모 영역" in js and "자유 영역" in js
    # 제품 목록은 오른쪽 탭이 아니라 아래 서랍 하나
    assert 'data-tab="lib"' not in js
