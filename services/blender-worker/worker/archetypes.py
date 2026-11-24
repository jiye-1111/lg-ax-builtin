"""제품군별 모양 틀. (폭 W, 깊이 D, 높이 H mm와 그 제품의 특징 값) → worker.shapes 부품 목록.

특징 값(문 나눔 위치, 받침 종류 등)은 LGE.COM 제품 사진·치수도에서 잰 것이고 data/models/features.json에 있다.
전체 크기는 카탈로그 값 그대로다. 로고·글자는 넣지 않는다.
"""
from __future__ import annotations

import math

from .shapes import Parts


# ---------------------------------------------------------------- 냉장고류
def fridge(W, D, H, rows=(), cols=None, gap=0.027, style="objet", handles=None, dispenser=None, glass=None,
           display=None, side="dark", top_strip=0.0, kick=0.0, door_t=None, **_):
    """문이 여러 장인 세로 캐비닛 (냉장고·김치냉장고·냉동고·컨버터블).

    rows: 가로 틈의 가운데 높이(위에서부터의 비율) 목록. cols: 단마다 세로 틈 위치(왼쪽에서부터 비율) 목록.
    gap: 가로 틈 굵기(높이 비율). 오브제컬렉션은 손을 넣는 어두운 홈이라 굵고, 일반형은 가늘다.
    handles: None | "bar"(세로 막대 손잡이) | "pocket"(문 옆 세로 홈). dispenser/glass/display: (문 번호, ...) 얹는 것.
    """
    p = Parts()
    x0, x1, f = -W / 2, W / 2, -D / 2
    bar = handles == "bar"
    hand = 48 if bar else 0                      # 막대 손잡이가 앞으로 나온 만큼
    door_t = door_t or (62 if style == "objet" else 55)
    fd = f + hand                                # 문 앞면
    body_mat = {"dark": "body", "same": "finish", "grey": "lightgrey"}[side]
    p.box(body_mat, x0, x1, fd + door_t + 3, D / 2, 14, H, r=4, ax="y", bev=3)
    p.box("dark", x0 + 3, x1 - 3, fd + door_t - 6, fd + door_t + 6, 20, H - 6, bev=0)       # 문 뒤 그늘
    for sx in (-1, 1):                            # 다리
        p.cyl("dark", "z", (sx * (W / 2 - 60), fd + door_t + 40, 8), 18, 16, bev=2)
        p.cyl("dark", "z", (sx * (W / 2 - 60), D / 2 - 60, 8), 18, 16, bev=2)
    top = H - (10 if style == "objet" else 6)
    bot = 38 if not kick else H * kick
    if kick:
        p.box("dark", x0 + 8, x1 - 8, fd + 30, fd + door_t, 0, bot - 4, bev=1)
    if top_strip:                                 # 문 위 조작부 띠
        p.box("black", x0, x1, fd + 2, fd + door_t, H * (1 - top_strip) + 2, top, r=3, bev=1.5)
        top = H * (1 - top_strip) - 2
    g = H * gap
    ys = [top] + [v for r in rows for v in (H * (1 - r) + g / 2, H * (1 - r) - g / 2)] + [bot]
    bands = [(ys[i], ys[i + 1]) for i in range(0, len(ys), 2)]          # (위, 아래)
    cols = list(cols or []) + [[]] * len(bands)
    vg = 4 if style == "objet" else 6
    doors = []
    for bi, (zt, zb) in enumerate(bands):
        xs = [x0 + 1] + [x0 + W * c for c in cols[bi]] + [x1 - 1]
        for di in range(len(xs) - 1):
            a, b = xs[di] + (vg / 2 if di else 0), xs[di + 1] - (vg / 2 if di < len(xs) - 2 else 0)
            p.box("finish", a, b, fd, fd + door_t, zb, zt, r=3 if style == "objet" else 8, bev=2.5)
            doors.append((a, b, zb, zt, bi, di, len(xs) - 1))
    for r in rows:                                # 가로 틈: 손 넣는 홈
        zc = H * (1 - r)
        if g > 20:
            p.box("dark", x0 + 2, x1 - 2, fd + 14, fd + door_t, zc - g / 2 - 2, zc + g / 2 + 2, bev=0)
    for i, (a, b, zb, zt, bi, di, n) in enumerate(doors):
        w, h = b - a, zt - zb
        if bar:                                   # 세로 막대(위 칸), 가로 막대(서랍)
            drawer = bi > 0 and n == 1 and h < H * 0.3
            if drawer:
                _bar(p, (a + w * 0.12, zt - 70), (b - w * 0.12, zt - 70), fd)
            else:
                hx = (b - 45) if (n > 1 and di == 0) or (n == 1 and handles_side(handles, i) == "r") else (a + 45)
                if n == 1:
                    hx = a + 45
                zc = zb + h * (0.42 if bi == 0 and len(bands) > 1 else 0.6)
                ln = min(h * 0.55, 620)
                _bar(p, (hx, zc - ln / 2), (hx, zc + ln / 2), fd)
        elif handles == "pocket" and n == 1:      # 문 옆 세로 홈
            zc = zt - min(h * 0.3, 330)
            p.box("dark", a + 8, a + 30, fd - 0.6, fd + 18, zc - 150, zc + 150, r=6, bev=0.5)
    if dispenser:                                 # 얼음정수 디스펜서: 검은 창 + 안쪽 홈
        di, cx, cz, dw, dh = dispenser
        a, b, zb, zt = doors[di][:4]
        ux, uz = a + (b - a) * cx, zb + (zt - zb) * cz
        w2, h2 = (b - a) * dw / 2, (zt - zb) * dh / 2
        p.box("black", ux - w2, ux + w2, fd - 1.5, fd + 20, uz - h2, uz + h2, r=10, bev=1)
        p.box("dark", ux - w2 * 0.72, ux + w2 * 0.72, fd - 2.2, fd + 10, uz - h2 * 0.9, uz + h2 * 0.25, r=8, bev=0.5)
        p.box("steel", ux - w2 * 0.6, ux + w2 * 0.6, fd - 2.6, fd + 6, uz - h2 * 0.9, uz - h2 * 0.78, bev=0.5)
    if glass:                                     # 노크온 인스타뷰: 문에 박힌 검은 유리
        di, m = glass
        a, b, zb, zt = doors[di][:4]
        mx, mz = (b - a) * m, (zt - zb) * m * 0.55
        p.box("black", a + mx, b - mx, fd - 1.5, fd + 8, zb + mz, zt - mz, r=6, bev=1)
    if display:                                   # 작은 표시창
        di, cx, cz = display
        a, b, zb, zt = doors[di][:4]
        ux, uz = a + (b - a) * cx, zb + (zt - zb) * cz
        p.box("black", ux - 32, ux + 32, fd - 1.2, fd + 6, uz - 70, uz + 70, r=5, bev=0.8)
    return p


def handles_side(handles, i):
    return "l"


def _bar(p, a, b, fd, t=11):
    """문 앞 막대 손잡이. a, b = (x, z) 양 끝."""
    (xa, za), (xb, zb) = a, b
    vert = abs(xa - xb) < 1
    y = fd - 40
    if vert:
        p.box("steel", xa - t, xa + t, y - t, y + t, za, zb, r=t * 0.8, ax="z", bev=2)
        for z in (za + 40, zb - 40):
            p.box("steel", xa - t * 0.7, xa + t * 0.7, y, fd + 2, z - 9, z + 9, r=3, ax="y", bev=1)
    else:
        p.box("steel", xa, xb, y - t, y + t, za - t, za + t, r=t * 0.8, ax="x", bev=2)
        for x in (xa + 50, xb - 50):
            p.box("steel", x - 9, x + 9, y, fd + 2, za - t * 0.7, za + t * 0.7, r=3, ax="y", bev=1)


