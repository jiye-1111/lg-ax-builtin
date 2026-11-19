"""Figma 도면(data/drawings/<sku>.json)을 Blender 부품 상자로 바꾼다.

도면 규칙 (1px = 1mm, 위에서 아래로 y)
- 정면(front): parts 프레임 안 사각형. 이름 = 역할[/번호[/방향]]  예) door/0, handle/2/h, vent, display, body
- 옆면(side): 왼쪽이 앞. door/side, handle/side, body 가 각 역할의 깊이(앞뒤 범위)를 정한다.
- 정면 크기는 카탈로그 폭·높이, 옆면 폭은 카탈로그 깊이와 같아야 한다 (1mm까지 허용).

결과 상자는 build_products.box()와 같은 Blender 좌표(m): x 폭(정면에서 볼 때 오른쪽 +),
y 깊이(정면 = -D/2), z 높이(바닥 0).
"""
from __future__ import annotations

import json
from pathlib import Path

TOL_MM = 1.0
# 옆면에 따로 없는 역할의 깊이: 문 앞면 기준 (앞으로 a mm, 뒤로 b mm)
FLUSH = {"vent": (-20.0, None), "display": (1.5, -2.0)}


class DrawingError(ValueError):
    pass


def load_drawing(drawings_dir: Path, sku: str) -> dict | None:
    p = Path(drawings_dir) / f"{sku}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _check(drawing: dict, dims: dict) -> None:
    f, s = drawing["front"], drawing["side"]
    pairs = (("폭", f["w"], dims["w"]), ("높이", f["h"], dims["h"]), ("깊이", s["w"], dims["d"]))
    for label, got, want in pairs:
        if abs(got - want) > TOL_MM:
            raise DrawingError(f"{drawing.get('sku')}: 도면 {label} {got}mm ≠ 카탈로그 {want}mm")


def _depths(side: dict) -> dict[str, tuple[float, float]]:
    out = {}
    for p in side["parts"]:
        role = p["name"].split("/")[0]
        out[role] = (p["x"], p["x"] + p["w"])
    if "door" not in out or "body" not in out:
        raise DrawingError("옆면에 door/side와 body가 있어야 한다")
    return out


def boxes_from_drawing(drawing: dict, dims: dict) -> list[dict]:
    _check(drawing, dims)
    W, H, D = dims["w"], dims["h"], dims["d"]
    depth = _depths(drawing["side"])
    door_front, door_back = depth["door"]
    boxes = []
    for p in drawing["front"]["parts"]:
        role = p["name"].split("/")[0]
        if role in depth:
            d0, d1 = depth[role]
        elif role in FLUSH:
            ahead, behind = FLUSH[role]
            d0 = door_front - ahead if ahead is not None else door_front
            d1 = door_front - behind if behind is not None else door_back
            d0, d1 = min(d0, d1), max(d0, d1)
        else:
            raise DrawingError(f"모르는 부품 이름: {p['name']}")
        boxes.append({
            "name": p["name"], "role": role,
            "x0": (p["x"] - W / 2) / 1000, "x1": (p["x"] + p["w"] - W / 2) / 1000,
            "y0": (d0 - D / 2) / 1000, "y1": (d1 - D / 2) / 1000,
            "z0": (H - p["y"] - p["h"]) / 1000, "z1": (H - p["y"]) / 1000,
        })
    return boxes
