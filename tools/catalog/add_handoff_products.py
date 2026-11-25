"""전달받은 묶음(LG-WEB-DEVELOPER-01, 485 SKU)의 모델을 카탈로그에 맞춘다.

    python3 tools/catalog/add_handoff_products.py <압축 푼 폴더>

- LGE.COM 제품 페이지에서 다시 확인한 값(tools/catalog/lgecom_handoff.json, fetch_lgecom_pages.mjs로 받음)으로
  판매 상태와 가격을 고친다. 묶음 모델이 카탈로그의 어느 제품인지는 모델명, 없으면 제품 페이지 주소로 찾는다
  (TV는 묶음이 OLED77B6SS, 카탈로그가 OLED77B6SNA처럼 이름이 달라 주소로 맞춘다)
- 지금 파는 모델(판매중·일시품절) 가운데 카탈로그에 없던 것을 넣는다. 이름·가격·판매 상태·색·용량·도어는 제품 페이지 값,
  치수는 묶음에 적힌 공식 치수(제품 페이지 스펙 표와 같은 수인지 확인한다), 종류·설치 방식은 같은 계열 모델과 같게 넣는다
- 팔지 않는 모델(단종·비매품·출시 전)은 카탈로그에 새로 넣지 않고 화면에도 내놓지 않는다
- 화면에 내놓을 모델 목록(data/catalog/lineup.json)을 쓴다. 에너지 등급은 여기서 넣지 않는다 (add_energy.py)
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
src = Path(sys.argv[1])
library = json.loads((src / "catalog/library.json").read_text(encoding="utf-8"))
page = json.loads((ROOT / "tools/catalog/lgecom_handoff.json").read_text(encoding="utf-8"))
day, pages = page["checked_at"], page["models"]
path = ROOT / "data/catalog/products.json"
raw = json.loads(path.read_text(encoding="utf-8"))
by_sku = {p["sku"]: p for p in raw["products"]}
by_url = {p["source_url"]: p for p in raw["products"]}
old_lineup = json.loads((ROOT / "data/catalog/lineup.json").read_text(encoding="utf-8"))["models"]

SELL = ("ACTIVE", "SOLD_OUT")
STATUS = {"ACTIVE": "ACTIVE", "SOLD_OUT": "SOLD_OUT", "NOT_FOR_SALE": "NOT_FOR_SALE", "DISCONTINUED": "DISCONTINUED"}  # 출시 예정은 아직 살 수 없어 null
# 같은 계열 모델이 카탈로그에 없거나, 있어도 종류가 다른 모델. 제품 페이지 이름과 주소의 분류만 보고 넣는다
FIRST = {
    "HEI1V9E": {"category": "cooktop", "zone_fit": ["kitchen"], "install_type": "freestanding", "options": {"kind": "포터블 인덕션"}},
    "AS405BWRP": {"category": "air_purifier", "zone_fit": ["living", "bedroom"], "install_type": "freestanding", "options": {}},
    "AS405BWRR": {"category": "air_purifier", "zone_fit": ["living", "bedroom"], "install_type": "freestanding", "options": {}},
}
DOT = ("door_finish", "front_finish", "finish", "upper_finish", "panel_nature_beige", "control_finish", "body_finish", "glass_finish",
       "glass_black", "panel_finish", "case_finish")
COLOR_LABELS = ("색상", "도어 색상", "외관 색상", "글라스컬러")
EMPTY3 = {"w": None, "h": None, "d": None}


def seg(url: str) -> str:
    """제품 페이지 주소의 분류 (care-solutions/dishwashers/… 는 dishwashers와 같은 분류)"""
    if "/product/" not in (url or ""):
        return ""
    return url.split("/product/")[1].rsplit("/", 1)[0].replace("care-solutions/", "").rstrip("s")


def catalog_row(p: dict):
    return by_sku.get(p["model"]) or by_url.get(p["source_url"])


def relative(p: dict, group: list[dict]):
    """종류·설치 방식을 따라 쓸 모델: 같은 제품군에서 모델명이 가장 비슷한 것, 없으면 같은 분류에서 앞 글자가 가장 길게 같은 것."""
    def common(a: str, b: str) -> int:
        n = 0
        while n < min(len(a), len(b)) and a[n] == b[n]:
            n += 1
        return n

    mates = [r for q in group if (r := catalog_row(q))]
    if mates:
        return max(mates, key=lambda r: common(r["sku"], p["model"]))
    best = max((r for r in raw["products"] if seg(r["source_url"]) == seg(p["source_url"])), key=lambda r: common(r["sku"], p["model"]), default=None)
    return best if best and common(best["sku"], p["model"]) >= 3 else None


def dot_hex(meta: dict):
    over = meta.get("material_overrides") or {}
    for k in DOT:
        if k in over:
            return "#%02X%02X%02X" % tuple(over[k][0])
    return None


def num(s: str):
    f = float(s.replace(",", ""))
    return int(f) if f == int(f) else f


def page_options(base: dict, specs: dict) -> dict:
    """스펙 표에 적힌 도어 수·재질·용량은 표의 값을 쓴다 (같은 계열이라도 색에 따라 재질이 다르다)."""
    opt = dict(base)
    if specs.get("도어 개수"):
        opt["doors"] = specs["도어 개수"]
    if specs.get("도어스타일/재질"):
        opt["door_material"] = specs["도어스타일/재질"]
    if re.fullmatch(r"[\d.,]+", specs.get("전체 용량 (L)") or ""):
        opt["capacity_l"] = num(specs["전체 용량 (L)"])
    if "capacity" in opt and (m := re.search(r"(\d+인용)", specs.get("용량") or "")):
        opt["capacity"] = m.group(1)
    return opt


def same_numbers(specs: dict, whd: list) -> bool:
    """제품 페이지 크기 칸에 묶음 치수와 같은 수가 적혀 있나 (칸마다 순서가 달라 수만 본다)."""
    for k, v in specs.items():
        if "크기" in k:
            got = sorted(num(x) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", re.sub(r"\([^)]*\)", "", v)))
            if got == sorted(whd):
                return True
    return False


groups = {g["id"]: [p for p in library["products"] if p["group_id"] == g["id"]] for g in library["groups"]}
# 같은 모델이 묶음에 두 번 든 것(T19MX7.AKOR와 리퍼 판매 페이지 T19MX7.AKOR-R1): 카탈로그 줄과 주소가 같은 쪽만 쓴다
same_model = Counter(p["model"] for p in library["products"])
added, lineup, moved, off, twice = [], {}, [], Counter(), []
for p in library["products"]:
    got = pages[p["sku"]]
    if same_model[p["model"]] > 1 and p["source_url"] != (by_sku.get(p["model"]) or {}).get("source_url"):
        twice.append(p["sku"])
        continue
    status = STATUS.get(got["model_status"])
    sell = status in SELL
    row = catalog_row(p)
    if row is None and not sell:
        off[got["model_status"]] += 1
        continue
    if row is None:
        meta = json.loads((src / p["metadata"]).read_text(encoding="utf-8"))
        sibling = None if p["model"] in FIRST else relative(p, groups[p["group_id"]])
        base = FIRST.get(p["model"]) or sibling
        w, h, d = p["placement_whd_mm"]
        if not same_numbers(got["specs"], [w, h, d]):
            raise SystemExit(f"{p['sku']}: 묶음 치수 {w}x{h}x{d}가 제품 페이지 크기와 다르다")
        colour = next((got["specs"][k] for k in COLOR_LABELS if got["specs"].get(k)), None)
        row = {
            "sku": p["model"], "name": got["name"], "category": base["category"], "zone_fit": base["zone_fit"],
            "install_type": base["install_type"], "product_dims_mm": {"w": w, "h": h, "d": d},
            "required_space_mm": (sibling or {}).get("required_space_mm", dict(EMPTY3)),
            "clearance_mm": (sibling or {}).get("clearance_mm", {"side": None, "top": None, "back": None}),
            "door_swing_mm": (sibling or {}).get("door_swing_mm"),
            "cutout_mm": (sibling or {}).get("cutout_mm", dict(EMPTY3)),
            "spec_notes": [f"크기 (WxHxD) {w} x {h} x {d}: 제품 페이지 스펙 표 (전달받은 모델 묶음 LG-WEB-DEVELOPER-01의 공식 치수와 같음)",
                           "이름·판매 상태·가격·색·용량·도어: LGE.COM 제품 페이지와 스펙 표"]
                          + (["종류·설치 방식: 같은 계열 모델 " + sibling["sku"] + "과 같게"] if sibling else []),
            "options": page_options(base["options"], got["specs"]),
            "cmf_options": [{"color": colour, "material": got["specs"].get("도어스타일/재질"), "finish": None, "hex_approx": dot_hex(meta)}],
            "source_url": got["source_url"], "source_checked_at": day,
            "sale_status": status, "sale_checked_at": day,
            "price_krw": got["price_krw"], "price_checked_at": day if got["price_krw"] else None,
            "energy_grade": None, "energy_checked_at": None,
            "model_3d": None, "demo_only": False,
        }
        raw["products"].append(row)
        by_sku[row["sku"]] = by_url[row["source_url"]] = row
        added.append(row["sku"])
    else:
        if row["sale_status"] != status:
            moved.append(f"{row['sku']} {row['sale_status']}→{status}")
        row["sale_status"], row["sale_checked_at"] = status, (day if status else None)
        if sell and got["price_krw"]:
            row["price_krw"], row["price_checked_at"] = got["price_krw"], day
    if sell:
        lineup[row["sku"]] = {"family_id": p["group_id"], "handoff_sku": p["sku"], "note": (old_lineup.get(row["sku"]) or {}).get("note")}

path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(ROOT / "data/catalog/lineup.json").write_text(json.dumps({
    "_note": "화면에 내놓는 모델. 전달받은 묶음(LG-WEB-DEVELOPER-01)에 3D 모델이 있고 LGE.COM에서 지금 파는 것만 적는다. "
             "여기 없는 카탈로그 제품은 목록·추천에 나오지 않는다 (.env CATALOG_LINEUP). family_id는 묶음의 제품군(group_id)",
    "package_id": "LG-WEB-DEVELOPER-01-20261125-485SKU", "models": lineup}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("추가", len(added), added)
print("판매 상태가 바뀐 것", len(moved), moved)
print("팔지 않아 넣지 않은 새 모델", dict(off))
print("같은 모델의 다른 판매 페이지라 건너뛴 것", len(twice), twice)
print("목록", len(lineup), "제품군", len({m["family_id"] for m in lineup.values()}))
