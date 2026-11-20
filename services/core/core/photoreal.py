"""실사로 보기: 지금 3D 화면을 이미지 AI(OpenAI 이미지 편집)로 사진처럼 바꾼다.

LG 제품은 바꾸면 안 된다 (실제 치수·색). 그래서
1) 브라우저가 같은 시점에서 LG 제품만 흰색인 마스크를 같이 보낸다
2) AI에는 지금 화면 전체를 참고 그림으로 주고 (마스크 없이, 구도·가구 유지)
3) 받은 그림 위에 제품 픽셀을 3D 그대로 다시 얹는다 (AI가 마스크를 넘어 손대도 제품은 그대로)
사진은 프로젝트 scene/photoreal.png 하나만 남긴다 (매번 덮어씀).
"""
from __future__ import annotations

import base64
import binascii
import io
import os
import re

import numpy as np
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
The plain background outside the room is empty: keep it plain and do not zoom in or crop.
The appliances are real products standing in this room: give them natural contact shadows on the floor
and soft light around them so they sit in the scene, but do not repaint them.
Plain boxes and cabinets are furniture cabinets with doors: never turn them into appliances
(no washing machines, dryers, ovens, microwaves, stoves, dishwashers).
Do not add, remove or move anything: no new furniture, devices, outlets, cables, plants, tableware or decorations.
No people, no text, no logos, no watermarks.
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


SPECK = 0.0002  # 화면의 0.02%보다 작은 조각(몇 픽셀 자투리)만 버린다. 멀리 있는 정수기처럼 작은 제품은 남겨야 한다
SHADE_GAIN = (0.93, 1.07)  # 넓히면 흰 냉장고가 회색·푸르스름하게 보인다  # 제품에 AI 사진의 빛을 입히는 범위. 색(채널 비율)은 그대로 두고 밝기만
SHADE_BLUR = 6  # 빛만 가져오고 AI가 그린 모양·글자는 안 가져오게 흐리는 정도


