"""Blender 없는 PC용 렌더 폴백: 박스 씬을 축측(아이소메트릭) 투영으로 PNG에 그린다.

카메라 쪽 벽은 낮게 잘라(돌하우스 컷어웨이) 안이 보이게 한다. 시연용 '디자인 미리보기' 품질.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from core.models import Room

from .glb import boxes_for_room

CAM = (-1.0, 1.0, 1.0)  # 평면 (x, z) 기준 카메라가 오는 방향(-x, +z 쪽 위)
LIGHT = (-0.4, 0.8, 0.45)


def _hex(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _shade(rgb, k):
    return tuple(max(0, min(255, int(c * k))) for c in rgb)


def _corners(b):
    cx, cy, cz = b["center"]
    sx, sy, sz = b["size"]
    c, s = math.cos(b["yaw"]), math.sin(b["yaw"])
    out = {}
    for ix in (-1, 1):
        for iy in (-1, 1):
            for iz in (-1, 1):
                lx, lz = ix * sx / 2, iz * sz / 2
                out[(ix, iy, iz)] = (cx + lx * c - lz * s, cy + iy * sy / 2, cz + lx * s + lz * c)
    return out


def _proj(p, scale, ox, oy):
    x, y, z = p
    # 등각 투영: 화면 x = (x + z)cos30, 화면 y = (z - x)sin30 - y  (카메라: -x,+z 방향 위)
    u = (x + z) * math.cos(math.radians(30))
    v = (z - x) * math.sin(math.radians(30)) - y
    return (ox + u * scale, oy - v * scale * -1)


def render_png(room: Room, out: str | Path, state: dict | None = None, size=(1280, 800), title: str | None = None) -> Path:
    boxes = boxes_for_room(room, state)
    xs = [p[0] for w in room.walls for p in (w.start, w.end)]
    zs = [p[1] for w in room.walls for p in (w.start, w.end)]
    cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
    # 카메라 쪽 벽 컷어웨이: 벽 중심이 방 중심보다 카메라 쪽이면 높이 0.25m
    for b in boxes:
        if b["kind"] in ("wall", "door", "window"):
            bx, _, bz = b["center"]
            if (bx - cx) * CAM[0] + (bz - cz) * CAM[2] > 0.3:
                if b["kind"] == "wall":
                    b["size"] = [b["size"][0], 0.25, b["size"][2]]
                    b["center"] = [bx, 0.125, bz]
                else:
                    b["skip"] = True
    boxes = [b for b in boxes if not b.get("skip")]

    img = Image.new("RGB", size, (246, 245, 242))
    d = ImageDraw.Draw(img, "RGBA")
    span = max(max(xs) - min(xs), max(zs) - min(zs), 1)
    scale = min(size) / (span * 1.55)
    # 중심 정렬
    c0 = _proj((cx, 1.0, cz), scale, 0, 0)
    ox, oy = size[0] / 2 - c0[0], size[1] / 2 - c0[1]

    def depth(b):  # 카메라에서 먼 것부터
        x, y, z = b["center"]
        bias = {"floor": -100, "door": 0.4, "window": 0.4, "opening": 0.4}.get(b["kind"], 0)
        return (x - cx) * CAM[0] + (z - cz) * CAM[2] + bias

    faces = {  # 축 방향 법선 → 꼭짓점 키
        "top": [(-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1)],
        "+x": [(1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)],
        "-x": [(-1, -1, -1), (-1, 1, -1), (-1, 1, 1), (-1, -1, 1)],
        "+z": [(-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)],
        "-z": [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1)],
    }
    for b in sorted(boxes, key=depth):
        cs = _corners(b)
        rgb = _hex(b["color"])
        alpha = 140 if b["kind"] == "window" else 255
        c, s = math.cos(b["yaw"]), math.sin(b["yaw"])
        for name, keys in faces.items():
            if name == "top":
                n = (0, 1, 0)
            else:
                ax = name[1]
                sign = 1 if name[0] == "+" else -1
                n = (c * sign, 0, s * sign) if ax == "x" else (-s * sign, 0, c * sign)
            if n[0] * CAM[0] + n[1] * CAM[1] + n[2] * CAM[2] <= 0:
                continue  # 뒷면
            lum = 0.72 + 0.3 * max(0, n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2])
            poly = [_proj(cs[k], scale, ox, oy) for k in keys]
            d.polygon(poly, fill=(*_shade(rgb, lum), alpha), outline=(*_shade(rgb, 0.6), 255))
    if title:
        try:
            font = ImageFont.load_default(size=22)
        except TypeError:
            font = ImageFont.load_default()
        d.text((24, 20), title, fill=(40, 40, 40), font=font)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out
