"""제품 특징표대로 3D 모델(glb)을 만든다.

    uv run python tools/models/plan.py --out .cache/model_plan.json
    blender -b -P build_models.py -- --plan .cache/model_plan.json --out apps/web/models/products [--sku X ...]
    (pip bpy 환경이면 python build_models.py --plan ... --out ...)

- 크기: 카탈로그 product_dims_mm 그대로. 바닥 가운데가 원점, 정면 = glTF +Z.
- 모양: worker/archetypes.py의 제품군 틀 + data/models/features.json의 제품별 값.
- 같은 모양인 색 다른 모델은 파일 하나를 같이 쓴다. index.json이 모델명 → 파일을 알려 준다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2]))
sys.path.insert(0, str(HERE.parent))
import realize  # noqa: E402
from worker import archetypes  # noqa: E402


def build(item: dict, out: Path) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    d = item["dims"]
    parts = getattr(archetypes, item["arch"])(d["w"], d["d"], d["h"], **item["params"])
    ob = realize.realize(parts, realize.Mats(item["hex"], item.get("feel")), item["sku"], d)
    realize.export_glb(ob, out / item["file"])
    return {"file": item["file"], "layout": item["arch"], "bbox_mm": {k: round(float(v), 1) for k, v in d.items()}}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sku", action="append", help="이 파일 주인 모델만 다시 만들기")
    a = ap.parse_args(argv)
    out = Path(a.out)
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    idx_path = out / "index.json"
    index = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {"models": {}}
    built = {}
    for item in plan["build"]:
        if a.sku and item["sku"] not in a.sku:
            continue
        built[item["file"]] = build(item, out)
        print(item["sku"], item["arch"], (out / item["file"]).stat().st_size // 1024, "KB", flush=True)
    for sku, e in plan["index"].items():
        if e["file"] in built:
            index["models"][sku] = built[e["file"]]
        elif not a.sku:                       # 직접 만든 모델을 같이 쓰는 색 다른 제품
            old = index["models"].get(e["file"][:-4], {})
            index["models"][sku] = {"file": e["file"], "layout": e["layout"], "bbox_mm": old.get("bbox_mm")}
    index["_note"] = ("모델명 → 모델 파일. layout은 만든 방법: 제품군 틀 이름(build_models.py), fusion(직접 모델링한 것을 "
                      "같이 씀), drawing(예전 도면 상자 모델, 판매 종료 제품).")
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.sku:
        return
    # 본체와 따로 놓이는 부품(정수기 파우셋)은 같은 파일을 쓰는 제품에도 붙인다
    comp_path = out / "companions.json"
    comps = json.loads(comp_path.read_text(encoding="utf-8")) if comp_path.exists() else {"models": {}}
    for sku, e in plan["index"].items():
        owner = e["file"][:-4]
        if owner in comps["models"] and sku not in comps["models"]:
            comps["models"][sku] = comps["models"][owner]
    comp_path.write_text(json.dumps(comps, ensure_ascii=False, indent=1), encoding="utf-8")
    # 이제 아무 제품도 가리키지 않는 예전 파일은 지운다
    used = {e["file"] for e in index["models"].values()} | {c["file"] for c in comps["models"].values()}
    for f in out.glob("*.glb"):
        if f.name not in used:
            f.unlink()


if __name__ == "__main__":
    main()
