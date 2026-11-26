"""실사로 보기: LG 제품이 실제 제품 사진처럼 나오게 (LGE.COM 사진을 참고로 주고, 해·재질을 글로 알려 주고,
AI가 모양을 지켰으면 AI가 그린 제품을 쓰되 색은 카탈로그 색으로 되돌린다)."""
import base64
import io
from types import SimpleNamespace as NS

import numpy as np
import pytest
from api import main
from core import photoreal
from core.service import Service
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"
W, H = 1536, 1024
BOX = (600, 300, 800, 800)  # 냉장고 자리 (픽셀)


def png_url(img):
    b = io.BytesIO()
    img.save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def fridge(color, split=550, gap=(40, 40, 40)):
    """문 네 짝 냉장고 같은 그림: 가운데 세로 줄 + 가로 줄"""
    view = Image.new("RGB", (W, H), (200, 190, 180))
    d = ImageDraw.Draw(view)
    d.rectangle(BOX, fill=color)
    d.line([(700, 300), (700, 800)], fill=gap, width=4)
    d.line([(600, split), (800, split)], fill=gap, width=4)
    return view


def mask_img():
    m = Image.new("RGB", (W, H), (0, 0, 0))
    m.paste((255, 255, 255), BOX)
    return m


def answer(img):
    b = io.BytesIO()
    img.save(b, "PNG")
    return NS(data=[NS(b64_json=base64.b64encode(b.getvalue()).decode())])


class AI:
    """AI가 돌려줄 그림을 정해 둔다. 받은 것도 남겨 둔다"""

    def __init__(self, make):
        self.make, self.sent = make, None

    def edit(self, **kw):
        self.sent = kw
        return answer(self.make())


def detailed_ai_fridge():
    """AI가 같은 냉장고를 더 사진처럼 그렸다: 줄은 같은 자리, 손잡이 홈·반사·로고가 생기고 색은 조금 누렇게"""
    out = fridge((214, 205, 180))
    out.paste((250, 100, 50), (0, 0, W, 200))  # 벽은 AI 마음대로
    d = ImageDraw.Draw(out)
    d.rectangle((690, 420, 696, 500), fill=(150, 145, 130))  # 손잡이 홈
    d.rectangle((620, 320, 640, 520), fill=(232, 224, 200))  # 유리 반사
    d.rectangle((740, 760, 760, 766), fill=(120, 115, 100))  # 작은 로고
    return out


def test_ai_detail_is_kept_when_the_shape_matches_but_colour_comes_from_3d():
    view, out = fridge((241, 238, 233)), detailed_ai_fridge()
    alpha = photoreal.product_alpha(mask_img())
    got = photoreal.blend_products(view, out, alpha, [BOX])
    assert got.getpixel((693, 460)) != view.getpixel((693, 460))  # 손잡이 홈은 AI 것
    inside = np.asarray(got.crop(BOX), dtype=float).reshape(-1, 3).mean(0)
    want = np.asarray(view.crop(BOX), dtype=float).reshape(-1, 3).mean(0)
    # 색(누런 기)은 3D(카탈로그 색)로 돌아온다: 채널 비율이 3D와 같다
    assert abs((inside[2] - inside[0]) - (want[2] - want[0])) < 4


def test_ai_product_is_dropped_when_the_shape_changed():
    view = fridge((241, 238, 233))
    out = Image.new("RGB", (W, H), (200, 190, 180))
    ImageDraw.Draw(out).rectangle((600, 300, 800, 800), fill=(60, 60, 60))  # AI가 다른 물건(검은 판)으로 바꿨다
    for x in range(610, 800, 25):
        ImageDraw.Draw(out).line([(x, 300), (x, 800)], fill=(200, 200, 200), width=3)
    alpha = photoreal.product_alpha(mask_img())
    got = photoreal.blend_products(view, out, alpha, [BOX])
    r, g, b = got.getpixel((650, 400))
    assert r > 200 and abs(r - 241) < 25  # 3D 제품이 그대로 남는다 (밝기만 조금)


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    s = Service(storage=tmp_path / "st")
    s.image_client = AI(detailed_ai_fridge)
    s.photo_fetch = lambda url: (Image.new("RGB", (800, 800), (245, 240, 230)), url)[0]
    return s


