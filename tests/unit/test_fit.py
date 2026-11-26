"""적합 판정 규칙 (기획 §9.1) — TDD로 먼저 작성한 테스트."""
import pytest

from core.models import (
    BBox, Clearance, Dims, MeasuredDims, Opening, Product, Room, RoomObject,
    ScannedDims, Wall, Zone,
)
from recommender.fit import FitConfig, Verdict, check_fit, judge_dimension


def make_room(measured=None, openings=(), objects=()):
    # 4m x 3m 직사각형 방. w1 = 바닥 y=0 벽 (x: 0→4)
    walls = [
        Wall(wall_id="w1", start=(0, 0), end=(4, 0), scanned=ScannedDims(length_m=4.0, height_m=2.4), measured=measured),
        Wall(wall_id="w2", start=(4, 0), end=(4, 3), scanned=ScannedDims(length_m=3.0, height_m=2.4)),
        Wall(wall_id="w3", start=(4, 3), end=(0, 3), scanned=ScannedDims(length_m=4.0, height_m=2.4)),
        Wall(wall_id="w4", start=(0, 3), end=(0, 0), scanned=ScannedDims(length_m=3.0, height_m=2.4)),
    ]
    return Room(walls=walls, openings=list(openings), objects=list(objects))


KITCHEN = Zone(zone_id="z_k", purpose="kitchen", polygon_m=[(0, 0), (4, 0), (4, 1.5), (0, 1.5)], wall_ids=["w1"])


def product(w=900, h=1800, d=700, side=5, top=10, back=50, required=None):
    return Product(
        sku="T-1", name="테스트 냉장고", category="refrigerator", zone_fit=["kitchen"], install_type="built_in",
        product_dims_mm=Dims(w=w, h=h, d=d), required_space_mm=required or Dims(),
        clearance_mm=Clearance(side=side, top=top, back=back), source_url=None, source_checked_at=None, demo_only=True,
    )


CFG = FitConfig(margin_scanned_mm=30, margin_measured_mm=5)


# ---- 단일 치수 규칙 ----
@pytest.mark.parametrize(
    "avail, req, measured, expected",
    [
        (1000, 900, True, Verdict.FIT),            # 여유 100 ≥ 5
        (1000, 900, False, Verdict.FIT),           # 스캔값이어도 여유 100 ≥ 30 이면 적합
        (903, 900, True, Verdict.CONDITIONAL),     # 0 ≤ 3 < 5
        (920, 900, False, Verdict.CONDITIONAL),    # 0 ≤ 20 < 30
        (899, 900, True, Verdict.NO_FIT),          # 여유 < 0
        (None, 900, True, Verdict.UNKNOWN),
        (1000, None, True, Verdict.UNKNOWN),
    ],
)
def test_judge_dimension(avail, req, measured, expected):
    assert judge_dimension(avail, req, measured, CFG).verdict == expected


def test_scanned_cap_option_keeps_old_rule():
    cfg = FitConfig(margin_scanned_mm=30, margin_measured_mm=5, scanned_max_conditional=True)
    assert judge_dimension(1000, 900, False, cfg).verdict == Verdict.CONDITIONAL
    assert judge_dimension(1000, 900, True, cfg).verdict == Verdict.FIT


def test_margin_boundary_is_inclusive():
    # 여유 == margin → 적합
    assert judge_dimension(905, 900, True, CFG).verdict == Verdict.FIT


# ---- 벽·영역 판정 ----
def test_scanned_with_enough_slack_is_fit():
    # 시연은 줄자 실측 없이 스캔값만 쓴다 → 마진 30mm를 넘게 남으면 적합
    r = check_fit(make_room(), KITCHEN, product(), CFG)
    assert r.verdict == Verdict.FIT
    assert r.wall_id == "w1"
    assert r.dims["width"].source == "scanned"


def test_measured_wall_with_measured_depth_can_be_fit():
    m = MeasuredDims(length_m=4.0, height_m=2.4, depth_m=1.5, by="technician")
    r = check_fit(make_room(measured=m), KITCHEN, product(), CFG)
    assert r.verdict == Verdict.FIT
    assert {d.source for d in r.dims.values()} == {"measured"}


