"""잰 벽 하나를 기준으로 나머지 벽 길이를 바로잡는 계산 (docs/specs/fit-rules.md '기준 벽')."""
import pytest

from core.models import MeasuredDims, ScannedDims, Wall
from recommender.reference import estimate


def wall(wid, start, end, measured=None, by="customer", scan=None):
    import math
    L = scan if scan is not None else math.dist(start, end)
    m = MeasuredDims(length_m=measured, by=by) if measured is not None else None
    return Wall(wall_id=wid, start=start, end=end, scanned=ScannedDims(length_m=L, height_m=2.4), measured=m)


def rect(w=5.0, d=4.0, **measured):
    """w1 아래, w2 오른쪽, w3 위, w4 왼쪽"""
    pts = {"w1": ((0, 0), (w, 0)), "w2": ((w, 0), (w, d)), "w3": ((w, d), (0, d)), "w4": ((0, d), (0, 0))}
    return [wall(k, a, b, measured.get(k)) for k, (a, b) in pts.items()]


def test_nothing_measured_gives_nothing():
    e = estimate(rect())
    assert e.lengths == {} and e.used == [] and e.scale == 1.0


def test_long_wall_sets_the_scale_for_other_walls():
    # 5 m 벽이 실제로는 5.05 m (1% 길다) → 4 m 벽도 거의 1% 늘어난다
    e = estimate(rect(w1=5.05))
    assert e.used == ["w1"]
    assert e.scale == pytest.approx(1.0097, abs=3e-4)
    assert e.lengths["w2"] == pytest.approx(4.0 * e.scale, abs=1e-3)
    assert "w1" not in e.lengths  # 잰 벽은 잰 값 그대로


def test_opposite_wall_takes_the_measured_length():
    e = estimate(rect(w1=5.05))
    assert e.lengths["w3"] == pytest.approx(5.05)


def test_short_wall_moves_the_scale_only_a_little():
    # 0.8 m 벽에서 1 cm 차이는 스캔 잡음일 수 있다: 10 m 벽을 12 cm나 늘리면 안 된다
    walls = [wall("a", (0, 0), (0.8, 0), measured=0.81), wall("b", (0.8, 0), (0.8, 10))]
    e = estimate(walls)
    assert 1.0 < e.scale < 1.007
    assert e.lengths["b"] < 10.07


def test_more_measured_walls_agreeing_pull_the_scale_closer():
    one = estimate(rect(w1=5.05))
    two = estimate(rect(w1=5.05, w2=4.04))
    assert one.scale < two.scale <= 1.01
    assert set(two.used) == {"w1", "w2"}


def test_far_off_measurement_fixes_only_that_wall():
    # 스캔 5 m인데 5.4 m로 쟀다: 스캔이 벽을 덜 잡은 것이지 배율 문제가 아니다
    e = estimate(rect(w1=5.4))
    assert e.used == [] and e.skipped == ["w1"]
    assert e.lengths == {} and e.scale == 1.0


def test_floorplan_and_old_estimates_are_not_measurements():
    walls = rect()
    walls[0].measured = MeasuredDims(length_m=5.05, by="floorplan")
    walls[1].measured = MeasuredDims(length_m=4.2, by="reference")
    e = estimate(walls)
    assert e.used == [] and e.lengths == {}


def test_floorplan_wall_keeps_its_plan_length():
    walls = rect(w1=5.05)
    walls[1].measured = MeasuredDims(length_m=4.0, by="floorplan")
    e = estimate(walls)
    assert "w2" not in e.lengths and "w4" in e.lengths


def test_unlike_wall_is_not_treated_as_opposite():
    # 길이가 같아도 직각으로 선 벽은 맞은편 벽이 아니다
    walls = [wall("a", (0, 0), (4, 0), measured=4.04), wall("b", (4, 0), (4, 4))]
    e = estimate(walls)
    assert e.lengths["b"] == pytest.approx(4.0 * e.scale, abs=1e-3)
    assert e.lengths["b"] < 4.04
