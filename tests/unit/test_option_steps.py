"""단계별 옵션 필터 (apps/web/js/options.js). 순수 함수라 node로 바로 돌려 본다."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from recommender.variants import families, shape_key

ROOT = Path(__file__).resolve().parents[2]
CAT = json.loads((ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]
JS = ROOT / "apps/web/js/options.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")


def run(category: str, sel: dict) -> dict:
    shapes = {}
    for p in CAT:
        f = ROOT / "data/drawings" / f"{p['sku']}.json"
        shapes[p["sku"]] = shape_key(json.loads(f.read_text(encoding="utf-8"))) if f.exists() else None
    variants = [v for f in families(CAT, shapes) if f["category"] == category and not f["demo_only"] for v in f["variants"]]
    code = f"""
import {{ optionSteps }} from {json.dumps(JS.as_uri())};
const input = JSON.parse(await new Promise((r) => {{ let s = ""; process.stdin.on("data", (d) => (s += d)).on("end", () => r(s)); }}));
const out = optionSteps(input.variants, input.sel);
console.log(JSON.stringify({{ steps: out.steps, skus: out.remaining.map((v) => v.sku), sel: out.sel }}));
"""
    r = subprocess.run(["node", "--input-type=module", "-e", code], input=json.dumps({"variants": variants, "sel": sel}),
                       capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(r.stdout)


def labels(out, key):
    return [v["label"] for s in out["steps"] if s["key"] == key for v in s["values"]]


def test_refrigerator_steps_follow_install_kind_doors_capacity_order():
    out = run("refrigerator", {})
    keys = [s["key"] for s in out["steps"]]
    assert keys[:4] == ["install", "kind", "doors", "capacity_l"]
    assert labels(out, "install") == ["빌트인", "일반"]
    assert set(labels(out, "kind")) == {"양문형", "상냉장/하냉동", "일반형"}
    assert len(out["skus"]) == sum(1 for p in CAT if p["category"] == "refrigerator")


def test_each_pick_narrows_the_next_steps():
    out = run("refrigerator", {"install": "일반", "kind": "양문형"})
    assert "양문형" in labels(out, "kind")
    assert "doors" not in [s["key"] for s in out["steps"]]  # 양문형은 전부 2도어 → 고를 게 없어 건너뛴다
    by = {p["sku"]: p for p in CAT}
    assert out["skus"] and all(by[s]["options"]["kind"] == "양문형" and by[s]["install_type"] == "freestanding" for s in out["skus"])


def test_built_in_choice_includes_fit_and_max():
    out = run("refrigerator", {"install": "빌트인"})
    by = {p["sku"]: p for p in CAT}
    assert {by[s]["install_type"] for s in out["skus"]} == {"built_in", "built_in_look"}


def test_capacity_is_bucketed_like_lgecom():
    out = run("refrigerator", {})
    assert set(labels(out, "capacity_l")) <= {"300L 이하", "300~400L", "400~600L", "600~800L", "800L 이상"}
    out = run("refrigerator", {"capacity_l": "800L 이상"})
    by = {p["sku"]: p for p in CAT}
    assert out["skus"] and all(by[s]["options"]["capacity_l"] >= 800 for s in out["skus"])


def test_pick_that_no_longer_matches_is_dropped():
    out = run("refrigerator", {"kind": "양문형", "doors": "4도어"})
    assert "doors" not in out["sel"] and out["skus"]


def test_other_categories_get_their_own_axes():
    assert [s["key"] for s in run("washer", {})["steps"]][:2] == ["kind", "wash_kg"]
    assert [s["key"] for s in run("tv", {})["steps"]][:2] == ["kind", "screen_cm"]
    assert "capacity" in [s["key"] for s in run("dishwasher", {})["steps"]]
    assert "kind" in [s["key"] for s in run("air_conditioner", {})["steps"]]