def chest_kimchi(W, D, H, seam=0.19, lids=1, **_):
    """뚜껑형 김치냉장고: 낮은 몸통 + 위로 여는 뚜껑, 앞쪽 위 조작부."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    zs = H * (1 - seam)
    p.box("finish", x0, x1, f, b, 30, zs - 6, r=10, ax="z", bev=4)
    p.box("dark", x0 + 6, x1 - 6, f + 6, b - 6, zs - 8, zs + 6, bev=0)             # 뚜껑 밑 틈
    xs = [x0, 0, x1] if lids == 2 else [x0, x1]
    for a, c in zip(xs, xs[1:]):
        p.box("finish", a + (3 if a > x0 else 0), c - (3 if c < x1 else 0), f, b - 30, zs + 4, H, r=12, ax="x", bev=4)
        p.box("dark", (a + c) / 2 - 90, (a + c) / 2 + 90, f - 0.5, f + 14, zs + 14, zs + 34, r=8, bev=0.5)  # 손잡이 홈
    p.box("dark", x0 + 20, x1 - 20, b - 34, b, zs + 4, H - 12, r=6, ax="x", bev=2)   # 뒤쪽 경첩 덮개
    p.box("black", -70, 70, f - 1, f + 6, zs - 60, zs - 28, r=6, bev=0.8)             # 조작부
    p.box("dark", x0 + 14, x1 - 14, f + 20, b - 14, 0, 32, r=8, ax="z", bev=2)        # 받침
    return p


def glass_cabinet(W, D, H, drawers=(), frame=22, handle="top", shelves=5, side="dark", **_):
    """유리문 캐비닛 (와인셀러, SIGNATURE 냉장고): 어두운 유리문, 아래는 서랍."""
    p = Parts()
    x0, x1, f = -W / 2, W / 2, -D / 2
    t = 55
    p.box("body" if side == "dark" else "finish", x0, x1, f + t + 3, D / 2, 12, H, r=4, bev=3)
    p.box("dark", x0 + 3, x1 - 3, f + t - 6, f + t + 6, 20, H - 6, bev=0)
    for sx in (-1, 1):
        p.cyl("dark", "z", (sx * (W / 2 - 55), f + t + 40, 7), 17, 14, bev=2)
        p.cyl("dark", "z", (sx * (W / 2 - 55), D / 2 - 55, 7), 17, 14, bev=2)
    g = 26
    zb = 36
    ys = sorted([H * (1 - d) for d in drawers], reverse=True)
    zt = H - 8
    door_bot = (ys[0] + g / 2) if ys else zb
    p.box("finish", x0 + 1, x1 - 1, f, f + t, door_bot, zt, r=4, bev=2.5)          # 문틀
    p.box("window", x0 + frame, x1 - frame, f - 1.2, f + 10, door_bot + frame, zt - frame, r=3, bev=0.8)
    n = shelves
    for i in range(n):                                                             # 유리 너머로 비치는 선반
        z = door_bot + frame + (zt - door_bot - 2 * frame) * (i + 0.8) / (n + 0.3)
        p.box("#6B5540/s", x0 + frame + 14, x1 - frame - 14, f - 1.6, f + 6, z - 5, z + 5, bev=0)
    edges = ys + [None]
    for i, y in enumerate(ys):                                                     # 서랍
        lo = (ys[i + 1] + g / 2) if i + 1 < len(ys) else zb
        p.box("finish", x0 + 1, x1 - 1, f, f + t, lo, y - g / 2, r=4, bev=2.5)
        p.box("dark", x0 + 2, x1 - 2, f + 14, f + t, y - g / 2 - 2, y + g / 2 + 2, bev=0)
    return p


def single_door_tall(W, D, H, glassy=False, strip="left", **_):
    """스타일러: 통짜 문 하나. 문 옆에 가는 어두운 조작 띠."""
    p = Parts()
    x0, x1, f = -W / 2, W / 2, -D / 2
    t = 45
    p.box("body", x0, x1, f + t + 3, D / 2, 10, H, r=4, bev=3)
    p.box("dark", x0 + 3, x1 - 3, f + t - 5, f + t + 6, 16, H - 5, bev=0)
    p.box("dark", x0 + 20, x1 - 20, f + 30, D / 2 - 20, 0, 12, bev=0)
    p.box("finish", x0 + 1, x1 - 1, f, f + t, 22, H - 4, r=3, bev=2.5)
    return p


# ---------------------------------------------------------------- 세탁·건조
def _feet(p, W, y0, y1, r=22, h=14):
    for sx in (-1, 1):
        for y in (y0, y1):
            p.cyl("dark", "z", (sx * (W / 2 - 55), y, h / 2), r, h, bev=2)


def _drum_door(p, cx, cz, f, R, ring="chrome", bulge=55, face="black"):
    """드럼 문: 테두리 고리 + 볼록한 짙은 유리 + 안쪽 통."""
    p.cyl(face, "y", (cx, f + bulge * 0.55, cz), R, bulge * 0.9, bev=10, seg=64)                # 문 판
    p.torus({"chrome": "chrome", "black": "black", "finish": "finish"}[ring], "y", (cx, f + bulge * 0.16, cz), R * 0.80, R * 0.075)
    p.ell("window", (cx, f + bulge * 0.42, cz), (R * 0.70, bulge * 0.42, R * 0.70), n=2.4)      # 볼록 유리
    p.torus("steel", "y", (cx, f + bulge * 0.18, cz), R * 0.50, R * 0.02)                       # 안쪽 통 테두리가 비치는 선


def drum(W, D, H, door=0.74, door_z=0.47, panel=0.135, panel_mat="black", ring="chrome", face="black", dial=0.5,
         drawer=True, kick=0.07, bulge=55, base=0, **_):
    """드럼세탁기·건조기·워시콤보: 위 조작부 띠 + 가운데 둥근 문."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    fb = f + bulge                                   # 몸통 앞면 (문이 그보다 앞으로 나온다)
    z0 = base + 14
    p.box("finish", x0, x1, fb, b, z0, H, r=14, ax="z", bev=5)
    _feet(p, W, fb + 60, b - 60)
    zp = H * (1 - panel)
    pm = panel_mat if panel_mat != "same" else "finish"
    p.box(pm, x0 + 6, x1 - 6, fb - 3, fb + 12, zp, H - 8, r=8, bev=1.5)                         # 조작부
    if dial is not None:
        p.cyl("chrome", "y", (x0 + W * dial, fb - 14, (zp + H - 8) / 2), H * panel * 0.30, 26, bev=4)
        p.cyl("black", "y", (x0 + W * dial, fb - 27, (zp + H - 8) / 2), H * panel * 0.22, 3, bev=1)
    if drawer:                                       # 세제함
        p.box("finish" if pm != "finish" else "lightgrey", x0 + 14, x0 + W * 0.26, fb - 5, fb + 8, zp + 8, H - 16, r=5, bev=1)
    if panel_mat != "black":                         # 표시창
        p.box("black", x1 - W * 0.36, x1 - 18, fb - 4, fb + 6, zp + H * panel * 0.22, H - 8 - H * panel * 0.22, r=4, bev=1)
    zk = z0 + H * kick
    p.box("dark", x0 + 4, x1 - 4, fb - 1, fb + 6, zk - 3, zk, bev=0)                            # 아래 이음선
    p.box("lightgrey" if panel_mat == "white" else "dark", x0 + 30, x0 + 110, fb - 2, fb + 6, z0 + 14, zk - 14, r=4, bev=1)
    R = W * door / 2
    cz = z0 + (zp - z0) * door_z + (zk - z0) * 0.2
    _drum_door(p, 0, cz, f, R, ring, bulge, face)
    return p


def wash_tower(W, D, H, mid=0.5, band=0.075, door=0.70, ring="black", bulge=50, **_):
    """워시타워: 아래 세탁기 + 위 건조기, 가운데 조작부."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    fb = f + bulge
    p.box("finish", x0, x1, fb, b, 14, H, r=14, ax="z", bev=5)
    _feet(p, W, fb + 60, b - 60)
    zc = H * mid
    hb = H * band / 2
    p.box("black", x0 + 6, x1 - 6, fb - 3, fb + 12, zc - hb, zc + hb, r=6, bev=1.5)
    p.cyl("chrome", "y", (0, fb - 12, zc), hb * 0.62, 20, bev=3)
    p.box("dark", x0 + 4, x1 - 4, fb - 1, fb + 6, zc + hb + 4, zc + hb + 7, bev=0)
    R = W * door / 2
    _drum_door(p, 0, (zc - hb + 14) / 2 + 30, f, R, ring, bulge)
    _drum_door(p, 0, (zc + hb + H) / 2 - 10, f, R, ring, bulge)
    p.box("dark", x0 + 30, x0 + 110, fb - 2, fb + 6, 30, 70, r=4, bev=1)
    return p


def mini_wash(W, D, H, **_):
    """미니워시: 세탁기 밑에 넣는 낮은 서랍형. 앞판을 당겨 연다."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    p.box("body", x0 + 4, x1 - 4, f + 40, b, 12, H, r=8, ax="z", bev=3)
    _feet(p, W, f + 90, b - 60, h=12)
    p.box("finish", x0, x1, f, f + 46, 18, H - 4, r=10, bev=3)
    p.box("dark", x0 + W * 0.22, x1 - W * 0.22, f - 0.6, f + 16, H - 62, H - 34, r=10, bev=0.5)   # 손잡이 홈
    p.box("black", x1 - 150, x1 - 40, f - 1, f + 5, H * 0.42, H * 0.42 + 26, r=5, bev=0.6)
    return p


