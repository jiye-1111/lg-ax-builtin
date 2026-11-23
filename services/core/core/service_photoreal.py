"""실사로 보기 (Service에 섞어 쓴다). 그림 계산은 core.photoreal."""
from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict, deque

from . import photoreal

log = logging.getLogger(__name__)
LIMIT_N, LIMIT_S = 3, 600  # 프로젝트마다 10분에 3장 (한 장마다 API 비용이 든다)
TOUR_LIMIT_N = 12           # 둘러보기는 들르는 곳마다 한 장이라 따로 센다 (여덟 곳 한 바퀴 + 조금)
BLENDER_LIMIT_N = 12        # 서버 Blender로 그리는 것도 집마다 10분에 12장까지 (CPU를 오래 쓴다)
SPOT_RE = re.compile(r"^[A-Za-z0-9_:-]{1,60}$")


class TooMany(RuntimeError):
    pass


class PhotorealMixin:
    image_client = None  # 테스트에서 바꿔 끼운다. None이면 서버 키로 만든다

    def _spot_dir(self, pid: str):
        return self.pdir(pid) / "scene" / "tour"

    def photoreal_spots(self, pid: str) -> dict:
        """둘러보기에서 만들어 둔 실사: {들르는 곳 id: {url, version(만들 때 장면 버전)}}"""
        self.get_project(pid)
        idx = self._spot_dir(pid) / "index.json"
        return {"spots": json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else {}}

    def photoreal_spot_path(self, pid: str, name: str):
        """저장해 둔 실사 파일 (없거나 이름이 이상하면 None)"""
        stem = name[:-4] if name.endswith(".png") else ""
        if not SPOT_RE.match(stem):
            return None
        p = self._spot_dir(pid) / f"{stem}.png"
        return p if p.exists() else None

    def photoreal(self, pid: str, image: str, mask: str, spot: str | None = None, camera: dict | None = None) -> dict:
        from .service import Invalid

        p = self.get_project(pid)
        try:
            view = photoreal.read_image(image, "화면")
            m = photoreal.read_image(mask, "제품 표시")
        except ValueError as e:
            raise Invalid(str(e)) from None
        if spot is not None and not SPOT_RE.match(spot):
            raise Invalid("들르는 곳 이름이 올바르지 않아요")
        t = time.time()
        try:
            out, model = self._ai_photo(pid, p, view, m, spot, t), photoreal.MODEL
        except (photoreal.Unavailable, TooMany):
            # 이미지 AI를 못 쓰거나 한도를 넘겼으면 서버의 Blender가 같은 시점으로 그린다. 그것도 안 되면 원래 안내 그대로
            out = self._blender_photo(pid, camera, t) if camera else None
            if out is None:
                raise
            model = "blender"
        if spot:
            return {**self._save_spot(pid, spot, out, int(p.get("version", 0)), int(t)), "model": model}
        path = self.pdir(pid) / "scene" / "photoreal.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        out.save(path, "PNG")
        view.save(path.with_name("photoreal_in.png"), "PNG")  # 결과가 이상할 때 AI에 보낸 화면과 견줘 보려고 (웹에는 안 나감)
        return {"url": f"/api/projects/{pid}/files/photoreal.png?v={int(t)}", "model": model}

    def _ai_photo(self, pid: str, p: dict, view, m, spot: str | None, t: float):
        client = self.image_client or photoreal.default_client()  # 키 없으면 Unavailable
        logs = self.__dict__.setdefault("_photo_log", defaultdict(deque))  # 서버 하나에 하나 (재시작하면 초기화)
        limit = TOUR_LIMIT_N if spot else LIMIT_N
        q = logs[(pid, bool(spot))]
        while q and t - q[0] > LIMIT_S:
            q.popleft()
        if len(q) >= limit:
            raise TooMany(f"실사 이미지는 10분에 {limit}장까지 만들 수 있어요. 잠시 뒤 다시 눌러 주세요")
        q.append(t)
        fin = p["scene_state"].get("finish_ids") or {}
        extra = "Keep the wall and floor colors close to the 3D view." if fin else ""
        try:
            return photoreal.make_photo(view, m, client, extra)
        except photoreal.Unavailable:
            raise
        except Exception as e:  # noqa: BLE001 - 네트워크·한도·거절: 사용자에게는 한 줄로
            q.pop()
            log.warning("실사 이미지 실패: %s", e)
            raise photoreal.Unavailable("지금은 실사 이미지를 못 만들었어요. 잠시 뒤 다시 눌러 주세요") from None

    def _blender_photo(self, pid: str, camera: dict, t: float):
        import io

        from PIL import Image
        from worker.runner import render_view, use_blender

        if not use_blender():
            return None
        q = self.__dict__.setdefault("_blender_log", defaultdict(deque))[pid]  # AI 한도와 따로 센다
        while q and t - q[0] > LIMIT_S:
            q.popleft()
        if len(q) >= BLENDER_LIMIT_N:
            return None
        q.append(t)
        room, _, state = self._scene_inputs(pid)
        png = render_view(room, state, self.pdir(pid) / "scene", camera)
        if png is None:
            q.pop()
            return None
        return Image.open(io.BytesIO(png)).convert("RGB")

    def _save_spot(self, pid: str, spot: str, out, version: int, t: int) -> dict:
        d = self._spot_dir(pid)
        d.mkdir(parents=True, exist_ok=True)
        stem = spot.replace(":", "_")
        out.save(d / f"{stem}.png", "PNG")
        url = f"/api/projects/{pid}/photoreal/spots/{stem}.png?v={t}"
        idx = d / "index.json"
        spots = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else {}
        idx.write_text(json.dumps({**spots, spot: {"url": url, "version": version}}, ensure_ascii=False), encoding="utf-8")
        return {"url": url}