def test_too_tall_is_no_fit():
    m = MeasuredDims(length_m=4.0, height_m=1.7, depth_m=1.5)
    r = check_fit(make_room(measured=m), KITCHEN, product(), CFG)
    assert r.verdict == Verdict.NO_FIT
    assert r.dims["height"].verdict == Verdict.NO_FIT


def test_required_space_overrides_dims_plus_clearance():
    m = MeasuredDims(length_m=4.0, height_m=2.4, depth_m=1.5)
    r = check_fit(make_room(measured=m), KITCHEN, product(required=Dims(w=5000, h=None, d=None)), CFG)
    assert r.dims["width"].required_mm == 5000
    assert r.verdict == Verdict.NO_FIT


def test_null_dims_gives_unknown():
    p = product(w=None)
    m = MeasuredDims(length_m=4.0, height_m=2.4, depth_m=1.5)
    r = check_fit(make_room(measured=m), KITCHEN, p, CFG)
    assert r.verdict == Verdict.UNKNOWN


def test_unknown_clearance_caps_at_conditional():
    p = product(side=None, top=None, back=None)
    m = MeasuredDims(length_m=4.0, height_m=2.4, depth_m=1.5)
    r = check_fit(make_room(measured=m), KITCHEN, p, CFG)
    assert r.verdict == Verdict.CONDITIONAL
    assert "clearance_unknown" in r.notes


def test_door_on_wall_reduces_available_width():
    # 문이 1.0~3.5m를 차지 → 남는 최대 연속 구간 = 1.0m
    door = Opening(opening_id="d1", type="door", wall_id="w1", offset_m=1.0, width_m=2.5, height_m=2.1)
    m = MeasuredDims(length_m=4.0, height_m=2.4, depth_m=1.5)
    r = check_fit(make_room(measured=m, openings=[door]), KITCHEN, product(w=900, side=5), CFG)
    assert r.dims["width"].available_mm == pytest.approx(1000)
    assert r.verdict == Verdict.FIT  # 1000 - 910 = 90 ≥ 5

    r2 = check_fit(make_room(measured=m, openings=[door]), KITCHEN, product(w=1000, side=5), CFG)
    assert r2.verdict == Verdict.NO_FIT


def test_high_window_does_not_block_short_product():
    win = Opening(opening_id="win1", type="window", wall_id="w1", offset_m=0.5, width_m=3.0, height_m=0.8, sill_m=1.2)
    m = MeasuredDims(length_m=4.0, height_m=2.4, depth_m=1.5)
    short = product(w=600, h=850, d=600, side=0, top=0, back=0)  # 식기세척기 높이
    r = check_fit(make_room(measured=m, openings=[win]), KITCHEN, short, CFG)
    assert r.dims["width"].available_mm == pytest.approx(4000)


def test_existing_object_against_wall_blocks_interval():
    # 벽 w1 앞 x=0..1.2 에 기존 수납장
    cab = RoomObject(object_id="o1", category="storage", bbox_m=BBox(w=1.2, h=0.9, d=0.6), position=(0.6, 0.45, 0.3))
    m = MeasuredDims(length_m=4.0, height_m=2.4, depth_m=1.5)
    r = check_fit(make_room(measured=m, objects=[cab]), KITCHEN, product(), CFG)
    assert r.dims["width"].available_mm == pytest.approx(2800, abs=1)


def test_zone_clips_wall_interval():
    # 영역이 벽 w1의 0~2m만 덮으면 가용 폭은 2m
    z = Zone(zone_id="z", purpose="kitchen", polygon_m=[(0, 0), (2, 0), (2, 1.5), (0, 1.5)], wall_ids=["w1"])
    m = MeasuredDims(length_m=4.0, height_m=2.4, depth_m=1.5)
    r = check_fit(make_room(measured=m), z, product(), CFG)
    assert r.dims["width"].available_mm == pytest.approx(2000)


def test_scanned_depth_comes_from_zone_polygon():
    r = check_fit(make_room(), KITCHEN, product(), CFG)
    assert r.dims["depth"].available_mm == pytest.approx(1500)
    assert r.dims["depth"].source == "scanned"


def test_auto_detects_zone_walls_when_not_given():
    z = KITCHEN.model_copy(update={"wall_ids": []})
    r = check_fit(make_room(), z, product(), CFG)
    assert r.wall_id in {"w1", "w2", "w4"}  # 영역 경계와 겹치는 벽 중 하나