def top_loader(W, D, H, deck=0.2, lid="#23252A/g", panel="back", **_):
    """통돌이: 네모난 몸통, 비스듬한 윗면에 유리 뚜껑, 뒤쪽에 조작부."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    zb = H * (1 - deck)                              # 몸통 높이
    zf = zb + H * deck * 0.25                        # 윗면 앞 높이
    p.box("finish", x0, x1, f, b, 16, zb, r=22, ax="z", bev=6)
    p.box("dark", x0 + 16, x1 - 16, f + 16, b - 16, 0, 18, r=14, ax="z", bev=2)
    # 윗판: 옆에서 본 단면 (앞이 낮고 뒤가 높다)
    top = [(f, zb - 2), (b, zb - 2), (b, H), (b - D * 0.2, H), (b - D * 0.26, zf + (H - zf) * 0.7), (f + 30, zf), (f, zf - 14)]
    p.ext("finish", "x", top, x0, x1, bev=6)
    # 뚜껑: 윗면 기울기를 따라 얹힌 얇은 판
    y_a, y_b = f + 40, b - D * 0.28
    z_a = zf + 3
    z_b = zf + (H - zf) * 0.62
    lid_pts = [(y_a, z_a), (y_b, z_b), (y_b, z_b + 9), (y_a, z_a + 9)]
    p.ext(lid, "x", lid_pts, x0 + 36, x1 - 36, bev=3)
    p.ext("dark", "x", [(y_a - 10, z_a - 1), (y_b + 8, z_b - 1), (y_b + 8, z_b + 5), (y_a - 10, z_a + 5)], x0 + 26, x1 - 26, bev=2)
    p.box("black", x0 + W * 0.16, x1 - W * 0.16, b - D * 0.2 + 6, b - D * 0.04, H - 1, H + 1.2, r=8, ax="z", bev=0.4)  # 조작부
    p.box("dark", -80, 80, f - 0.5, f + 12, zf - 40, zf - 22, r=8, bev=0.5)                      # 뚜껑 손잡이 홈
    return p


# ---------------------------------------------------------------- TV
def tv(W, D, H, stand="feet", sf=0.07, pos=0.09, sw=0.24, thick=None, bezel=6, frame=None, **_):
    """TV. stand: feet(양쪽 발) | pedestal(가운데 받침) | wall(벽걸이, 받침 없음) | floor(바닥 스탠드) | easel.

    sf: 받침이 차지하는 높이 비율(제품 사진에서 잰 값). pos: 발 위치(끝에서부터 폭 비율). sw: 가운데 받침 폭 비율.
    """
    p = Parts()
    x0, x1 = -W / 2, W / 2
    wall = stand == "wall"
    t = thick or (min(D, 60) if wall else max(22, min(58, W * 0.028)))
    hs = 0 if wall else H * sf
    yc = 0 if not wall else 0
    f = -t / 2 if not wall else -D / 2
    if wall:
        t = D
    zb, zt = hs, H
    slim = t * 0.45 if t > 30 else t
    p.box("finish", x0, x1, f, f + slim, zb, zt, r=5, bev=1.2)                                  # 패널
    p.box("screen", x0 + bezel, x1 - bezel, f - min(0.8, t * 0.02), f + min(3, t * 0.3), zb + bezel + 4, zt - bezel, r=2, bev=0.3)
    if frame:                                         # 갤러리 TV 액자 테두리
        p.box(frame, x0, x1, f - 6, f + slim, zb, zt, r=3, bev=1.5)
        p.box("screen", x0 + 24, x1 - 24, f - 6.8, f, zb + 24, zt - 24, r=1, bev=0.3)
    if t > 30:                                        # 뒤쪽 두툼한 부분
        p.box("dark", x0 + W * 0.08, x1 - W * 0.08, f + slim - 2, f + t, zb + (zt - zb) * 0.06, zb + (zt - zb) * 0.72, r=18, bev=6)
    if stand == "feet":
        fw = max(18, W * 0.016)
        for sx in (-1, 1):
            cx = sx * (W / 2 - W * pos)
            # 옆에서 보면 ㅅ 모양 발: 앞뒤로 뻗고 가운데가 패널 밑에 닿는다
            pts = [(-D / 2, 0), (-D / 2 + 26, 0), (0, hs - 8), (D / 2 - 26, 0), (D / 2, 0), (10, hs + 14), (-10, hs + 14)]
            p.ext("dark", "x", pts, cx - fw / 2, cx + fw / 2, bev=3)
    elif stand == "pedestal":
        bw = W * sw
        p.box("#3A3B3E/m", -bw / 2, bw / 2, -D / 2, D / 2, 0, max(8, hs * 0.14), r=min(60, D * 0.3), ax="z", bev=3)
        nw = min(bw * 0.6, 260)
        neck = [(D * 0.05, 0), (D * 0.32, 0), (t / 2 + 20, hs + (zt - zb) * 0.28), (t / 2 - 4, hs + (zt - zb) * 0.28)]
        p.ext("dark", "x", neck, -nw / 2, nw / 2, bev=4)
    elif stand == "floor":                            # 바닥까지 내려오는 다리 둘
        for sx in (-1, 1):
            cx = sx * (W / 2 - W * pos)
            p.box("#B9BCC0/m", cx - 14, cx + 14, -9, 9, 0, hs + 40, r=4, ax="z", bev=2)
            p.box("#B9BCC0/m", cx - 16, cx + 16, -D / 2, D / 2, 0, 16, r=6, ax="x", bev=3)
    elif stand == "cabinet":                          # OLED T: 아래 장 위에 투명 화면
        pass
    if wall and D > 40:
        p.box("dark", x0 + W * 0.2, x1 - W * 0.2, D / 2 - 6, D / 2, H * 0.3, H * 0.7, r=10, bev=2)
    if not wall and stand in ("feet", "floor"):
        pass
    return p


def tv_cabinet(W, D, H, screen_h=0.6, **_):
    """SIGNATURE OLED T: 낮은 장 위에 투명 화면이 서 있다."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    zc = H * (1 - screen_h)
    for sx in (-1, 1):
        p.box("#C9CCD0/m", sx * (W / 2 - 14) - 14, sx * (W / 2 - 14) + 14, f, b, 0, zc, r=3, ax="x", bev=2)
    p.box("#C9CCD0/m", x0, x1, f, b, zc - 60, zc, r=4, ax="x", bev=3)
    p.box("#C9CCD0/m", x0, x1, f, b, zc * 0.45 - 12, zc * 0.45 + 12, r=3, ax="x", bev=2)
    p.box("#C9CCD0/m", x0, x1, f, b, 0, 24, r=3, ax="x", bev=2)
    p.box("finish", x0 + 10, x1 - 10, -30, 30, zc - 2, zc + 46, r=6, bev=2)
    p.box("glass", x0 + 16, x1 - 16, -5, 5, zc + 40, H, r=4, bev=1)
    p.box("black", x0 + 16, x1 - 16, -6, 6, zc + 40, zc + 52, bev=0.5)
    return p


def stand_screen(W, D, H, screen_w=None, screen_h=None, base_r=None, **_):
    """스탠바이미처럼 기둥 위에 화면이 달린 이동식 스크린."""
    p = Parts()
    sw = screen_w or W
    sh = screen_h or sw * 0.58
    br = base_r or min(W, D) / 2
    p.lathe("finish", (0, D / 2 - br), [(0, 0), (br, 0), (br, 16), (br - 8, 26), (0, 26)], seg=48)
    p.cyl("finish", "z", (0, D / 2 - br, (H - sh / 2) / 2 + 10), 17, H - sh / 2 - 20, bev=2)
    p.box("finish", -sw / 2, sw / 2, -D / 2, -D / 2 + 22, H - sh, H, r=8, bev=2)
    p.box("screen", -sw / 2 + 9, sw / 2 - 9, -D / 2 - 0.8, -D / 2 + 3, H - sh + 9, H - 9, r=3, bev=0.3)
    p.box("finish", -70, 70, -D / 2 + 20, D / 2 - br + 20, H - sh / 2 - 60, H - sh / 2 + 60, r=20, bev=4)
    return p


