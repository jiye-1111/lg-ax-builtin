"""도면 그림(PNG·JPG·WEBP·PDF)에서 벽·문·창 좌표를 읽는다.

그림을 읽는 일만 AI가 한다. 읽은 좌표를 다듬고 집 모양으로 만드는 계산은 worker/plan_room.py가 한다.
API 키는 서버 .env에만 둔다 (ANTHROPIC_API_KEY가 있으면 Claude, OPENAI_API_KEY만 있으면 OpenAI).
"""
from __future__ import annotations

import base64
import io
import logging
import os

from worker.plan_room import PlanRead, better_reading

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
- 치수가 하나도 없어도 멈추지 않는다. 방문(여닫이문의 문짝이나 열리는 호)이 하나라도 보이면 그 폭을 900 mm로 보고 그림 비율로 모든 좌표를 정한다(scale_from="door_width"). 어림값이어도 괜찮다.
- 치수도 없고 문도 전혀 보이지 않을 때만 scale_from="none"으로 하고 벽은 비운다.

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


REVIEW = """두 번째 그림은 방금 이 도면에서 옮겨 적은 결과를 다시 그린 것이다. 검은 선과 숫자는 벽과 그 번호, 파란 선은 창, 주황 선은 문이다. 아래 JSON이 그 결과다.
원래 도면과 하나씩 견줘 보고, 고친 전체 결과를 같은 형식으로 다시 적는다.
- 도면에는 있는데 빠진 벽(비스듬한 벽, 밖으로 튀어나온 부분 포함), 창, 문을 더한다. 바깥벽에 난 창은 하나도 빠뜨리지 않는다.
- 도면에 없는데 적힌 것은 뺀다. 위치나 길이가 눈에 띄게 다른 것은 고친다.
- 맞는 것은 좌표를 그대로 둔다. 좌표 원점과 크기 기준(scale_from)은 바꾸지 않는다.
- 벽을 더하거나 빼면 문과 창의 wall 번호를 새 목록 순서에 맞게 다시 매긴다."""
SKETCH_PX = 1000
SKETCH_COLORS = {"door": (230, 126, 34), "window": (41, 128, 185), "sliding_door": (41, 128, 185)}


def plan_sketch(plan: PlanRead) -> bytes:
    """읽은 벽·문·창을 다시 그린 그림(PNG). AI가 원래 도면과 견줘 볼 수 있게 벽 번호를 적는다."""
    from PIL import Image, ImageDraw

    xs = [v for w in plan.walls for v in (w.x1, w.x2)]
    ys = [v for w in plan.walls for v in (w.y1, w.y2)]
    x0, y0, span = min(xs), min(ys), max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    k, pad = (SKETCH_PX - 120) / span, 60

    def px(x: float, y: float) -> tuple[float, float]:
        return (x - x0) * k + pad, (y - y0) * k + pad

    im = Image.new("RGB", (int((max(xs) - x0) * k) + 2 * pad, int((max(ys) - y0) * k) + 2 * pad), "white")
    d = ImageDraw.Draw(im)
    for w in plan.walls:
        d.line([px(w.x1, w.y1), px(w.x2, w.y2)], fill=(20, 20, 20), width=7 if w.exterior else 4)
    for o in plan.openings:
        if not 0 <= o.wall < len(plan.walls):
            continue
        w = plan.walls[o.wall]
        L = ((w.x2 - w.x1) ** 2 + (w.y2 - w.y1) ** 2) ** 0.5 or 1.0
        ux, uy = (w.x2 - w.x1) / L, (w.y2 - w.y1) / L
        a, b = o.offset_mm, o.offset_mm + o.width_mm
        d.line([px(w.x1 + ux * a, w.y1 + uy * a), px(w.x1 + ux * b, w.y1 + uy * b)], fill=SKETCH_COLORS[o.type], width=11)
    for i, w in enumerate(plan.walls):
        cx, cy = px((w.x1 + w.x2) / 2, (w.y1 + w.y2) / 2)
        d.rectangle([cx - 11, cy - 8, cx + 11, cy + 8], fill="white")
        d.text((cx, cy), str(i), fill=(200, 0, 0), anchor="mm")
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def _ask(client, provider: str, system: str, content: list[dict]) -> PlanRead | None:
    if provider == "openai":
        r = client.chat.completions.parse(
            model=PLAN_OPENAI_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
            response_format=PlanRead,
            **({"reasoning_effort": os.getenv("PLAN_AI_OPENAI_EFFORT", "medium")} if openai_extra(PLAN_OPENAI_MODEL) else {}),
        )
        msg = r.choices[0].message
        return None if getattr(msg, "refusal", None) else msg.parsed
    r = client.beta.messages.parse(
        model=PLAN_MODEL, max_tokens=8000, system=system,
        messages=[{"role": "user", "content": content}], output_format=PlanRead,
    )
    return None if r.stop_reason == "refusal" else getattr(r, "parsed_output", None)


def _review(client, provider: str, plan_parts: list[dict], first: PlanRead) -> PlanRead:
    """읽은 결과를 그림으로 다시 그려 도면과 같이 보여 주고 고친 결과를 받는다. 받아들일지는 코드가 정한다."""
    try:
        sketch = _image_parts(plan_sketch(first), "image/png", "sketch.png", provider)[0]
        text = {"type": "text", "text": REVIEW + "\n\n" + first.model_dump_json()}
        second = _ask(client, provider, SYSTEM, [plan_parts[0], sketch, text])
    except Exception as e:  # noqa: BLE001 - 다시 보기는 덤이다: 실패하면 처음 읽은 것을 그대로 쓴다
        log.warning("도면 다시 보기 실패 (%s): %s", provider, e)
        return first
    return better_reading(first, second)


def read_plan(data: bytes, content_type: str, filename: str = "floorplan", client=None, provider: str | None = None) -> PlanRead:
    provider = provider or pick_provider()
    if provider is None:
        raise PlanReadError("도면을 읽는 기능이 아직 켜져 있지 않아요. 스캔 파일로 만들어 주세요")
    content = _image_parts(data, content_type, filename, provider)
    try:
        if client is None:
            if provider == "openai":
                import openai
                client = openai.OpenAI(timeout=TIMEOUT_S, max_retries=1)
            else:
                import anthropic
                client = anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=1)
        out = _ask(client, provider, SYSTEM, content)
    except Exception as e:
        log.warning("도면 읽기 실패 (%s): %s", provider, e)
        raise PlanReadError("도면을 읽다가 멈췄어요. 잠시 뒤에 다시 올려 주세요") from e
    if out is None:
        raise PlanReadError("도면을 읽지 못했어요. 벽이 또렷하게 보이는 도면을 올려 주세요")
    if out.readable and out.walls and os.getenv("PLAN_AI_REVIEW") == "1":
        out = _review(client, provider, content, out)
    return out
