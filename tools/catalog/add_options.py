"""LGE.COM 스펙 표의 옵션 값(종류·도어 수·용량·화면 크기…)과 문 열림 깊이를 카탈로그에 넣는다."""
import json, re, sys
from collections import Counter
root = sys.argv[1]; O = json.load(open(sys.argv[2]))
path = f"{root}/data/catalog/products.json"
raw = json.load(open(path, encoding="utf-8"))
num = lambda s: float(str(s).replace(",", "").strip())
def n(v):
    try:
        f = num(v); return int(f) if f == int(f) else f
    except Exception: return None
FR = {"일반 냉장고": "일반형", "일반냉장고": "일반형", "양문형": "양문형", "상냉장/하냉동": "상냉장/하냉동"}
stat = Counter()
for p in raw["products"]:
    r = O.get(p["sku"]) or O.get(p["sku"] + "__")
    opt = {}
    if r:
        c, sub = p["category"], (r.get("s") or "").strip()
        if c == "refrigerator":
            kind = FR.get(r.get("type")) or (sub if sub in ("양문형", "상냉장/하냉동", "일반형") else None)
        else:
            kind = sub if sub and "세트" not in sub else None
        if c == "dishwasher": kind = None  # 12인용·14인용은 용량(capacity)으로만 둔다
        if kind: opt["kind"] = kind
        if r.get("dc"): opt["doors"] = r["dc"]
        if r.get("dm"): opt["door_material"] = r["dm"]
        if r.get("door"): opt["door_type"] = r["door"]
        if r.get("cap") and n(r["cap"]) is not None: opt["capacity_l"] = n(r["cap"])
        if r.get("mcap"):
            m = re.match(r"\s*([\d.]+)", r["mcap"])
            if m: opt["capacity_l"] = n(m.group(1))
        w, d = r.get("wkg"), r.get("dkg")
        if r.get("kg"):
            m = re.match(r"세탁\s*([\d.]+)\s*/\s*건조\s*([\d.]+)", r["kg"])
            if m: w, d = m.group(1), m.group(2)
        if w and n(w) is not None and c in ("washer", "wash_tower", "washer_dryer"): opt["wash_kg"] = n(w)
        if d and n(d) is not None and c in ("dryer", "wash_tower", "washer_dryer"): opt["dry_kg"] = n(d)
        if r.get("cp2"):
            m = re.search(r"(\d+인용)", r["cp2"])
            opt["capacity"] = m.group(1) if m else r["cp2"]
        if r.get("scr"):
            m = re.match(r"\s*([\d.]+)\s*cm", r["scr"])
            if m: opt["screen_cm"] = n(m.group(1))
        if r.get("open") and p.get("door_swing_mm") is None and p["product_dims_mm"].get("d"):
            dd = num(re.split(r"[x×]", r["open"])[2]) - p["product_dims_mm"]["d"]
            if 100 <= dd <= 900:
                p["door_swing_mm"] = dd
                note = f"문 열림 깊이 {dd:g}: 스펙 표 '도어 열림 시 크기' {r['open']} 의 깊이에서 제품 깊이를 뺀 값"
                if note not in p["spec_notes"]: p["spec_notes"].append(note)
                stat["door_swing"] += 1
    p["options"] = opt
    stat["with_options" if opt else "no_options"] += 1
    # 키 순서: options를 cmf_options 앞에
    keys = list(p.keys()); keys.remove("options"); keys.insert(keys.index("cmf_options"), "options")
    q = {k: p[k] for k in keys}; p.clear(); p.update(q)
json.dump(raw, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(stat)
ax = {}
for p in raw["products"]:
    for k, v in p["options"].items(): ax.setdefault(p["category"], {}).setdefault(k, Counter())[v] += 1
for c, a in sorted(ax.items()):
    print(c, {k: (dict(v) if len(v) <= 8 else f"{len(v)} values") for k, v in a.items()})