# ---------------------------------------------------------------- 에어컨
def ac_stand(W, D, H, kind="cool", split=0.42, **_):
    """스탠드 에어컨. kind: cool(양옆 세로 바람구멍) | winner(옆이 둥글게 파인 창 + 가운데 원) | tower(위쪽 원형 표시창) | plain."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    r = min(W, D) * 0.16
    zs = H * split
    p.box("finish", x0, x1, f + 6, b, 24, H, r=r, ax="z", bev=6)                      # 몸통
    p.box("dark", x0 + 14, x1 - 14, f + 20, b - 14, 0, 26, r=r * 0.8, ax="z", bev=2)  # 받침
    p.box("finish_matte" if kind == "tower" else "finish", x0 + 5, x1 - 5, f, f + 22, 30, zs - 3, r=10, bev=3)   # 아래 앞판
    p.box("finish", x0 + 5, x1 - 5, f, f + 22, zs + 3, H - 6, r=10, bev=3)            # 위 앞판
    p.box("dark", x0 + 8, x1 - 8, f + 8, f + 20, zs - 5, zs + 5, bev=0)
    p.box("dark", x0 + W * 0.12, x1 - W * 0.12, b - 3, b + 0.01, H * 0.18, H * 0.8, bev=0)   # 뒤 흡입구
    if kind == "cool":
        for sx in (-1, 1):
            cx = sx * W * 0.30
            p.box("black", cx - 15, cx + 15, f - 0.8, f + 12, zs + H * 0.07, H - H * 0.05, r=14, bev=0.6)
        p.box("black", -26, 26, f - 0.8, f + 6, zs - 90, zs - 60, r=6, bev=0.4)
    elif kind == "winner":
        z0, z1 = zs + H * 0.05, H - H * 0.035
        zc, hh = (z0 + z1) / 2, (z1 - z0) / 2
        for sx in (-1, 1):                              # 옆으로 휜 검은 창
            pts = []
            for i in range(25):
                t = -1 + 2 * i / 24
                pts.append((sx * (W * 0.44 - W * 0.30 * (1 - t * t) ** 0.5 * 0.55), zc + hh * t))
            outer = [(sx * W * 0.45, zc + hh * (1 - 2 * i / 24)) for i in range(25)]
            poly = pts + outer
            if sx < 0:
                poly = poly[::-1]
            p.ext("black", "y", poly, f - 0.8, f + 12, bev=0.4)
        p.cyl("chrome", "y", (0, f - 1, zc + hh * 0.25), W * 0.085, 5, bev=1.5)
        p.cyl("#C7473A/s", "y", (0, f - 3.6, zc + hh * 0.25), W * 0.05, 1.5, bev=0.4)
        for i in range(4):
            p.cyl("dark", "y", (0, f - 0.6, zc - hh * 0.05 - i * 34), 5, 2, bev=0.3)
    elif kind == "tower":
        rc = W * 0.33
        zc = H - rc - H * 0.035
        p.cyl("black", "y", (0, f + 2, zc), rc, 10, bev=2, seg=64)
        p.torus("chrome", "y", (0, f - 2, zc), rc * 0.97, 2.2)
        for sx in (-1, 1):                              # 옆면 세로 바람구멍
            p.box("black", sx * (W / 2) - 1.2, sx * (W / 2) + 1.2, f + D * 0.3, f + D * 0.5, zs + H * 0.05, zc - rc - 30, bev=0)
        p.box("dark", -W * 0.38, W * 0.38, f - 0.6, f + 10, zs + H * 0.03, zs + H * 0.03 + 14, r=5, bev=0.3)
    return p


def ac_wall(W, D, H, strip=None, **_):
    """벽걸이 에어컨: 앞이 둥글게 나온 몸통, 아래 앞쪽에 바람 나오는 검은 틈과 날개."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    # 옆에서 본 단면 (y 앞 -, z 위): 윗면 → 둥근 앞면 → 아래로 접히는 턱
    prof = [(b, 0), (b, H), (f + D * 0.34, H), (f + D * 0.13, H * 0.95), (f + D * 0.03, H * 0.84), (f, H * 0.7),
            (f, H * 0.36), (f + D * 0.06, H * 0.27), (f + D * 0.5, H * 0.01), (f + D * 0.56, 0)]
    p.ext("finish", "x", prof, x0, x1, bev=min(14, H * 0.05))
    # 바람 나오는 틈: 앞 아래 비스듬한 면을 따라 파인 검은 띠
    a0, a1 = (f + D * 0.07, H * 0.262), (f + D * 0.47, H * 0.028)
    nx, nz = -(a1[1] - a0[1]), (a1[0] - a0[0])
    ln = math.hypot(nx, nz)
    nx, nz = nx / ln, nz / ln                      # 면에서 바깥(앞 아래)쪽
    def off(pt, d):
        return (pt[0] - nx * d, pt[1] - nz * d)
    p.ext("black", "x", [off(a0, 1.2), off(a1, 1.2), off(a1, -8), off(a0, -8)], x0 + W * 0.06, x1 - W * 0.06, bev=0.4)
    m0 = (a0[0] + (a1[0] - a0[0]) * 0.06, a0[1] + (a1[1] - a0[1]) * 0.06)
    m1 = (a0[0] + (a1[0] - a0[0]) * 0.62, a0[1] + (a1[1] - a0[1]) * 0.62)
    p.ext("finish", "x", [off(m0, 2.6), off(m1, 2.6), off(m1, 0.2), off(m0, 0.2)], x0 + W * 0.07, x1 - W * 0.07, bev=0.8)   # 날개
    p.box("dark", x0 + W * 0.05, x1 - W * 0.05, f + D * 0.4, b - D * 0.1, H - 0.4, H + 0.01, bev=0)       # 윗면 흡입구
    if strip:                                      # 듀얼쿨: 앞면 아래쪽 어두운 띠
        p.box("black", x0 + 10, x1 - 10, f - 0.8, f + 8, H * 0.38, H * 0.47, r=4, bev=0.5)
    p.box("black", x1 - W * 0.17, x1 - W * 0.08, f - 0.6, f + 5, H * 0.5, H * 0.5 + 9, r=4, bev=0.3)        # 표시등
    return p


def ac_portable(W, D, H, **_):
    """이동식 에어컨: 둥근 몸통, 윗면 바람구멍, 바퀴."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    p.box("finish", x0, x1, f, b, 34, H, r=min(W, D) * 0.2, ax="z", bev=24)
    p.box("dark", x0 + 30, x1 - 30, f + 30, b - 30, 22, 40, r=40, ax="z", bev=2)
    for sx in (-1, 1):
        for y in (f + 80, b - 80):
            p.cyl("dark", "x", (sx * (W / 2 - 80), y, 17), 17, 22, bev=3)
    p.box("black", x0 + W * 0.16, x1 - W * 0.16, f + D * 0.12, f + D * 0.5, H - 1, H + 0.01, r=30, ax="z", bev=0)
    for i in range(6):
        y = f + D * 0.16 + i * D * 0.055
        p.box("finish", x0 + W * 0.18, x1 - W * 0.18, y, y + D * 0.022, H - 6, H, r=4, ax="x", bev=1)
    p.box("black", -W * 0.2, W * 0.2, f + D * 0.6, f + D * 0.74, H - 1, H + 0.01, r=14, ax="z", bev=0)
    p.box("dark", x0 + W * 0.2, x1 - W * 0.2, b - 2, b + 0.01, H * 0.3, H * 0.85, r=10, bev=0)
    return p


# ---------------------------------------------------------------- 공기청정기·가습기·제습기
def purifier_round(W, D, H, body="dots", stages=1, top="display", base=0.05, cap=0.12, body_mat=None, booster=False,
                   taper=0.0, **_):
    """원통형 공기청정기. body: dots(구멍 뚫린 판) | slats(세로 살). stages 2면 위아래 두 단."""
    p = Parts()
    R = min(W, D) / 2
    zb = H * base
    zt = H * (1 - cap)
    if booster:
        zt = H * (1 - cap - 0.1)
    p.lathe("dark" if body == "slats" else "finish", (0, 0), [(0, 0), (R * 0.9, 0), (R * 0.93, zb * 0.6), (R * 0.86, zb), (0, zb)])
    seg_h = (zt - zb) / stages
    for s in range(stages):
        a, b = zb + s * seg_h + (6 if s else 0), zb + (s + 1) * seg_h - 6
        r0, r1 = R * (1 - taper * (1 - s / stages)), R * (1 - taper * (1 - (s + 1) / stages))
        if body == "slats":
            p.lathe(body_mat or "#6F6659/s", (0, 0), [(r0 * 0.985, a), (r1 * 0.985, b)], ribs=(44, R * 0.06))
            p.lathe("dark", (0, 0), [(r0 * 0.88, a), (r1 * 0.88, b)])
        else:
            p.lathe("finish_dots", (0, 0), [(r0 * 0.99, a + 20), (r1 * 0.99, b - 20)], uv=7.0)
            p.lathe("finish", (0, 0), [(r0, a), (r0, a + 22)])
            p.lathe("finish", (0, 0), [(r1, b - 22), (r1, b)])
        if s:
            p.lathe("dark", (0, 0), [(R * 0.9, a - 14), (R * 0.9, a + 2)])
    z = zt
    if booster:                                         # 위로 올라오는 클린부스터
        p.lathe("dark", (0, 0), [(R * 0.5, z - 4), (R * 0.5, z + H * 0.04)])
        z += H * 0.04
        p.lathe("finish", (0, 0), [(0, z), (R * 0.96, z), (R, z + 10), (R, H - 12), (R * 0.96, H), (0, H)])
        p.lathe("finish_dots", (0, 0), [(R * 1.0, z + 12), (R * 1.0, H - 30)], uv=6.0)
        p.cyl("black", "z", (0, 0, H - 0.5), R * 0.7, 2, bev=0.5)
        return p
    p.lathe("finish", (0, 0), [(R, z), (R, H - 14), (R * 0.97, H - 4), (R * 0.9, H), (0, H)])
    if top == "display":
        p.cyl("black", "z", (0, 0, H + 0.2), R * 0.72, 2.4, bev=0.6)
        p.torus("dark", "z", (0, 0, H - 1), R * 0.80, 3)
    elif top == "grille":
        p.cyl("dark", "z", (0, 0, H + 0.2), R * 0.8, 2, bev=0.5)
        for i in range(1, 5):
            p.torus("finish", "z", (0, 0, H + 1), R * 0.18 * i, 3.5)
    return p


def purifier_panel(W, D, H, legs=0.24, **_):
    """월핏: 얇고 넓은 판 모양 공기청정기. 구멍 뚫린 앞판, 가는 다리."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    zl = H * legs
    t = min(D * 0.62, 120)
    p.box("finish", x0, x1, -t / 2, t / 2, zl, H, r=min(60, H * 0.12), bev=10)
    p.box("finish_dots", x0 + 26, x1 - 26, -t / 2 - 1.5, -t / 2 + 6, zl + 26, H - 26, r=min(44, H * 0.09), bev=0.6, uvs=11.0)
    p.box("dark", x0 + 40, x1 - 40, -t / 2 + 20, t / 2 - 20, H - 1, H + 0.01, r=14, ax="z", bev=0)
    for sx in (-1, 1):
        cx = sx * (W / 2 - min(90, W * 0.14))
        p.tube("finish", [(cx, f + 6, 6), (cx, f + 12, zl * 0.5), (cx, -t * 0.2, zl + 10)], 6)
        p.tube("finish", [(cx, b - 6, 6), (cx, b - 12, zl * 0.5), (cx, t * 0.2, zl + 10)], 6)
        p.tube("finish", [(cx, f + 6, 6), (cx, b - 6, 6)], 6, smooth=False)
    return p


