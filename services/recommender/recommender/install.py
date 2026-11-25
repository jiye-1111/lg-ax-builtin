"""설치 전 확인 목록. 놓은 제품의 판정 결과를 기사와 고객이 방문 전에 볼 수 있게 한 줄씩 정리한다.

상태는 네 가지.
- ok: 스캔으로 확인됨
- check: 걸리는 것이 있어 확인 필요
- blocked: 지금 자리에는 들어가지 않음
- site: 스캔으로는 알 수 없어 현장에서 봐야 함 (콘센트, 급수·배수, 현관·복도)
"""
from __future__ import annotations

from typing import Callable, Iterable

from core.models import Product, Room

from .contract import site_lines
from .fit import FitConfig, front_space

# 급수·배수 연결이 필요한 제품군
NEEDS_WATER = {"dishwasher", "washer", "wash_tower", "washer_dryer", "water_purifier"}
# 벽 치수 오차에 따라 결과가 달라지는 이유 → 그 벽을 줄자로 재면 판정이 확실해진다
MEASURE_CODES = {"tight", "clearance_blocked", "ceiling_tight", "ceiling_low"}
OWN_LINE = {"front_blocked", "front_space_assumed", "passage_narrow", "entry_narrow"}
STATUS = {"fit": "ok", "conditional": "check", "unknown": "check", "no_fit": "blocked"}
_RANK = {"ok": 0, "site": 0, "check": 1, "blocked": 2}


def _line(code: str, label: str, status: str, detail: str = "") -> dict:
    return {"code": code, "label": label, "status": status, "detail": detail}


def _mm(v: float) -> str:
    return f"{round(v):,} mm"


def _water_detail(p: Product) -> str:
    m, bits = p.install_mm, []
    if "water_source_max" in m:
        bits.append(f"수도에서 {m['water_source_max'] / 1000:g} m 안")
    if p.needs_drain:
        bits.append("배수 호스 연결 필요")
    if "hose_hole_dia" in m:
        bits.append(f"호스가 지나갈 싱크대 구멍 약 {_mm(m['hose_hole_dia'])}")
    return " · ".join(bits)


def _water_purifier_lines(p: Product) -> list[dict]:
    """정수기 설치가이드의 현장 확인 항목. 스캔으로는 알 수 없어 모두 '현장 확인'."""
    m, c, out = p.install_mm, p.clearance_mm, []
    if "faucet_hole_dia" in m:
        bits = [f"구멍 지름 {_mm(m['faucet_hole_dia'])}"]
        if "faucet_ring_dia" in m:
            bits.append(f"위쪽 고정 자리 지름 {_mm(m['faucet_ring_dia'])}")
        if "faucet_under_w" in m and "faucet_under_d" in m:
            bits.append(f"아래쪽 가로 {_mm(m['faucet_under_w'])} × 세로 {_mm(m['faucet_under_d'])}")
        out.append(_line("faucet", "출수구 자리 (싱크볼·상판)", "site", " · ".join(bits)))
    if p.install_form == "빌트인":
        bits = []
        if c.back is not None and c.side_total is not None:
            bits.append(f"하부장 안 벽 쪽 {_mm(c.back)}, 옆 쪽 {_mm(c.side_total)} 여유")
        if "faucet_to_body_max" in m:
            bits.append(f"출수구에서 본체까지 {_mm(m['faucet_to_body_max'])} 안")
        if "cord_hole_dia" in m:
            bits.append(f"하부장에 콘센트가 없으면 전선 구멍 {_mm(m['cord_hole_dia'])}")
        out.append(_line("body", "하부장 안 본체 자리", "site", " · ".join(bits)))
    elif p.install_form == "데스크" and c.top is not None:
        out.append(_line("above", "제품 위 여유", "site", f"위로 {_mm(c.top)} 넘게 비어 있어야 해요 (상부장 아래에 놓을 때)"))
    if "cabinet_top_min" in m:
        out.append(_line("above", "가구장 안에 놓을 때", "site",
                         f"위로 {_mm(m['cabinet_top_min'])} 넘게 비우고 바닥에 바로 놓아야 해요 (슬라이딩 선반 위 불가)"))
    return out


