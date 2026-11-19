"""작업 실행기: 스캔 처리·씬 갱신. Blender가 있으면 bpy, 없으면 순수 Python 폴백."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from core.models import Room

from .converter import convert_usdz
from .glb import room_to_glb
from .plan_render import render_png

SCRIPT = Path(__file__).parent / "bpy_scripts" / "build_scene.py"
# 웹과 같은 제품 모델을 렌더에도 쓴다 (build_products.py 결과)
MODELS_DIR = Path(__file__).resolve().parents[3] / "apps" / "web" / "models" / "products"


def blender_bin() -> str | None:
    return os.getenv("BLENDER_BIN") or shutil.which("blender")


def process_scan(usdz: Path, out_dir: Path) -> Room:
    out_dir.mkdir(parents=True, exist_ok=True)
    room = convert_usdz(usdz)
    (out_dir / "room.json").write_text(room.model_dump_json(indent=2), encoding="utf-8")
    return room


def build_scene(room: Room, usdz: Path | None, state: dict, out_dir: Path, render: bool = False) -> dict:
    """glb(항상), png(render=True일 때)를 만든다. 반환: {glb, png, engine}"""
    out_dir.mkdir(parents=True, exist_ok=True)
    glb, png = out_dir / "scene.glb", out_dir / "render.png"
    exe = blender_bin()
    if exe and usdz and os.getenv("USE_BLENDER", "1") == "1":
        state_p = out_dir / "scene_state.json"
        state_p.write_text(json.dumps(state), encoding="utf-8")
        job = {"usdz": str(usdz), "state": str(state_p), "out_glb": str(glb),
               "out_png": str(png) if render else None, "out_blend": str(out_dir / "scene.blend"),
               "models_dir": str(MODELS_DIR) if MODELS_DIR.exists() else None}
        job_p = out_dir / "job.json"
        job_p.write_text(json.dumps(job), encoding="utf-8")
        r = subprocess.run([exe, "-b", "-P", str(SCRIPT), "--", "--job", str(job_p)],
                           capture_output=True, text=True, timeout=int(os.getenv("BLENDER_TIMEOUT_S", 300)))
        if r.returncode == 0 and glb.exists():
            return {"glb": glb, "png": png if render and png.exists() else None, "engine": "blender"}
        (out_dir / "blender.log").write_text(r.stdout[-20000:] + r.stderr[-20000:], encoding="utf-8")
    room_to_glb(room, glb, state)
    if render:
        render_png(room, png, state, title=state.get("title"))
    return {"glb": glb, "png": png if render else None, "engine": "fallback"}
