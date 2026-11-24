"""제품 모양 틀(worker.archetypes)과 특징표(data/models/features.json).

Blender 없이 부품 목록만으로 확인한다: 틀마다 부품이 제품 치수를 5% 안에서 꽉 채우는지(그래야 내보낼 때
카탈로그 치수에 맞춰진다), 특징표가 판매 중인 제품 줄을 빠짐없이 덮는지.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "models"))

from worker import archetypes  # noqa: E402
from worker.shapes import Parts, bbox  # noqa: E402

FEATS = json.loads((ROOT / "data/models/features.json").read_text(encoding="utf-8"))["models"]
CATALOG = {p["sku"]: p for p in json.loads((ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]}
MATS = {"finish", "finish_dots", "finish_matte", "body", "dark", "black", "screen", "window", "chrome", "steel", "grey",
        "lightgrey", "white", "rubber", "glass", "print", "glow"}


def test_box_bounds_are_sorted():
    p = Parts()
    p.box("finish", 10, -10, 5, -5, 30, 0)
    assert bbox(p) == {"w": 20, "d": 10, "h": 30, "lo": [-10, -5, 0], "hi": [10, 5, 30]}


def test_rotated_ellipsoid_bounds_cover_the_tilt():
    p = Parts()
    p.ell("finish", (0, 0, 0), (10, 10, 100), rot=(90, 0, 0))
    b = bbox(p)
    assert b["d"] == pytest.approx(200, abs=1) and b["h"] == pytest.approx(20, abs=1)


@pytest.mark.parametrize("sku", sorted(FEATS))
def test_feature_builds_parts_that_fill_catalog_dims(sku):
    f = FEATS[sku]
    d = CATALOG[sku]["product_dims_mm"]
    parts = getattr(archetypes, f["arch"])(d["w"], d["d"], d["h"], **f["params"])
    assert parts, "부품이 하나도 없다"
    b = bbox(parts)
    for k in ("w", "d", "h"):
        assert abs(b[k] / d[k] - 1) <= 0.05, f"{sku} {k}: 부품 {b[k]:.0f} / 카탈로그 {d[k]}"
    assert b["lo"][2] >= -1, "바닥 아래로 내려간 부품이 있다"
    for part in parts:
        assert part["mat"] in MATS or part["mat"].startswith("#"), part["mat"]
    assert any(part["mat"].startswith("finish") for part in parts), "제품 색을 입힐 겉면(finish)이 없다"


def test_every_sellable_row_has_a_model():
    """판매 중인 줄은 모두 직접 만든 모델, 전달받은 모델, 특징표 중 하나로 모델이 정해진다."""
    from plan import plan

    pl = plan()
    assert pl["missing"] == []
    files = {b["file"] for b in pl["build"]}
    fusion = {p.name for p in (ROOT / "data/fusion").iterdir()}
    for sku, e in pl["index"].items():
        assert e["file"] in files or e["file"][:-4] in fusion, sku


def test_plan_never_overwrites_handed_over_or_hand_made_models():
    from plan import plan

    pl = plan()
    handoff = set(json.loads((ROOT / "apps/web/models/products/handoff.json").read_text(encoding="utf-8"))["models"])
    fusion = {p.name for p in (ROOT / "data/fusion").iterdir()}
    for b in pl["build"]:
        assert b["sku"] not in handoff and b["sku"] not in fusion
    assert not set(pl["index"]) & (handoff | fusion)


def test_discontinued_rows_are_left_alone():
    from plan import plan

    pl = plan()
    for sku in pl["index"]:
        fam = [s for s, e in pl["index"].items() if e["file"] == pl["index"][sku]["file"]]
        assert any(CATALOG[s].get("sale_status") in ("ACTIVE", "SOLD_OUT") for s in fam) or pl["index"][sku]["layout"] == "fusion"
