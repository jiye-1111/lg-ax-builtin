"""조건으로 제품 찾기: 종류·용량·색상·가격·설치 공간으로 좁히고 줄 세운다.

- 파는 제품만 (recommend.py와 같은 기준).
- 설치 공간: 그려 둔 영역이 있으면 영역 판정(zone_fit), 없으면 직접 넣은 공간 치수(space_w/h/d)와
  필요 설치 치수(fit.required_space)를 견준다. 직접 넣은 값은 잰 값으로 본다(마진 5 mm).
- 추천순: 들어가는 것 → 빠듯한 것 → 모르는 것 → 안 들어가는 것. 같은 판정 안에서는 공간에 딱 맞는 순.
- 가격·용량 조건을 걸면 그 값을 모르는 제품은 뺀다.
순수 Python. 규칙 설명은 docs/specs/fit-rules.md "조건으로 찾기".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from core.models import Product

from .fit import FitConfig, Verdict, judge_dimension, required_space, worst

COLOR_GROUPS = ["화이트", "베이지", "실버·그레이", "블랙", "그린", "기타"]
# 색 이름에 이 말이 들어 있으면 그 묶음 (앞에서부터 먼저 맞는 것)
_NAME_KEYS = [
    ("베이지", ("베이지", "크림", "샌드", "클레이")),
    ("블랙", ("블랙", "그라파이트", "차콜")),
    ("실버·그레이", ("실버", "스테인리스", "그레이", "샤인", "메탈")),
    ("그린", ("그린", "민트")),
    ("화이트", ("화이트", "스노우", "퓨어")),
]
# 가격대 (원). 경계값은 위 구간에 넣는다
PRICE_BUCKETS = [(None, 1_000_000, "100만 원 이하"), (1_000_000, 2_000_000, "100~200만 원"), (2_000_000, 3_000_000, "200~300만 원"),
                 (3_000_000, 5_000_000, "300~500만 원"), (5_000_000, None, "500만 원 이상")]
CAPACITY_BUCKETS = [(None, 400, "400L 이하"), (400, 600, "400~600L"), (600, None, "600L 이상")]
_ORDER = [Verdict.FIT.value, Verdict.CONDITIONAL.value, Verdict.UNKNOWN.value, Verdict.NO_FIT.value]
_DIM_KO = {"width": "폭", "height": "높이", "depth": "깊이"}


def color_group(color: Optional[str], hex_: Optional[str]) -> Optional[str]:
    """색 이름(LGE.COM)으로 묶고, 이름이 없으면 색 값의 밝기·채도로 묶는다."""
    if color:
        first = color.split("/")[0]
        for group, keys in _NAME_KEYS:
            if any(k in first for k in keys):
                return group
    if hex_ and len(hex_) == 7:
        r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
        hi, lo = max(r, g, b), min(r, g, b)
        if hi < 70:
            return "블랙"
        if hi - lo < 18:
            return "화이트" if lo > 225 else "실버·그레이"
        if g == hi and g - r > 12:
            return "그린"
        if r >= g >= b and lo > 150:
            return "베이지"
        return "기타"
    return "기타" if color else None


def _first_cmf(p: Product):
    return p.cmf_options[0] if p.cmf_options else None


def product_color_group(p: Product) -> Optional[str]:
    c = _first_cmf(p)
    # 색상 이름이 없으면(LGE.COM에 색상 표기가 없는 TV 등) 근사색만으로 묶지 않는다
    return color_group(c.color, c.hex_approx) if c and c.color else None


@dataclass(frozen=True)
class Conditions:
    category: Optional[str] = None
    zone: Optional[str] = None        # 공간 용도 (kitchen 등)
    install: Optional[str] = None     # built_in(빌트인 핏 포함) | freestanding
    capacity_min: Optional[float] = None   # L, 이상
    capacity_max: Optional[float] = None   # L, 이하
    color: Optional[str] = None       # COLOR_GROUPS 중 하나
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    space_w: Optional[float] = None   # 설치 공간 mm
    space_h: Optional[float] = None
    space_d: Optional[float] = None
    fits_only: bool = False
    sort: str = "recommended"         # recommended | size | price
    limit: Optional[int] = None


def space_fit(p: Product, space: dict, cfg: FitConfig) -> Optional[dict]:
    """직접 넣은 설치 공간(mm, width/height/depth 중 준 것만)에 들어가는지. 준 값이 없으면 None."""
    given = {k: v for k, v in space.items() if v}
    if not given:
        return None
    req, clearance_unknown = required_space(p)
    dims = {k: judge_dimension(v, req[k], True, cfg) for k, v in given.items()}
    verdict = worst(d.verdict for d in dims.values())
    notes = []
    if clearance_unknown:
        notes.append("clearance_unknown")
        if verdict == Verdict.FIT:
            verdict = Verdict.CONDITIONAL
    return {"verdict": verdict.value, "label": verdict.label, "source": "typed",
            "dims": {k: d.to_dict() for k, d in dims.items()}, "notes": notes}


def _on_sale(p: Product) -> bool:
    return p.demo_only or p.sale_status in ("ACTIVE", "SOLD_OUT")


def _in_scope(p: Product, c: Conditions) -> bool:
    if c.category and p.category != c.category:
        return False
    if c.zone and c.zone not in p.zone_fit:
        return False
    if c.install:
        built = p.install_type in ("built_in", "built_in_look")
        if (c.install == "built_in") != built:
            return False
    return True


def _capacity(p: Product) -> Optional[float]:
    v = p.options.get("capacity_l")
    return v if isinstance(v, (int, float)) else None


def _matches(p: Product, c: Conditions) -> bool:
    if c.capacity_min is not None or c.capacity_max is not None:
        cap = _capacity(p)
        if cap is None or (c.capacity_min is not None and cap < c.capacity_min) or (c.capacity_max is not None and cap > c.capacity_max):
            return False
    if c.color and product_color_group(p) != c.color:
        return False
    if c.price_min is not None or c.price_max is not None:
        if p.price_krw is None or (c.price_min is not None and p.price_krw < c.price_min) \
                or (c.price_max is not None and p.price_krw > c.price_max):
            return False
    return True


def _buckets(values: list, buckets: list) -> list[dict]:
    out = []
    for lo, hi, label in buckets:
        # 경계값은 위 구간에 넣는다. 맨 아래 구간만 위 끝을 포함 (예: 400L 이하)
        n = sum(1 for x in values if (lo is None or x >= lo) and (hi is None or (x < hi if lo is not None else x <= hi)))
        row = {"label": label}
        if lo is not None:
            row["min"] = lo
        if hi is not None:
            row["max"] = hi
        out.append({**row, "count": n})
    return out


def _facets(scope: list[Product]) -> dict:
    caps = [x for x in map(_capacity, scope) if x is not None]
    capacity = _buckets(caps, CAPACITY_BUCKETS)
    counts: dict[str, int] = {}
    for p in scope:
        g = product_color_group(p)
        if g:
            counts[g] = counts.get(g, 0) + 1
    prices = [p.price_krw for p in scope if p.price_krw is not None]
    return {
        "capacity": capacity if caps else [],
        "color": [{"label": g, "count": counts[g]} for g in COLOR_GROUPS if g in counts],
        # 가격을 아는 제품이 하나도 없으면 null (화면에서 가격대 필터를 숨긴다)
        "price": {"min": min(prices), "max": max(prices), "known": len(prices),
                  "buckets": [b for b in _buckets(prices, PRICE_BUCKETS) if b["count"]]} if prices else None,
    }


def _slack(fit: Optional[dict]) -> float:
    """판정에 쓴 축 가운데 가장 작은 여유. 작을수록 공간에 딱 맞는다."""
    if not fit:
        return 0.0
    s = [d["slack_mm"] for d in fit.get("dims", {}).values() if d.get("slack_mm") is not None]
    return min(s) if s else 0.0


def _n(x: float) -> str:
    return f"{round(x):,}"


def _reasons(p: Product, c: Conditions, fit: Optional[dict], space: dict) -> list[str]:
    out = []
    if fit and fit.get("source") == "typed":
        for k, d in fit["dims"].items():
            if d["slack_mm"] is None:
                out.append(f"{_DIM_KO[k]} 치수를 몰라서 확인이 필요해요")
            elif d["slack_mm"] < 0:
                out.append(f"{_DIM_KO[k]}이 {_n(-d['slack_mm'])} mm 모자라요" if k != "height" else f"높이가 {_n(-d['slack_mm'])} mm 모자라요")
            elif d["verdict"] == "conditional":
                out.append(f"{_DIM_KO[k]} {_n(space[k])} mm 공간에 빠듯해요 (여유 {_n(d['slack_mm'])} mm)")
            else:
                out.append(f"{_DIM_KO[k]} {_n(space[k])} mm 공간에 들어가요 (여유 {_n(d['slack_mm'])} mm)")
    elif fit:
        out.append({"fit": "그려 둔 영역에 들어가요", "conditional": "그려 둔 영역에 빠듯하게 들어가요",
                    "no_fit": "그려 둔 영역에는 안 들어가요"}.get(fit["verdict"], "영역에 들어가는지 확인이 필요해요"))
    cap = _capacity(p)
    if cap is not None and (c.capacity_min is not None or c.capacity_max is not None):
        out.append(f"용량 {_n(cap)} L")
    if c.color:
        out.append(f"{c.color} 계열")
    if p.price_krw is not None and (c.price_min is not None or c.price_max is not None):
        out.append(f"{_n(p.price_krw)}원")
    return out


def find_products(products: list[Product], cond: Conditions, cfg: FitConfig | None = None,
                  zone_fit: Callable[[Product], Optional[dict]] | None = None) -> dict:
    """→ {items: [{product, fit, reasons, color_group}], total, facets}. zone_fit을 주면 그 판정을 쓴다(영역 기준)."""
    cfg = cfg or FitConfig()
    scope = [p for p in products if _on_sale(p) and _in_scope(p, cond)]
    space = {"width": cond.space_w, "height": cond.space_h, "depth": cond.space_d}
    rows = []
    for i, p in enumerate(scope):
        if not _matches(p, cond):
            continue
        fit = None
        if zone_fit:
            z = zone_fit(p)
            fit = {**z, "source": "zone"} if z else None
        if fit is None:
            fit = space_fit(p, space, cfg)
        if cond.fits_only and fit and fit["verdict"] == "no_fit":
            continue
        rows.append((i, p, fit))

    def recommended(r):
        i, p, fit = r
        return (_ORDER.index(fit["verdict"]) if fit else 0, _slack(fit) if fit and fit["verdict"] != "no_fit" else 0, i)

    def size(r):
        d = r[1].product_dims_mm
        return (d.w is None, d.w or 0, d.h or 0, d.d or 0, r[0])

    def price(r):
        return (r[1].price_krw is None, r[1].price_krw or 0, r[0])

    rows.sort(key={"size": size, "price": price}.get(cond.sort, recommended))
    total = len(rows)
    if cond.limit:
        rows = rows[:cond.limit]
    return {
        "items": [{"product": p.model_dump(), "fit": fit, "reasons": _reasons(p, cond, fit, space),
                   "color_group": product_color_group(p)} for _, p, fit in rows],
        "total": total,
        "facets": _facets(scope),
    }
