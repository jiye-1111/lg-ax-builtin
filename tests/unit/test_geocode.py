"""주소 찾기: 아파트 이름처럼 지도에 없는 말이 들어와도 동네까지는 찾아 준다 — 테스트 먼저."""
import json
import urllib.parse

import pytest

from sim.geocode import GeocodeError, geocode

DONG = {"lat": "37.2596", "lon": "127.0465", "display_name": "영통동, 영통구, 수원시, 경기도", "category": "boundary", "type": "administrative"}
STATION = {"lat": "37.2515", "lon": "127.0713", "display_name": "영통역", "category": "railway", "type": "station"}


def fake(table):
    """q → 결과 목록. 부른 q를 calls에 남긴다."""
    calls = []

    def fetch(url, headers):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["q"][0]
        calls.append(q)
        return json.dumps(table.get(q, []))
    return fetch, calls


def test_exact_match_is_not_approx():
    fetch, calls = fake({"수원시 영통구 영통로 100": [DONG]})
    g = geocode("수원시 영통구 영통로 100", fetch)
    assert g["approx"] is False and calls == ["수원시 영통구 영통로 100"]


def test_apartment_name_falls_back_to_neighbourhood():
    fetch, calls = fake({"영통": [STATION, DONG]})
    g = geocode("영통포레 파크원", fetch)
    assert g["approx"] is True and g["lat"] == pytest.approx(37.2596)
    assert g["address"].startswith("영통동") and g["axis_deg"] is None   # 어느 동인지 모르니 건물 방향은 쓰지 않는다
    assert calls[0] == "영통포레 파크원" and calls[-1] == "영통"


def test_fallback_drops_trailing_words_first():
    fetch, calls = fake({"수원시 영통구": [DONG]})
    g = geocode("수원시 영통구 없는아파트 101동", fetch)
    assert g["approx"] is True and "수원시 영통구" in calls


def test_station_counts_as_neighbourhood_and_label_is_the_dong():
    # 실제 Nominatim은 "영통"에 역만 돌려준다. 역도 동네로 받고, 화면에는 역 이름이 아니라 동 이름을 보여 준다
    real = {"lat": "37.2513466", "lon": "127.0712790", "category": "railway", "type": "station",
            "display_name": "영통, 봉영로, 영통동, 영통구, 수원시, 경기도, 16701, 대한민국"}
    fetch, _ = fake({"영통": [real]})
    g = geocode("영통포레 파크원", fetch)
    assert g["approx"] is True and g["area"] == "영통동" and g["lat"] == pytest.approx(37.2513466)


def test_area_label_falls_back_to_first_part():
    fetch, _ = fake({"수원시 영통구": [DONG]})
    assert geocode("수원시 영통구 없는아파트 101동", fetch)["area"] == "영통동"


def test_fallback_ignores_shops():
    fetch, _ = fake({"영통": [{**STATION, "category": "shop"}]})
    with pytest.raises(GeocodeError):
        geocode("영통포레 파크원", fetch)


def test_fallback_is_bounded():
    fetch, calls = fake({})
    with pytest.raises(GeocodeError, match="찾지 못했어요"):
        geocode("가 나 다 라 마 바 사 아 자", fetch)
    assert len(calls) <= 5
