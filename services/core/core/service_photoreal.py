"""실사로 보기 (Service에 섞어 쓴다). 그림 계산은 core.photoreal."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import defaultdict, deque

from . import photoreal, photoreal_check
from .photoreal_words import (
    DECOR_WORDS,
    SCAN_WORDS,
    STRUCTURE,
    fix_words,
    product_words,
    scene_words,
    sun_words,
    thing_words,
)

log = logging.getLogger(__name__)
LIMIT_N, LIMIT_S = 3, 600  # 프로젝트마다 10분에 3장 (한 장마다 API 비용이 든다)
TOUR_LIMIT_N = 12           # 둘러보기는 들르는 곳마다 한 장이라 따로 센다 (여덟 곳 한 바퀴 + 조금)
BLENDER_LIMIT_N = 12        # 서버 Blender로 그리는 것도 집마다 10분에 12장까지 (CPU를 오래 쓴다)
SPOT_RE = re.compile(r"^[A-Za-z0-9_:-]{1,60}$")
SKU_RE = re.compile(r"^[A-Za-z0-9_.-]{2,40}$")
MAX_THINGS = 40  # 목록에 적는 물건 수 (화면에서 크게 보이는 것부터)
MAX_TRIES = 2    # 3D와 다르면 한 번 더 그린다. 그래도 다르면 Blender (없으면 덜 틀린 쪽)
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
    with urllib.request.urlopen(req, timeout=8) as r:
        return Image.open(io.BytesIO(r.read(4_000_000))).convert("RGB")


class TooMany(RuntimeError):
    pass


class PhotorealMixin:
    image_client = None  # 테스트에서 바꿔 끼운다. None이면 서버 키로 만든다
    photo_checker = None  # 다 그린 사진을 3D와 견줘 보는 것 (테스트에서 바꿔 끼운다). None이면 서버 키로 OpenAI 비전
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

    def _photo_items(self, p: dict, products: list[dict] | None, objects: list[dict] | None) -> list[dict]:
        """화면에 보이는 물건 → [{box, what | prod, on_ref, ref}] 크게 보이는 것부터.
        objects(웹이 보낸 화면 속 물건 전부)가 있으면 그것으로, 없으면 예전처럼 LG 제품(products)만"""
        items = []
        if objects is None:
            for x in products or []:
                try:
                    items.append({"box": x["box"], "prod": self.catalog.get(x["sku"]), "ref": None, "on": None})
                except KeyError:
                    continue  # 카탈로그에 없는 SKU는 글도 사진도 안 쓴다
        else:
            pls = {x["placement_id"]: x for x in p["scene_state"].get("placements", [])}
            room = self.get_room(p["project_id"])
            scanned = {o.object_id: o for o in room.objects}
            hidden = set(p["scene_state"].get("hidden_objects") or [])
            rt = p["scene_state"].get("router")
            seen = set()
            for x in objects:
                ref, box = x["ref"], x["box"]
                if ref in seen:
                    continue
                seen.add(ref)
                if ref == "router":
                    if not rt:
                        continue
                    h, under = self._surface_under(p, tuple(rt["center_xz"]))
                    items.append({"box": box, "what": "a small Wi-Fi router (keep its exact look and size)", "ref": ref,
                                  "on": under if h > 0.03 else None, "below": h > 0.03})
                elif ref.startswith("obj:"):
                    o = scanned.get(ref[4:])
                    if o is None or o.object_id in hidden:
                        continue
                    items.append({"box": box, "what": SCAN_WORDS.get(o.category, f"a {o.category}"), "ref": o.object_id,
                                  "on": None, "below": o.position[1] - o.bbox_m.h / 2 > 0.05})
                elif ref in pls:
                    pl = pls[ref]
                    sku = pl.get("sku") or ""
                    hung = bool(pl.get("hung"))
                    it = {"box": box, "ref": ref, "on": "wall" if hung else pl.get("on"),
                          "below": not hung and float(pl.get("base_m") or 0) > 0.05}
                    if sku.startswith("decor:"):
                        kind = sku[6:]
                        if kind in STRUCTURE or kind not in DECOR_WORDS:
                            continue  # 벽·문·창은 방 모양 (따로 그대로 두라고 한다)
                        it["what"] = DECOR_WORDS[kind]
                    else:
                        try:
                            it["prod"] = self.catalog.get(sku)
                        except KeyError:
                            continue
                    items.append(it)
        items.sort(key=lambda t: -(t["box"][2] - t["box"][0]) * (t["box"][3] - t["box"][1]))
        return items[:MAX_THINGS]

    def _photo_scene(self, p: dict, products: list[dict] | None, objects: list[dict] | None = None):
        """→ 물건 목록 글 (견줘 볼 때도 쓴다), LG 제품 사진 [(이름, bytes, mime)], LG 제품 화면 자리 (픽셀)"""
        W, H = photoreal.SIZE
        items = self._photo_items(p, products, objects)
        num = {it["ref"]: i for i, it in enumerate(items, 1) if it.get("ref")}
        seen, lines, refs, boxes = set(), [], [], []
        for i, it in enumerate(items, 1):
            on = it.get("on")
            on = on if on == "wall" else num.get(on) or ("below" if it.get("below") else None)
            prod, b = it.get("prod"), it["box"]
            if prod is None:
                lines.append(thing_words(i, it["what"], b, on))
                continue
            ref_no = None
            if prod.sku not in seen and len(refs) < MAX_REFS:
                jpg = self.photo_ref(prod.sku)
                if jpg:
                    refs.append((f"{prod.sku}.jpg", jpg, "image/jpeg"))
                    ref_no = len(refs) + 1  # 1번은 지금 화면
                    seen.add(prod.sku)
            lines.append(product_words(i, prod, b, ref_no, on))
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
                  products: list[dict] | None = None, daylight: dict | None = None,
                  objects: list[dict] | None = None) -> dict:
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
            out, wrong = self._ai_photo(pid, p, view, m, spot, t, camera, products, sun, objects)
            model = photoreal.MODEL
            if wrong:  # 두 번 그려도 3D와 다르다: 서버 Blender가 치수 그대로 그린 것을 낸다 (못 그리면 덜 틀린 AI 그림)
                bl = self._blender_photo(pid, camera, t, sun[0] if sun else None) if camera else None
                if bl is not None:
                    out, model = bl, "blender"
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

    def _checker(self):
        if self.photo_checker is not None:
            return self.photo_checker
        if os.getenv("PHOTOREAL_CHECK", "1") == "0":
            return None
        return photoreal_check.check if self.image_client is None else None  # 테스트에서 가짜 AI만 끼웠으면 견줘 보지 않는다

    def _ai_photo(self, pid: str, p: dict, view, m, spot: str | None, t: float, camera=None, products=None, sun=None,
                  objects=None):
        """→ (사진, 남은 틀린 것). 3D와 견줘 보고 틀린 게 있으면 그걸 짚어 한 번 더 그린다"""
        client = self.image_client or photoreal.default_client()  # 키 없으면 Unavailable
        logs = self.__dict__.setdefault("_photo_log", defaultdict(deque))  # 서버 하나에 하나 (재시작하면 초기화)
        limit = TOUR_LIMIT_N if spot else LIMIT_N
        q = logs[(pid, bool(spot))]
        while q and t - q[0] > LIMIT_S:
            q.popleft()
        if len(q) >= limit:
            raise TooMany(f"실사 이미지는 10분에 {limit}장까지 만들 수 있어요. 잠시 뒤 다시 눌러 주세요")
        q.append(t)  # 다시 그려도 한 장으로 센다
        fin = p["scene_state"].get("finish_ids") or {}
        lines, refs, boxes = self._photo_scene(p, products, objects)
        extra = "\n".join(x for x in [
            "Keep the wall and floor colors close to the 3D view." if fin else "",
            sun_words(sun[0], camera, sun[1], sun[2]) if sun else "",
            scene_words(len(lines)) if objects is not None else "",
            *lines] if x)
        check = self._checker()
        tries: list[dict] = []
        try:
            for _ in range(MAX_TRIES):
                fix = fix_words(tries[-1]["problems"]) if tries else ""
                notes: dict = {}
                out = photoreal.make_photo(view, m, client, "\n".join(x for x in [extra, fix] if x), refs=refs or None,
                                           boxes=boxes or None, notes=notes,
                                           quality=photoreal.TOUR_QUALITY if spot else photoreal.QUALITY)
                problems = check(view, out, lines) if check else None
                tries.append({"out": out, "ai": notes.pop("ai", None), "notes": notes, "problems": problems or [], "fix": fix})
                if not problems:
                    break
        except photoreal.Unavailable:
            raise
        except Exception as e:  # noqa: BLE001 - 네트워크·한도·거절: 사용자에게는 한 줄로
            if not tries:
                q.pop()
                log.warning("실사 이미지 실패: %s", e)
                raise photoreal.Unavailable("지금은 실사 이미지를 못 만들었어요. 잠시 뒤 다시 눌러 주세요") from None
            log.warning("실사 다시 그리기 실패 (먼저 그린 것을 씀): %s", e)
        best = min(tries, key=lambda x: len(x["problems"]))
        # 결과가 이상할 때 견줘 보려고 AI가 그린 그대로와 판단을 남긴다 (웹에는 안 나감)
        d = self.pdir(pid) / "scene"
        d.mkdir(parents=True, exist_ok=True)
        if best["ai"] is not None:
            best["ai"].save(d / "photoreal_ai.png", "PNG")
        (d / "photoreal_notes.json").write_text(json.dumps({
            **best["notes"], "refs": [r[0] for r in refs], "prompt_extra": extra,
            "tries": [{"problems": x["problems"], "fix": x["fix"]} for x in tries]}, ensure_ascii=False, indent=1), encoding="utf-8")
        return best["out"], best["problems"]

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
