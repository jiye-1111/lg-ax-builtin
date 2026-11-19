"""room.json + 씬 상태 → glTF 2.0 바이너리(.glb). Blender가 없는 PC용 폴백 (plan.md ADR-3).

치수 기반 박스로 벽·개구부·오브젝트·배치 제품을 만든다. 노드 이름 = 요소 id (웹에서 강조용).
좌표: glTF Y-up. 평면 (x, z) = room.json (x, y).
"""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Iterable

from core.models import Room

DEFAULT_COLORS = {
    "wall": "#EDEBE7", "floor": "#C9B8A0", "door": "#8A6A4F", "window": "#9EC9E6",
    "opening": "#DDDDDD", "object": "#B9BEC4", "product": "#F4F4F2",
}

# 단위 큐브 (-0.5..0.5), 면마다 법선을 가진 24 정점
_FACES = [
    ((1, 0, 0), [(.5, -.5, -.5), (.5, .5, -.5), (.5, .5, .5), (.5, -.5, .5)]),
    ((-1, 0, 0), [(-.5, -.5, .5), (-.5, .5, .5), (-.5, .5, -.5), (-.5, -.5, -.5)]),
    ((0, 1, 0), [(-.5, .5, -.5), (-.5, .5, .5), (.5, .5, .5), (.5, .5, -.5)]),
    ((0, -1, 0), [(-.5, -.5, .5), (-.5, -.5, -.5), (.5, -.5, -.5), (.5, -.5, .5)]),
    ((0, 0, 1), [(.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5), (-.5, -.5, .5)]),
    ((0, 0, -1), [(-.5, -.5, -.5), (-.5, .5, -.5), (.5, .5, -.5), (.5, -.5, -.5)]),
]


def hex_rgba(h: str, a: float = 1.0) -> list[float]:
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return lin + [a]


def _quat_y(yaw: float) -> list[float]:
    # 평면 yaw(x→z 방향 각)는 glTF에서 Y축 기준 -yaw 회전
    return [0.0, math.sin(-yaw / 2), 0.0, math.cos(-yaw / 2)]


def boxes_for_room(room: Room, state: dict | None = None) -> list[dict]:
    state = state or {}
    colors = {**DEFAULT_COLORS, **(state.get("materials") or {})}
    boxes: list[dict] = []
    xs = [p[0] for w in room.walls for p in (w.start, w.end)] or [0]
    zs = [p[1] for w in room.walls for p in (w.start, w.end)] or [0]
    boxes.append({"name": "floor", "kind": "floor", "center": [(min(xs) + max(xs)) / 2, -0.01, (min(zs) + max(zs)) / 2],
                  "size": [max(xs) - min(xs), 0.02, max(zs) - min(zs)], "yaw": 0.0, "color": colors["floor"]})
    for w in room.walls:
        dx, dz = w.end[0] - w.start[0], w.end[1] - w.start[1]
        L = math.hypot(dx, dz)
        h = (w.measured.height_m if w.measured and w.measured.height_m else None) or w.scanned.height_m
        boxes.append({"name": w.wall_id, "kind": "wall", "center": [(w.start[0] + w.end[0]) / 2, h / 2, (w.start[1] + w.end[1]) / 2],
                      "size": [L, h, w.thickness_m or 0.1], "yaw": math.atan2(dz, dx),
                      "color": (state.get("wall_colors") or {}).get(w.wall_id, colors["wall"])})
    walls = {w.wall_id: w for w in room.walls}
    for o in room.openings:
        w = walls.get(o.wall_id)
        if not w:
            continue
        dx, dz = w.end[0] - w.start[0], w.end[1] - w.start[1]
        L = math.hypot(dx, dz) or 1
        u = o.offset_m + o.width_m / 2
        cx, cz = w.start[0] + dx / L * u, w.start[1] + dz / L * u
        boxes.append({"name": o.opening_id, "kind": o.type, "center": [cx, o.sill_m + o.height_m / 2, cz],
                      "size": [o.width_m, o.height_m, (w.thickness_m or 0.1) + 0.02], "yaw": math.atan2(dz, dx),
                      "color": colors.get(o.type, colors["opening"])})
    for ob in room.objects:
        boxes.append({"name": ob.object_id, "kind": "object", "center": list(ob.position),
                      "size": [ob.bbox_m.w, ob.bbox_m.h, ob.bbox_m.d], "yaw": ob.yaw_rad, "color": colors["object"],
                      "category": ob.category})
    for pl in state.get("placements") or []:
        w_, h_, d_ = pl["size_m"]
        boxes.append({"name": f"product:{pl['sku']}", "kind": "product",
                      "center": [pl["center_xz"][0], h_ / 2, pl["center_xz"][1]], "size": [w_, h_, d_],
                      # placement yaw는 벽 안쪽 법선 방향 → 제품 정면 축과 맞추기 위해 90° 보정
                      "yaw": pl["yaw_rad"] - math.pi / 2, "color": pl.get("hex") or colors["product"]})
    return boxes


def write_glb(boxes: Iterable[dict], out: str | Path) -> Path:
    boxes = list(boxes)
    pos, nrm, idx = bytearray(), bytearray(), bytearray()
    for n, quad in _FACES:
        for v in quad:
            pos += struct.pack("<3f", *v)
            nrm += struct.pack("<3f", *n)
    base = 0
    for _ in _FACES:
        idx += struct.pack("<6H", base, base + 1, base + 2, base, base + 2, base + 3)
        base += 4
    bin_ = bytes(pos + nrm + idx)
    materials, mat_index, meshes, nodes = [], {}, [], []
    for b in boxes:
        key = b["color"].upper()
        if key not in mat_index:
            mat_index[key] = len(materials)
            alpha = 0.55 if b["kind"] == "window" else 1.0
            m = {"name": key, "pbrMetallicRoughness": {"baseColorFactor": hex_rgba(key, alpha), "metallicFactor": 0.0,
                                                        "roughnessFactor": 0.8}}
            if alpha < 1:
                m["alphaMode"] = "BLEND"
            materials.append(m)
        meshes.append({"name": b["name"], "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2,
                                                          "material": mat_index[key]}]})
        nodes.append({"name": b["name"], "mesh": len(meshes) - 1, "translation": [float(c) for c in b["center"]],
                      "rotation": _quat_y(b["yaw"]), "scale": [max(float(s), 1e-4) for s in b["size"]],
                      "extras": {"kind": b["kind"], **({"category": b["category"]} if b.get("category") else {})}})
    gltf = {
        "asset": {"version": "2.0", "generator": "lg-ax-builtin glb fallback"},
        "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes, "meshes": meshes,
        "materials": materials,
        "buffers": [{"byteLength": len(bin_)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(pos), "target": 34962},
            {"buffer": 0, "byteOffset": len(pos), "byteLength": len(nrm), "target": 34962},
            {"buffer": 0, "byteOffset": len(pos) + len(nrm), "byteLength": len(idx), "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 24, "type": "VEC3", "min": [-.5, -.5, -.5], "max": [.5, .5, .5]},
            {"bufferView": 1, "componentType": 5126, "count": 24, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5123, "count": 36, "type": "SCALAR"},
        ],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    bn = bin_ + b"\0" * (-len(bin_) % 4)
    total = 12 + 8 + len(js) + 8 + len(bn)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON") + js)
        f.write(struct.pack("<I4s", len(bn), b"BIN\0") + bn)
    return out


def room_to_glb(room: Room, out: str | Path, state: dict | None = None) -> Path:
    return write_glb(boxes_for_room(room, state), out)
