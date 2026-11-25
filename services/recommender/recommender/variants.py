"""같은 모델의 색·재질 다른 제품(SKU)을 하나로 묶는다.

같은 모델 = 종류·치수(LGE.COM)가 같고, Figma 도면 모양(문 나눔·손잡이·화구)이 같은 제품.
도면이 없으면 종류·치수만 본다. 순수 Python, 입력은 카탈로그 dict 목록.
"""
from __future__ import annotations

import json
import re


def shape_key(drawing: dict) -> str:
    """도면에서 모양만 남긴 문자열 (색·출처 같은 값은 뺀다)."""
    views = {k: {**drawing[k], "parts": sorted(drawing[k]["parts"], key=lambda q: q["name"])}
             for k in ("front", "side", "top") if k in drawing}  # 부품 순서는 상관없다
    return json.dumps(views, sort_keys=True, separators=(",", ":"))


_PAREN = re.compile(r"\s*\(([^()]*)\)\s*$")


def family_name(names: list[str]) -> str:
    """'이름 (650L, 메탈)' 들에서 모두에 들어 있는 괄호 항목만 남긴다."""
    if len(names) == 1:
        return names[0]
    split = []
    for n in names:
        m = _PAREN.search(n)
        base = n[:m.start()] if m else n
        tokens = [t.strip() for t in m.group(1).split(",")] if m else []
        split.append((base.strip(), tokens))
    base = split[0][0]
    common = [t for t in split[0][1] if all(t in toks for _, toks in split)]
    return f"{base} ({', '.join(common)})" if common else base


def _dims(p: dict) -> tuple:
    d = p.get("product_dims_mm") or {}
    return d.get("w"), d.get("h"), d.get("d")


def families(products: list[dict], shapes: dict[str, str | None]) -> list[dict]:
    """카탈로그 순서를 지키며 모델별로 묶는다. 첫 SKU가 family_id."""
    groups: dict[tuple, list[dict]] = {}
    for p in products:
        key = (p["category"], bool(p.get("demo_only")), _dims(p), shapes.get(p["sku"]))
        groups.setdefault(key, []).append(p)
    out = []
    for (cat, demo, dims, _shape), ps in groups.items():
        out.append({
            "family_id": ps[0]["sku"],
            "name": family_name([p["name"] for p in ps]),
            "category": cat,
            "demo_only": demo,
            "product_dims_mm": ps[0].get("product_dims_mm"),
            "variants": [{
                "sku": p["sku"],
                "name": p["name"],
                "color": (p.get("cmf_options") or [{}])[0].get("color"),
                "material": (p.get("cmf_options") or [{}])[0].get("material"),
                "hex": (p.get("cmf_options") or [{}])[0].get("hex_approx"),
                "install_type": p.get("install_type"),
                "options": p.get("options") or {},
                "sale_status": p.get("sale_status"),
                "listed": p.get("listed", True),
                "note": p.get("lineup_note"),
                "price_krw": p.get("price_krw"),
            } for p in ps],
        })
    return out
