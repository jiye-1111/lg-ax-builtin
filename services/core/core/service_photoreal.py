"""실사로 보기 (Service에 섞어 쓴다). 그림 계산은 core.photoreal."""
from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict, deque

from . import photoreal
from .photoreal_words import product_words, sun_words

log = logging.getLogger(__name__)
LIMIT_N, LIMIT_S = 3, 600  # 프로젝트마다 10분에 3장 (한 장마다 API 비용이 든다)
TOUR_LIMIT_N = 12           # 둘러보기는 들르는 곳마다 한 장이라 따로 센다 (여덟 곳 한 바퀴 + 조금)
BLENDER_LIMIT_N = 12        # 서버 Blender로 그리는 것도 집마다 10분에 12장까지 (CPU를 오래 쓴다)
SPOT_RE = re.compile(r"^[A-Za-z0-9_:-]{1,60}$")
SKU_RE = re.compile(r"^[A-Za-z0-9_.-]{2,40}$")
MAX_REFS = 6     # 이미지 AI에 같이 보내는 제품 사진 수 (화면에서 크게 보이는 제품부터)
REF_SIDE = 640   # 제품 사진은 이 크기로 줄여 보낸다 (그림 하나당 토큰·시간)
PHOTO_REFS = None  # SKU → LGE.COM 대표 사진 주소 (data/catalog/photo_refs.json)


def _photo_refs() -> dict:
    global PHOTO_REFS
    if PHOTO_REFS is None:
        from .config import ROOT

        f = ROOT / "data" / "catalog" / "photo_refs.json"
        PHOTO_REFS = json.loads(f.read_text(encoding="utf-8"))["photos"] if f.exists() else {}
    return PHOTO_REFS


def _download(url: str):
    """LGE.COM 사진 한 장 (PIL 그림). 막히면 예외"""
    import io
    import urllib.request

    from PIL import Image

    if not url.startswith("https://www.lge.co.kr/"):
        raise ValueError("LGE.COM 사진만 받는다")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.lge.co.kr/"})
    with urllib.request.urlopen(req, timeout=8) as r:  # noqa: S310 - 주소는 위에서 LGE.COM으로 묶었다
        return Image.open(io.BytesIO(r.read(4_000_000))).convert("RGB")


class TooMany(RuntimeError):
    pass


