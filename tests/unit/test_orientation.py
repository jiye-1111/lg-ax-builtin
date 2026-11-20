"""집 방향(남향·북향)과 주소 → 위도·경도. 판정은 코드가 한다.

north_deg: 평면도 위쪽에서 북쪽까지 시계 방향 각도 (Service.set_site와 같은 뜻).
4m x 3m 방, w1(y=0, 평면 위쪽 벽)에 큰 창. north_deg=180이면 w1이 남쪽.
"""
import json

import pytest

from core.models import Opening, Room, ScannedDims, Wall
from sim.geocode import GeocodeError, geocode, parse_place
from sim.orientation import bearing_label, estimate_north, footprint_axis_deg, window_facings


def room(extra=()):
    walls = [
        Wall(wall_id="w1", start=(0, 0), end=(4, 0), thickness_m=0.1, scanned=ScannedDims(length_m=4, height_m=2.4)),
        Wall(wall_id="w2", start=(4, 0), end=(4, 3), thickness_m=0.1, scanned=ScannedDims(length_m=3, height_m=2.4)),
        Wall(wall_id="w3", start=(4, 3), end=(0, 3), thickness_m=0.1, scanned=ScannedDims(length_m=4, height_m=2.4)),
        Wall(wall_id="w4", start=(0, 3), end=(0, 0), thickness_m=0.1, scanned=ScannedDims(length_m=3, height_m=2.4)),
    ]
    ops = [Opening(opening_id="big", type="window", wall_id="w1", offset_m=1.0, width_m=2.0, height_m=1.2, sill_m=0.8), *extra]
    return Room(walls=walls, openings=ops)


def test_bearing_labels_are_eight_way():
    assert [bearing_label(d) for d in (0, 44, 90, 135, 180, 225, 270, 315, 359)] == ["북", "북동", "동", "남동", "남", "남서", "서", "북서", "북"]


def test_window_facing_follows_north():
    f = window_facings(room(), 180)[0]
    assert f["wall_id"] == "w1" and f["bearing_deg"] == pytest.approx(180, abs=0.1) and f["label"] == "남향"
    assert window_facings(room(), 0)[0]["label"] == "북향"
    assert window_facings(room(), 90)[0]["label"] == "서향"  # 평면 위쪽(-y)이 서쪽


def test_facings_are_sorted_by_window_area_and_skip_doors():
    small = Opening(opening_id="small", type="window", wall_id="w2", offset_m=1.0, width_m=0.6, height_m=0.6, sill_m=1.2)
    door = Opening(opening_id="d", type="door", wall_id="w3", offset_m=1.0, width_m=0.9, height_m=2.1)
    fs = window_facings(room([small, door]), 180)
    assert [f["wall_id"] for f in fs] == ["w1", "w2"]
    assert fs[0]["area_m2"] == pytest.approx(2.4) and fs[1]["label"] == "서향"


def test_estimate_assumes_main_window_faces_south():
    e = estimate_north(room())
    assert e["north_deg"] == pytest.approx(180, abs=0.1) and e["basis"] == "main_window_south" and e["main_wall_id"] == "w1"
    assert window_facings(room(), e["north_deg"])[0]["label"] == "남향"


def test_estimate_snaps_to_building_axis():
    # 건물 변이 북에서 20° 돌아가 있으면 남쪽에 가장 가까운 면은 200°(남남서)
    e = estimate_north(room(), axis_deg=20)
    assert e["basis"] == "building_footprint"
    assert window_facings(room(), e["north_deg"])[0]["bearing_deg"] == pytest.approx(200, abs=0.1)
    # 70° → 160°(남남동)
    e = estimate_north(room(), axis_deg=70)
    assert window_facings(room(), e["north_deg"])[0]["bearing_deg"] == pytest.approx(160, abs=0.1)


def test_estimate_without_windows_is_none():
    r = room()
    assert estimate_north(Room(walls=r.walls, openings=[])) is None


def test_footprint_axis_from_rotated_rectangle():
    import math
    lat, lon, m = 37.5, 127.0, 1 / 111_320
    def pt(e, n):  # 동쪽 e m, 북쪽 n m
        return [lon + e * m / math.cos(math.radians(lat)), lat + n * m]
    a = math.radians(25)  # 긴 변이 북에서 25° 방향인 40 m × 12 m 건물
    L, W = (math.sin(a) * 40, math.cos(a) * 40), (math.cos(a) * 12, -math.sin(a) * 12)
    ring = [pt(0, 0), pt(*L), pt(L[0] + W[0], L[1] + W[1]), pt(*W), pt(0, 0)]
    assert footprint_axis_deg(ring) == pytest.approx(25, abs=0.5)
    assert footprint_axis_deg([pt(0, 0), pt(1, 0)]) is None


NOMINATIM = [{"lat": "37.5667893", "lon": "126.9784204", "display_name": "서울특별시청, 110, 세종대로, 중구, 서울특별시, 대한민국",
              "geojson": {"type": "Polygon", "coordinates": [[[126.9778, 37.5669], [126.9778, 37.5664], [126.9790, 37.5664], [126.9790, 37.5669], [126.9778, 37.5669]]]}}]


def test_parse_place_reads_lat_lon_and_building_axis():
    p = parse_place(NOMINATIM)
    assert p["lat"] == pytest.approx(37.5667893) and p["lon"] == pytest.approx(126.9784204)
    assert "세종대로" in p["address"]
    assert p["axis_deg"] == pytest.approx(0, abs=1) or p["axis_deg"] == pytest.approx(90, abs=1)
    assert parse_place([{"lat": "35.1", "lon": "129.0", "display_name": "부산", "geojson": {"type": "Point", "coordinates": [129.0, 35.1]}}])["axis_deg"] is None


def test_geocode_uses_injected_fetch_and_rejects_bad_input():
    seen = {}
    def fetch(url, headers):
        seen.update(url=url, headers=headers)
        return json.dumps(NOMINATIM)
    p = geocode("서울 중구 세종대로 110", fetch=fetch)
    assert p["lat"] == pytest.approx(37.5667893)
    assert "polygon_geojson=1" in seen["url"] and "User-Agent" in seen["headers"]
    with pytest.raises(GeocodeError):
        geocode("  ", fetch=fetch)
    with pytest.raises(GeocodeError):
        geocode("없는 주소", fetch=lambda u, h: "[]")
    with pytest.raises(GeocodeError):
        geocode("x" * 300, fetch=fetch)
