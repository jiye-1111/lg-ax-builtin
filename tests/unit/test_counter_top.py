"""인덕션은 상판에 넣는 제품이라 하부장·아일랜드 위에만 놓는다 (docs/specs/fit-rules.md '상판에 넣는 제품')."""
import math

from core.models import Clearance, Dims, Product
from recommender.fit import FitConfig, Verdict
from recommender.pose import Pose, can_sit, check_pose, needs_counter

from .test_pose import fridge, room

UP = math.pi / 2
CFG = FitConfig(margin_scanned_mm=30, margin_measured_mm=5)
codes = lambda r: {x["code"] for x in r.reasons}  # noqa: E731
TOP = {"id": "pl1", "center_xz": (2.0, 1.5), "yaw_rad": 0.0, "w": 1.8, "d": 0.9, "top_m": 0.9}
ISLAND = {"placement_id": "pl1", "sku": "decor:island", "center_xz": [2.0, 1.5], "yaw_rad": UP, "size_m": [1.8, 0.9, 0.9]}


def cooktop():
    return Product(sku="T-C", name="인덕션", category="cooktop", zone_fit=["kitchen"], install_type="built_in",
                   product_dims_mm=Dims(w=580, h=59, d=520), clearance_mm=Clearance(side=0, top=0, back=0),
                   door_swing_mm=0, source_url=None, source_checked_at=None, demo_only=True)


def test_cooktop_needs_a_counter_and_other_products_do_not():
    assert needs_counter(cooktop()) and can_sit(cooktop())
    assert not needs_counter(fridge())


def test_cooktop_on_the_floor_does_not_fit():
    r = check_pose(room(), cooktop(), Pose((2.0, 1.5), UP), CFG)
    assert r.verdict == Verdict.NO_FIT
    assert "needs_counter" in codes(r)
    assert next(x for x in r.reasons if x["code"] == "needs_counter")["label"] == "하부장이나 아일랜드 위에 놓아야 해요"


def test_cooktop_on_an_island_fits_at_its_top():
    r = check_pose(room(), cooktop(), Pose((2.0, 1.5), UP), CFG, others=[ISLAND], host=TOP)
    assert r.verdict != Verdict.NO_FIT
    assert "needs_counter" not in codes(r)
    assert r.base_m == 0.9 and r.on == "pl1"
