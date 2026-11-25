"""공간 꾸미기 라이브러리: 일반 가구·수납·소품·가벽 (제품 정보 없는 모양만).

LG 가전과 같은 판정(벽·겹침)을 쓰려고 판정용 Product를 만든다. 가격·출처·브랜드는 없다.
3D 모델은 apps/web/models/furniture (build_furniture.py로 생성).
sku는 "decor:<종류>" 꼴. 크기는 배치마다 바꿀 수 있다 (가벽 길이 등).
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from .models import Clearance, Dims, Product

PREFIX = "decor:"
MIN_MM, MAX_MM = 10, 8000

# group: structure(벽체·구조) · furniture(가구) · storage(수납·선반) · decor(소품)
# size_mm: 기본 크기 (w, h, d). flat: 다른 것과 겹쳐도 되는 바닥 깔개. swing: 앞으로 여는 문 (열림 공간 = 폭)
DECOR: dict[str, dict] = {
    "wall": {"label": "벽 추가", "name": "가벽", "group": "structure", "model": "wall", "size_mm": (2000, 2400, 100)},
    "partition": {"label": "파티션", "group": "structure", "model": "partition", "size_mm": (1200, 2100, 50)},
    # 문: 벽·가벽에 겹쳐 단다. 앞쪽으로 문짝 폭만큼 비어 있어야 열린다 (swing)
    "door": {"label": "문", "group": "structure", "model": "door", "size_mm": (900, 2100, 140), "swing": True},
    # 창: 벽에 겹쳐 단다. 창문은 바닥에서 띄워서(pose.SILL_M), 베란다 유리문은 바닥부터
    "window": {"label": "창문", "group": "structure", "model": "window", "size_mm": (1200, 1200, 140)},
    "glassdoor": {"label": "베란다 유리문", "group": "structure", "model": "glassdoor", "size_mm": (1800, 2100, 140)},
    "sofa": {"label": "소파", "group": "furniture", "model": "sofa", "size_mm": (2000, 850, 900)},
    "table": {"label": "식탁", "group": "furniture", "model": "table", "size_mm": (1600, 740, 800)},
    "chair": {"label": "의자", "group": "furniture", "model": "chair", "size_mm": (500, 850, 520)},
    # 아일랜드 식탁: 수납이 달린 조리대 높이 식탁. 기본 크기는 한샘 모디 아일랜드식탁 120cm (출처는 PRESETS)
    "islandtable": {"label": "아일랜드 식탁", "group": "furniture", "model": "islandtable", "size_mm": (1200, 890, 750)},
    "coffee": {"label": "테이블", "group": "furniture", "model": "coffee", "size_mm": (1000, 400, 600)},
    "bed": {"label": "침대", "group": "furniture", "model": "bed", "size_mm": (1600, 950, 2100)},
    "desk": {"label": "책상", "group": "furniture", "model": "desk", "size_mm": (1200, 730, 600)},
    "wardrobe": {"label": "장롱", "group": "storage", "model": "wardrobe", "size_mm": (1000, 2360, 580)},
    "tallcab": {"label": "키큰장", "group": "storage", "model": "tallcab", "size_mm": (600, 2000, 600)},
    "storage": {"label": "수납장", "group": "storage", "model": "storage", "size_mm": (1000, 1900, 450)},
    "shelf": {"label": "선반", "group": "storage", "model": "shelf", "size_mm": (800, 1800, 300)},
    "dresser": {"label": "서랍장", "group": "storage", "model": "dresser", "size_mm": (800, 900, 450)},
    "sink": {"label": "싱크대", "group": "storage", "model": "sink", "size_mm": (1200, 880, 600)},
    "basecab": {"label": "주방 하부장", "group": "storage", "model": "basecab", "size_mm": (1200, 850, 600)},
    "island": {"label": "아일랜드", "group": "storage", "model": "island", "size_mm": (1800, 900, 900)},
    # 후드: 인덕션 위에 단다. 벽 쪽 조리대 위는 벽에 거는 것(hang), 아일랜드 위는 천장에서 내려오는 것
    # 기본 크기는 IKEA RYTMISK 벽고정레인지후드 60 (높이는 가장 짧게 뺐을 때)
    "hood": {"label": "후드", "group": "storage", "model": "hood", "size_mm": (600, 620, 471), "hang": True},
    "islandhood": {"label": "아일랜드 후드", "group": "storage", "model": "islandhood", "size_mm": (900, 800, 600), "listed": False},
    "tvstand": {"label": "거실장", "group": "storage", "model": "tvstand", "size_mm": (1600, 450, 400)},
    "rug": {"label": "러그", "group": "decor", "model": "rug", "size_mm": (2000, 12, 1400), "flat": True},
    "lamp": {"label": "조명", "group": "decor", "model": "lamp", "size_mm": (400, 1600, 400)},
    "plant": {"label": "식물", "group": "decor", "model": "plant", "size_mm": (500, 1200, 500)},
}


IKEA = "https://www.ikea.com/"


def _p(label: str, w: int, h: int, d: int, path: str) -> dict:
    return {"label": label, "size_mm": {"w": w, "h": h, "d": d}, "source_url": path if path.startswith("https://") else IKEA + path}


# 크기 프리셋: 실제 판매 제품의 공개 치수 (폭·높이·깊이 mm). 출처는 docs/catalog-sources.md '가구 크기 프리셋'
PRESETS: dict[str, list[dict]] = {
    "wardrobe": [
        _p("IKEA PAX 50", 500, 2010, 580, "kr/ko/p/pax-wardrobe-frame-white-20355127/"),
        _p("IKEA PAX 75 얕은 장", 750, 2010, 350, "kr/ko/p/pax-wardrobe-frame-white-00355133/"),
        _p("IKEA PAX 100 높은 장", 1000, 2360, 580, "gb/en/p/pax-wardrobe-frame-white-80458207/"),
    ],
    "tallcab": [_p("IKEA METOD 키큰장 60", 600, 2000, 600, "kr/ko/p/metod-high-cabinet-white-40270938/")],
    "basecab": [
        _p("IKEA METOD 40", 400, 800, 600, "kr/ko/p/metod-base-cabinet-white-20270883/"),
        _p("IKEA METOD 60", 600, 800, 600, "kr/ko/p/metod-base-cabinet-white-90270889/"),
        _p("IKEA METOD 80", 800, 800, 600, "kr/ko/p/metod-base-cabinet-white-10270893/"),
    ],
    "islandtable": [
        _p("한샘 모디 120", 1200, 890, 750, "https://store.hanssem.com/goods/883389"),
        _p("IKEA TORNVIKEN", 1260, 900, 770, "kr/ko/p/tornviken-kitchen-island-off-white-oak-30402246/"),
        _p("IKEA VADHOLMA", 1260, 900, 790, "kr/ko/p/vadholma-kitchen-island-black-oak-80359189/"),
    ],
    "hood": [_p("IKEA RYTMISK 60", 600, 620, 471, "kr/ko/p/rytmisk-wall-mounted-extractor-hood-stainless-steel-10508951/")],
    "dresser": [
        _p("IKEA MALM 4칸", 800, 1000, 480, "kr/ko/p/malm-chest-of-4-drawers-white-20354646/"),
        _p("IKEA MALM 6칸", 1600, 780, 480, "kr/ko/p/malm-chest-of-6-drawers-white-70354644/"),
    ],
}


def is_decor(sku: str | None) -> bool:
    return bool(sku) and sku.startswith(PREFIX)


def kind_of(sku: str) -> str:
    key = sku[len(PREFIX):] if is_decor(sku) else sku
    if key not in DECOR:
        raise KeyError(sku)
    return key


def is_flat(sku: str | None) -> bool:
    return is_decor(sku) and DECOR.get(sku[len(PREFIX):], {}).get("flat", False)


def decor_items() -> list[dict]:
    """웹 라이브러리용 목록. 이름·묶음·기본 크기·모델만 (가격·출처 없음).
    hang: 벽에 거는 것 · listed=False: 목록에는 안 보이고 다른 것에 딸려 놓이는 것."""
    return [{"sku": PREFIX + k, "label": d["label"], "name": d.get("name", d["label"]), "group": d["group"], "model": d["model"],
             "size_mm": dict(zip("whd", d["size_mm"])), "flat": d.get("flat", False), "presets": PRESETS.get(k, []),
             "hang": d.get("hang", False), "listed": d.get("listed", True)} for k, d in DECOR.items()]


def _clamp(v: float) -> float:
    return min(max(v, MIN_MM), MAX_MM)


def decor_product(sku: str, size_m: Sequence[float] | None = None) -> Product:
    """판정용 Product. size_m(m)을 주면 그 크기, 없으면 기본 크기. 이격은 0 (가구라 필요 없음). 문만 앞쪽 열림 공간을 본다."""
    key = kind_of(sku)
    d = DECOR[key]
    if size_m and not all(math.isfinite(v) for v in size_m):
        raise ValueError("크기는 숫자여야 해요")
    w, h, dp = (v * 1000 for v in size_m) if size_m else d["size_mm"]
    return Product(sku=PREFIX + key, name=d.get("name", d["label"]), category=f"decor_{key}", zone_fit=[], install_type="freestanding",
                   product_dims_mm=Dims(w=_clamp(w), h=_clamp(h), d=_clamp(dp)),
                   clearance_mm=Clearance(side=0, top=0, back=0), door_swing_mm=_clamp(w) if d.get("swing") else None, source_url=None, source_checked_at=None)
