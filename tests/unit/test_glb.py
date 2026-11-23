import json, struct

from core.models import Room
from worker.glb import room_to_glb

ROOM = Room.model_validate_json(open("data/samples/synthetic_room.room.json").read())


def _read(p):
    b = p.read_bytes()
    magic, ver, total = struct.unpack("<4sII", b[:12])
    n, kind = struct.unpack("<I4s", b[12:20])
    return magic, ver, total, len(b), json.loads(b[20:20 + n])


def test_glb_is_valid_container(tmp_path):
    magic, ver, total, size, js = _read(room_to_glb(ROOM, tmp_path / "s.glb"))
    assert (magic, ver, total) == (b"glTF", 2, size)
    names = {n["name"] for n in js["nodes"]}
    assert {"floor", "w1", "w2", "w3", "w4", "d1", "win1", "o1"} <= names


def test_state_materials_and_placements(tmp_path):
    st = {"materials": {"wall": "#112233"},
          "placements": [{"sku": "S1", "center_xz": [1, 0.3], "yaw_rad": 1.5708, "size_m": [0.6, 0.85, 0.6], "hex": "#C8A27A"}]}
    *_, js = _read(room_to_glb(ROOM, tmp_path / "s.glb", st))
    assert "product:S1" in {n["name"] for n in js["nodes"]}
    assert "#112233" in {m["name"] for m in js["materials"]}


def test_scanned_objects_carry_category_for_web_models(tmp_path):
    *_, js = _read(room_to_glb(ROOM, tmp_path / "s.glb"))
    o1 = next(n for n in js["nodes"] if n["name"] == "o1")
    assert o1["extras"] == {"kind": "object", "category": ROOM.objects[0].category}
    wall = next(n for n in js["nodes"] if n["name"] == "w1")
    assert "category" not in wall["extras"]


def test_floor_follows_the_outer_walls_when_the_home_is_not_a_rectangle(tmp_path):
    from worker.plan_room import PlanRead, PlanWall, room_from_plan

    pts = [(0, 0), (8000, 0), (8000, 4000), (5000, 4000), (5000, 7000), (0, 7000)]
    plan = PlanRead(readable=True, scale_from="dimensions",
                    walls=[PlanWall(x1=a[0], y1=a[1], x2=b[0], y2=b[1]) for a, b in zip(pts, pts[1:] + pts[:1])])
    *_, js = _read(room_to_glb(room_from_plan(plan), tmp_path / "l.glb"))
    floor = next(n for n in js["nodes"] if n["name"] == "floor")
    assert floor["scale"][0] == 8 and floor["scale"][2] == 7  # 상자는 그대로 (웹이 천장·카메라에 쓴다)
    assert len(floor["extras"]["outline"]) == 6 and [5, 4] in floor["extras"]["outline"]


def test_rectangular_home_has_no_outline_extra(tmp_path):
    *_, js = _read(room_to_glb(ROOM, tmp_path / "s.glb"))
    assert next(n for n in js["nodes"] if n["name"] == "floor")["extras"] == {"kind": "floor"}
