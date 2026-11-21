"""주소 → 위도·경도 (+ 건물 외곽선이 있으면 건물 방향). 채광의 해 위치 계산에 쓴다.

기본은 OpenStreetMap Nominatim (키 없음, 초당 1회 이하). 주소는 .env의 GEOCODER_URL로 바꿀 수 있다.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Callable, Optional

from .orientation import footprint_axis_deg

MAX_QUERY = 200
NOMINATIM_GAP_S = 1.0


class GeocodeError(ValueError):
    pass


def _http_get(url: str, headers: dict) -> str:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=float(os.getenv("GEOCODER_TIMEOUT_S", 8))) as r:  # noqa: S310 (주소는 .env)
        return r.read(2_000_000).decode("utf-8")


def parse_place(items: list) -> dict:
    if not items:
        raise GeocodeError("주소를 찾지 못했어요")
    it = items[0]
    try:
        lat, lon = float(it["lat"]), float(it["lon"])
    except (KeyError, TypeError, ValueError) as e:
        raise GeocodeError("주소 검색 결과를 읽지 못했어요") from e
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise GeocodeError("주소 검색 결과를 읽지 못했어요")
    axis: Optional[float] = None
    gj = it.get("geojson") or {}
    if gj.get("type") == "Polygon" and gj.get("coordinates"):
        try:
            axis = footprint_axis_deg(gj["coordinates"][0])
        except (TypeError, ValueError, IndexError):
            axis = None
    return {"lat": round(lat, 6), "lon": round(lon, 6), "address": str(it.get("display_name") or "")[:200],
            "axis_deg": None if axis is None else round(axis, 1)}


AREA_KINDS = {"boundary", "place", "highway", "railway"}   # 동네로 받아들이는 것: 행정 구역·지명·길·역. 가게 같은 점은 엉뚱한 곳일 수 있어 뺀다
MAX_AREA_TRIES = 4
NOT_FOUND = "주소를 찾지 못했어요. 도로명 주소나 동 이름으로 다시 적어 주세요"


def area_label(display_name: str) -> str:
    """지도 이름("영통, 봉영로, 영통동, 영통구, …")에서 화면에 보여 줄 동네 이름. 동·읍·면이 먼저, 없으면 구·군·시, 그것도 없으면 맨 앞."""
    parts = [p.strip() for p in display_name.split(",") if p.strip()]
    for ends in ("동읍면", "구군시"):
        for p in parts:
            if len(p) >= 2 and p[-1] in ends:
                return p
    return parts[0] if parts else ""


def area_queries(q: str) -> list[str]:
    """못 찾았을 때 다시 물어볼 말. 뒤 낱말을 하나씩 떼고, 마지막에는 첫 낱말의 앞 3·2글자 (아파트 이름은 대개 동 이름으로 시작한다)."""
    words = q.split()
    out = [" ".join(words[:n]) for n in range(len(words) - 1, 1, -1)]
    head = words[0]
    out += [head] if len(words) > 1 and len(head) <= 3 else []
    out += [head[:n] for n in (3, 2) if len(head) > n]
    return list(dict.fromkeys(out))[:MAX_AREA_TRIES]


def _search(q: str, limit: int, fetch: Callable[[str, dict], str]) -> list:
    base = os.getenv("GEOCODER_URL", "https://nominatim.openstreetmap.org/search")
    url = base + "?" + urllib.parse.urlencode({"format": "jsonv2", "limit": limit, "countrycodes": "kr", "accept-language": "ko",
                                               "polygon_geojson": 1, "q": q})
    headers = {"User-Agent": os.getenv("GEOCODER_USER_AGENT", "housetwin-demo/0.1")}
    try:
        items = json.loads(fetch(url, headers))
    except Exception as e:  # 네트워크·형식 오류
        raise GeocodeError("주소 검색에 연결하지 못했어요. 잠시 뒤 다시 해 보세요") from e
    if not isinstance(items, list):
        raise GeocodeError("주소 검색 결과를 읽지 못했어요")
    return items


def geocode(query: str, fetch: Callable[[str, dict], str] | None = None) -> dict:
    """approx=True면 적은 곳 그대로는 못 찾아 동네까지만 찾은 것. 해 위치에는 충분하지만 건물 방향(axis_deg)은 쓰지 않는다."""
    q = (query or "").strip()
    if not q:
        raise GeocodeError("주소를 적어 주세요")
    if len(q) > MAX_QUERY:
        raise GeocodeError("주소가 너무 길어요")
    live = fetch is None
    get = fetch or _http_get
    items = _search(q, 1, get)
    if items:
        return {**parse_place(items), "approx": False, "area": None}
    for sub in area_queries(q):
        if live:
            time.sleep(NOMINATIM_GAP_S)   # Nominatim은 초당 1회 이하로 써야 한다
        areas = [it for it in _search(sub, 5, get) if isinstance(it, dict) and it.get("category") in AREA_KINDS]
        areas.sort(key=lambda it: it.get("category") == "railway")   # 역보다 행정 구역·지명이 먼저
        if areas:
            place = parse_place(areas[:1])
            return {**place, "axis_deg": None, "approx": True, "area": area_label(place["address"])}
    raise GeocodeError(NOT_FOUND)
