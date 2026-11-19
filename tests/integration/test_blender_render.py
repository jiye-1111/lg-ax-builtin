"""실제 Blender로 렌더 이미지를 만든다. Blender가 없는 PC에서는 건너뛴다."""
import json
import os
import shutil
import struct

import pytest

from core.models import Room
from worker import runner
from worker.glb import room_to_glb

EXE = os.getenv("BLENDER_BIN") or shutil.which("blender")
if not EXE:
    for v in ("5.2", "5.1", "5.0", "4.5", "4.4", "4.2"):
        p = rf"C:\Program Files\Blender Foundation\Blender {v}\blender.exe"
        if os.path.exists(p):
            EXE = p
            break

pytestmark = pytest.mark.skipif(not EXE or not os.path.exists(EXE), reason="Blender 없음")

ROOM = Room.model_validate_json(open("data/samples/synthetic_room.room.json").read())


def _names(p):
    b = p.read_bytes()
    n = struct.unpack_from("<I", b, 12)[0]
    return [(x["name"], x.get("extras")) for x in json.loads(b[20:20 + n])["nodes"]]


def test_blender_renders_room_and_keeps_web_glb(monkeypatch, tmp_path):
    monkeypatch.setenv("BLENDER_BIN", EXE)
    monkeypatch.setenv("USE_BLENDER", "1")
    usdz = tmp_path / "room.usdz"
    usdz.write_bytes(b"")  # 렌더는 상자 목록만 쓴다
    state = {"materials": {"floor": "#C8A27A"}, "placements": []}
    res = runner.build_scene(ROOM, usdz, state, tmp_path / "scene", render=True)
    log = tmp_path / "scene" / "blender.log"
    assert res["engine"] == "blender", log.read_text(encoding="utf-8")[-2000:] if log.exists() else ""
    png = res["png"].read_bytes()
    assert png[:4] == b"\x89PNG"
    w, h = struct.unpack(">II", png[16:24])
    assert (w, h) == (1600, 900)
    assert (tmp_path / "scene" / "scene.blend").exists()
    assert _names(res["glb"]) == _names(room_to_glb(ROOM, tmp_path / "ref.glb", state))
