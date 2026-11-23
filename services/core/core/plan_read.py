"""도면 그림(PNG·JPG·WEBP·PDF)에서 벽·문·창 좌표를 읽는다.

그림을 읽는 일만 AI가 한다. 읽은 좌표를 다듬고 집 모양으로 만드는 계산은 worker/plan_room.py가 한다.
API 키는 서버 .env에만 둔다 (ANTHROPIC_API_KEY가 있으면 Claude, OPENAI_API_KEY만 있으면 OpenAI).
"""
from __future__ import annotations

import base64
import logging
import os

from worker.plan_room import PlanRead

from .ai_style import MODEL, OPENAI_MODEL, openai_extra, pick_provider

log = logging.getLogger(__name__)
TIMEOUT_S = float(os.getenv("PLAN_AI_TIMEOUT_S") or 90)
PLAN_OPENAI_MODEL = os.getenv("PLAN_AI_OPENAI_MODEL") or OPENAI_MODEL
PLAN_MODEL = os.getenv("PLAN_AI_MODEL") or MODEL

SYSTEM = """집 평면도 한 장을 보고 벽, 문, 창의 위치를 mm 좌표로 옮겨 적는다.

좌표
- 단위는 mm. x는 그림의 오른쪽, y는 그림의 아래쪽으로 커진다. 집의 왼쪽 위 바깥 모서리를 (0, 0) 근처에 둔다.
- 벽은 중심선의 양 끝점으로 적는다. 꺾이는 곳마다 벽을 나눈다. 이어지는 벽은 끝점 좌표가 정확히 같아야 한다.
- 바깥벽은 한 바퀴 돌아 닫히게 차례대로 먼저 적고(exterior=true), 그다음 방을 나누는 안쪽 벽을 적는다(exterior=false).
- 가구, 치수선, 글자, 발코니 난간은 벽이 아니다.

크기
- 도면에 적힌 치수 숫자를 그대로 쓴다(scale_from="dimensions"). 숫자가 벽마다 다 있지 않으면 적힌 숫자와 그림 비율로 나머지를 정한다.
- 치수가 하나도 없으면 방문 폭을 900 mm로 보고 비율을 정한다(scale_from="door_width").
- 치수도 방문도 없어서 크기를 정할 수 없으면 scale_from="none"으로 하고 벽은 비운다.

문과 창
- door: 여닫이·미닫이 방문과 현관문. window: 벽에 난 창. sliding_door: 거실에서 발코니로 나가는 바닥까지 내려오는 큰 유리문.
- wall은 그 문·창이 있는 벽이 walls 목록에서 몇 번째인지(0부터), offset_mm는 그 벽의 (x1, y1) 끝에서 문·창이 시작하는 곳까지의 거리다.

평면도가 아니거나 너무 흐려서 벽을 알아볼 수 없으면 readable=false로 하고 reason에 한국어 한 문장으로 이유를 쓴다."""
ASK = "이 도면의 벽, 문, 창을 옮겨 적어 주세요."


class PlanReadError(Exception):
    """도면을 읽지 못한 이유를 사용자에게 그대로 보여 준다."""


def _image_parts(data: bytes, content_type: str, filename: str, provider: str) -> list[dict]:
    b64 = base64.standard_b64encode(data).decode()
    pdf = content_type == "application/pdf"
    if provider == "openai":
        part = ({"type": "file", "file": {"filename": filename, "file_data": f"data:application/pdf;base64,{b64}"}} if pdf
                else {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{b64}", "detail": "high"}})
    else:
        part = {"type": "document" if pdf else "image", "source": {"type": "base64", "media_type": content_type, "data": b64}}
    return [part, {"type": "text", "text": ASK}]


def read_plan(data: bytes, content_type: str, filename: str = "floorplan", client=None, provider: str | None = None) -> PlanRead:
    provider = provider or pick_provider()
    if provider is None:
        raise PlanReadError("도면을 읽는 기능이 아직 켜져 있지 않아요. 스캔 파일로 만들어 주세요")
    content = _image_parts(data, content_type, filename, provider)
    try:
        if provider == "openai":
            if client is None:
                import openai
                client = openai.OpenAI(timeout=TIMEOUT_S, max_retries=1)
            r = client.chat.completions.parse(
                model=PLAN_OPENAI_MODEL,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
                response_format=PlanRead,
                **({"reasoning_effort": os.getenv("PLAN_AI_OPENAI_EFFORT", "medium")} if openai_extra(PLAN_OPENAI_MODEL) else {}),
            )
            msg = r.choices[0].message
            out = None if getattr(msg, "refusal", None) else msg.parsed
        else:
            if client is None:
                import anthropic
                client = anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=1)
            r = client.beta.messages.parse(
                model=PLAN_MODEL, max_tokens=8000, system=SYSTEM,
                messages=[{"role": "user", "content": content}], output_format=PlanRead,
            )
            out = None if r.stop_reason == "refusal" else getattr(r, "parsed_output", None)
    except Exception as e:
        log.warning("도면 읽기 실패 (%s): %s", provider, e)
        raise PlanReadError("도면을 읽다가 멈췄어요. 잠시 뒤에 다시 올려 주세요") from e
    if out is None:
        raise PlanReadError("도면을 읽지 못했어요. 벽이 또렷하게 보이는 도면을 올려 주세요")
    return out
