"""실사로 보기: 지금 3D 화면을 이미지 AI(OpenAI 이미지 편집)로 사진처럼 바꾼다.

LG 제품은 바꾸면 안 된다 (실제 치수·색). 그래서
1) 브라우저가 같은 시점에서 LG 제품만 흰색인 마스크를 같이 보낸다
2) AI에는 제품 자리를 막은 마스크를 주고 (투명 = 바꿔도 되는 곳)
3) 받은 그림 위에 제품 픽셀을 3D 그대로 다시 얹는다 (AI가 마스크를 넘어 손대도 제품은 그대로)
사진은 프로젝트 scene/photoreal.png 하나만 남긴다 (매번 덮어씀).
"""
from __future__ import annotations

import base64
import binascii
import io
import os
import re

from PIL import Image, ImageFilter

SIZE = (1536, 1024)  # 이미지 AI가 받는 가로 크기
MIN_SIDE = 480
MAX_BYTES = 8 * 1024 * 1024
# 키마다 쓸 수 있는 이미지 모델이 다르다 (PC 키는 gpt-image-1이 '없는 모델'). 정해 두지 않았으면 좋은 것부터 차례로 시도하고
# 처음 된 모델을 기억한다
MODELS = [m for m in [os.getenv("PHOTOREAL_MODEL")] if m] or ["gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"]
MODEL = MODELS[0]
QUALITY = os.getenv("PHOTOREAL_QUALITY", "medium")
_DATA_URL = re.compile(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$")

PROMPT = """Turn this 3D interior visualization into a realistic interior photograph of the same room.
Keep exactly the same camera angle, room shape, walls, windows, doors, and every object's position, size and shape.
Make surfaces look real: wall paint or wallpaper texture, real wood or stone floor, soft fabric, natural daylight
through the windows with soft shadows and bounce light, gentle depth like a real camera.
Do not add, remove or move any furniture or appliance. No people, no text, no logos, no watermarks.
{extra}"""


class Unavailable(RuntimeError):
    """서버에 이미지 AI 키가 없다"""


def read_image(data_url: str, what: str) -> Image.Image:
    m = _DATA_URL.match(data_url or "")
    if not m:
        raise ValueError(f"{what}을 읽을 수 없어요")
    try:
        raw = base64.b64decode(m.group(2), validate=True)
    except (binascii.Error, ValueError):
        raise ValueError(f"{what}을 읽을 수 없어요") from None
    if len(raw) > MAX_BYTES:
        raise ValueError(f"{what}이 너무 커요")
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:  # noqa: BLE001 - PIL은 깨진 파일마다 다른 예외를 낸다
        raise ValueError(f"{what}을 읽을 수 없어요") from None
    if min(img.size) < MIN_SIDE:
        raise ValueError(f"{what}이 너무 작아요")
    return img.convert("RGB").resize(SIZE, Image.LANCZOS)


def product_alpha(mask: Image.Image) -> Image.Image:
    """흰 부분(LG 제품) = 255. 가장자리 1~2픽셀 번짐은 막으려고 살짝 넓힌다."""
    a = mask.convert("L").point(lambda v: 255 if v > 127 else 0)
    return a.filter(ImageFilter.MaxFilter(5))


def png_bytes(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def _no_such_model(e: Exception) -> bool:
    t = str(e).lower()
    return "does not exist" in t or "model_not_found" in t or "invalid model" in t or "not have access to model" in t


def edit_any_model(client, **kw):
    """MODELS를 차례로. '없는 모델'이면 다음, 된 모델은 맨 앞으로 (다음부터 바로 그것)."""
    global MODEL
    last = None
    for m in list(MODELS):
        try:
            r = client.edit(model=m, **kw)
        except Exception as e:  # noqa: BLE001 - openai 예외 종류에 묶이지 않게
            if not _no_such_model(e):
                raise
            last = e
            continue
        if MODELS[0] != m:
            MODELS.remove(m)
            MODELS.insert(0, m)
        MODEL = m
        return r
    raise last or RuntimeError("쓸 수 있는 이미지 모델이 없음")


def make_photo(view: Image.Image, mask: Image.Image, client, extra: str = "") -> Image.Image:
    alpha = product_alpha(mask)
    ai_mask = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    ai_mask.putalpha(alpha)  # 제품 자리는 불투명(못 바꿈), 나머지는 투명(바꿔도 됨)
    r = edit_any_model(client, image=("view.png", png_bytes(view), "image/png"), mask=("mask.png", png_bytes(ai_mask), "image/png"),
                       prompt=PROMPT.format(extra=extra).strip(), size=f"{SIZE[0]}x{SIZE[1]}", quality=QUALITY, n=1)
    out = Image.open(io.BytesIO(base64.b64decode(r.data[0].b64_json))).convert("RGB")
    if out.size != SIZE:
        out = out.resize(SIZE, Image.LANCZOS)
    keep = alpha.filter(ImageFilter.GaussianBlur(1))  # 제품 테두리만 살짝 섞는다
    keep = keep.point(lambda v: 255 if v >= 250 else v)
    return Image.composite(view, out, keep)


def default_client():
    if not os.getenv("OPENAI_API_KEY"):
        raise Unavailable("실사로 보기는 서버에 OpenAI 키가 있어야 해요")
    import openai
    return openai.OpenAI(timeout=float(os.getenv("PHOTOREAL_TIMEOUT_S", 150)), max_retries=0).images
