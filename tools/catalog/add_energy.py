"""LGE.COM 제품 페이지 스펙 표의 '에너지 소비효율등급'을 카탈로그 energy_grade(1~5)에 넣는다.

    python3 tools/catalog/add_energy.py . tools/catalog/lgecom_energy.json 2026-11-25

lgecom_energy.json: {모델명: 스펙 표에 적힌 글자 그대로}. "1등급"~"5등급"만 숫자로 넣고,
"해당없음"·"등급 외 제품"이거나 표에 그 항목이 없으면(null) 등급은 null로 둔다. 페이지를 열어 본 모델에는 확인한 날을 적는다.
"""
import json, re, sys
root, src, day = sys.argv[1], sys.argv[2], sys.argv[3]
S = json.load(open(src, encoding="utf-8"))
path = f"{root}/data/catalog/products.json"
raw = json.load(open(path, encoding="utf-8"))
n = 0
for p in raw["products"]:
    m = re.fullmatch(r"([1-5])등급", S.get(p["sku"]) or "")
    grade = int(m.group(1)) if m else None
    n += grade is not None
    keys = [k for k in p if k not in ("energy_grade", "energy_checked_at")]
    i = keys.index("price_checked_at") + 1
    q = {k: p[k] for k in keys[:i]} | {"energy_grade": grade, "energy_checked_at": day if p["sku"] in S else None} | {k: p[k] for k in keys[i:]}
    p.clear(); p.update(q)
json.dump(raw, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"등급 있음 {n} / 확인한 모델 {len(S)} / 전체 {len(raw['products'])}")
