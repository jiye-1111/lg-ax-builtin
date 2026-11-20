"""실사로 보기 (Service에 섞어 쓴다). 그림 계산은 core.photoreal."""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from . import photoreal

log = logging.getLogger(__name__)
LIMIT_N, LIMIT_S = 3, 600  # 프로젝트마다 10분에 3장 (한 장마다 API 비용이 든다)


class TooMany(RuntimeError):
    pass


class PhotorealMixin:
    image_client = None  # 테스트에서 바꿔 끼운다. None이면 서버 키로 만든다

    def photoreal(self, pid: str, image: str, mask: str) -> dict:
        from .service import Invalid

        p = self.get_project(pid)
        try:
            view = photoreal.read_image(image, "화면")
            m = photoreal.read_image(mask, "제품 표시")
        except ValueError as e:
            raise Invalid(str(e)) from None
        client = self.image_client or photoreal.default_client()  # 키 없으면 Unavailable
        logs = self.__dict__.setdefault("_photo_log", defaultdict(deque))  # 서버 하나에 하나 (재시작하면 초기화)
        q, t = logs[pid], time.time()
        while q and t - q[0] > LIMIT_S:
            q.popleft()
        if len(q) >= LIMIT_N:
            raise TooMany(f"실사 이미지는 10분에 {LIMIT_N}장까지 만들 수 있어요. 잠시 뒤 다시 눌러 주세요")
        q.append(t)
        fin = p["scene_state"].get("finish_ids") or {}
        extra = "Keep the wall and floor colors close to the 3D view." if fin else ""
        try:
            out = photoreal.make_photo(view, m, client, extra)
        except photoreal.Unavailable:
            raise
        except Exception as e:  # noqa: BLE001 - 네트워크·한도·거절: 사용자에게는 한 줄로
            q.pop()
            log.warning("실사 이미지 실패: %s", e)
            raise photoreal.Unavailable("지금은 실사 이미지를 못 만들었어요. 잠시 뒤 다시 눌러 주세요") from None
        path = self.pdir(pid) / "scene" / "photoreal.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        out.save(path, "PNG")
        return {"url": f"/api/projects/{pid}/files/photoreal.png?v={int(t)}", "model": photoreal.MODEL}
