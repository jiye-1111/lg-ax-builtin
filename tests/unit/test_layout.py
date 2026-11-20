"""조합 자동 배치 (docs/specs/layout-rules.md) — 테스트 먼저.

규칙 근거: Merrell 외 2011 표 1(Panero & Repetto 인체치수) + LGE.COM 설치 가이드.
방: 4.6m x 3.6m, 아래 벽(w1) 왼쪽에 문.
"""
import math

from core.decor import decor_product
from core.models import Opening, Room, ScannedDims, Wall
from recommender.fit import FitConfig
from recommender.layout import BEDSIDE_M, COFFEE_GAP_M, Item, arrange
from recommender.pose import rect

CFG = FitConfig(margin_scanned_mm=30, margin_measured_mm=5)


def room(W=4.6, D=3.6, door=True):
    walls = [
        Wall(wall_id="w1", start=(0, 0), end=(W, 0), thickness_m=0.1, scanned=ScannedDims(length_m=W, height_m=2.4)),
        Wall(wall_id="w2", start=(W, 0), end=(W, D), thickness_m=0.1, scanned=ScannedDims(length_m=D, height_m=2.4)),
        Wall(wall_id="w3", start=(W, D), end=(0, D), thickness_m=0.1, scanned=ScannedDims(length_m=W, height_m=2.4)),
        Wall(wall_id="w4", start=(0, D), end=(0, 0), thickness_m=0.1, scanned=ScannedDims(length_m=D, height_m=2.4)),
    ]
    ops = [Opening(opening_id="d1", type="door", wall_id="w1", offset_m=0.2, width_m=0.9, height_m=2.0)] if door else []
    return Room(walls=walls, openings=ops)


def item(kind, role, size=None, key=None):
    return Item(key=key or kind, sku=f"decor:{kind}", product=decor_product(f"decor:{kind}", size), role=role)


def by_key(out):
    return {p.item.key: p for p in out}


def test_bed_is_anchor_against_a_wall_without_the_door_and_centred():
    out = by_key(arrange(room(), [item("bed", "anchor")], CFG))
    bed = out["bed"]
    assert bed.pose.wall_id != "w1"  # 문 있는 벽은 피한다
    # 정면이 방 안을 향한다
    cx, cz = bed.pose.center_xz
    fx, fz = math.cos(bed.pose.yaw_rad), math.sin(bed.pose.yaw_rad)
    assert (2.3 - cx) * fx + (1.8 - cz) * fz > 0


def test_nightstands_are_symmetric_on_both_sides_of_the_bed():
    ns = (0.45, 0.55, 0.4)
    out = by_key(arrange(room(), [item("bed", "anchor"), item("dresser", "pair", ns, "ns")], CFG))
    bed = out["bed"]
    pair = [p for p in arrange(room(), [item("bed", "anchor"), item("dresser", "pair", ns, "ns")], CFG) if p.item.key == "ns"]
    assert len(pair) == 2
    d = [math.dist(p.pose.center_xz, bed.pose.center_xz) for p in pair]
    assert abs(d[0] - d[1]) < 0.02
    for p in pair:
        assert abs(p.pose.yaw_rad - bed.pose.yaw_rad) < 1e-6


def test_bed_keeps_walking_space_beside_it():
    out = by_key(arrange(room(), [item("bed", "anchor")], CFG))
    bed = out["bed"]
    assert bed.free_side_m >= BEDSIDE_M - 1e-6


def test_coffee_table_sits_in_front_of_sofa_at_seat_gap():
    out = by_key(arrange(room(), [item("sofa", "anchor"), item("coffee", "front")], CFG))
    s, c = out["sofa"], out["coffee"]
    gap = math.dist(s.pose.center_xz, c.pose.center_xz) - s.size[2] / 2 - c.size[2] / 2
    assert abs(gap - COFFEE_GAP_M) < 0.02


def test_tv_stand_faces_the_sofa_from_the_opposite_wall():
    out = by_key(arrange(room(), [item("sofa", "anchor"), item("tvstand", "facing")], CFG))
    s, t = out["sofa"], out["tvstand"]
    assert abs(math.cos(s.pose.yaw_rad - t.pose.yaw_rad) + 1) < 0.05  # 서로 마주 본다


def test_rug_is_under_the_bed_front_and_flat_items_do_not_block():
    out = by_key(arrange(room(), [item("bed", "anchor"), item("rug", "rug")], CFG))
    assert "rug" in out
    r, b = out["rug"], out["bed"]
    assert math.dist(r.pose.center_xz, b.pose.center_xz) < b.size[2]


def test_nothing_overlaps_and_door_front_stays_clear():
    items = [item("bed", "anchor"), item("dresser", "pair", (0.45, 0.55, 0.4), "ns"), item("rug", "rug"),
             item("storage", "wall"), item("plant", "corner"), item("lamp", "corner")]
    out = arrange(room(), items, CFG)
    solid = [p for p in out if p.item.key != "rug"]
    from recommender.pose import overlaps
    polys = [rect(p.pose.center_xz, p.pose.yaw_rad - math.pi / 2, p.size[0], p.size[2]) for p in solid]
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            assert not overlaps(polys[i], polys[j]), (solid[i].item.key, solid[j].item.key)
    door_zone = rect((0.65, 0.5), 0.0, 0.9, 0.9)
    for p, poly in zip(solid, polys):
        assert not overlaps(poly, door_zone), p.item.key


def test_items_that_do_not_fit_are_left_out_not_forced():
    tiny = room(2.0, 2.0)
    out = arrange(tiny, [item("bed", "anchor"), item("sofa", "wall"), item("storage", "wall")], CFG)
    assert len(out) < 3
    assert all(p.verdict != "no_fit" for p in out)


def test_same_input_same_layout():
    items = [item("sofa", "anchor"), item("coffee", "front"), item("tvstand", "facing"), item("plant", "corner")]
    a = [(p.item.key, p.pose.center_xz) for p in arrange(room(), items, CFG)]
    b = [(p.item.key, p.pose.center_xz) for p in arrange(room(), items, CFG)]
    assert a == b


def test_study_chair_sits_in_front_of_the_desk_facing_it():
    out = by_key(arrange(room(), [item("desk", "anchor"), item("chair", "desk_chair")], CFG))
    assert "chair" in out
    d, c = out["desk"], out["chair"]
    assert abs(math.cos(d.pose.yaw_rad - c.pose.yaw_rad) + 1) < 1e-6
    assert math.dist(d.pose.center_xz, c.pose.center_xz) < d.size[2] / 2 + c.size[2] / 2 + 0.1
