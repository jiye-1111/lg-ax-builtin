"""LGE.COM 제품 페이지의 판매 상태(modelStatus)를 카탈로그에 넣는다. 확인 못 한 제품은 null."""
import json, sys
from collections import Counter
root, src, day = sys.argv[1], sys.argv[2], sys.argv[3]
S = json.load(open(src, encoding="utf-8"))
path = f"{root}/data/catalog/products.json"
raw = json.load(open(path, encoding="utf-8"))
c = Counter()
for p in raw["products"]:
    v = S.get(p["sku"]) or S.get(p["sku"] + "__")
    p["sale_status"], p["sale_checked_at"] = v, (day if v else None)
    c[v] += 1
    keys = [k for k in p if k not in ("sale_status", "sale_checked_at")]
    i = keys.index("source_checked_at") + 1
    q = {k: p[k] for k in keys[:i]} | {"sale_status": p["sale_status"], "sale_checked_at": p["sale_checked_at"]} | {k: p[k] for k in keys[i:]}
    p.clear(); p.update(q)
json.dump(raw, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(dict(c))
