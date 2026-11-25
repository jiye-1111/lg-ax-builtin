"""전달받은 묶음의 설치 계약에 적힌 설명서 수치를 카탈로그에 넣는다.

    uv run python tools/catalog/add_contract_values.py

- 환기 이격(clearance_mm), 인덕션 상판 타공(cutout_mm), 빌트인 개구 최소 치수(required_space_mm)만 옮긴다
- 카탈로그에 이미 값이 있으면 건드리지 않는다. 계약에 없는 값은 null 그대로
- 어느 설명서에서 왔는지 spec_notes에 적는다
"""
import json
from pathlib import Path

from recommender.contract import clearances, cutout, opening

ROOT = Path(__file__).resolve().parents[2]
path = ROOT / "data/catalog/products.json"
raw = json.loads(path.read_text(encoding="utf-8"))
lineup = json.loads((ROOT / "data/catalog/lineup.json").read_text(encoding="utf-8"))["models"]
MARK = "설치 설명서"
changed = []
for p in raw["products"]:
    if p["sku"] not in lineup:
        continue
    c = json.loads((ROOT / "data/lg-library/contracts" / f"{p['sku']}.json").read_text(encoding="utf-8"))
    said = []
    for field, got, names in (("clearance_mm", clearances(c), {"side": "양옆", "back": "뒤", "top": "위"}),
                              ("cutout_mm", cutout(c), {"w": "폭", "d": "깊이"}),
                              ("required_space_mm", opening(c), {"w": "폭", "h": "높이", "d": "깊이"})):
        new = {k: v for k, v in got.items() if p[field].get(k) is None}
        if not new:
            continue
        p[field].update(new)
        title = {"clearance_mm": "환기 이격", "cutout_mm": "상판 타공", "required_space_mm": "장 개구 최소"}[field]
        said.append(title + " " + ", ".join(f"{names[k]} {v:g}" for k, v in new.items()))
    if said and not any(MARK in n for n in p["spec_notes"]):
        src = c.get("source") or next((r["source"] for r in c["rules"] if r.get("source", {}).get("document")), {})
        doc = " ".join(x for x in (src.get("document"), src.get("reference")) if x)
        p["spec_notes"].append(f"{' · '.join(said)} (mm): {MARK} {doc}".strip() + " (전달받은 묶음의 설치 계약)")
        changed.append(p["sku"])
path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(len(changed), changed)
