"""작업 실행기: 스캔 처리·씬 갱신. Blender가 있으면 bpy, 없으면 순수 Python 폴백."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

from core.models import Room

from .converter import convert_usdz
from .glb import boxes_for_room, room_to_glb
from .plan_render import render_png

SCRIPT = Path(__file__).parent / "bpy_scripts" / "build_scene.py"
# 웹과 같은 제품·가구 모델을 렌더에도 쓴다 (build_products.py, build_furniture.py 결과)
MODELS_DIR = Path(__file__).resolve().parents[3] / "apps" / "web" / "models" / "products"
FURNITURE_DIR = MODELS_DIR.parent / "furniture"
_VIEW_LOCK = threading.Lock()  # 작은 서버라 시점 렌더는 한 번에 하나만


def blender_bin() -> str | None:
    return os.getenv("BLENDER_BIN") or shutil.which("blender")


def process_scan(usdz: Path, out_dir: Path) -> Room:
    out_dir.mkdir(parents=True, exist_ok=True)
    room = convert_usdz(usdz)
    (out_dir / "room.json").write_text(room.model_dump_json(indent=2), encoding="utf-8")
    return room


def use_blender() -> str | None:
    """렌더는 상자 목록만 받으므로 스캔 파일이 없는 집(도면으로 만든 집)도 쓴다"""
    exe = blender_bin()
    return exe if exe and os.getenv("USE_BLENDER", "1") == "1" else None


def _run_blender(exe: str, job: dict, out_dir: Path, png: Path) -> bool:
    """job을 넘겨 Blender를 화면 없이 돌린다. 실패하면 blender.log를 남기고 False"""
    job_p = out_dir / "job.json"
    job_p.write_text(json.dumps(job), encoding="utf-8")
    png.unlink(missing_ok=True)
    cmd = [exe, "-b", "-P", str(SCRIPT), "--", "--job", str(job_p)]
    if os.name == "posix" and shutil.which("nice"):  # 렌더하는 동안에도 웹 요청이 밀리지 않게
        cmd = ["nice", "-n", "10", *cmd]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=int(os.getenv("BLENDER_TIMEOUT_S", 300)))
        log, ok = r.stdout[-20000:] + r.stderr[-20000:], r.returncode == 0 and png.exists()
    except (OSError, subprocess.TimeoutExpired) as e:
        log, ok = f"{type(e).__name__}: {e}", False
    if not ok:
        (out_dir / "blender.log").write_text(log, encoding="utf-8")
    return ok


def _job(room: Room, state: dict, out_dir: Path, png: Path) -> dict:
    state_p = out_dir / "scene_state.json"
    state_p.write_text(json.dumps(state), encoding="utf-8")
    return {"boxes": boxes_for_room(room, state), "state": str(state_p), "out_png": str(png),
            "models_dir": str(MODELS_DIR) if MODELS_DIR.exists() else None,
            "furniture_dir": str(FURNITURE_DIR) if FURNITURE_DIR.exists() else None,
            "engine": os.getenv("BLENDER_ENGINE") or None, "title": state.get("title"),
            "sun": state.get("sun")}  # 채광과 같은 해 (sim.daylight.sun_light), 없으면 기본 해


def render_view(room: Room, state: dict, out_dir: Path, camera: dict) -> Path | None:
    """웹에서 보던 시점 그대로 한 장. camera = {pos, target, fov} (웹 3D 좌표, fov는 세로 각도).

    Blender가 없거나 다른 렌더가 돌고 있거나 실패하면 None.
    """
    exe = use_blender()
    if not exe or not _VIEW_LOCK.acquire(blocking=False):
        return None
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        png = out_dir / "view.png"
        return png if _run_blender(exe, {**_job(room, state, out_dir, png), "camera": camera}, out_dir, png) else None
    finally:
        _VIEW_LOCK.release()


def build_scene(room: Room, usdz: Path | None, state: dict, out_dir: Path, render: bool = False) -> dict:
    """glb(항상), png(render=True일 때)를 만든다. 반환: {glb, png, engine}

    웹 3D 파일(scene.glb)은 Blender 유무와 관계없이 glb.py가 만든다. 웹이 노드 이름(o1, w1)과
    extras(kind, category), 단위 상자 scale로 가구를 고르고 모델을 바꾸고 벽을 흐리게 하기 때문이다.
    Blender는 렌더 이미지(render.png, scene.blend)만 맡고, 렌더를 누를 때만 띄운다.
    engine은 렌더를 누가 맡는지를 뜻한다.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    glb, png = out_dir / "scene.glb", out_dir / "render.png"
    room_to_glb(room, glb, state)
    exe = use_blender()
    if not render:
        return {"glb": glb, "png": None, "engine": "blender" if exe else "fallback"}
    if exe:
        job = {**_job(room, state, out_dir, png), "out_blend": str(out_dir / "scene.blend")}
        if _run_blender(exe, job, out_dir, png):
            return {"glb": glb, "png": png, "engine": "blender"}
    render_png(room, png, state, title=state.get("title"))
    return {"glb": glb, "png": png, "engine": "fallback"}
