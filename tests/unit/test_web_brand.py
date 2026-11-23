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


def test_home_shows_only_upload_samples_and_recent():
    """지예: 첫 화면은 스캔 올리기(스캔 파일·도면 칸 따로), 샘플 집 카드, 최근에 만든 집만."""
    js = (WEB / "js" / "pages.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")
    for el in ('slotHtml("scan"', 'slotHtml("plan"', 'id="go"', "data-sample=", 'id="projects"', "/api/me/projects", "data-del="):
        assert el in js, el
    home = js.split("// ---------- 화면: 방문 스캔 신청")[0]
    for gone in ('id="sample"', 'id="pick"', 'class="steps"', "hero-cap", "꾸미던 집 이어서", "기사 스캔", "placements.length}개"):
        assert gone not in home, gone
    assert "data-nav" not in html and "기사 화면" not in html
    for f in ("apt_living_kitchen", "studio_living", "ugscan_2026-11-18"):
        assert (WEB / "img" / "samples" / f"{f}.webp").exists(), f


def test_remodel_is_simple():
    js = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    # 조작키는 버튼으로 여는 별도 창
    assert 'id="keysBtn"' in js and 'id="keysPop"' in js
    # 영역 그리기·추천 탭은 뺐다 (지예: 추천은 하우니 대화로)
    assert "영역 □" not in js and "영역 ⬠" not in js
    assert 'data-mode="rect"' not in js
    # 제품 목록은 오른쪽 탭이 아니라 왼쪽 세로 목록 하나 (지예: 가로보다 세로)
    assert 'data-tab="lib"' not in js
    css = (WEB / "style.css").read_text(encoding="utf-8")
    assert '"lib stage side"' in css


def test_product_detail_and_filters():
    js = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    # 제품을 누르면 상세 창, 거기서 넣어 보기
    assert 'id="pdModal"' in js and 'id="pdPlace"' in js
    # 필터: 폭, 높이 + 단계별 옵션(설치 방식 → 종류 → … → 색상)
    for f in ('id="fW"', 'id="fH"', 'id="steps"', "optionSteps("):
        assert f in js
    # 먼저 공간 용도를 묻고, 그 용도에 맞는 가전 종류를 보여 준다
    assert 'id="ask"' in js and "이 공간을 어떤 용도로 쓰실 건가요?" in js
    assert "놓는 곳" not in js and "빌트인 느낌" not in js
    # LGE.COM에서 파는 제품만 목록에 나온다 (판매 상태를 화면에 따로 적지는 않는다)
    assert "f.variants.filter(sellable)" in js and 'id="fSale"' not in js and "판매 상태" not in js


def test_remodel_stage_is_uncluttered():
    """지예: '아직도 조잡해 보인다' → 3D를 가리는 아래 칸을 없애고, 목록은 한 줄씩, 긴 설명은 접는다."""
    js = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    canvas = js.split('<div class="canvas">', 1)[1].split('<aside class="side"', 1)[0]
    # 살아 보기 설정과 안내는 3D 아래 칸이 아니라 3D 위에 뜨는 작은 카드
    assert 'id="simctl"' in canvas and 'id="hint"' in canvas
    # 지예: 참고 사항 칸은 뺀다. 살아 보기 칸은 입력 한 줄과 결과 한 줄
    assert "sim-notes" not in js and "참고 사항" not in js and js.count('<div class="sim-row">') == 3
    assert 'style="font-size:12px;margin:6px 0 0">참고용' not in js
    s = css()
    assert re.search(r"\.lib #lib\s*{[^}]*grid-template-columns:\s*1fr", s)


def test_product_detail_has_no_verdict_or_spec_notes():
    """지예: 들어가는지는 넣고 나서 3D에서 초록/빨강으로 판단한다 → 상세 창엔 판정 줄도 근거 문구도 없다. 크기·색만."""
    js = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    assert 'id="pdVerdict"' not in js and "넣어 보면 알려" not in js
    assert "설치 사양 근거" not in js and "확인 안 됨" not in js and "색상 표기 없음" not in js


def test_logo_goes_to_start_screen_without_demo_tag():
    """지예: 왼쪽 위 로고를 누르면 시작 화면으로, '시연' 글자는 뺀다."""
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert 'class="brand" href="#/new"' in html
    assert ">시연<" not in html
