"""실사로 보기: 다 그린 사진을 3D 화면과 견줘 본다 (더한 것·뺀 것·두 번 그린 것·바뀐 것·떠 있는 것).

이미지 AI는 구도를 지켜도 가끔 빈 바닥에 소파를 그리거나 침대를 소파로 바꾼다. 그림 픽셀만으로는
햇빛 자국·바닥 무늬와 새 가구를 가르기 어려워서, 보는 AI(OpenAI 비전)에게 물건 목록과 두 그림을 주고
틀린 것만 적게 한다. 다시 그릴지, Blender로 넘길지는 코드(service_photoreal)가 정한다.
"""
from __future__ import annotations

import base64
import io
import logging
import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger(__name__)
CHECK_MODEL = os.getenv("PHOTOREAL_CHECK_MODEL") or os.getenv("STYLE_AI_OPENAI_MODEL", "gpt-5-mini")
CHECK_EFFORT = os.getenv("PHOTOREAL_CHECK_EFFORT", "low")
CHECK_SIDE = 1024  # 견줘 볼 그림 크기 (가로). 작은 공유기도 보일 만큼

SYSTEM = """You compare two pictures of the same room from the same camera.
Image 1 is a 3D render: it is the truth. Image 2 is a photo-like picture made from it.
Find only clear differences in OBJECTS between them:
- added: an object in image 2 that is not in image 1 (for example a sofa, chair, appliance, rug, plant or lamp on floor that is empty in image 1)
- missing: an object of image 1 that is gone in image 2
- duplicated: one object drawn twice, or a second ghost copy next to it
- changed: an object turned into a different kind of object (a bed became a sofa, a cabinet became a washing machine)
- moved: an object clearly in another place
- floating: an object hanging in the air that stands on the floor or on furniture in image 1
- overlap: objects that are apart in image 1 but overlap or merge in image 2
Ignore everything else: colours, materials, textures, lighting, sun patches, shadows, reflections, small details,
handles, logos, wall or floor finish, sharpness, and the plain background outside the room.
Image 1 may show coloured overlays or lines on the floor; ignore them.
For each problem say what it is in a few English words and where it is in image 2 (like "lower left").
If the two pictures hold the same objects in the same places, answer with no problems."""


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["added", "missing", "duplicated", "changed", "moved", "floating", "overlap"]
    what: str = Field(description="what object, a few English words, e.g. 'a white sofa'")
    where: str = Field(description="where in image 2, e.g. 'lower left'")


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problems: list[Problem]


def _jpeg(img) -> str:
    w, h = img.size
    small = img.convert("RGB").resize((CHECK_SIDE, round(CHECK_SIDE * h / w)))
    b = io.BytesIO()
    small.save(b, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def check(view, out, scene_lines: list[str], client=None) -> list[dict] | None:
    """틀린 것 목록 [{kind, what, where}]. 견줘 보지 못했으면 None (그림은 그대로 쓴다)"""
    if client is None:
        if not os.getenv("OPENAI_API_KEY"):
            return None
        import openai

        client = openai.OpenAI(timeout=float(os.getenv("PHOTOREAL_CHECK_TIMEOUT_S", "60")), max_retries=1)
    listing = "\n".join(scene_lines) or "(no listed objects)"
    content = [
        {"type": "text", "text": "Objects in image 1 (positions are % of the picture):\n" + listing},
        {"type": "image_url", "image_url": {"url": _jpeg(view), "detail": "high"}},
        {"type": "image_url", "image_url": {"url": _jpeg(out), "detail": "high"}},
    ]
    extra = {"reasoning_effort": CHECK_EFFORT} if CHECK_EFFORT and CHECK_MODEL.startswith(("gpt-5", "o")) else {}
    try:
        r = client.chat.completions.parse(model=CHECK_MODEL, response_format=Verdict, **extra,
                                          messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}])
        msg = r.choices[0].message
        if getattr(msg, "refusal", None) or msg.parsed is None:
            return None
        return [p.model_dump() for p in msg.parsed.problems]
    except Exception as e:  # noqa: BLE001 - 견줘 보기는 덤이다: 못 해도 사진은 낸다
        log.warning("실사 견줘 보기 실패: %s", e)
        return None
