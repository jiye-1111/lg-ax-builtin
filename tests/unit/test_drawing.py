"""Figma 도면(data/drawings/*.json) → Blender 부품 상자 변환 확인."""
import json
from pathlib import Path

import pytest

from worker.drawing import DrawingError, boxes_from_drawing, load_drawing

ROOT = Path(__file__).resolve().parents[2]
DIMS = {"w": 914, "h": 1860, "d": 709}


def drawing() -> dict:
    return json.loads((ROOT / "data/drawings/G646GBB031.json").read_text(encoding="utf-8"))


def test_boxes_cover_catalog_size():
    boxes = boxes_from_drawing(drawing(), DIMS)
    xs = [v for b in boxes for v in (b["x0"], b["x1"])]
    ys = [v for b in boxes for v in (b["y0"], b["y1"])]
    zs = [v for b in boxes for v in (b["z0"], b["z1"])]
    assert max(xs) - min(xs) == pytest.approx(0.914, abs=1e-6)
    assert max(ys) - min(ys) == pytest.approx(0.709, abs=1e-6)
    assert max(zs) - min(zs) == pytest.approx(1.860, abs=1e-6)
    assert min(zs) == pytest.approx(0.0)


def test_parts_keep_roles_and_count():
    boxes = boxes_from_drawing(drawing(), DIMS)
    roles = [b["role"] for b in boxes]
    assert roles.count("door") == 4
    assert roles.count("handle") == 4
    assert roles.count("body") == 1 and roles.count("vent") == 1 and roles.count("display") == 1


def test_front_is_minus_y_and_drawing_top_is_up():
    boxes = {b["name"]: b for b in boxes_from_drawing(drawing(), DIMS)}
    door0, handle = boxes["door/0"], boxes["handle/0/v"]
    assert door0["y0"] == pytest.approx(-0.709 / 2 + 0.022)   # 손잡이 뒤가 문 앞면
    assert handle["y0"] == pytest.approx(-0.709 / 2)          # 손잡이가 가장 앞
    assert door0["z1"] == pytest.approx(1.858)                # 도면 y=2 → 위에서 2mm
    assert door0["x0"] == pytest.approx(-0.457 + 0.002)       # 도면 왼쪽 = 정면에서 볼 때 왼쪽(-X)


def test_mismatched_size_is_rejected():
    with pytest.raises(DrawingError):
        boxes_from_drawing(drawing(), {"w": 900, "h": 1860, "d": 709})


def test_load_drawing_returns_none_when_missing(tmp_path):
    assert load_drawing(tmp_path, "NOPE") is None
    (tmp_path / "X1.json").write_text(json.dumps(drawing()), encoding="utf-8")
    assert load_drawing(tmp_path, "X1")["sku"] == "G646GBB031"
