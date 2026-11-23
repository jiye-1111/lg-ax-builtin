"""도면을 조각으로 나눠 읽기: 그림에서 집 테두리 찾기, 조각 자르기, 조각 결과 합치기."""
import io
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from core.plan_read import read_plan
from core.plan_tiles import house_box, tiles_for
from worker.plan_merge import TileOpening, TileRead
from worker.plan_room import PlanRead, PlanWall


def drawing(w=1000, h=700, box=(150, 120, 850, 580)):
    """두꺼운 바깥벽, 얇은 치수선, 글자 같은 작은 점이 있는 도면"""
    im = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(im)
    d.rectangle(box, outline=0, width=8)
    d.line([(box[0], 40), (box[2], 40)], fill=0, width=1)   # 치수선 (얇다)
    for x in range(60, 940, 37):
        d.rectangle([x, 640, x + 6, 652], fill=0)            # 글자
    b = io.BytesIO()
    im.convert("RGB").save(b, "PNG")
    return b.getvalue()


def plan(w=7000, d=4600):
    pts = [(0, 0), (w, 0), (w, d), (0, d)]
    return PlanRead(readable=True, scale_from="dimensions",
                    walls=[PlanWall(x1=a[0], y1=a[1], x2=b[0], y2=b[1]) for a, b in zip(pts, pts[1:] + pts[:1])])


def test_house_box_is_the_thick_outer_wall_not_text_or_dimension_lines():
    x0, y0, x1, y1 = house_box(Image.open(io.BytesIO(drawing())))
    assert abs(x0 - 150) <= 8 and abs(y0 - 120) <= 8 and abs(x1 - 850) <= 8 and abs(y1 - 580) <= 8


def test_no_box_for_a_blank_picture():
    assert house_box(Image.new("RGB", (400, 300), "white")) is None


def test_four_overlapping_tiles_cover_the_house_and_are_enlarged():
    im = Image.open(io.BytesIO(drawing()))
    tiles = tiles_for(im, (150, 120, 850, 580))
    assert len(tiles) == 4
    for png, (ox, oy, k) in tiles:
        t = Image.open(io.BytesIO(png))
        assert min(t.size) >= 768 and k > 1
    xs = sorted({o[0] for _, o in tiles})
    assert xs[0] <= 150 and xs[1] < 500  # 가운데가 겹친다


class Answers:
    """처음은 집 전체, 그다음부터는 조각마다 같은 답"""

    def __init__(self, first, tile):
        self.calls, self.first, self.tile = [], first, tile
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))

    def _parse(self, **kw):
        self.calls.append(kw)
        parsed = self.first if len(self.calls) == 1 else self.tile
        if isinstance(parsed, Exception):
            raise parsed
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed, refusal=None))])


def test_tiles_add_what_the_first_look_missed(monkeypatch):
    monkeypatch.delenv("PLAN_AI_TILES", raising=False)
    # 조각마다 조각 좌표로 창 하나를 답한다. 위쪽 벽 위에 오는 조각 것만 붙는다
    c = Answers(plan(), TileRead(openings=[TileOpening(type="window", x1=300, y1=0, x2=500, y2=0)]))
    out = read_plan(drawing(), "image/png", "a.png", client=c, provider="openai")
    assert len(c.calls) == 5
    assert c.calls[1]["response_format"] is TileRead
    assert 1 <= len(out.openings) <= 4 and all(o.type == "window" for o in out.openings)


def test_failed_tiles_keep_the_first_reading(monkeypatch):
    monkeypatch.delenv("PLAN_AI_TILES", raising=False)
    c = Answers(plan(), RuntimeError("timeout"))
    assert read_plan(drawing(), "image/png", "a.png", client=c, provider="openai") == plan()


def test_tiles_can_be_turned_off_and_skip_pdf(monkeypatch):
    monkeypatch.setenv("PLAN_AI_TILES", "0")
    c = Answers(plan(), TileRead())
    read_plan(drawing(), "image/png", "a.png", client=c, provider="openai")
    assert len(c.calls) == 1
    monkeypatch.delenv("PLAN_AI_TILES")
    c = Answers(plan(), TileRead())
    read_plan(b"%PDF-1.4", "application/pdf", "a.pdf", client=c, provider="openai")
    assert len(c.calls) == 1


def test_tiles_are_skipped_when_printed_dimensions_disagree_with_the_picture(monkeypatch):
    monkeypatch.delenv("PLAN_AI_TILES", raising=False)
    c = Answers(plan(w=14000, d=3000), TileRead())  # 그림은 7:4.6인데 치수로 읽은 집은 14:3
    read_plan(drawing(), "image/png", "a.png", client=c, provider="openai")
    assert len(c.calls) == 1


def test_estimated_size_is_reshaped_to_the_picture_then_tiles_run(monkeypatch):
    monkeypatch.delenv("PLAN_AI_TILES", raising=False)
    first = plan(w=14000, d=3000).model_copy(update={"scale_from": "door_width"})
    c = Answers(first, TileRead())
    out = read_plan(drawing(), "image/png", "a.png", client=c, provider="openai")
    xs = [v for w in out.walls for v in (w.x1, w.x2)]
    ys = [v for w in out.walls for v in (w.y1, w.y2)]
    assert len(c.calls) == 5 and abs((max(xs) - min(xs)) / (max(ys) - min(ys)) - 700 / 460) < 0.05