class PhotorealMixin:
    image_client = None  # 테스트에서 바꿔 끼운다. None이면 서버 키로 만든다
    photo_fetch = staticmethod(_download)  # 테스트에서 바꿔 끼운다

    def photo_ref(self, sku: str) -> bytes | None:
        """그 제품의 LGE.COM 대표 사진 (JPEG). 처음 한 번 받아서 서버에 둔다. 주소가 없거나 못 받으면 None"""
        import io

        url = _photo_refs().get(sku)
        if not url or not SKU_RE.match(sku):
            return None
        f = self.root / "photo_refs" / f"{sku}.jpg"
        if f.exists():
            return f.read_bytes()
        try:
            img = self.photo_fetch(url)
            img.thumbnail((REF_SIDE, REF_SIDE))
        except Exception as e:  # noqa: BLE001 - 사진이 없어도 실사는 만든다
            log.warning("제품 사진을 못 받음 %s: %s", sku, e)
            return None
        b = io.BytesIO()
        img.convert("RGB").save(b, "JPEG", quality=88)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b.getvalue())
        return b.getvalue()

    def _photo_sun(self, p: dict, daylight: dict | None):
        """채광 화면에서 고른 날짜·시각의 해 → (해, "HH:MM", 큰 창 향). 북쪽을 모르거나 시각이 없으면 None"""
        if not daylight or (p.get("site") or {}).get("north_deg") is None:
            return None
        from sim.daylight import sun_light
        from sim.orientation import window_facings

        s, _, when = self._sun_site(p, daylight["date"], daylight.get("time"))
        faces = window_facings(self.get_room(p["project_id"]), p["site"]["north_deg"])
        return sun_light(s, when), when.strftime("%H:%M"), faces[0]["label"] if faces else None

    def _photo_products(self, products: list[dict] | None):
        """화면에 보이는 LG 제품 → 글 (제품마다 한 줄), 사진 [(이름, bytes, mime)], 자리 (픽셀). 크게 보이는 것부터"""
        W, H = photoreal.SIZE
        seen, items = set(), []
        for x in products or []:
            try:
                prod = self.catalog.get(x["sku"])
            except KeyError:
                continue  # 카탈로그에 없는 SKU는 글도 사진도 안 쓴다
            b = x["box"]
            items.append(((b[2] - b[0]) * (b[3] - b[1]), prod, b))
        items.sort(key=lambda t: -t[0])
        lines, refs, boxes = [], [], []
        for i, (_, prod, b) in enumerate(items[:12], 1):
            ref_no = None
            if prod.sku not in seen and len(refs) < MAX_REFS:
                jpg = self.photo_ref(prod.sku)
                if jpg:
                    refs.append((f"{prod.sku}.jpg", jpg, "image/jpeg"))
                    ref_no = len(refs) + 1  # 1번은 지금 화면
                    seen.add(prod.sku)
            lines.append(product_words(i, prod, b, ref_no))
            boxes.append([b[0] * W, b[1] * H, b[2] * W, b[3] * H])
        return lines, refs, boxes

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

    def photoreal(self, pid: str, image: str, mask: str, spot: str | None = None, camera: dict | None = None,
                  products: list[dict] | None = None, daylight: dict | None = None) -> dict:
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
        sun = self._photo_sun(p, daylight)  # 채광 화면의 그 시각 해 (AI 글에도, Blender 빛에도 같은 해)
        try:
            out, model = self._ai_photo(pid, p, view, m, spot, t, camera, products, sun), photoreal.MODEL
        except (photoreal.Unavailable, TooMany):
            # 이미지 AI를 못 쓰거나 한도를 넘겼으면 서버의 Blender가 같은 시점으로 그린다. 그것도 안 되면 원래 안내 그대로
            out = self._blender_photo(pid, camera, t, sun[0] if sun else None) if camera else None
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

    def _ai_photo(self, pid: str, p: dict, view, m, spot: str | None, t: float, camera=None, products=None, sun=None):
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
        lines, refs, boxes = self._photo_products(products)
        extra = "\n".join(x for x in [
            "Keep the wall and floor colors close to the 3D view." if fin else "",
            sun_words(sun[0], camera, sun[1], sun[2]) if sun else "",
            *lines] if x)
        notes: dict = {}
        try:
            out = photoreal.make_photo(view, m, client, extra, refs=refs or None, boxes=boxes or None, notes=notes)
            # 결과가 이상할 때 견줘 보려고 AI가 그린 그대로와 판단을 남긴다 (웹에는 안 나감)
            d = self.pdir(pid) / "scene"
            d.mkdir(parents=True, exist_ok=True)
            if notes.get("ai") is not None:
                notes.pop("ai").save(d / "photoreal_ai.png", "PNG")
            (d / "photoreal_notes.json").write_text(json.dumps({**notes, "refs": [r[0] for r in refs], "prompt_extra": extra},
                                                               ensure_ascii=False, indent=1), encoding="utf-8")
            return out
        except photoreal.Unavailable:
            raise
        except Exception as e:  # noqa: BLE001 - 네트워크·한도·거절: 사용자에게는 한 줄로
            q.pop()
            log.warning("실사 이미지 실패: %s", e)
            raise photoreal.Unavailable("지금은 실사 이미지를 못 만들었어요. 잠시 뒤 다시 눌러 주세요") from None

    def _blender_photo(self, pid: str, camera: dict, t: float, sun: dict | None = None):
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
        room, _, state = self._scene_inputs(pid, sun)
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
