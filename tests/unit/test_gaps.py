"""옆·뒤·위 남는 틈 재기와 빈틈에 맞춰 폭 늘리기 — 테스트 먼저.

좌표: 4m x 3m 방, 벽 두께 0.1 (안쪽 면은 중심선에서 0.05).
yaw = 정면 방향. UP(π/2)이면 정면이 +y, 등이 아래 벽 w1. 이때 폭 축은 +x라 왼쪽 = -x, 오른쪽 = +x.
"""
import math

import pytest

from core.models import Clearance, Dims, Product, Room, ScannedDims, Wall
from recommender.fit import FitConfig
from recommender.gaps import fill_width, measure
from recommender.pose import Pose

UP = math.pi / 2
CFG = FitConfig(margin_scanned_mm=30, margin_measured_mm=5)


def room(h=2.4):
    pts = [((0, 0), (4, 0)), ((4, 0), (4, 3)), ((4, 3), (0, 3)), ((0, 3), (0, 0))]
    return Room(walls=[Wall(wall_id=f"w{i + 1}", start=a, end=b, thickness_m=0.1,
                            scanned=ScannedDims(length_m=math.dist(a, b), height_m=h)) for i, (a, b) in enumerate(pts)],
                openings=[], objects=[])


def item(w=600, h=1860, d=700, side=4, top=15, back=None, sku="T-FM", install="built_in_look"):
    return Product(sku=sku, name="테스트", category="refrigerator", zone_fit=["kitchen"], install_type=install,
                   product_dims_mm=Dims(w=w, h=h, d=d), clearance_mm=Clearance(side=side, top=top, back=back),
                   source_url=None, source_checked_at=None, demo_only=True)


def cab(center, w=0.6, h=2.2, d=0.6, yaw=UP, pid="pl_cab", **extra):
    return {"placement_id": pid, "sku": "decor:tallcab", "center_xz": list(center), "yaw_rad": yaw, "size_m": [w, h, d], **extra}


def test_side_gaps_to_walls_in_mm():
    # 폭 0.6, 가운데 x=1.0 → 왼쪽 면 0.7, 왼쪽 벽 안쪽 면 0.05 → 650 mm. 오른쪽 면 1.3 → 벽 3.95까지 2650 mm
    g = measure(room(), item(), Pose((1.0, 0.45), UP), CFG)
    assert g["left"]["mm"] == pytest.approx(650, abs=0.5) and g["left"]["ref"] == "w4" and g["left"]["kind"] == "wall"
    assert g["right"]["mm"] == pytest.approx(2650, abs=0.5) and g["right"]["ref"] == "w2"


def test_back_and_top_gap():
    # 깊이 0.7, 가운데 y=0.45 → 등 0.10, 벽 안쪽 면 0.05 → 50 mm. 천장 2400 - 1860 = 540 mm
    g = measure(room(), item(), Pose((1.0, 0.45), UP), CFG)
    assert g["back"]["mm"] == pytest.approx(50, abs=0.5) and g["back"]["ref"] == "w1"
    assert g["top"]["mm"] == pytest.approx(540, abs=0.5)


def test_neighbor_cabinet_is_nearer_than_wall():
    # 오른쪽에 키큰장: 왼쪽 면 x=1.31 → 냉장고 오른쪽 면 1.3에서 10 mm
    g = measure(room(), item(), Pose((1.0, 0.45), UP), CFG, others=[cab((1.61, 0.4))])
    assert g["right"]["mm"] == pytest.approx(10, abs=0.5)
    assert g["right"]["ref"] == "pl_cab" and g["right"]["kind"] == "placement"


def test_need_comes_from_product_clearance():
    g = measure(room(), item(side=4, top=15), Pose((1.0, 0.45), UP), CFG, others=[cab((1.61, 0.4))])
    assert g["right"]["need_mm"] == 4 and g["right"]["ok"] is True
    assert g["top"]["need_mm"] == 15 and g["top"]["ok"] is True
    assert g["back"]["need_mm"] is None and g["back"]["ok"] is None  # LGE.COM에 값이 없으면 판단하지 않는다


