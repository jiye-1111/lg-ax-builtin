"""와이파이 다중 벽 경로손실 (S7).
식: RSSI = Ptx - PL(d0=1m) - 10·n·log10(d) - Σ 벽 감쇠. 상수는 WifiConfig."""
import math

import pytest

from core.models import Opening, Room, ScannedDims, Wall
from sim.wifi import WifiConfig, best_router_spot, coverage, rssi_at

CFG = WifiConfig(band="5", tx_dbm=20, pl0_db=46.4, n=2.0, wall_db=12, grade_good=-60, grade_ok=-70)


def room(partition=False, door=False):
    walls = [
        Wall(wall_id="w1", start=(0, 0), end=(8, 0), thickness_m=0.1, scanned=ScannedDims(length_m=8, height_m=2.4)),
        Wall(wall_id="w2", start=(8, 0), end=(8, 4), thickness_m=0.1, scanned=ScannedDims(length_m=4, height_m=2.4)),
        Wall(wall_id="w3", start=(8, 4), end=(0, 4), thickness_m=0.1, scanned=ScannedDims(length_m=8, height_m=2.4)),
        Wall(wall_id="w4", start=(0, 4), end=(0, 0), thickness_m=0.1, scanned=ScannedDims(length_m=4, height_m=2.4)),
    ]
    ops = []
    if partition:  # x=4 칸막이 벽
        walls.append(Wall(wall_id="w5", start=(4, 0), end=(4, 4), thickness_m=0.1, scanned=ScannedDims(length_m=4, height_m=2.4)))
        if door:
            ops.append(Opening(opening_id="d1", type="door", wall_id="w5", offset_m=1.5, width_m=1.0, height_m=2.1))
    return Room(walls=walls, openings=ops)


def test_free_space_formula():
    r = rssi_at(room(), (1, 2), (3, 2), CFG)
    assert r == pytest.approx(20 - 46.4 - 20 * math.log10(2), abs=1e-6)


def test_each_wall_adds_loss():
    open_ = rssi_at(room(), (1, 2), (7, 2), CFG)
    walled = rssi_at(room(partition=True), (1, 2), (7, 2), CFG)
    assert open_ - walled == pytest.approx(12, abs=1e-6)


def test_open_door_is_not_a_wall():
    assert rssi_at(room(partition=True, door=True), (1, 2), (7, 2), CFG) == pytest.approx(rssi_at(room(), (1, 2), (7, 2), CFG))


def test_symmetry_and_near_field_clamp():
    a = rssi_at(room(partition=True), (1, 1), (6, 3), CFG)
    b = rssi_at(room(partition=True), (6, 3), (1, 1), CFG)
    assert a == pytest.approx(b)
    assert rssi_at(room(), (2, 2), (2, 2), CFG) == pytest.approx(20 - 46.4)  # 1 m 안은 1 m로 본다


def test_coverage_grid_and_grades():
    g = coverage(room(partition=True), (1, 2), CFG, cell_m=0.5)
    vals = [v for row in g["values"] for v in row if v is not None]
    assert max(vals) > min(vals) + 12
    assert set(g["share"]) == {"good", "ok", "weak"} and abs(sum(g["share"].values()) - 1) < 1e-6
    assert g["assumptions"]


def test_best_spot_beats_corner():
    r = room(partition=True)
    spot, worst = best_router_spot(r, CFG, cell_m=0.5)
    corner_worst = min(v for row in coverage(r, (0.3, 0.3), CFG, cell_m=0.5)["values"] for v in row if v is not None)
    assert worst > corner_worst
    assert 2 < spot[0] < 6  # 칸막이 근처 가운데 쪽이 유리