def aero_tower(W, D, H, **_):
    """에어로타워: 살이 있는 원뿔 받침 위에 길쭉한 날개 둘."""
    p = Parts()
    R = min(W, D) / 2
    zb = H * 0.30
    p.lathe("dark", (0, 0), [(0, 0), (R * 0.92, 0), (R * 0.92, 10), (0, 10)])
    p.lathe("#6F6659/s", (0, 0), [(R, 8), (R * 0.62, zb)], ribs=(40, R * 0.07))
    p.lathe("dark", (0, 0), [(R * 0.9, 8), (R * 0.55, zb)])
    p.lathe("finish", (0, 0), [(R * 0.66, zb - 4), (R * 0.6, zb + 22), (0, zb + 22)])
    for sx in (-1, 1):
        p.ell("finish", (sx * R * 0.36, 0, (zb + H) / 2 + 6), (R * 0.24, R * 0.42, (H - zb) / 2 + 6), n=3.2)
    p.box("black", -6, 6, -R * 0.36, -R * 0.34, zb + 60, H - 80, bev=0)
    return p


def aero_ring(W, D, H, **_):
    """에어로부스터: 살이 있는 기둥 위에 둥근 고리 머리."""
    p = Parts()
    R = min(W, D) / 2
    rr = R * 0.92
    zc = H - rr
    zn = zc - rr - 20
    p.lathe("dark", (0, 0), [(0, 0), (R, 0), (R, 14), (0, 14)])
    p.lathe("#7C7F84/s", (0, 0), [(R * 0.96, 12), (R * 0.96, zn)], ribs=(34, R * 0.07))
    p.lathe("dark", (0, 0), [(R * 0.86, 12), (R * 0.86, zn)])
    p.lathe("finish", (0, 0), [(R * 0.97, zn - 4), (R * 0.6, zn + 26), (0, zn + 26)])
    p.torus("finish", "y", (0, 0, zc), rr - R * 0.13, R * 0.13)
    p.cyl("white", "y", (0, 0, zc), rr - R * 0.2, R * 0.2, bev=4)
    p.torus("#8FB7E8/g", "y", (0, -R * 0.1, zc), rr - R * 0.22, 3)
    return p


def aero_table(W, D, H, cat=False, **_):
    """에어로퍼니처: 살이 있는 원뿔 몸통 위에 둥근 상판. cat이면 위에 반구 자리와 발판(캣타워)."""
    p = Parts()
    if cat:
        R = D / 2 * 0.62
        cx = W / 2 - D / 2
        zt = H * 0.62
        p.lathe("dark", (cx, 0), [(0, 0), (R * 0.95, 0), (R * 0.95, 12), (0, 12)])
        p.lathe("#3B3B3D/s", (cx, 0), [(R, 10), (R * 0.72, zt)], ribs=(40, R * 0.07))
        p.lathe("finish", (cx, 0), [(R, 10), (R * 0.72, zt)], seg=40)
        p.lathe("finish", (cx, 0), [(R * 0.76, zt - 6), (R * 0.9, zt + 20), (0, zt + 20)])
        Rb = D / 2
        prof = [(0, zt + 30)] + [(Rb * math.sin(math.radians(a)), H - Rb * 0.02 - (H - zt - 40) * math.cos(math.radians(a))) for a in range(10, 91, 10)]
        p.lathe("finish", (cx, 0), prof + [(Rb * 0.93, H), (Rb * 0.88, H - 12)] + [
            (Rb * 0.86 * math.sin(math.radians(a)), H - 14 - (H - zt - 80) * 0.8 * math.cos(math.radians(a))) for a in range(90, 9, -10)] + [(0, zt + 78)])
        p.lathe("#D9CBB7/f", (cx, 0), [(0, H - (H - zt) * 0.55), (Rb * 0.6, H - (H - zt) * 0.5), (Rb * 0.84, H - 26), (Rb * 0.6, H - 40), (0, H - 60)])
        sx = -W / 2 + D * 0.3                           # 발판
        p.cyl("finish", "z", (sx, 0, H * 0.33), D * 0.3, 26, bev=8)
        p.cyl("#D9CBB7/f", "z", (sx, 0, H * 0.33 + 16), D * 0.27, 10, bev=4)
        p.tube("finish", [(sx, 0, H * 0.33), (sx + 40, 0, H * 0.2), (cx - R * 0.8, 0, H * 0.14)], 14)
        p.box("finish", -W / 2, cx + R * 0.6, -D * 0.34, D * 0.34, 0, 14, r=D * 0.3, ax="z", bev=4)
        return p
    R = min(W, D) / 2
    zt = H * 0.86
    Rb = R * 0.62
    p.lathe("dark", (0, 0), [(0, 0), (Rb * 0.95, 0), (Rb * 0.95, 12), (0, 12)])
    p.lathe("#2F2F31/s", (0, 0), [(Rb, 10), (Rb * 0.72, zt - 60)], ribs=(40, Rb * 0.07))
    p.lathe("finish", (0, 0), [(Rb * 0.97, 10), (Rb * 0.70, zt - 60)], seg=40)
    p.lathe("finish", (0, 0), [(Rb * 0.74, zt - 64), (Rb * 0.5, zt), (0, zt)])
    p.lathe("finish", (0, 0), [(0, zt), (R * 0.5, zt), (R * 0.96, H - 26), (R, H - 14), (R, H - 4), (R * 0.985, H), (0, H)])
    return p


def pot(W, D, H, kind="hw300", **_):
    """항아리 모양 가습기."""
    p = Parts()
    R = W / 2
    sy = D / W
    if kind == "hw300":      # 허리가 잘록한 흰 항아리, 위에 조작 고리
        prof = [(0, 0), (R * 0.62, 0), (R * 0.9, H * 0.08), (R, H * 0.26), (R * 0.9, H * 0.48), (R * 0.84, H * 0.56),
                (R * 0.92, H * 0.74), (R * 0.9, H * 0.9), (R * 0.8, H * 0.975), (R * 0.7, H), (0, H)]
        p.lathe("finish", (0, 0), prof, sy=sy)
        p.cyl("black", "z", (0, 0, H + 0.2), R * 0.52, 2, bev=0.5)
        p.torus("lightgrey", "z", (0, 0, H - 2), R * 0.62, 5)
    else:                    # 아래가 넓고 회색 받침이 있는 통
        prof = [(0, 0), (R * 0.9, 0), (R, H * 0.06), (R, H * 0.14), (R * 0.96, H * 0.16), (R * 0.9, H * 0.6), (R * 0.82, H * 0.9),
                (R * 0.72, H * 0.985), (R * 0.6, H), (0, H)]
        p.lathe("finish", (0, 0), prof, sy=sy)
        p.lathe("#9EA1A5/s", (0, 0), [(R * 1.0, H * 0.02), (R * 1.0, H * 0.13)], sy=sy)
        p.cyl("black", "z", (0, 0, H + 0.2), R * 0.42, 2, bev=0.5)
        p.torus("lightgrey", "z", (0, 0, H - 3), R * 0.56, 6)
    return p


def glow_tower(W, D, H, **_):
    """하이드로에센셜: 흰 원통, 위쪽에 불빛이 비치는 띠, 둥근 받침."""
    p = Parts()
    R = min(W, D) / 2
    p.lathe("finish", (0, 0), [(0, 0), (R, 0), (R, 12), (R * 0.9, 20), (0, 20)])
    p.lathe("finish", (0, 0), [(R * 0.84, 18), (R * 0.84, H * 0.86)])
    p.lathe("glow", (0, 0), [(R * 0.82, H * 0.86), (R * 0.82, H * 0.93)])
    p.lathe("finish", (0, 0), [(R * 0.84, H * 0.93), (R * 0.84, H - 8), (R * 0.8, H), (0, H)])
    p.cyl("dark", "z", (0, 0, H + 0.2), R * 0.5, 1.5, bev=0.4)
    p.box("black", -14, 14, -R * 0.84 - 0.8, -R * 0.8, H * 0.6, H * 0.6 + 60, r=8, bev=0.3)
    return p


