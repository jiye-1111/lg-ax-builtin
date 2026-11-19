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


# ---------- 윗면 도면 (인덕션처럼 위에서 봐야 하는 제품) ----------
COOK = {"w": 580, "h": 59, "d": 520}


def cooktop_drawing() -> dict:
    return {
        "sku": "COOK",
        "front": {"w": 580, "h": 59, "parts": [
            {"name": "glass", "x": 0, "y": 0, "w": 580, "h": 6},
            {"name": "body", "x": 30, "y": 6, "w": 520, "h": 53},
        ]},
        "side": {"w": 520, "h": 59, "parts": [
            {"name": "glass/side", "x": 0, "y": 0, "w": 520, "h": 6},
            {"name": "body", "x": 30, "y": 6, "w": 460, "h": 53},
        ]},
        # 윗면: 아래쪽이 앞 (앞에 서서 내려다본 모습)
        "top": {"w": 580, "h": 520, "parts": [
            {"name": "zone/0", "shape": "circle", "x": 40, "y": 40, "w": 200, "h": 200},
            {"name": "panel", "x": 190, "y": 470, "w": 200, "h": 30},
        ]},
    }


def test_door_is_optional_and_glass_gets_side_depth():
    boxes = {b["name"]: b for b in boxes_from_drawing(cooktop_drawing(), COOK)}
    assert boxes["glass"]["y0"] == pytest.approx(-0.26) and boxes["glass"]["y1"] == pytest.approx(0.26)
    assert boxes["glass"]["z1"] == pytest.approx(0.059)


def test_top_view_rings_and_prints_sit_on_top():
    from worker.drawing import top_items
    rings, prints = top_items(cooktop_drawing(), COOK)
    r = rings[0]
    assert r["r"] == pytest.approx(0.1)
    assert r["cx"] == pytest.approx(0.14 - 0.29)          # 도면 x 중심 140mm → 왼쪽
    assert r["cy"] == pytest.approx(0.26 - 0.14)          # 도면 위쪽 = 뒤(+Y)
    assert r["z"] > 0.059
    p = prints[0]
    assert p["y0"] == pytest.approx(-0.26 + 0.02)         # 아래 끝에서 20mm = 앞쪽
    assert p["z0"] == pytest.approx(0.059)


def test_top_view_must_match_width_and_depth():
    d = cooktop_drawing()
    d["top"]["h"] = 500
    with pytest.raises(DrawingError):
        boxes_from_drawing(d, COOK)


def test_no_top_view_gives_no_items():
    from worker.drawing import top_items
    assert top_items(drawing(), DIMS) == ([], [])


def test_every_catalog_product_has_a_drawing_that_matches_its_size():
    """카탈로그 제품마다 Figma 도면이 있고, 도면 크기가 LGE.COM 치수와 맞아야 한다."""
    from worker.drawing import top_items
    cat = json.loads((ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]
    for p in cat:
        d = load_drawing(ROOT / "data/drawings", p["sku"])
        assert d is not None, f"{p['sku']} 도면 없음"
        assert d["sku"] == p["sku"]
        boxes_from_drawing(d, p["product_dims_mm"])
        top_items(d, p["product_dims_mm"])
