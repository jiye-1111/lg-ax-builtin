"""실사로 보기: 지금 3D 화면 + LG 제품 마스크 → 이미지 AI가 벽·바닥·빛만 사진처럼, 제품 픽셀은 그대로."""
import base64
import io

import pytest
from api import main
from core.service import Service
from fastapi.testclient import TestClient
from PIL import Image

REAL = main.config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"
W, H = 1536, 1024


def png_url(img: Image.Image) -> str:
    b = io.BytesIO()
    img.save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def view_and_mask():
    view = Image.new("RGB", (W, H), (200, 190, 180))
    mask = Image.new("RGB", (W, H), (0, 0, 0))
    # 가운데에 LG 제품이 있다 (흰 마스크)
    view.paste((10, 20, 30), (600, 400, 800, 700))
    mask.paste((255, 255, 255), (600, 400, 800, 700))
    return view, mask


class FakeImages:
    def __init__(self):
        self.sent = None

    def edit(self, **kw):
        self.sent = kw
        out = Image.new("RGB", (W, H), (250, 100, 50))  # AI가 전부 다른 색으로 칠했다고 치자
        b = io.BytesIO()
        out.save(b, "PNG")
        from types import SimpleNamespace as NS
        return NS(data=[NS(b64_json=base64.b64encode(b.getvalue()).decode())])


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    s = Service(storage=tmp_path / "st")
    s.image_client = FakeImages()
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


def test_photoreal_keeps_lg_product_pixels_and_changes_the_rest(c, svc, pid):
    view, mask = view_and_mask()
    r = c.post(f"/api/projects/{pid}/photoreal", json={"image": png_url(view), "mask": png_url(mask)})
    assert r.status_code == 200, r.text
    got = Image.open(io.BytesIO(c.get(r.json()["url"].replace("/api", "/api", 1)).content)).convert("RGB")
    assert got.size == (W, H)
    r_, g_, b_ = got.getpixel((700, 550))                   # 제품은 3D 그대로 (실제 치수·색), 밝기만 주변 빛에 맞춤
    assert abs(r_ * 2 - g_) <= 2 and abs(r_ * 3 - b_) <= 3 and 8 <= r_ <= 11
    assert got.getpixel((100, 100)) == (250, 100, 50)      # 나머지는 AI가 바꾼 것
    sent = svc.image_client.sent
    assert "Do not add, remove or move" in sent["prompt"]
    m = Image.open(io.BytesIO(sent["mask"][1])).convert("RGBA")
    assert m.getpixel((700, 550))[3] == 255 and m.getpixel((100, 100))[3] == 0  # 투명 = AI가 바꿔도 되는 곳


def test_photoreal_needs_a_server_key(c, svc, pid, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    svc.image_client = None
    view, mask = view_and_mask()
    r = c.post(f"/api/projects/{pid}/photoreal", json={"image": png_url(view), "mask": png_url(mask)})
    assert r.status_code == 503 and "키" in r.json()["detail"]


def test_photoreal_is_limited_per_project(c, svc, pid):
    view, mask = view_and_mask()
    body = {"image": png_url(view), "mask": png_url(mask)}
    codes = [c.post(f"/api/projects/{pid}/photoreal", json=body).status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429


def test_photoreal_rejects_bad_images(c, pid):
    view, mask = view_and_mask()
    assert c.post(f"/api/projects/{pid}/photoreal", json={"image": "data:image/png;base64,AAAA", "mask": png_url(mask)}).status_code == 422
    small = view.resize((100, 100))
    assert c.post(f"/api/projects/{pid}/photoreal", json={"image": png_url(small), "mask": png_url(mask)}).status_code == 422


def test_photoreal_tries_the_next_model_when_the_key_cannot_use_one(c, svc, pid, monkeypatch):
    from core import photoreal
    monkeypatch.setattr(photoreal, "MODELS", ["gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"])
    tried = []
    inner = svc.image_client

    class Picky:
        def edit(self, **kw):
            tried.append(kw["model"])
            if kw["model"] != "gpt-image-1-mini":
                raise RuntimeError(f"Error code: 400 - The model '{kw['model']}' does not exist.")
            return inner.edit(**kw)

    svc.image_client = Picky()
    view, mask = view_and_mask()
    r = c.post(f"/api/projects/{pid}/photoreal", json={"image": png_url(view), "mask": png_url(mask)})
    assert r.status_code == 200 and r.json()["model"] == "gpt-image-1-mini"
    assert tried == ["gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"]
    tried.clear()
    c.post(f"/api/projects/{pid}/photoreal", json={"image": png_url(view), "mask": png_url(mask)})
    assert tried == ["gpt-image-1-mini"]  # 된 모델을 기억한다


def test_tiny_product_specks_are_dropped_and_products_get_a_floor_shadow():
    from core import photoreal
    _, mask = view_and_mask()
    mask.paste((255, 255, 255), (100, 900, 120, 915))  # 멀리 걸친 모서리 조각
    alpha = photoreal.drop_specks(photoreal.product_alpha(mask))
    assert alpha.getpixel((110, 905)) == 0 and alpha.getpixel((700, 550)) == 255
    out = photoreal.contact_shadow(Image.new("RGB", (W, H), (200, 200, 200)), alpha)
    assert out.getpixel((700, 706))[0] < 190     # 제품 바로 아래 바닥은 어두워지고
    assert out.getpixel((100, 100))[0] == 200    # 먼 곳은 그대로
