"""판매 중인 제품 줄마다 어떤 모델 파일을 쓸지 정한다.  uv run python tools/models/plan.py --out .cache/model_plan.json

- 직접 모델링한 것(data/fusion)이 있는 줄: 같은 줄의 다른 색 모델도 그 파일을 쓴다 (색은 웹에서 입힌다)
- 전달받은 모델(handoff.json)은 그대로 둔다
- 나머지: data/models/features.json의 틀과 값으로 새로 만든다 (build_models.py)
- 판매 종료된 줄은 건드리지 않는다
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for s in ("core", "recommender", "blender-worker"):
    sys.path.insert(0, str(ROOT / "services" / s))

from core import config  # noqa: E402
from core.service import Catalog  # noqa: E402

SELL = {"ACTIVE", "SOLD_OUT"}


def plan() -> dict:
    cat = Catalog(config.catalog_paths())
    feats = json.loads((ROOT / "data/models/features.json").read_text(encoding="utf-8"))["models"]
    handoff = set(json.loads((ROOT / "apps/web/models/products/handoff.json").read_text(encoding="utf-8"))["models"])
    # 직접 모델링한 것 중 전달받은 모델로 바뀐 것은 색이 파일에 들어 있어서 다른 색 제품이 같이 쓸 수 없다
    fusion = {p.name for p in (ROOT / "data/fusion").iterdir() if (p / "drawing.json").exists()} - handoff
    build, index, missing = [], {}, []
    for fam in cat.families():
        vs = fam["variants"]
        if not any(v.get("sale_status") in SELL for v in vs):
            continue
        skus = [v["sku"] for v in vs]
        made = [s for s in skus if s in fusion]
        rest = [s for s in skus if s not in fusion and s not in handoff]
        if not rest:
            continue
        if made:
            for s in rest:
                mat = cat.get(s).cmf_options[0].material if cat.get(s).cmf_options else None
                same = [m for m in made if (cat.get(m).cmf_options[0].material if cat.get(m).cmf_options else None) == mat]
                index[s] = {"file": f"{(same or made)[0]}.glb", "layout": "fusion"}
            continue
        key = next((s for s in skus if s in feats), None)
        if not key:
            missing.append((skus[0], fam["name"]))
            continue
        owner = rest[0]
        p = cat.get(owner)
        opt = p.cmf_options[0] if p.cmf_options else None
        d = p.product_dims_mm
        build.append({"file": f"{owner}.glb", "sku": owner, "feature": key, "arch": feats[key]["arch"],
                      "params": feats[key]["params"], "dims": {"w": d.w, "h": d.h, "d": d.d},
                      "hex": (opt.hex_approx if opt else None) or "#F2F2F0", "feel": opt.material if opt else None,
                      "category": p.category, "name": p.name})
        for s in rest:
            index[s] = {"file": f"{owner}.glb", "layout": feats[key]["arch"]}
    return {"build": build, "index": index, "missing": missing}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / ".cache" / "model_plan.json"))
    a = ap.parse_args()
    pl = plan()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(pl, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"새로 만들 모델 {len(pl['build'])}개, 파일을 바꿔 가리킬 제품 {len(pl['index'])}개, 특징표에 없는 줄 {len(pl['missing'])}개")
    for m in pl["missing"]:
        print("  없음:", *m)
