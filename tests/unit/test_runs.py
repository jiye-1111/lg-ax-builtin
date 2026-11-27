"""벽면 맞춤가구 세트 배치 (recommender/runs.py)."""
import math

import pytest

from recommender.cabinet import normalize
from recommender.runs import align_counter, layout, preset_cfg, presets

WALL = {"wall_id": "w0", "start": (0.0, 0.0), "end": (4.0, 0.0), "thickness_m": 0.1, "inward_hint": (2.0, 1.5),
        "openings": [{"opening_id": "o1", "type": "window", "wall_id": "w0", "offset_m": 2.5, "width_m": 1.0,
                      "height_m": 1.2, "sill_m": 1.0}]}


def cfg(pid, **kw):
    c = preset_cfg(pid)
    c.update(kw)
    return normalize(c)


def run(base=(), wall=(), start=None):
    return {"start_mm": start or {"base": 0, "wall": 0},
            "rows": {"base": [{"id": i, "gap_mm": g} for i, g in base], "wall": [{"id": i, "gap_mm": g} for i, g in wall]}}


def test_every_preset_makes_a_valid_cabinet_and_says_where_it_came_from():
    data = presets()
    assert set(data["sources"]) >= {"ikea_metod", "ikea_besta", "housetwin"}
    for p in data["presets"]:
        c = normalize(preset_cfg(p["id"]))
        assert c["preset"] == p["id"]
        assert p["source"] in data["sources"]
    # 섬·TV월·코너는 HouseTwin 시작값 (제작 규격처럼 보이면 안 됨)
    by = data["by_id"]
    assert {by[i]["source"] for i in ("island", "tvwall", "corner", "sideboard", "bench")} == {"housetwin"}


def test_body_height_gets_legs_and_counter_added():
    c = cfg("base_door")
    assert c["outer_mm"] == {"w": 600, "h": 910, "d": 600}  # 몸체 800 + 다리 80 + 상판 30
    t = cfg("tall_pantry")
    assert t["outer_mm"]["h"] == 2280  # 몸체 2200 + 다리 80
    w = cfg("wall_door")
    assert w["outer_mm"] == {"w": 600, "h": 600, "d": 370} and w["base_mm"] == 1500


def test_starters_only_use_known_presets():
    data = presets()
    ids = {s["id"] for s in data["starters"]}
    assert ids == {"empty", "kitchen", "tvwall", "storage"}
    for s in data["starters"]:
        for tier in ("base", "wall"):
            for x in s["rows"][tier]:
                assert (x if isinstance(x, str) else x["preset"]) in data["by_id"]


def test_modules_stack_left_to_right_on_the_wall_face():
    cfgs = {"a": cfg("base_door"), "b": cfg("base_drawer3", outer_mm={"w": 800, "h": 910, "d": 600})}
    out = layout(WALL, run([("a", 0), ("b", 0)], start={"base": 100, "wall": 0}), cfgs)
    a, b = out["modules"]
    assert (a["s0"], a["s1"], b["s0"], b["s1"]) == (100, 700, 700, 1500)
    # 안쪽(+z)을 보고, 벽 면(두께 절반)에서 깊이 절반만큼 나온다
    assert a["yaw_rad"] == pytest.approx(math.pi / 2)
    assert a["center_xz"] == pytest.approx([0.4, 0.05 + 0.005 + 0.3])
    assert out["usage"]["base"]["used_mm"] == 1400 and out["usage"]["base"]["left_mm"] == 2600
    assert out["usage"]["wall"]["used_mm"] == 0


def test_elevation_left_is_the_viewers_left_even_if_the_wall_runs_backwards():
    w = {**WALL, "start": (4.0, 0.0), "end": (0.0, 0.0), "openings": []}
    out = layout(w, run([("a", 0)]), {"a": cfg("base_door")})
    assert out["flip"] is True
    assert out["modules"][0]["center_xz"][0] == pytest.approx(0.3)


