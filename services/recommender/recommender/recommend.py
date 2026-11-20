"""영역 추천: 영역 × 카탈로그 → 적합 판정 + CMF 상위 옵션 (기획 F8·F9)."""
from __future__ import annotations

from core.models import Product, Room, Zone

from .cmf import rank_cmf
from .fit import FitConfig, Verdict, check_fit

_ORDER = [Verdict.FIT, Verdict.CONDITIONAL, Verdict.UNKNOWN, Verdict.NO_FIT]


def recommend_zone(room: Room, zone: Zone, products: list[Product], cfg: FitConfig | None = None,
                   top_k_cmf: int = 3, include_no_fit: bool = True) -> list[dict]:
    out = []
    for p in products:
        if zone.purpose not in p.zone_fit:
            continue
        if p.sale_status == "NOT_FOR_SALE":  # LGE.COM에서 팔지 않는 제품은 추천하지 않는다
            continue
        fit = check_fit(room, zone, p, cfg)
        if fit.verdict == Verdict.NO_FIT and not include_no_fit:
            continue
        cmf = rank_cmf(p, zone.style_tags, top_k_cmf)
        out.append({
            "product": p.model_dump(),
            "fit": fit.to_dict(),
            "cmf": [m.to_dict() for m in cmf],
            "_sort": (_ORDER.index(fit.verdict), -(cmf[0].score if cmf else 0)),
        })
    out.sort(key=lambda r: r.pop("_sort"))
    return out