def dehumidifier(W, D, H, **_):
    """제습기: 둥근 흰 몸통, 위 손잡이, 아래 옆에 비치는 물통, 바퀴."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    r = min(W, D) * 0.22
    p.box("finish", x0, x1, f, b, 30, H * 0.94, r=r, ax="z", bev=20)
    for sx in (-1, 1):
        for y in (f + 60, b - 60):
            p.cyl("dark", "x", (sx * (W / 2 - 70), y, 15), 15, 20, bev=3)
    p.box("#AEB4BA/g", x0 + W * 0.42, x1 + 0.0, f - 0.0, f + D * 0.7, 46, H * 0.36, r=r * 0.8, ax="z", bev=6)      # 물통
    p.box("dark", x0 + W * 0.42 - 3, x0 + W * 0.42, f - 0.5, f + 20, 46, H * 0.36, bev=0)
    # 윗면 조작부와 손잡이
    p.box("dark", x0 + W * 0.16, x1 - W * 0.16, f + D * 0.2, b - D * 0.2, H * 0.94 - 2, H * 0.94 + 1, r=30, ax="z", bev=0.5)
    p.tube("#C9CCD0/m", [(x1 - W * 0.12, 0, H * 0.84), (x1 - W * 0.04, 0, H * 0.96), (x1 - W * 0.2, 0, H - 9), (x0 + W * 0.3, 0, H - 9)], 9)
    p.box("dark", x0 + 30, x1 - 30, b - 2, b + 0.01, H * 0.4, H * 0.84, r=14, bev=0)
    return p


# ---------------------------------------------------------------- 주방 소형
def microwave(W, D, H, panel=0.24, dials=0, handle=False, door="black", feet=True, window=0.62, **_):
    """전자레인지: 왼쪽 문(가운데 창) + 오른쪽 조작부. dials: 다이얼 수(0이면 버튼식)."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    fh = 52 if handle else (21 if dials else 0)
    fd = f + fh
    z0 = 10 if feet else 0
    p.box("finish", x0, x1, fd + 22, b, z0, H, r=10, bev=4)
    if feet:
        _feet(p, W, fd + 50, b - 40, r=12, h=10)
    xp = x1 - W * panel
    dm = {"black": "black", "same": "finish"}[door]
    p.box(dm, x0 + 2, xp - 2, fd, fd + 24, z0 + 4, H - 3, r=8, bev=2)                         # 문
    wx0, wx1 = x0 + (xp - x0) * (1 - window) / 2, xp - (xp - x0) * (1 - window) / 2
    p.box("window", wx0, wx1, fd - 1, fd + 6, z0 + H * 0.2, H - H * 0.2, r=12, bev=0.6)
    pm = "black" if door == "black" else "finish"
    p.box(pm, xp + 2, x1 - 2, fd, fd + 24, z0 + 4, H - 3, r=8, bev=2)                         # 조작부
    cx = (xp + x1) / 2
    pw = W * panel
    if dials:
        for i in range(dials):
            cz = z0 + (H - z0) * (0.7 - 0.4 * i if dials > 1 else 0.38)
            p.cyl("chrome" if door == "black" else "#D8D2C6/s", "y", (cx, fd - 9, cz), pw * 0.26, 20, bev=4)
            p.box("dark", cx - 1.5, cx + 1.5, fd - 20.5, fd - 19, cz + pw * 0.08, cz + pw * 0.22, bev=0)
        if dials == 1:
            p.box("#101113/g", cx - pw * 0.33, cx + pw * 0.33, fd - 0.8, fd + 4, H * 0.66, H * 0.84, r=4, bev=0.4)
    else:
        p.box("#101113/g", cx - pw * 0.36, cx + pw * 0.36, fd - 0.8, fd + 4, H * 0.72, H * 0.86, r=4, bev=0.4)
        for j in range(4):
            for i in range(3):
                bx, bz = cx + (i - 1) * pw * 0.25, H * 0.6 - j * H * 0.1
                p.box("#3A3C40/s", bx - pw * 0.09, bx + pw * 0.09, fd - 1, fd + 3, bz - H * 0.03, bz + H * 0.03, r=3, bev=0.3)
        p.box("#C9CCD0/m", cx - pw * 0.34, cx + pw * 0.34, fd - 1.4, fd + 3, z0 + H * 0.06, z0 + H * 0.15, r=4, bev=0.5)   # 문 열림 단추
    if handle:
        hx = xp - 26
        _bar(p, (hx, z0 + H * 0.16), (hx, H - H * 0.16), fd, t=8)
    p.box("dark", x0 + W * 0.1, x1 - W * 0.1, b - 2, b + 0.01, H * 0.25, H * 0.75, bev=0)
    return p


def oven(W, D, H, panel=0.2, handle="bar", dials=0, **_):
    """광파오븐: 위 조작부 띠 + 아래로 여는 유리문(가로 손잡이), 받침 발."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    fh = 38
    fd = f + fh
    p.box("finish", x0, x1, fd + 20, b, 14, H, r=12, bev=4)
    _feet(p, W, fd + 60, b - 50, r=16, h=14)
    zp = H * (1 - panel)
    p.box("finish", x0 + 2, x1 - 2, fd, fd + 22, zp + 2, H - 3, r=8, bev=2)                   # 조작부
    p.box("#101113/g", -W * 0.16, W * 0.16, fd - 0.8, fd + 4, zp + H * panel * 0.25, H - H * panel * 0.25, r=4, bev=0.4)
    if dials:
        for sx in (-1, 1):
            p.cyl("chrome", "y", (sx * W * 0.33, fd - 9, (zp + H) / 2), H * panel * 0.28, 20, bev=4)
    else:
        for i in range(4):
            for sx in (-1, 1):
                bx = sx * (W * 0.24 + i * W * 0.055)
                p.cyl("#C9CCD0/m", "y", (bx, fd - 1, (zp + H) / 2), 9, 3, bev=0.8)
    p.box("finish", x0 + 2, x1 - 2, fd, fd + 22, 18, zp - 2, r=8, bev=2)                      # 문
    p.box("window", x0 + W * 0.09, x1 - W * 0.09, fd - 1, fd + 6, 18 + (zp - 18) * 0.18, zp - (zp - 18) * 0.2, r=10, bev=0.6)
    _bar(p, (x0 + W * 0.1, zp - (zp - 18) * 0.1), (x1 - W * 0.1, zp - (zp - 18) * 0.1), fd, t=8)
    p.box("dark", x0 + W * 0.1, x1 - W * 0.1, b - 2, b + 0.01, H * 0.25, H * 0.75, bev=0)
    return p


def cooktop(W, D, H, zones=((-0.24, 0.16, 105), (-0.24, -0.2, 85), (0.2, 0.0, 115)), knob=False, under=None, **_):
    """인덕션·하이브리드: 얇은 검은 유리 상판 + 아래 몸체. zones = (x 비율, y 비율, 반지름 mm)."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    g = 6
    p.box("dark", x0 + 30, x1 - 30, f + 30, b - 30, 0, H - g, r=10, ax="z", bev=2)
    p.box("finish", x0, x1, f, b, H - g, H, r=8, ax="z", bev=1.5)
    for cx, cy, r in zones:
        p.torus("print", "z", (W * cx, -D * cy, H + 0.2), r, 1.1)
        p.torus("print", "z", (W * cx, -D * cy, H + 0.2), r * 0.42, 0.8)
    for i in range(5):
        p.cyl("print", "z", (-80 + i * 40, f + 38, H + 0.1), 7, 0.6, bev=0, seg=24)
    return p