def _item(room: Room, x: dict, p: Product, contract: dict | None = None) -> dict:
    d = p.product_dims_mm
    reasons = x.get("reasons") or []
    by_code = {r["code"]: r for r in reasons}
    walls = {w.wall_id: w for w in room.walls}
    checks: list[dict] = []

    # 자리: 앞 공간·들여오는 길은 따로 줄을 두므로 여기서는 뺀다
    space = [r for r in reasons if r["code"] not in OWN_LINE]
    worst = max((STATUS.get(r.get("verdict"), "check") for r in space), key=_RANK.get, default="ok")
    if x.get("verdict") == "unknown":
        worst = "check"
    checks.append(_line("space", "놓을 자리", worst, " · ".join(r["label"] for r in space)))

    front_mm, _ = front_space(p, FitConfig())
    if front_mm is not None:  # 일반 가전 중 앞으로 문을 여는 것만
        if "front_blocked" in by_code:
            checks.append(_line("front", "문 열고 쓰는 앞 공간", "blocked", by_code["front_blocked"]["label"]))
        elif "front_space_assumed" in by_code:
            checks.append(_line("front", "문 열고 쓰는 앞 공간", "check", by_code["front_space_assumed"]["label"]))
        else:
            checks.append(_line("front", "문 열고 쓰는 앞 공간", "ok"))

    if "passage_narrow" in by_code:
        checks.append(_line("passage", "앞 통로", "check", by_code["passage_narrow"]["label"]))

    need = sorted({r["ref"] for r in reasons if r["code"] in MEASURE_CODES and r.get("ref") in walls
                   and not (walls[r["ref"]].measured and (walls[r["ref"]].measured.length_m or walls[r["ref"]].measured.height_m))})
    if need:
        checks.append(_line("measure", "줄자로 잴 벽", "check", ", ".join(need)))

    thin = min(v for v in (d.w, d.d) if v is not None) if (d.w is not None or d.d is not None) else None
    doors = [op for op in room.openings if op.type in ("door", "opening") and op.width_m > 0]
    if doors and thin is not None:
        widest = round(max(op.width_m for op in doors) * 1000)
        narrow = "entry_narrow" in by_code
        checks.append(_line("entry", "방 문 통과", "check" if narrow else "ok",
                            f"문 폭 {widest:,} mm, 제품 얇은 쪽 {round(thin):,} mm"))
    if thin is not None:
        checks.append(_line("carry", "현관·복도·엘리베이터", "site", f"폭 {round(thin):,} mm 넘게 비어 있어야 들어와요"))
    checks.append(_line("power", "콘센트 위치", "site"))
    if p.category in NEEDS_WATER:
        checks.append(_line("water", "급수·배수 연결 위치", "site", _water_detail(p)))
    checks += _water_purifier_lines(p)
    if contract:  # 전달받은 묶음의 설치 계약: 설명서 조건은 현장 값이 있어야 알 수 있어 모두 '현장 확인'
        checks += [_line(c["code"], c["label"], c["status"], c["detail"]) for c in site_lines(contract)]

    status = max((c["status"] for c in checks), key=_RANK.get)
    return {"placement_id": x.get("placement_id"), "sku": p.sku, "name": p.name, "category": p.category,
            "dims_mm": {"w": d.w, "h": d.h, "d": d.d}, "source_url": p.source_url, "verdict": x.get("verdict"), "wall_id": x.get("wall_id"),
            "status": "ok" if status == "site" else status, "checks": checks, "_measure": need}


def install_checklist(room: Room, placements: Iterable[dict], get_product: Callable[[str], Product],
                      get_contract: Callable[[str], dict | None] | None = None) -> dict:
    items = []
    for x in placements:
        try:
            p = get_product(x["sku"])
        except KeyError:
            continue
        items.append(_item(room, x, p, get_contract(p.sku) if get_contract else None))
    walls = sorted({w for it in items for w in it.pop("_measure")})
    count = lambda s: sum(1 for it in items if it["status"] == s)  # noqa: E731
    return {"summary": {"products": len(items), "ok": count("ok"), "check": count("check"), "blocked": count("blocked"),
                        "walls_to_measure": walls}, "items": items}
