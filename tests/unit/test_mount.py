"""설치 방식대로 붙이기 (docs/specs/fit-rules.md '벽에 걸거나 붙여 설치하는 제품') — 테스트 먼저.

4 x 3 m 방, 벽 두께 0.1 (안쪽 면 0.05), 천장 2.4. yaw = 제품 정면 방향. UP이면 등이 벽 w1(y=0) 쪽.
"""
import math

from core.models import Clearance, Dims, Product
from recommender.fit import FitConfig, Verdict
from recommender.mount import BUILTIN, FLUSH, WALL, default_base, hang, mount_kind
from recommender.pose import Pose, can_sit, check_pose, find_spot

from .test_pose import fridge, room

UP = math.pi / 2
CFG = FitConfig(margin_scanned_mm=30, margin_measured_mm=5)
codes = lambda r: {x["code"] for x in r.reasons}  # noqa: E731
label = lambda r, code: next(x["label"] for x in r.reasons if x["code"] == code)  # noqa: E731


def item(name, category, install_type="freestanding", w=1000, h=600, d=50, options=None, **clear):
    return Product(sku="T-" + category, name=name, category=category, zone_fit=["living"], install_type=install_type,
                   product_dims_mm=Dims(w=w, h=h, d=d), clearance_mm=Clearance(**clear), options=options or {},
                   source_url=None, source_checked_at=None, demo_only=True)


def wall_tv():
    return item("LG 올레드 evo AI 65형 (벽걸이형)", "tv", w=1441, h=826, d=45)


def wall_ac():
    return item("LG 휘센 사계절에어컨 (벽걸이)", "air_conditioner", w=998, h=330, d=210, options={"kind": "벽걸이형"})


def wallfit():
    return item("LG 퓨리케어 AI 오브제컬렉션 월핏 (스탠드)", "air_purifier", w=560, h=540, d=180)


def dishwasher():
    return item("식기세척기", "dishwasher", "built_in", w=598, h=815, d=570, side=0, top=0, back=0)


FACES = [((0.0, 0.0), (4.0, 0.0), 0.1, "w1"), ((4.0, 0.0), (4.0, 3.0), 0.1, "w2"),
         ((4.0, 3.0), (0.0, 3.0), 0.1, "w3"), ((0.0, 3.0), (0.0, 0.0), 0.1, "w4")]


# ---------- 어떤 제품이 어디에 붙나 ----------
def test_kinds_follow_the_catalog_wording():
    assert mount_kind(wall_tv()) == WALL
    assert mount_kind(wall_ac()) == WALL
    assert mount_kind(item("LG 올레드 evo AI (스탠드형)", "tv")) is None
    assert mount_kind(item("LG 휘센 뷰I 에어컨 2in1 (스탠드)", "air_conditioner", options={"kind": "2in1"})) is None
    assert mount_kind(wallfit()) == FLUSH
    assert mount_kind(item("냉장고 Fit & Max", "refrigerator", "built_in_look")) == FLUSH
    assert mount_kind(dishwasher()) == BUILTIN
    assert mount_kind(fridge()) == BUILTIN


def test_counter_and_undersink_products_keep_their_own_rule():
    assert mount_kind(item("인덕션", "cooktop", "built_in")) is None
    assert mount_kind(item("정수기 (빌트인)", "water_purifier", "built_in")) is None


def test_wall_tv_does_not_sit_on_furniture():
    assert not can_sit(wall_tv())
    assert can_sit(item("LG 올레드 evo AI (스탠드형)", "tv"))


# ---------- 벽걸이: 벽에 걸기 ----------
def test_hang_puts_the_back_on_the_nearest_wall_face():
    p = hang(FACES, Pose((2.0, 1.2), 0.3), 1.441, 0.045)
    assert p.wall_id == "w1"
    assert math.isclose(p.center_xz[0], 2.0, abs_tol=1e-6)
    assert math.isclose(p.center_xz[1], 0.05 + 0.0225, abs_tol=1e-3)
    assert math.isclose(p.yaw_rad, UP, abs_tol=1e-6)


def test_hang_keeps_the_item_inside_the_wall_ends():
    p = hang(FACES, Pose((0.3, 0.2), UP), 1.441, 0.045)
    assert p.wall_id == "w1"
    assert p.center_xz[0] >= 0.05 + 1.441 / 2 - 1e-6


def test_hang_skips_walls_shorter_than_the_item():
    stub = ((1.8, 0.9), (2.2, 0.9), 0.1, "stub")  # 기둥 옆 40 cm 벽이 더 가깝다
    assert hang([*FACES, stub], Pose((2.0, 1.0), UP), 1.441, 0.045).wall_id == "w1"
    assert hang([stub], Pose((2.0, 1.0), UP), 1.441, 0.045).wall_id == "stub"


def test_hang_slides_off_a_wall_that_pokes_in_near_the_corner():
    # 스캔 벽은 모서리가 딱 안 맞는다: w1 끝 0.5 m 앞에서 방 안으로 튀어나온 벽
    poke = ((3.4, 0.0), (3.4, 0.5), 0.1, "poke")
    p = hang([*FACES, poke], Pose((3.0, 0.3), UP), 1.441, 0.045)
    assert p.wall_id == "w1"
    assert p.center_xz[0] + 1.441 / 2 <= 3.35 + 1e-6


def test_default_height():
    # TV는 앉은 눈높이에 화면 가운데, 에어컨은 천장 아래
    assert math.isclose(default_base(wall_tv(), 2.4), 1.1 - 0.413, abs_tol=1e-6)
    assert math.isclose(default_base(wall_ac(), 2.4), 2.4 - 0.15 - 0.33, abs_tol=1e-6)


