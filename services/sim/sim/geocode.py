"""주소 → 위도·경도 (+ 건물 외곽선이 있으면 건물 방향). 채광의 해 위치 계산에 쓴다.

기본은 OpenStreetMap Nominatim (키 없음, 초당 1회 이하). 주소는 .env의 GEOCODER_URL로 바꿀 수 있다.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Callable, Optional

from .orientation import footprint_axis_deg

MAX_QUERY = 200


class GeocodeError(ValueError):
    pass


def _http_get(url: str, headers: dict) -> str:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=float(os.getenv("GEOCODER_TIMEOUT_S", 8))) as r:  # noqa: S310 (주소는 .env)
        return r.read(2_000_000).decode("utf-8")


def parse_place(items: list) -> dict:
    if not items:
        raise GeocodeError("주소를 찾지 못했어요. 도로명 주소나 건물 이름으로 다시 적어 주세요")
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


def geocode(query: str, fetch: Callable[[str, dict], str] | None = None) -> dict:
    q = (query or "").strip()
    if not q:
        raise GeocodeError("주소를 적어 주세요")
    if len(q) > MAX_QUERY:
        raise GeocodeError("주소가 너무 길어요")
    base = os.getenv("GEOCODER_URL", "https://nominatim.openstreetmap.org/search")
    url = base + "?" + urllib.parse.urlencode({"format": "jsonv2", "limit": 1, "countrycodes": "kr", "accept-language": "ko",
                                               "polygon_geojson": 1, "q": q})
    headers = {"User-Agent": os.getenv("GEOCODER_USER_AGENT", "housetwin-demo/0.1")}
    try:
        body = (fetch or _http_get)(url, headers)
        items = json.loads(body)
    except GeocodeError:
        raise
    except Exception as e:  # 네트워크·형식 오류
        raise GeocodeError("주소 검색에 연결하지 못했어요. 잠시 뒤 다시 해 보거나 지역을 직접 골라 주세요") from e
    if not isinstance(items, list):
        raise GeocodeError("주소 검색 결과를 읽지 못했어요")
    return parse_place(items)
