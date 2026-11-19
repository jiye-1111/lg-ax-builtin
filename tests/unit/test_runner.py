"""씬 빌드 실행기: Blender가 있어도 웹 3D 파일 규칙(노드 이름·extras)은 폴백과 같아야 한다."""
import json
import struct
import subprocess

import pytest

from core.models import Room
from worker import runner
from worker.glb import room_to_glb

ROOM = Room.model_validate_json(open("data/samples/synthetic_room.room.json").read())
STATE = {"materials": {"wall": "#112233"},
         "placements": [{"sku": "S1", "center_xz": [1, 0.3], "yaw_rad": 1.5708, "size_m": [0.6, 0.85, 0.6],
                         "hex": "#C8A27A"}]}


def _nodes(p):
    b = p.read_bytes()
    n = struct.unpack_from("<I", b, 12)[0]
    js = json.loads(b[20:20 + n])
    return [(x["name"], x.get("extras")) for x in js["nodes"]]


@pytest.fixture
def fake_blender(monkeypatch, tmp_path):
    """Blender를 흉내 낸다: job을 기록하고, 렌더 PNG와 (예전 방식이면) 엉뚱한 glb를 쓴다."""
    calls = []
    usdz = tmp_path / "room.usdz"
    usdz.write_bytes(b"usdz")

    def run(cmd, **kw):
        job = json.loads(open(cmd[cmd.index("--job") + 1], encoding="utf-8").read())
        calls.append(job)
        if job.get("out_png"):
            open(job["out_png"], "wb").write(b"\x89PNG fake")
        if job.get("out_glb"):  # Blender가 USD를 그대로 내보낸 glb: 웹 규칙이 없다
            open(job["out_glb"], "wb").write(b"not the web glb")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(runner, "blender_bin", lambda: "blender.exe")
    monkeypatch.setattr(runner.subprocess, "run", run)
    monkeypatch.setenv("USE_BLENDER", "1")
    return calls, usdz


def test_blender_render_keeps_web_glb_contract(fake_blender, tmp_path):
    calls, usdz = fake_blender
    res = runner.build_scene(ROOM, usdz, STATE, tmp_path / "scene", render=True)
    assert res["engine"] == "blender"
    assert res["png"] and res["png"].exists()
    want = _nodes(room_to_glb(ROOM, tmp_path / "ref.glb", STATE))
    assert _nodes(res["glb"]) == want  # o1·w1 이름, extras.kind·category가 폴백과 같다


def test_no_blender_run_without_render(fake_blender, tmp_path):
    calls, usdz = fake_blender
    res = runner.build_scene(ROOM, usdz, STATE, tmp_path / "scene", render=False)
    assert calls == []  # 가구를 옮길 때마다 Blender를 띄우지 않는다
    assert res["png"] is None
    assert {"o1", "w1", "floor"} <= {n for n, _ in _nodes(res["glb"])}


def test_render_job_describes_current_room(fake_blender, tmp_path):
    """렌더는 USDZ가 아니라 지금 집 모습(옮긴·치운 가구 반영)을 상자 목록으로 받는다."""
    calls, usdz = fake_blender
    moved = ROOM.model_copy(update={"objects": [o.model_copy(update={"position": (9.0, o.position[1], 8.0)})
                                                for o in ROOM.objects[:1]]})
    runner.build_scene(moved, usdz, STATE, tmp_path / "scene", render=True)
    job = calls[0]
    objs = [b for b in job["boxes"] if b["kind"] == "object"]
    assert [b["name"] for b in objs] == [ROOM.objects[0].object_id]
    assert objs[0]["center"][0] == 9.0 and objs[0]["center"][2] == 8.0
    assert job["furniture_dir"] and job["furniture_dir"].endswith("furniture")


def test_blender_failure_falls_back_to_python_render(monkeypatch, tmp_path):
    usdz = tmp_path / "room.usdz"
    usdz.write_bytes(b"usdz")
    monkeypatch.setattr(runner, "blender_bin", lambda: "blender.exe")
    monkeypatch.setattr(runner.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "boom"))
    res = runner.build_scene(ROOM, usdz, STATE, tmp_path / "scene", render=True)
    assert res["engine"] == "fallback"
    assert res["png"].exists() and res["png"].read_bytes()[:4] == b"\x89PNG"
    assert "boom" in (tmp_path / "scene" / "blender.log").read_text(encoding="utf-8")
