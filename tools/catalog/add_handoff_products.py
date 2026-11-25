"""전달받은 묶음(LG-HANDOFF-01)의 모델을 카탈로그에 맞춘다.

    python3 tools/catalog/add_handoff_products.py <압축 푼 폴더>

- 카탈로그에 없던 모델을 넣는다. 치수·색 이름은 묶음에 적힌 LGE.COM 스펙 기록, 이름·판매 상태·가격은
  tools/catalog/lgecom_handoff.json(LGE.COM 제품 페이지에서 다시 확인한 값)에서 온다
- 종류·설치 방식·옵션은 같은 제품군(색만 다른 모델)이 카탈로그에 있으면 그 값을 쓴다. 없으면 FIRST에 적은 값만 넣고 나머지는 null.
  옵션은 LGE.COM 스펙 표와 대조했고, 다른 것은 PAGE_OPTIONS에 적은 값으로 넣는다
- 이미 있던 모델은 판매 상태와 가격만 새로 확인한 값으로 바꾼다
- 화면에 내놓을 모델 목록(data/catalog/lineup.json)을 쓴다
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
src = Path(sys.argv[1])
library = json.loads((src / "catalog/library.json").read_text(encoding="utf-8"))
page = json.loads((ROOT / "tools/catalog/lgecom_handoff.json").read_text(encoding="utf-8"))
day, pages = page["checked_at"], page["models"]
path = ROOT / "data/catalog/products.json"
raw = json.loads(path.read_text(encoding="utf-8"))
by_sku = {p["sku"]: p for p in raw["products"]}

# 같은 제품군이 카탈로그에 하나도 없는 모델: 제품 페이지 주소의 분류와 설치 방식만 넣는다
FIRST = {
    "BEI3GQK-builtin": {"category": "cooktop", "zone_fit": ["kitchen"], "install_type": "built_in", "options": {"kind": "인덕션"}},
    "MX0140-batch03": {"category": "air_purifier", "zone_fit": ["living", "bedroom"], "install_type": "built_in", "options": {}},
    "B124W-batch06": {"category": "refrigerator", "zone_fit": ["kitchen"], "install_type": "freestanding", "options": {"kind": "일반형"}},
}
# 2026-11-25 LGE.COM 제품 페이지 스펙 표에서 읽은 옵션. 같은 제품군 모델에서 가져온 값과 다르거나 가져올 모델이 없던 것만 적는다
# (나머지 새 모델의 용량·도어 값은 스펙 표와 같은 것을 확인했다)
PAGE_OPTIONS = {
    "B124W14": {"kind": "일반형", "doors": "2도어", "door_material": "메탈", "capacity_l": 121},
    "B332W34": {"door_material": "메탈"},
}
STATUS = {"ACTIVE": "ACTIVE", "SOLD_OUT": "SOLD_OUT", "NOT_FOR_SALE": "NOT_FOR_SALE", "DISCONTINUED": "DISCONTINUED"}  # 출시 예정은 아직 살 수 없어 null
DOT = ("door_finish", "front_finish", "panel_nature_beige", "control_finish", "body_finish", "glass_finish", "glass_black", "panel_finish")
COLOR_LABELS = ("색상", "도어 색상")
EMPTY3 = {"w": None, "h": None, "d": None}


def short(sku: str) -> str:
    return sku.rsplit(".", 1)[0]  # DUE6BGE.AKOR → DUE6BGE


def dot_hex(meta: dict) -> str | None:
    over = meta.get("material_overrides") or {}
    for k in DOT:
        if k in over:
            return "#%02X%02X%02X" % tuple(over[k][0])
    return None


def colour(meta: dict, fallback: str) -> str:
    for f in meta.get("official_fields_as_published") or []:
        if f["label"] in COLOR_LABELS and f["value"]:
            return f["value"]
    return fallback


added, lineup = [], {}
for fam in library["families"]:
    sibling = next((by_sku[short(v["sku"])] for v in fam["variants"] if short(v["sku"]) in by_sku), None)
    for v in fam["variants"]:
        sku, got = short(v["sku"]), pages[v["sku"]]
        note = v["selection_label"].replace(v["color_label"], "").strip(" ·") or None  # 색 이름을 뺀 구성 차이
        lineup[sku] = {"family_id": fam["family_id"], "handoff_sku": v["sku"], "note": note}
        status = STATUS.get(got["model_status"])
        sell = status in ("ACTIVE", "SOLD_OUT")
        if sku in by_sku:
            p = by_sku[sku]
            p["sale_status"], p["sale_checked_at"] = status, (day if status else None)
            if sell and got["price_krw"]:
                p["price_krw"], p["price_checked_at"] = got["price_krw"], day
            continue
        meta = json.loads((src / v["metadata"]).read_text(encoding="utf-8"))
        base = sibling or FIRST[fam["family_id"]]
        w, h, d = fam["whd_mm"]
        material = next((f["value"] for f in meta.get("official_fields_as_published") or [] if f["label"] == "도어스타일/재질"), None)
        row = {
            "sku": sku, "name": got["name"], "category": base["category"], "zone_fit": base["zone_fit"],
            "install_type": base["install_type"], "product_dims_mm": {"w": w, "h": h, "d": d},
            "required_space_mm": (sibling or {}).get("required_space_mm", dict(EMPTY3)),
            "clearance_mm": (sibling or {}).get("clearance_mm", {"side": None, "top": None, "back": None}),
            "door_swing_mm": (sibling or {}).get("door_swing_mm"),
            "cutout_mm": (sibling or {}).get("cutout_mm", dict(EMPTY3)),
            "spec_notes": [f"크기 (WxHxD) {w} x {h} x {d}: 전달받은 모델 묶음(LG-HANDOFF-01)에 적힌 LGE.COM 스펙 기록",
                           "이름·판매 상태·가격·옵션: LGE.COM 제품 페이지와 스펙 표"]
                          + (["종류·설치 방식: 색만 다른 같은 제품군 모델 " + sibling["sku"] + "과 같게"] if sibling else []),
            "options": dict(base["options"]) | PAGE_OPTIONS.get(sku, {}),
            "cmf_options": [{"color": colour(meta, v["color_label"]), "material": material, "finish": None, "hex_approx": dot_hex(meta)}],
            "source_url": got["source_url"], "source_checked_at": day,
            "sale_status": status, "sale_checked_at": day if status else None,
            "price_krw": got["price_krw"] if sell else None, "price_checked_at": day if sell and got["price_krw"] else None,
            "model_3d": None, "demo_only": False,
        }
        raw["products"].append(row)
        by_sku[sku] = row
        added.append(sku)

path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(ROOT / "data/catalog/lineup.json").write_text(json.dumps({
    "_note": "화면에 내놓는 모델. 전달받은 묶음(LG-HANDOFF-01)에 3D 모델이 있는 것만 적는다. "
             "여기 없는 카탈로그 제품은 목록·추천에 나오지 않는다 (.env CATALOG_LINEUP)",
    "package_id": library["package_id"], "models": lineup}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("추가", len(added), added)
print("목록", len(lineup))