def drop_specks(alpha: Image.Image) -> Image.Image:
    """작은 덩어리 지우기. 1/4로 줄여 덩어리를 세고 원래 크기로 되돌린다."""
    w, h = alpha.size
    small = np.array(alpha.resize((w // 4, h // 4), Image.NEAREST)) > 127
    seen = np.zeros_like(small)
    keep = np.zeros_like(small)
    limit = SPECK * small.size
    for y0, x0 in zip(*np.nonzero(small)):
        if seen[y0, x0]:
            continue
        stack, part = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            part.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < small.shape[0] and 0 <= nx < small.shape[1] and small[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(part) >= limit:
            ys, xs = zip(*part)
            keep[list(ys), list(xs)] = True
    big = Image.fromarray((keep * 255).astype(np.uint8)).resize((w, h), Image.NEAREST)
    return Image.fromarray(np.minimum(np.array(alpha), np.array(big)))


def match_light(view: Image.Image, out: Image.Image, alpha: Image.Image) -> Image.Image:
    """제품 모양·색(채널 비율)은 3D 그대로, 빛만 AI 사진에서 가져온다.
    AI가 같은 자리에 그린 밝기 / 3D 밝기를 넓게 흐려서 곱한다 (스티커처럼 평평하게 떠 보이지 않게)."""
    a = np.array(alpha) > 127
    if not a.any():
        return view
    soft = lambda im: np.array(im.convert("L").filter(ImageFilter.GaussianBlur(SHADE_BLUR)), dtype=np.float32)
    gain = np.clip(soft(out) / np.maximum(soft(view), 8.0), *SHADE_GAIN)
    v = np.array(view, dtype=np.float32)
    v[a] = np.clip(v[a] * gain[a][:, None], 0, 255)
    return Image.fromarray(v.astype(np.uint8))


ALIGN_SCALES = [round(0.9 + 0.02 * i, 2) for i in range(26)]  # AI가 화면을 키우거나 줄여 그리는 배율 후보 (0.9~1.4)
ALIGN_MIN = 0.2  # 맞춘 뒤에도 윤곽이 이만큼 안 겹치면 제품을 얹지 않는다 (얹으면 두 대로 보임)


def _edges(img: Image.Image) -> np.ndarray:
    g = np.array(img.convert("L").filter(ImageFilter.GaussianBlur(1)), dtype=np.float32)  # 사진 결·재질 무늬는 흐려서 윤곽만
    e = np.abs(np.diff(g, axis=0, prepend=g[:1])) + np.abs(np.diff(g, axis=1, prepend=g[:, :1]))
    e -= e.mean()
    return e / (np.linalg.norm(e) + 1e-6)


def _zoom(img: Image.Image, k: float, dx: float = 0, dy: float = 0) -> Image.Image:
    """가운데 기준 k배 + (dx, dy)만큼 옮겨 그린다. k<1이면 줄인다 (AI가 키워 그린 걸 되돌릴 때)."""
    w, h = img.size
    a = 1 / k
    return img.transform((w, h), Image.AFFINE, (a, 0, w / 2 - a * (w / 2 + dx), 0, a, h / 2 - a * (h / 2 + dy)), Image.BICUBIC)


def align_to_view(view: Image.Image, out: Image.Image) -> tuple[Image.Image, float]:
    """AI 그림이 3D보다 확대·이동돼 있으면 되돌려 맞춘다. 작은 그림(1/8)에서 찾고 원래 크기에 한 번 적용. (맞춘 그림, 겹침 점수)"""
    w, h = view.size
    sw, sh = w // 8, h // 8
    ev, small = _edges(view.resize((sw, sh), Image.BILINEAR)), out.resize((sw, sh), Image.BILINEAR)
    score = lambda k, dx, dy: float((_edges(_zoom(small, 1 / k, dx, dy)) * ev).sum())
    # 굵게 찾고 (배율 0.04, 이동 2칸) 그 둘레만 촘촘히
    best = max((score(k, dx, dy), k, dx, dy) for k in ALIGN_SCALES[::2] for dx in range(-6, 7, 2) for dy in range(-6, 7, 2))
    _, k0, x0, y0 = best
    best = max([best] + [(score(k, dx, dy), k, dx, dy) for k in (round(k0 - 0.02, 2), k0, round(k0 + 0.02, 2))
                         for dx in (x0 - 1, x0, x0 + 1) for dy in (y0 - 1, y0, y0 + 1)])
    sc, k, dx, dy = best
    if k == 1.0 and dx == 0 and dy == 0:
        return out, sc  # 안 건드리면 흐려지지도 않는다
    fixed = _zoom(out, 1 / k, dx * 8, dy * 8)
    inside = _zoom(Image.new("L", out.size, 255), 1 / k, dx * 8, dy * 8)  # 줄이며 생긴 바깥 빈 곳은 3D 배경으로
    return Image.composite(fixed, view, inside), sc


def contact_shadow(out: Image.Image, alpha: Image.Image) -> Image.Image:
    """제품 아래쪽에 옅은 접지 그림자. AI가 못 그려 줘도 바닥에 붙어 보이게."""
    # 세게 하면 위에서 내려다본 화면에서 제품 둘레가 회색 판처럼 보인다. AI도 그림자를 그리니 옅게만
    sh = alpha.transform(alpha.size, Image.AFFINE, (1, 0, 0, 0, 1, -6))
    sh = np.array(sh.filter(ImageFilter.GaussianBlur(6)), dtype=np.float32) / 255 * 0.15
    o = np.array(out, dtype=np.float32) * (1 - sh[..., None])
    return Image.fromarray(np.clip(o, 0, 255).astype(np.uint8))


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
    alpha = drop_specks(product_alpha(mask))
    # 마스크를 주면 작은 모델이 마스크 밖을 새 방으로 다시 그려 버린다 (거실 → 주방 → 빈 방). 마스크 없이 지금 화면 전체를
    # 참고 그림으로 주고 (input_fidelity high: 구도·가구 유지), 제품 자리는 아래에서 3D 픽셀로 다시 덮는다
    kw = {"image": ("view.png", png_bytes(view), "image/png"), "prompt": PROMPT.format(extra=extra).strip(),
          "size": f"{SIZE[0]}x{SIZE[1]}", "quality": QUALITY, "n": 1}
    try:
        r = edit_any_model(client, input_fidelity="high", **kw)
    except Exception as e:  # noqa: BLE001
        if "input_fidelity" not in str(e):
            raise
        r = edit_any_model(client, **kw)  # 이 모델은 input_fidelity를 모른다
    out = Image.open(io.BytesIO(base64.b64decode(r.data[0].b64_json))).convert("RGB")
    if out.size != SIZE:
        out = out.resize(SIZE, Image.LANCZOS)
    out, score = align_to_view(view, out)
    if score < ALIGN_MIN:  # AI가 구도를 너무 바꿨다: 제품을 얹으면 엉뚱한 곳에 떠 보인다
        return out
    out = contact_shadow(out, alpha)
    keep = alpha.filter(ImageFilter.GaussianBlur(2.5))  # 제품 테두리만 살짝 섞는다
    keep = keep.point(lambda v: 255 if v >= 250 else v)
    return Image.composite(match_light(view, out, alpha), out, keep)


def default_client():
    if not os.getenv("OPENAI_API_KEY"):
        raise Unavailable("실사로 보기는 서버에 OpenAI 키가 있어야 해요")
    import openai
    return openai.OpenAI(timeout=float(os.getenv("PHOTOREAL_TIMEOUT_S", 150)), max_retries=0).images