def test_picks_best_wall():
    # w1에는 큰 문, w4는 비어 있음 → w4 선택
    door = Opening(opening_id="d1", type="door", wall_id="w1", offset_m=0.2, width_m=3.6, height_m=2.1)
    z = Zone(zone_id="z", purpose="kitchen", polygon_m=[(0, 0), (4, 0), (4, 3), (0, 3)], wall_ids=["w1", "w4"])
    r = check_fit(make_room(openings=[door]), z, product(), CFG)
    assert r.wall_id == "w4"


# ---- 일반(프리스탠딩) 가전: 놓을 자리 + 앞쪽 문 열림 공간 ----
def freestanding(door=580, category="washer", install="freestanding"):
    return Product(
        sku="T-WM", name="테스트 세탁기", category=category, zone_fit=["laundry"], install_type=install,
        product_dims_mm=Dims(w=700, h=990, d=830), clearance_mm=Clearance(side=5, top=10, back=50),
        door_swing_mm=door, source_url=None, source_checked_at=None, demo_only=True,
    )


def test_freestanding_checks_front_door_space():
    r = check_fit(make_room(), KITCHEN, freestanding(), CFG)
    f = r.dims["front"]
    assert f.required_mm == 580 and f.available_mm == pytest.approx(3000 - 880)
    assert r.verdict == Verdict.FIT


def test_freestanding_front_blocked_by_object_is_no_fit():
    table = RoomObject(object_id="t1", category="table", bbox_m=BBox(w=1.0, h=0.75, d=0.5), position=(2.0, 0.375, 1.2))
    r = check_fit(make_room(objects=[table]), KITCHEN, freestanding(), CFG)
    assert r.dims["front"].verdict == Verdict.NO_FIT and r.verdict == Verdict.NO_FIT


def test_built_in_has_no_front_check():
    r = check_fit(make_room(), KITCHEN, freestanding(install="built_in"), CFG)
    assert "front" not in r.dims


def test_unknown_door_space_uses_default_and_caps_conditional():
    cfg = FitConfig(margin_scanned_mm=30, margin_measured_mm=5, front_default_mm=600)
    r = check_fit(make_room(), KITCHEN, freestanding(door=None, category="refrigerator"), cfg)
    assert r.dims["front"].required_mm == 600 and "front_space_assumed" in r.notes
    assert r.verdict == Verdict.CONDITIONAL


def test_doorless_product_has_no_front_check():
    r = check_fit(make_room(), KITCHEN, freestanding(door=None, category="tv"), CFG)
    assert "front" not in r.dims


def test_fit_and_max_is_judged_like_built_in():
    r = check_fit(make_room(), KITCHEN, freestanding(door=None, category="refrigerator", install="built_in_look"), CFG)
    assert "front" not in r.dims


def test_floorplan_length_is_used_but_keeps_the_scan_margin():
    # 도면 치수는 줄자로 잰 값이 아니다: 길이는 도면 값을 쓰되 여유는 스캔과 같은 30 mm를 둔다
    m = MeasuredDims(length_m=0.925, by="floorplan")  # 제품 900 + 옆 5×2 = 910 → 15 mm 남는다
    r = check_fit(make_room(measured=m), KITCHEN, product(), CFG)
    assert r.dims["width"].source == "scanned" and r.dims["width"].available_mm == 925
    assert r.dims["width"].verdict == Verdict.CONDITIONAL
    tape = MeasuredDims(length_m=0.925, by="technician")
    assert check_fit(make_room(measured=tape), KITCHEN, product(), CFG).dims["width"].verdict == Verdict.FIT


def test_length_estimated_from_a_reference_wall_keeps_the_scan_margin():
    # 다른 벽을 재서 바로잡은 길이는 이 벽을 직접 잰 값이 아니다: 길이는 쓰되 여유는 스캔과 같다
    m = MeasuredDims(length_m=0.925, by="reference")
    r = check_fit(make_room(measured=m), KITCHEN, product(), CFG)
    assert r.dims["width"].source == "scanned" and r.dims["width"].available_mm == 925
    assert r.dims["width"].verdict == Verdict.CONDITIONAL