def test_gap_smaller_than_need_is_not_ok():
    g = measure(room(), item(side=4), Pose((1.0, 0.45), UP), CFG, others=[cab((1.602, 0.4))])  # 틈 2 mm
    assert g["right"]["mm"] == pytest.approx(2, abs=0.5) and g["right"]["ok"] is False


def test_cabinet_next_to_appliance_inherits_neighbor_need():
    # 장을 고르면: 옆 가전이 요구하는 옆 여유(4 mm)가 그 틈의 기준이 된다
    fridge = {"placement_id": "pl_rf", "sku": "T-FM", "center_xz": [1.0, 0.45], "yaw_rad": UP, "size_m": [0.6, 1.86, 0.7], "side_mm": 4}
    c = item(w=600, h=2200, d=600, side=0, top=0, back=0, sku="decor:tallcab", install="freestanding")
    g = measure(room(), c, Pose((1.602, 0.4), UP), CFG, others=[fridge])
    assert g["left"]["ref"] == "pl_rf" and g["left"]["need_mm"] == 4 and g["left"]["ok"] is False


def test_things_not_beside_are_ignored():
    # 앞쪽 멀리 있는 가구는 옆 틈이 아니다
    g = measure(room(), item(), Pose((1.0, 0.45), UP), CFG, others=[cab((2.0, 2.0))])
    assert g["right"]["ref"] == "w2"


def test_lower_things_do_not_count_for_item_on_top():
    g = measure(room(), item(h=300, d=300, w=300), Pose((1.0, 0.45), UP), CFG, others=[cab((1.5, 0.45), h=0.85)], base=0.9)
    assert g["right"]["ref"] == "w2"


def test_rotated_item_uses_its_own_axes():
    # 정면이 +x (yaw 0) → 등이 왼쪽 벽 w4. 폭 축은 -y라 '왼쪽'은 위쪽 벽 w3
    g = measure(room(), item(), Pose((0.45, 1.5), 0.0), CFG)
    assert g["back"]["ref"] == "w4" and g["back"]["mm"] == pytest.approx(50, abs=0.5)
    assert {g["left"]["ref"], g["right"]["ref"]} == {"w1", "w3"}


def test_gap_has_line_endpoints_for_drawing():
    g = measure(room(), item(), Pose((1.0, 0.45), UP), CFG)
    a, b = g["left"]["line"]
    assert a == pytest.approx([0.7, 0.45], abs=1e-3) and b == pytest.approx([0.05, 0.45], abs=1e-3)


def test_fill_width_between_fridge_and_wall():
    # 냉장고(오른쪽 면 1.3, 옆 4 mm 필요)와 오른쪽 벽(3.95) 사이에 놓인 장 → 1.304 ~ 3.95를 꽉 채운다
    fridge = {"placement_id": "pl_rf", "sku": "T-FM", "center_xz": [1.0, 0.45], "yaw_rad": UP, "size_m": [0.6, 1.86, 0.7], "side_mm": 4}
    c = item(w=600, h=2200, d=600, side=0, top=0, back=0, sku="decor:tallcab", install="freestanding")
    out = fill_width(room(), c, Pose((2.5, 0.4), UP), CFG, others=[fridge])
    assert out is not None
    center, w = out
    assert w == pytest.approx(3.95 - 1.304, abs=1e-3)
    assert center[0] == pytest.approx((3.95 + 1.304) / 2, abs=1e-3) and center[1] == pytest.approx(0.4)


def test_fill_width_refuses_when_overlapping():
    fridge = {"placement_id": "pl_rf", "sku": "T-FM", "center_xz": [1.0, 0.45], "yaw_rad": UP, "size_m": [0.6, 1.86, 0.7], "side_mm": 4}
    c = item(w=600, h=2200, d=600, side=0, top=0, back=0, sku="decor:tallcab", install="freestanding")
    assert fill_width(room(), c, Pose((1.2, 0.4), UP), CFG, others=[fridge]) is None
