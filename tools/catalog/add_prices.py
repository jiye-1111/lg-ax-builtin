"""LGE.COM 제품 페이지의 판매가를 카탈로그 price_krw에 넣는다. 못 읽었거나 0원이면 null.

    python3 tools/catalog/add_prices.py . tools/catalog/lgecom_prices.json 2026-11-20

lgecom_prices.json: {모델명: {price(페이지의 판매가 obsSellingPrice), list_price(정가 obsOriginalPrice), status}}
"""
import json, sys
root, src, day = sys.argv[1], sys.argv[2], sys.argv[3]
S = json.load(open(src, encoding="utf-8"))
path = f"{root}/data/catalog/products.json"
raw = json.load(open(path, encoding="utf-8"))
n = 0
for p in raw["products"]:
    v = (S.get(p["sku"]) or S.get(p["sku"] + "__") or {}).get("price")
    n += v is not None
    keys = [k for k in p if k not in ("price_krw", "price_checked_at")]
    i = keys.index("sale_checked_at") + 1
    q = {k: p[k] for k in keys[:i]} | {"price_krw": v, "price_checked_at": day if v is not None else None} | {k: p[k] for k in keys[i:]}
    p.clear(); p.update(q)
json.dump(raw, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"가격 있음 {n} / {len(raw['products'])}")
