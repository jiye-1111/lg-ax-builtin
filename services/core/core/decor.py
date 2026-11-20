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
# size_mm: 기본 크기 (w, h, d). flat: 다른 것과 겹쳐도 되는 바닥 깔개
DECOR: dict[str, dict] = {
    "wall": {"label": "벽 추가", "name": "가벽", "group": "structure", "model": "wall", "size_mm": (2000, 2400, 100)},
    "partition": {"label": "파티션", "group": "structure", "model": "partition", "size_mm": (1200, 2100, 50)},
    "sofa": {"label": "소파", "group": "furniture", "model": "sofa", "size_mm": (2000, 850, 900)},
    "table": {"label": "식탁", "group": "furniture", "model": "table", "size_mm": (1600, 740, 800)},
    "chair": {"label": "의자", "group": "furniture", "model": "chair", "size_mm": (500, 850, 520)},
    "coffee": {"label": "테이블", "group": "furniture", "model": "coffee", "size_mm": (1000, 400, 600)},
    "bed": {"label": "침대", "group": "furniture", "model": "bed", "size_mm": (1600, 950, 2100)},
    "desk": {"label": "책상", "group": "furniture", "model": "desk", "size_mm": (1200, 730, 600)},
    "storage": {"label": "수납장", "group": "storage", "model": "storage", "size_mm": (1000, 1900, 450)},
    "shelf": {"label": "선반", "group": "storage", "model": "shelf", "size_mm": (800, 1800, 300)},
    "island": {"label": "아일랜드", "group": "storage", "model": "island", "size_mm": (1800, 900, 900)},
    "tvstand": {"label": "거실장", "group": "storage", "model": "tvstand", "size_mm": (1600, 450, 400)},
    "rug": {"label": "러그", "group": "decor", "model": "rug", "size_mm": (2000, 12, 1400), "flat": True},
    "lamp": {"label": "조명", "group": "decor", "model": "lamp", "size_mm": (400, 1600, 400)},
    "plant": {"label": "식물", "group": "decor", "model": "plant", "size_mm": (500, 1200, 500)},
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
    """웹 라이브러리용 목록. 이름·묶음·기본 크기·모델만 (가격·출처 없음)."""
    return [{"sku": PREFIX + k, "label": d["label"], "name": d.get("name", d["label"]), "group": d["group"], "model": d["model"],
             "size_mm": dict(zip("whd", d["size_mm"])), "flat": d.get("flat", False)} for k, d in DECOR.items()]


def _clamp(v: float) -> float:
    return min(max(v, MIN_MM), MAX_MM)


def decor_product(sku: str, size_m: Sequence[float] | None = None) -> Product:
    """판정용 Product. size_m(m)을 주면 그 크기, 없으면 기본 크기. 이격·문 열림은 0 (가구라 필요 없음)."""
    key = kind_of(sku)
    d = DECOR[key]
    if size_m and not all(math.isfinite(v) for v in size_m):
        raise ValueError("크기는 숫자여야 해요")
    w, h, dp = (v * 1000 for v in size_m) if size_m else d["size_mm"]
    return Product(sku=PREFIX + key, name=d.get("name", d["label"]), category=f"decor_{key}", zone_fit=[], install_type="freestanding",
                   product_dims_mm=Dims(w=_clamp(w), h=_clamp(h), d=_clamp(dp)),
                   clearance_mm=Clearance(side=0, top=0, back=0), source_url=None, source_checked_at=None)
