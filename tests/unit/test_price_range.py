"""가격 손잡이 범위 (apps/web/js/options.js priceScale). 한두 개뿐인 초고가 제품 때문에 눈금이 1억까지 늘어나지 않게 한다."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "apps/web/js/options.js"
CAT = json.loads((ROOT / "data/catalog/products.json").read_text(encoding="utf-8"))["products"]
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")


def scale(prices):
    code = f"""
import {{ priceScale }} from {json.dumps(JS.as_uri())};
console.log(JSON.stringify(priceScale({json.dumps(prices)})));
"""
    r = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def prices(category):
    return [p["price_krw"] for p in CAT if p["category"] == category and isinstance(p.get("price_krw"), int)
            and p.get("sale_status") in ("ACTIVE", "SOLD_OUT")]


def test_tv_range_is_not_stretched_to_100_million():
    s = scale(prices("tv"))
    assert s["hi"] <= 12_000_000 and s["open"] is True   # 맨 오른쪽은 "이상": 더 비싼 제품도 빠지지 않는다
    assert s["lo"] <= min(prices("tv"))
    inside = sum(1 for v in prices("tv") if v <= s["hi"]) / len(prices("tv"))
    assert inside >= 0.9


def test_plain_range_keeps_the_real_max():
    s = scale([450_000, 1_050_000, 2_050_000, 2_200_000, 2_200_000])
    assert s == {"lo": 450_000, "hi": 2_200_000, "step": 50_000, "open": False}


def test_step_grows_with_the_range():
    assert scale([134_000, 171_000, 201_000, 270_000])["step"] == 10_000
    assert scale(prices("refrigerator"))["step"] >= 100_000
    s = scale(prices("refrigerator"))
    assert (s["hi"] - s["lo"]) % s["step"] == 0


def test_every_category_fits_the_rail():
    for cat in {p["category"] for p in CAT}:
        ps = prices(cat)
        if len(ps) < 2:
            continue
        s = scale(ps)
        assert s["hi"] <= 12_000_000, cat
        assert 2 <= (s["hi"] - s["lo"]) / s["step"] <= 120, (cat, s)