def dishwasher_free(W, D, H, **_):
    """프리스탠딩 식기세척기: 어두운 상판, 위쪽 조작부 띠, 통짜 문, 아래 받침."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    p.box("body", x0, x1, f + 30, b, 60, H - 30, r=4, bev=3)
    p.box("#2E2F32/s", x0, x1, f + 4, b, H - 30, H, r=6, ax="x", bev=3)                       # 상판
    p.box("dark", x0 + 20, x1 - 20, f + 60, b - 20, 0, 62, bev=1)
    _feet(p, W, f + 80, b - 50, r=16, h=10)
    zc = H - 30 - H * 0.105
    p.box("finish", x0 + 1, x1 - 1, f, f + 30, zc + 2, H - 33, r=4, bev=2)                    # 조작부
    p.box("black", -W * 0.18, W * 0.18, f - 0.8, f + 4, zc + 22, H - 52, r=4, bev=0.4)
    p.box("finish", x0 + 1, x1 - 1, f, f + 30, 92, zc - 2, r=4, bev=2)                        # 문
    p.box("dark", x0 + 2, x1 - 2, f + 12, f + 30, zc - 3, zc + 3, bev=0)
    p.box("finish", x0 + 1, x1 - 1, f + 4, f + 30, 62, 88, r=3, bev=1.5)                      # 걸레받이
    return p


def plant_tray(W, D, H, **_):
    """틔운 미니: 낮은 흰 받침 + 위로 둥근 사각 고리(조명 손잡이)."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    zb = H * 0.3
    p.box("finish", x0, x1, f, b, 0, zb, r=min(40, D * 0.28), ax="z", bev=8)
    p.box("#E7E3DA/s", x0 + 16, x1 - 16, f + 14, b - 14, zb - 1, zb + 3, r=24, ax="z", bev=1)
    for i in range(5):
        cx = x0 + W * (0.18 + 0.16 * i)
        p.cyl("#4E8A3B/f", "z", (cx, 0, zb + 5), 16, 6, bev=2, seg=20)
    r = 11
    xa, xb = x0 + W * 0.07, x1 - W * 0.07
    p.tube("finish", [(xa, 0, zb - 6), (xa, 0, H - r - 40), (xa + 40, 0, H - r), (xb - 40, 0, H - r), (xb, 0, H - r - 40), (xb, 0, zb - 6)], r)
    p.box("glow", xa + 60, xb - 60, -7, 7, H - r * 2 - 0.5, H - r * 2 + 1.5, r=5, ax="z", bev=0.3)
    return p


def ironing(W, D, H, **_):
    """시스템 아이어닝: 다리미판 상판 + 가운데 기둥 받침."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    zt = H * 0.8
    # 상판: 한쪽이 뾰족한 다리미판 (위에서 본 모양)
    pts = [(x0 + W * 0.02, -D * 0.2), (x0 + W * 0.1, f), (x1 - W * 0.12, f), (x1, f + D * 0.2), (x1, b - D * 0.2), (x1 - W * 0.12, b), (x0 + W * 0.1, b), (x0 + W * 0.02, D * 0.2)]
    p.ext("#2B2C2F/f", "z", pts, zt, zt + 32, bev=10)
    p.ext("dark", "z", [(x * 0.97, y * 0.9) for x, y in pts], zt - 26, zt + 2, bev=6)
    p.box("finish", -W * 0.11, W * 0.11, f + D * 0.22, b - D * 0.22, 60, zt - 20, r=40, ax="z", bev=8)
    p.box("dark", -W * 0.16, W * 0.16, f + D * 0.05, b - D * 0.05, 0, 64, r=50, ax="z", bev=10)
    # 다리미 걸이와 다리미
    p.tube("#C9CCD0/m", [(x1 - W * 0.2, 0, zt + 30), (x1 - W * 0.16, 0, H - 30), (x1 - W * 0.3, 0, H - 8)], 5)
    p.ell("finish", (x1 - W * 0.36, 0, zt + 62), (W * 0.075, D * 0.13, 30), n=2.6)
    return p


# ---------------------------------------------------------------- 청소기
def robot_vac(W, D, H, lidar=True, square=False, **_):
    """로봇청소기 본체: 납작한 원반, 위에 센서 돌기와 단추."""
    p = Parts()
    R = min(W, D) / 2
    hb = H - (22 if lidar else 0)
    if square:
        p.box("finish", -W / 2, W / 2, -D / 2, D / 2, 8, hb, r=R * 0.55, ax="z", bev=8)
        for sx in (-1, 1):
            p.cyl("#D8D5CE/f", "z", (sx * W * 0.24, D * 0.1, 5), W * 0.22, 10, bev=3)
    else:
        p.lathe("finish", (0, 0), [(0, 8), (R * 0.9, 8), (R, 22), (R, hb - 10), (R * 0.97, hb), (0, hb)])
        p.lathe("dark", (0, 0), [(0, 0), (R * 0.82, 0), (R * 0.86, 10), (0, 10)])
    p.lathe("dark", (0, 0), [(R * 1.002, 26), (R * 1.002, hb * 0.62)]) if not square else None       # 범퍼 띠
    if lidar:
        p.cyl("dark", "z", (0, -R * 0.2, hb + 11), R * 0.24, 22, bev=4)
        p.cyl("black", "z", (0, -R * 0.2, hb + 22.2), R * 0.2, 1.2, bev=0.3)
    else:
        p.cyl("black", "z", (0, 0, H), R * 0.5, 1.2, bev=0.3) if False else p.cyl("black", "z", (0, 0, hb + 0.3), R * 0.5, 1.5, bev=0.3)
    p.box("black", -R * 0.3, R * 0.3, R * 0.5, R * 0.62, hb - 0.4, hb + 0.6, r=6, ax="z", bev=0.2)
    return p


def stick_vac(W, D, H, style="a7", **_):
    """무선청소기를 거치대에 세워 둔 모습: 받침·기둥 + 손잡이 본체 + 긴 관 + 흡입구."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    # 거치대
    p.box("dark", x0, x1, f, b, 0, 16, r=min(W, D) * 0.3, ax="z", bev=5)
    p.box("dark", -20, 20, b - 46, b - 6, 10, H * 0.82, r=10, ax="z", bev=3)
    # 흡입구
    p.box("finish", x0 + 8, x1 - 8, f + 20, f + D * 0.5, 18, 62, r=18, ax="x", bev=5)
    p.box("dark", x0 + 20, x1 - 20, f + 14, f + D * 0.3, 20, 44, r=10, ax="x", bev=2)
    # 관
    yc = f + D * 0.52
    p.cyl("finish" if style == "a5" else "#C9CCD0/m", "z", (0, yc, H * 0.36), 17, H * 0.56, bev=2)
    # 본체: 먼지통 + 모터 + 손잡이
    zb = H * 0.66
    p.cyl("#3A3C40/g", "z", (0, yc, zb + H * 0.06), 44, H * 0.12, bev=6)                        # 먼지통
    p.cyl("finish", "y", (0, yc + 6, zb + H * 0.17), 50, 120, bev=12)                           # 모터
    p.cyl("dark", "y", (0, yc - 56, zb + H * 0.17), 34, 8, bev=2)
    p.box("finish", -22, 22, yc + 40, b - 10, zb + H * 0.02, zb + H * 0.14, r=16, ax="x", bev=5)   # 배터리
    hz = zb + H * 0.24
    p.tube("finish", [(0, yc + 30, hz - 20), (0, yc + 50, H - 26), (0, yc + 10, H - 14), (0, yc - 40, H - 22), (0, yc - 30, hz - 6)], 14)
    return p


def canister_vac(W, D, H, **_):
    """유선(캐니스터) 청소기 본체: 둥근 몸통, 큰 뒷바퀴, 비치는 먼지통, 위 손잡이. 호스·흡입구는 뺐다(치수가 본체 기준).

    세워서 보관하는 모델(높이가 깊이보다 큰 것)은 같은 모양을 세운 것이다.
    """
    up = H > D * 1.15
    L, T = (H, D) if up else (D, H)                # L 몸통 길이, T 몸통 높이
    q = Parts()
    R = T * 0.40
    q.ell("finish", (0, 0, T * 0.5), (W * 0.42, L / 2, T * 0.5), n=2.8, cut=("z", -0.86))
    q.ell("#3B3D42/g", (0, -L * 0.2, T * 0.62), (W * 0.33, L * 0.25, T * 0.36), n=2.4)                    # 먼지통
    q.torus("#C9CCD0/m", "y", (0, -L * 0.2, T * 0.62), min(W * 0.3, T * 0.3), 4)
    for sx in (-1, 1):
        q.cyl("dark", "x", (sx * (W / 2 - 17), L * 0.18, R), R, 30, bev=9)
        q.cyl("#B9BCC0/m", "x", (sx * (W / 2 - 3), L * 0.18, R), R * 0.52, 6, bev=1.5)
    q.cyl("dark", "y", (0, -L / 2 + 13, T * 0.4), min(30, W * 0.12), 26, bev=4)                           # 호스 구멍
    q.tube("dark", [(0, -L * 0.02, T - 16), (0, L * 0.12, T - 7), (0, L * 0.3, T - 24)], 8)                # 손잡이
    if not up:
        return q
    p = Parts()                                    # 앞쪽을 위로 세운다: (x, y, z) → (x, T/2 - z, L/2 - y)
    for part in q:
        k = part["kind"]
        tr = lambda v: (v[0], T / 2 - v[2], L / 2 - v[1])
        if k == "ell":
            part["c"] = tr(part["c"])
            rx, ry, rz = part["rad"]
            part["rad"] = (rx, rz, ry)
            if part.get("cut"):
                part["cut"] = ("y", 0.86)
        elif k in ("cyl", "torus"):
            part["c"] = tr(part["c"])
            part["axis"] = {"x": "x", "y": "z", "z": "y"}[part["axis"]]
        elif k == "tube":
            part["pts"] = [tr(v) for v in part["pts"]]
        p.append(part)
    return p