def test_tall_cabinet_uses_both_bands_and_upper_row_cannot_overlap_it():
    cfgs = {"t": cfg("tall_pantry"), "u": cfg("wall_door")}
    out = layout(WALL, run([("t", 0)], [("u", 0)]), cfgs)
    assert out["usage"]["wall"]["used_mm"] == 600
    assert any(i["code"] == "overlap" and i["id"] == "u" for i in out["issues"])
    ok = layout(WALL, run([("t", 0)], [("u", 600)]), cfgs)
    assert not any(i["code"] == "overlap" for i in ok["issues"])
    assert ok["usage"]["wall"]["used_mm"] == 1200


def test_upper_over_base_is_fine_but_window_is_reported_not_shrunk():
    cfgs = {"a": cfg("base_door"), "u": cfg("wall_door")}
    out = layout(WALL, run([("a", 2400)], [("u", 2500)]), cfgs)
    codes = {(i["code"], i["id"]) for i in out["issues"]}
    assert ("overlap", "u") not in codes
    assert ("blocks_window", "u") in codes          # 상부장 1500~2100이 창 1000~2200과 겹침
    assert ("blocks_window", "a") not in codes      # 하부장 0~910은 창틀 1000 아래
    assert out["modules"][1]["s1"] - out["modules"][1]["s0"] == 600  # 크기는 그대로


def test_running_past_the_wall_end_is_reported():
    cfgs = {"a": cfg("base_door")}
    out = layout(WALL, run([("a", 3700)]), cfgs)
    i = next(i for i in out["issues"] if i["code"] == "past_wall")
    assert "300 mm" in i["label"] and i["level"] == "no"


def test_neighbour_lines_are_reported_and_aligned_only_on_request():
    a = cfg("base_door")
    b = cfg("base_door", parts={"toe_kick": 120})
    b["outer_mm"]["h"] = 950
    b = normalize(b)
    out = layout(WALL, run([("a", 0), ("b", 0)]), {"a": a, "b": b})
    assert any(i["code"] == "counter_line" for i in out["issues"])
    fixed, notes = align_counter([a, b])
    assert fixed[1]["outer_mm"]["h"] == 910 and fixed[1]["parts"]["toe_kick"] == 80
    assert a["outer_mm"]["h"] == 910 and b["outer_mm"]["h"] == 950  # 원본은 그대로
    assert notes


def test_align_leaves_appliance_bays_alone():
    dw = normalize({"kind": "dishwasher", "outer_mm": {"w": 600, "h": 850, "d": 600}})
    a, b = cfg("base_door"), cfg("base_drawer3")
    fixed, notes = align_counter([a, dw, b])
    assert fixed[1] is dw and any("가전 공간" in n for n in notes)


def test_gap_to_wall_suggests_filler_and_exposed_side_suggests_end_panel():
    out = layout(WALL, run([("a", 40)]), {"a": cfg("base_door")})
    codes = {i["code"] for i in out["issues"]}
    assert "filler" in codes and "end_panel" in codes


def test_bench_under_window_asks_to_check_the_window_swing():
    out = layout(WALL, run([("b", 2400)]), {"b": cfg("bench")})
    assert any(i["code"] == "window_swing" for i in out["issues"])
    assert not any(i["code"].startswith("blocks_") for i in out["issues"])


def test_corner_must_sit_at_the_row_end():
    cfgs = {"c": cfg("corner"), "a": cfg("base_door")}
    bad = layout(WALL, run([("c", 0), ("a", 0)]), cfgs)
    assert any(i["code"] == "corner_end" for i in bad["issues"])
    good = layout(WALL, run([("a", 0), ("c", 0)]), cfgs)
    assert not any(i["code"] == "corner_end" for i in good["issues"])


def test_length_starts_at_the_inner_corner_of_joined_walls():
    w = {**WALL, "inset_start_m": 0.05, "inset_end_m": 0.05}
    out = layout(w, run([("a", 0)]), {"a": cfg("base_door")})
    assert out["length_mm"] == 3900
    assert out["modules"][0]["center_xz"][0] == pytest.approx(0.35)  # 옆 벽 면에서 시작
    assert out["openings"][0]["s0"] == 2450
