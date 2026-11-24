"""제품 모델을 이루는 부품 목록(mm). Blender 없이도 만들고 검사할 수 있다.

좌표: x 폭(정면에서 볼 때 오른쪽 +, 가운데 0), y 깊이(정면 = -D/2, 뒤 = +D/2), z 높이(바닥 0).
부품 하나 = dict(kind, mat, ...). kind
- box   둥근 모서리 상자. ax 방향에서 봤을 때 모서리가 r만큼 둥글다 (ax="y"면 정면에서 본 모서리)
- cyl   원기둥·원뿔대 (axis, c = 가운데, r, r2, l = 길이)
- lathe 세로축 회전체. prof = [(반지름, 높이)], ribs = (개수, 깊이)면 세로 살이 생긴다
- ext   다각형 단면을 axis 방향으로 a0~a1까지 밀어낸 것 (pts는 단면 좌표)
- torus 고리 (axis, c, R = 고리 반지름, r = 굵기 반지름)
- ell   타원체 (c, 반지름 3개, rot = 도 단위 xyz 회전, n = 각진 정도. 2면 타원, 클수록 상자에 가깝다)
- tube  점들을 따라가는 둥근 관 (pts, r)
재질 이름 finish*는 웹에서 제품 색으로 칠해지는 겉면이다.
"""
from __future__ import annotations

import math


class Parts(list):
    def box(self, mat, x0, x1, y0, y1, z0, z1, r=0.0, ax="y", bev=1.5, **kw):
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        if z1 < z0:
            z0, z1 = z1, z0
        self.append({"kind": "box", "mat": mat, "x0": x0, "x1": x1, "y0": y0, "y1": y1, "z0": z0, "z1": z1,
                     "r": r, "ax": ax, "bev": bev, **kw})
        return self[-1]

    def cyl(self, mat, axis, c, r, l, r2=None, bev=1.0, seg=48, **kw):
        self.append({"kind": "cyl", "mat": mat, "axis": axis, "c": tuple(c), "r": r, "r2": r if r2 is None else r2,
                     "l": l, "bev": bev, "seg": seg, **kw})
        return self[-1]

    def lathe(self, mat, c, prof, ribs=None, seg=56, **kw):
        self.append({"kind": "lathe", "mat": mat, "c": tuple(c), "prof": [tuple(p) for p in prof], "ribs": ribs,
                     "seg": seg, **kw})
        return self[-1]

    def ext(self, mat, axis, pts, a0, a1, bev=1.5, smooth=False, **kw):
        self.append({"kind": "ext", "mat": mat, "axis": axis, "pts": [tuple(p) for p in pts], "a0": min(a0, a1),
                     "a1": max(a0, a1), "bev": bev, "smooth": smooth, **kw})
        return self[-1]

    def torus(self, mat, axis, c, R, r, **kw):
        self.append({"kind": "torus", "mat": mat, "axis": axis, "c": tuple(c), "R": R, "r": r, **kw})
        return self[-1]

    def ell(self, mat, c, rad, rot=(0, 0, 0), n=2.0, **kw):
        self.append({"kind": "ell", "mat": mat, "c": tuple(c), "rad": tuple(rad), "rot": tuple(rot), "n": n, **kw})
        return self[-1]

    def tube(self, mat, pts, r, **kw):
        self.append({"kind": "tube", "mat": mat, "pts": [tuple(p) for p in pts], "r": r, **kw})
        return self[-1]


def _rot(v, rot):
    x, y, z = v
    for i, a in enumerate(rot):
        a = math.radians(a)
        c, s = math.cos(a), math.sin(a)
        if i == 0:
            y, z = y * c - z * s, y * s + z * c
        elif i == 1:
            x, z = x * c + z * s, -x * s + z * c
        else:
            x, y = x * c - y * s, x * s + y * c
    return x, y, z


def bounds(part: dict) -> tuple[float, float, float, float, float, float]:
    """부품이 차지하는 범위 (x0, x1, y0, y1, z0, z1). 타원체·관은 넉넉하게 잡는다."""
    k = part["kind"]
    if k == "box":
        return part["x0"], part["x1"], part["y0"], part["y1"], part["z0"], part["z1"]
    if k in ("cyl", "torus"):
        cx, cy, cz = part["c"]
        if k == "cyl":
            rr, hl = max(part["r"], part["r2"]), part["l"] / 2
        else:
            rr, hl = part["R"] + part["r"], part["r"]
        ext = {"x": (hl, rr, rr), "y": (rr, hl, rr), "z": (rr, rr, hl)}[part["axis"]]
        return cx - ext[0], cx + ext[0], cy - ext[1], cy + ext[1], cz - ext[2], cz + ext[2]
    if k == "lathe":
        cx, cy = part["c"]
        rr = max(p[0] for p in part["prof"])
        zs = [p[1] for p in part["prof"]]
        sy = part.get("sy", 1.0)
        return cx - rr, cx + rr, cy - rr * sy, cy + rr * sy, min(zs), max(zs)
    if k == "ext":
        us = [p[0] for p in part["pts"]]
        vs = [p[1] for p in part["pts"]]
        a0, a1 = part["a0"], part["a1"]
        if part["axis"] == "x":      # 단면 = (y, z)
            return a0, a1, min(us), max(us), min(vs), max(vs)
        if part["axis"] == "y":      # 단면 = (x, z)
            return min(us), max(us), a0, a1, min(vs), max(vs)
        return min(us), max(us), min(vs), max(vs), a0, a1  # z: 단면 = (x, y)
    if k == "ell":
        cx, cy, cz = part["c"]
        rx, ry, rz = part["rad"]
        # 둥근 상자(초타원체)가 각 축으로 뻗는 길이: (Σ|반지름·축 성분|^q)^(1/q), q = n/(n-1)
        ax = [_rot(v, part["rot"]) for v in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
        q = part["n"] / (part["n"] - 1)
        ex = [sum(abs(r * a[i]) ** q for r, a in zip((rx, ry, rz), ax)) ** (1 / q) for i in range(3)]
        return cx - ex[0], cx + ex[0], cy - ex[1], cy + ex[1], cz - ex[2], cz + ex[2]
    if k == "tube":
        r = part["r"]
        xs, ys, zs = zip(*part["pts"])
        return min(xs) - r, max(xs) + r, min(ys) - r, max(ys) + r, min(zs) - r, max(zs) + r
    raise ValueError(k)


def bbox(parts: list[dict]) -> dict:
    bs = [bounds(p) for p in parts]
    lo = [min(b[i] for b in bs) for i in (0, 2, 4)]
    hi = [max(b[i] for b in bs) for i in (1, 3, 5)]
    return {"w": hi[0] - lo[0], "d": hi[1] - lo[1], "h": hi[2] - lo[2], "lo": lo, "hi": hi}
