"""실제 UGScan RoomPlan 내보내기 (2026-11-18 팀 스캔). 구조 분석: docs/specs/usdz-analysis-2026-11-18.md

실제 구조: /RoomPlan/Mesh_grp/Arch_grp/Wall_N_grp(Xform) 안에 WallN·WindowN·DoorN 메시가 함께 들어 있다.
→ `_grp`는 컨테이너로 보고 안쪽 메시를 요소로 잡아야 문·창을 잃지 않는다.
"""
from collections import Counter

import pytest

from core import config
from worker.converter import convert_usdz

SAMPLE = config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"


@pytest.fixture(scope="module")
def room():
    return convert_usdz(SAMPLE)


def test_counts_match_prim_tree(room):
    assert len(room.walls) == 8
    assert Counter(o.type for o in room.openings) == {"window": 4, "door": 1}
    assert Counter(o.category for o in room.objects) == {"chair": 18, "table": 10, "storage": 1}


def test_section_labels_are_not_objects(room):
    assert all(o.category != "unidentified" for o in room.objects)


def test_openings_attach_to_their_parent_wall(room):
    # Door0는 Wall_7_grp 안에 있다 → 그 벽 길이 안에 들어가야 한다
    door = next(o for o in room.openings if o.type == "door")
    w = room.wall(door.wall_id)
    assert door.offset_m + door.width_m <= w.scanned.length_m + 0.05
    assert 0.6 < door.width_m < 1.5 and 1.8 < door.height_m < 2.4
    for win in (o for o in room.openings if o.type == "window"):
        assert win.sill_m > 0.1  # 창은 바닥에서 떠 있다


def test_wall_heights_are_plausible(room):
    assert all(2.0 < w.scanned.height_m < 3.2 for w in room.walls)
    assert all(0.05 < (w.thickness_m or 0) < 0.3 for w in room.walls)