def test_wall_tv_on_the_wall_fits_at_its_height():
    r = check_pose(room(), wall_tv(), Pose((2.0, 0.05 + 0.0225), UP, "w1"), CFG)
    assert r.verdict != Verdict.NO_FIT
    assert "needs_wall" not in codes(r) and "tight" not in codes(r)
    assert math.isclose(r.base_m, 1.1 - 0.413, abs_tol=1e-3)


def test_wall_tv_height_can_be_chosen_and_stays_under_the_ceiling():
    r = check_pose(room(), wall_tv(), Pose((2.0, 0.0725), UP, "w1"), CFG, base_m=1.3)
    assert math.isclose(r.base_m, 1.3, abs_tol=1e-6)
    r = check_pose(room(), wall_tv(), Pose((2.0, 0.0725), UP, "w1"), CFG, base_m=5.0)
    assert math.isclose(r.base_m, 2.4 - 0.826, abs_tol=1e-6)
    r = check_pose(room(), wall_tv(), Pose((2.0, 0.0725), UP, "w1"), CFG, base_m=-1.0)
    assert r.base_m == 0.0


def test_wall_tv_in_the_middle_of_the_room_does_not_fit():
    r = check_pose(room(), wall_tv(), Pose((2.0, 1.5), UP), CFG)
    assert r.verdict == Verdict.NO_FIT
    assert label(r, "needs_wall") == "벽에 걸어야 해요"


def test_wall_tv_hangs_above_low_furniture():
    stand = {"placement_id": "pl1", "sku": "decor:tvstand", "center_xz": [2.0, 0.25], "yaw_rad": UP, "size_m": [1.6, 0.45, 0.4]}
    r = check_pose(room(), wall_tv(), Pose((2.0, 0.0725), UP, "w1"), CFG, others=[stand])
    assert r.verdict != Verdict.NO_FIT and "overlaps_placement" not in codes(r)


def test_wall_tv_can_hang_on_an_added_wall():
    part = {"placement_id": "pl9", "sku": "decor:wall", "center_xz": [2.0, 1.5], "yaw_rad": UP, "size_m": [2.0, 2.4, 0.1]}
    r = check_pose(room(), wall_tv(), Pose((2.0, 1.55 + 0.0225), UP, "pl9"), CFG, others=[part])
    assert r.verdict != Verdict.NO_FIT and "needs_wall" not in codes(r)


def test_find_spot_hangs_wall_products():
    r = find_spot(room(), wall_ac(), CFG)
    assert r is not None and r.verdict != Verdict.NO_FIT
    assert r.base_m > 1.5 and "needs_wall" not in codes(r)


# ---------- 월핏·Fit & Max: 뒷면을 벽에 ----------
def test_wallfit_away_from_the_wall_does_not_fit():
    r = check_pose(room(), wallfit(), Pose((2.0, 1.5), UP), CFG)
    assert r.verdict == Verdict.NO_FIT
    assert label(r, "needs_wall") == "뒷면을 벽에 붙여야 해요"


def test_wallfit_against_the_wall_fits():
    r = check_pose(room(), wallfit(), Pose((2.0, 0.05 + 0.03 + 0.09), UP, "w1"), CFG)
    assert r.verdict != Verdict.NO_FIT and "needs_wall" not in codes(r)


def test_wallfit_facing_away_from_the_wall_does_not_count():
    r = check_pose(room(), wallfit(), Pose((2.0, 0.05 + 0.03 + 0.09), -UP), CFG)  # 정면이 벽을 본다
    assert "needs_wall" in codes(r)


# ---------- 빌트인: 벽이나 장에 ----------
def test_builtin_alone_in_the_room_does_not_fit():
    r = check_pose(room(), dishwasher(), Pose((2.0, 1.5), UP), CFG)
    assert r.verdict == Verdict.NO_FIT
    assert label(r, "needs_wall") == "벽이나 장에 붙여야 해요"


def test_builtin_against_the_wall_fits():
    r = check_pose(room(), dishwasher(), Pose((2.0, 0.05 + 0.03 + 0.285), UP, "w1"), CFG)
    assert "needs_wall" not in codes(r)


def test_builtin_next_to_a_cabinet_counts_even_off_the_wall():
    # 방 가운데 아일랜드 옆에 나란히
    island = {"placement_id": "pl1", "sku": "decor:island", "center_xz": [2.0, 1.5], "yaw_rad": UP, "size_m": [1.2, 0.9, 0.6]}
    r = check_pose(room(), dishwasher(), Pose((2.0 + 0.6 + 0.299, 1.5), UP), CFG, others=[island])
    assert "needs_wall" not in codes(r)


def test_builtin_next_to_a_sofa_does_not_count():
    sofa = {"placement_id": "pl1", "sku": "decor:sofa", "center_xz": [2.0, 1.5], "yaw_rad": UP, "size_m": [1.2, 0.9, 0.6]}
    r = check_pose(room(), dishwasher(), Pose((2.0 + 0.6 + 0.299, 1.5), UP), CFG, others=[sofa])
    assert "needs_wall" in codes(r)


def test_freestanding_products_are_free():
    free = item("세탁기", "washer", w=600, h=850, d=600, side=0, top=0, back=0)
    assert mount_kind(free) is None
    assert "needs_wall" not in codes(check_pose(room(), free, Pose((2.0, 1.5), UP), CFG))