@pytest.fixture
def c(svc):
    main.app.dependency_overrides[main.get_service] = lambda: svc
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def pid(c):
    with open(REAL, "rb") as f:
        return c.post("/api/projects", files={"file": ("home.usdz", f)}, data={"scanned_by": "customer"}).json()["project_id"]


CAM = {"pos": [8.0, 1.6, 9.0], "target": [3.5, 1.2, 5.0], "fov": 50}
SKU = "G646GBB031"


def body(**kw):
    return {"image": png_url(fridge((241, 238, 233))), "mask": png_url(mask_img()), "camera": CAM,
            "products": [{"sku": SKU, "box": [600 / W, 300 / H, 800 / W, 800 / H]}], **kw}


def test_real_lg_photo_and_words_go_to_the_image_ai(c, svc, pid):
    r = c.post(f"/api/projects/{pid}/photoreal", json=body())
    assert r.status_code == 200, r.text
    sent = svc.image_client.sent
    imgs = sent["image"]
    assert isinstance(imgs, list) and len(imgs) == 2  # 지금 화면 + LGE.COM 사진 한 장
    assert "오브제컬렉션 베이지" in sent["prompt"] and "image 2" in sent["prompt"] and "glass" in sent["prompt"]
    # 사진은 한 번 받으면 서버에 남겨 두고 다시 받지 않는다
    calls = []
    svc.photo_fetch = lambda url: calls.append(url)
    c.post(f"/api/projects/{pid}/photoreal", json=body())
    assert calls == [] and len(svc.image_client.sent["image"]) == 2


def test_unknown_or_bad_products_are_ignored_or_rejected(c, svc, pid):
    r = c.post(f"/api/projects/{pid}/photoreal", json=body(products=[{"sku": "NOPE123", "box": [0.1, 0.1, 0.2, 0.2]}]))
    assert r.status_code == 200 and not isinstance(svc.image_client.sent["image"], list)
    for bad in ([{"sku": "../x", "box": [0, 0, 1, 1]}], [{"sku": SKU, "box": [0, 0, 2, 1]}], [{"sku": SKU, "box": [0, 0]}]):
        assert c.post(f"/api/projects/{pid}/photoreal", json=body(products=bad)).status_code == 422


def test_photo_download_failure_still_makes_a_picture(c, svc, pid):
    def boom(url):
        raise OSError("blocked")
    svc.photo_fetch = boom
    r = c.post(f"/api/projects/{pid}/photoreal", json=body())
    assert r.status_code == 200 and not isinstance(svc.image_client.sent["image"], list)


def test_daylight_time_and_facing_go_into_the_prompt(c, svc, pid):
    assert c.put(f"/api/projects/{pid}/site", json={"auto_north": True}).status_code == 200
    r = c.post(f"/api/projects/{pid}/photoreal", json=body(daylight={"date": "2026-11-26", "time": "15:30"}))
    assert r.status_code == 200, r.text
    p = svc.image_client.sent["prompt"]
    assert "15:30" in p and "-facing" in p and "Sunlight" in p


def test_blender_fallback_uses_the_same_sun(c, svc, pid, monkeypatch):
    import json
    import subprocess

    from worker import runner

    jobs = []

    def run(cmd, **kw):
        job = json.loads(open(cmd[cmd.index("--job") + 1], encoding="utf-8").read())
        jobs.append(job)
        Image.new("RGB", (48, 32), (90, 120, 150)).save(job["out_png"], "PNG")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(runner, "blender_bin", lambda: "blender")
    monkeypatch.setattr(runner.subprocess, "run", run)
    monkeypatch.setenv("USE_BLENDER", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    svc.image_client = None
    c.put(f"/api/projects/{pid}/site", json={"auto_north": True})
    r = c.post(f"/api/projects/{pid}/photoreal", json=body(daylight={"date": "2026-11-26", "time": "15:30"}))
    assert r.status_code == 200 and r.json()["model"] == "blender"
    assert jobs[0]["sun"] and jobs[0]["sun"]["altitude_deg"] < 30  # 11월 오후 세 시 반, 낮은 해