# ---------------------------------------------------------------- 정수기
def purifier_slim(W, D, H, head=0.42, spout_z=0.56, **_):
    """슬림 직수 정수기: 좁고 깊은 몸통, 앞 위쪽이 머리처럼 튀어나오고 그 아래로 물이 나온다."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    hd = D * head                                      # 머리가 앞으로 나온 길이
    zh = H * spout_z
    p.box("finish", x0, x1, f + hd, b, 0, H, r=min(18, W * 0.14), ax="z", bev=6)                # 몸통
    p.box("finish", x0, x1, f, f + hd + 20, zh, H, r=min(18, W * 0.14), ax="z", bev=6)          # 머리
    p.cyl("chrome", "z", (0, f + hd * 0.42, zh - 9), 9, 18, bev=2)                              # 출수구
    p.box("black", x0 + W * 0.16, x1 - W * 0.16, f + hd * 0.12, f + hd * 0.9, H - 0.6, H + 0.6, r=10, ax="z", bev=0.2)
    p.box("finish", x0 + 6, x1 - 6, f + 4, f + hd + 10, 0, 16, r=10, ax="z", bev=4)             # 물받이
    p.box("#C9CCD0/m", x0 + 16, x1 - 16, f + 14, f + hd - 4, 15, 17.5, r=8, ax="z", bev=0.4)
    return p


def purifier_ice(W, D, H, **_):
    """얼음정수기: 위쪽 검은 표시창 머리, 아래쪽은 세로 살 앞판, 가운데 출수 공간."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    zs = H * 0.47
    zh = H * 0.66
    p.box("finish", x0, x1, f + D * 0.2, b, 0, H, r=14, ax="z", bev=5)
    p.box("finish", x0, x1, f, f + D * 0.3, zh, H, r=14, ax="z", bev=5)                         # 머리
    p.box("black", x0 + W * 0.14, x1 - W * 0.14, f - 0.8, f + 5, zh + (H - zh) * 0.42, zh + (H - zh) * 0.74, r=6, bev=0.4)
    for sx in (-0.5, 0.5):
        p.cyl("chrome", "z", (sx * W * 0.34, f + D * 0.12, zh - 12), 9, 24, bev=2)
    p.box("#D8C9B8/s", x0, x1, f, f + D * 0.3, 14, zs, r=14, ax="z", bev=5)                      # 아래 앞부분
    n = max(8, int(W / 16))
    for i in range(n):
        cx = x0 + W * (i + 0.5) / n
        p.box("#CDBBA7/s", cx - W / n * 0.28, cx + W / n * 0.28, f - 3, f + 6, 24, zs - 10, r=3, ax="z", bev=0.5)
    p.box("#C9CCD0/m", x0 + 14, x1 - 14, f + 8, f + D * 0.28, zs - 2, zs + 2, r=10, ax="z", bev=0.5)   # 물받이
    p.box("dark", x0 + 10, x1 - 10, f + 16, b - 10, 0, 16, bev=1)
    return p


def purifier_stand(W, D, H, **_):
    """스탠드 정수기: 키 큰 몸통, 가슴 높이에 출수 공간, 그 아래 세로 살 판."""
    p = Parts()
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    z0, z1 = H * 0.62, H * 0.82
    p.box("finish", x0, x1, f + D * 0.22, b, 0, H, r=16, ax="z", bev=5)
    p.box("finish", x0, x1, f, f + D * 0.3, z1, H, r=16, ax="z", bev=5)
    p.box("finish", x0, x1, f, f + D * 0.3, 0, z0, r=16, ax="z", bev=5)
    p.box("black", x0 + W * 0.2, x1 - W * 0.2, f - 0.8, f + 5, z1 + (H - z1) * 0.3, z1 + (H - z1) * 0.62, r=6, bev=0.4)
    for sx in (-0.5, 0.5):
        p.cyl("chrome", "z", (sx * W * 0.3, f + D * 0.13, z1 - 14), 10, 28, bev=2)
    n = max(8, int(W / 18))
    for i in range(n):
        cx = x0 + W * (i + 0.5) / n
        p.box("#CDBBA7/s", cx - W / n * 0.28, cx + W / n * 0.28, f - 3, f + 6, z0 - H * 0.2, z0 - 12, r=3, ax="z", bev=0.5)
    p.box("#C9CCD0/m", x0 + 16, x1 - 16, f + 8, f + D * 0.28, z0 - 2, z0 + 2, r=10, ax="z", bev=0.5)
    p.box("dark", x0 + 3, x1 - 3, f + 3, f + D * 0.3 - 3, H * 0.3, H * 0.3 + 3, bev=0)
    return p


# ---------------------------------------------------------------- 안마의자
def massage_chair(W, D, H, cushion="#B9AC9B/f", **_):
    """전신형 안마의자: 양옆 둥근 겉껍질 사이에 기울어진 등받이·좌석·다리 받침."""
    p = Parts()
    f, b = -D / 2, D / 2
    sw = W * 0.17                                         # 옆 껍질 두께
    for sx in (-1, 1):                                    # 옆 껍질 (팔걸이 포함)
        cx = sx * (W / 2 - sw / 2)
        p.ell("finish", (cx, D * 0.04, H * 0.34), (sw / 2, D * 0.40, H * 0.34), n=3.2, cut=("z", -0.9))
        p.ell(cushion, (sx * (W / 2 - sw * 0.75), -D * 0.12, H * 0.57), (sw * 0.42, D * 0.2, H * 0.06), n=2.6)   # 팔 넣는 곳
    p.box("dark", -W * 0.36, W * 0.36, f + D * 0.16, b - D * 0.12, 0, H * 0.1, r=30, ax="z", bev=6)      # 받침
    iw = W / 2 - sw * 0.8
    p.ell(cushion, (0, -D * 0.02, H * 0.37), (iw, D * 0.2, H * 0.09), n=3.0)                              # 좌석
    p.ell(cushion, (0, D * 0.25, H * 0.64), (iw * 0.94, D * 0.085, H * 0.37), rot=(-24, 0, 0), n=3.0)     # 등받이
    p.ell("finish", (0, D * 0.31, H * 0.6), (iw * 1.06, D * 0.09, H * 0.41), rot=(-24, 0, 0), n=3.2)      # 등 뒤 껍질
    p.ell(cushion, (0, D * 0.33, H * 0.9), (iw * 0.5, D * 0.05, H * 0.09), rot=(-24, 0, 0), n=2.6)        # 머리 쿠션
    p.ell("finish", (0, -D * 0.34, H * 0.25), (iw * 1.02, D * 0.16, H * 0.19), rot=(18, 0, 0), n=3.2)       # 다리 받침
    for sx in (-1, 1):
        p.ell(cushion, (sx * iw * 0.48, -D * 0.4, H * 0.27), (iw * 0.34, D * 0.09, H * 0.15), rot=(18, 0, 0), n=3.0)
    return p


def lounge_chair(W, D, H, cushion="#B9A68C/f", **_):
    """가구형 안마의자: 달걀 모양 껍질 안에 쿠션, 둥근 회전 받침."""
    p = Parts()
    p.lathe("#3A3B3E/m", (0, D * 0.06), [(0, 0), (W * 0.36, 0), (W * 0.36, 10), (W * 0.1, 24), (W * 0.05, H * 0.2), (0, H * 0.2)])
    p.ell("finish", (0, D * 0.07, H * 0.58), (W / 2, D * 0.36, H * 0.44), rot=(-20, 0, 0), n=2.5)        # 껍질
    p.ell(cushion, (0, -D * 0.03, H * 0.6), (W * 0.4, D * 0.3, H * 0.36), rot=(-20, 0, 0), n=2.6)         # 등·머리 쿠션
    p.ell(cushion, (0, -D * 0.22, H * 0.33), (W * 0.41, D * 0.27, H * 0.11), rot=(6, 0, 0), n=2.8)        # 좌석
    for sx in (-1, 1):
        p.ell("finish", (sx * W * 0.43, -D * 0.12, H * 0.42), (W * 0.07, D * 0.3, H * 0.13), rot=(8, 0, 0), n=2.6)   # 팔걸이
    return p


def drum_pedestal(W, D, H, ped=0.26, **kw):
    """받침 서랍(미니워시) 위에 올린 드럼세탁기."""
    zp = H * ped
    p = drum(W, D, H, base=zp, **kw)
    x0, x1, f, b = -W / 2, W / 2, -D / 2, D / 2
    p.box("finish", x0, x1, f + 50, b, 14, zp + 10, r=14, ax="z", bev=5)
    p.box("finish", x0 + 2, x1 - 2, f + 30, f + 60, 22, zp + 4, r=10, bev=3)
    p.box("dark", x0 + W * 0.22, x1 - W * 0.22, f + 29.4, f + 44, zp - 54, zp - 28, r=10, bev=0.5)
    _feet(p, W, f + 110, b - 60)
    return p
