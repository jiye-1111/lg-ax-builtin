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
