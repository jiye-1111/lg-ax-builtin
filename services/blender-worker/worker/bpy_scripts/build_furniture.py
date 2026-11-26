"""스캔 가구(RoomPlan 종류별) 3D 모델을 Blender로 만든다.

    blender -b -P build_furniture.py -- --out apps/web/models/furniture
    python build_furniture.py --out ...      (pip bpy 모듈로 실행할 때)

- 종류마다 기준 크기(ref_m)로 한 벌씩 만든다. 바닥 가운데가 원점, 정면 = glTF +Z.
- 부품은 따로 둔다. 웹이 스캔 크기에 맞춰 부품별로 늘리기 때문이다 (다리 굵기·상판 두께는 그대로).
- 부품 extras.rig: glTF 축(x 폭, y 높이, z 깊이)마다 한 글자
    s = 크기와 위치를 같이 늘림, p = 위치만 늘림, e = 크기 그대로 + 가까운 모서리와 거리 유지
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from furn_parts import MATS, bake_uvs, ball, bar, bowed, cyl, leaf, part, rod, slab, soft  # noqa: E402


# ---------- 종류별 모양 ----------
CORNERS = [(-1, 1), (1, 1), (-1, -1), (1, -1)]  # 다리 네 개: (좌우, 앞뒤)


def chair(w, h, d):
    """식탁 의자: 가는 원목 틀에 천을 씌운 방석과 몸을 감싸는 등받이 (요즘 많이 보이는 패브릭 다이닝 체어)."""
    seat, pad = 0.46, 0.06
    under = seat - pad
    for i, sx in enumerate((-1, 1)):
        rod(f"leg_f{i}", "frame:oak_light", (sx * (w / 2 - 0.03), 0.002, d / 2 - 0.04), (sx * (w / 2 - 0.06), under, d / 2 - 0.07),
            0.012, 0.018, "ese")
        rod(f"leg_b{i}", "frame:oak_light", (sx * (w / 2 - 0.035), 0.002, -d / 2 + 0.03), (sx * (w / 2 - 0.06), under, -d / 2 + 0.1),
            0.012, 0.018, "ese")
        rod(f"post{i}", "frame:oak_light", (sx * (w / 2 - 0.06), under, -d / 2 + 0.1), (sx * (w / 2 - 0.075), h - 0.1, -d / 2 + 0.055),
            0.018, 0.013, "ese")
    part("frame", "frame:oak_light", -w / 2 + 0.04, w / 2 - 0.04, -d / 2 + 0.08, d / 2 - 0.05, under - 0.035, under, "sps", 0.008)
    soft("seat", "seat:boucle", -w / 2, w / 2, -d / 2 + 0.06, d / 2, under, seat, "sps", r=0.028, puff=0.014)
    # 등받이: 굽은 판에 천을 씌운 모양 (가운데가 뒤로 들어간다)
    bowed("back", "back:boucle", -w / 2 + 0.03, w / 2 - 0.03, h - 0.3, h, -d / 2 + 0.0725, 0.05, 0.045, "sse", edge=0.018)


def table(w, h, d):
    """식탁: 네 귀를 굴린 얇은 상판, 안쪽으로 들인 틀, 아래로 가늘어지는 둥근 다리."""
    top, inset = 0.03, 0.11
    slab("top", "top:oak_light", -w / 2, w / 2, -d / 2, d / 2, h - top, h, "ses", corner=0.09, edge=0.008)
    for i, (sx, sz) in enumerate(CORNERS):
        rod(f"leg{i}", "leg:oak_light", (sx * (w / 2 - 0.075), 0, sz * (d / 2 - 0.075)),
            (sx * (w / 2 - inset), h - top, sz * (d / 2 - inset)), 0.016, 0.03, "ese")
    for i, sz in enumerate((-1, 1)):
        z = sz * (d / 2 - inset)
        part(f"apron{i}", "leg:oak_light", -w / 2 + inset, w / 2 - inset, z - 0.01, z + 0.01, h - top - 0.06, h - top, "see", 0.004)
    for i, sx in enumerate((-1, 1)):
        x = sx * (w / 2 - inset)
        part(f"apron_s{i}", "leg:oak_light", x - 0.01, x + 0.01, -d / 2 + inset, d / 2 - inset, h - top - 0.06, h - top, "ees", 0.004)


def _flat_doors(prefix, look, x0, x1, y0, y1, zf, n, t=0.02, gap=0.003, rig="sse"):
    """손잡이 없는 납작한 문 n짝을 나란히. 문 사이에는 가는 틈만 보인다 (틈 뒤는 어둡게)."""
    part(f"{prefix}_bed", "shadow", x0 + 0.002, x1 - 0.002, zf - t - 0.003, zf - 0.012, y0 + 0.002, y1 - 0.002, rig, 0.001)
    step = (x1 - x0) / n
    for i in range(n):
        part(f"{prefix}{i}", look, x0 + i * step + gap, x0 + (i + 1) * step - gap, zf - t, zf, y0 + gap, y1 - gap, rig, 0.0025)


def storage(w, h, d):
    """수납장: 손잡이 없는 무광 문 위아래 + 가운데 뚫린 나무 칸 (요즘 붙박이 수납장 모양, 정면 +Z)."""
    base, t = 0.07, 0.02
    front = d / 2
    lo, hi = base + (h - base) * 0.42, base + (h - base) * 0.6  # 뚫린 칸 아래·위
    part("plinth", "plinth", -w / 2 + 0.02, w / 2 - 0.02, -d / 2, front - 0.06, 0, base, "ses", 0.003)
    part("body_low", "white:matte", -w / 2, w / 2, -d / 2, front - t, base, lo, "sss", 0.003)
    part("body_up", "white:matte", -w / 2, w / 2, -d / 2, front - t, hi, h, "sss", 0.003)
    part("niche_back", "niche:oak_light", -w / 2 + 0.018, w / 2 - 0.018, -d / 2, -d / 2 + 0.02, lo, hi, "sss", 0.001)
    for i, sx in enumerate((-1, 1)):
        x0 = -w / 2 if sx < 0 else w / 2 - 0.018
        part(f"niche_side{i}", "white:matte", x0, x0 + 0.018, -d / 2, front, lo, hi, "ess", 0.002)
    part("niche_floor", "niche:oak_light", -w / 2 + 0.018, w / 2 - 0.018, -d / 2 + 0.02, front, lo - 0.001, lo + 0.018, "sps", 0.002)
    _flat_doors("door_low", "white:matte", -w / 2, w / 2, base, lo, front, 2)
    _flat_doors("door_up", "white:matte", -w / 2, w / 2, hi, h, front, 2)


def sofa(w, h, d):
    """패브릭 소파: 낮고 깊은 몸통, 도톰한 팔걸이, 두툼한 방석 두 장과 등쿠션, 포인트 쿠션 둘, 낮은 발."""
    arm, foot, seat, back_t = 0.2, 0.06, 0.43, 0.2
    for i, (sx, sz) in enumerate(CORNERS):
        x, z = sx * (w / 2 - 0.1), sz * (d / 2 - 0.1)
        part(f"foot{i}", "leg:black", x - 0.025, x + 0.025, z - 0.025, z + 0.025, 0, foot + 0.01, "eee", 0.006)
    soft("base", "fabric:sofa", -w / 2 + 0.01, w / 2 - 0.01, -d / 2 + 0.01, d / 2 - 0.02, foot, seat - 0.15, "sss", r=0.035)
    for i, sx in enumerate((-1, 1)):
        x0 = -w / 2 if sx < 0 else w / 2 - arm
        soft(f"arm{i}", "fabric:sofa", x0, x0 + arm, -d / 2, d / 2 - 0.01, foot + 0.005, 0.6, "ess", r=0.075)
    soft("back", "fabric:sofa", -w / 2 + 0.02, w / 2 - 0.02, -d / 2, -d / 2 + back_t, foot + 0.005, h - 0.13, "sse", r=0.07)
    inner = w - 2 * arm
    for i in range(2):
        x0 = -w / 2 + arm + i * inner / 2 + 0.003
        x1 = x0 + inner / 2 - 0.006
        soft(f"cushion{i}", "fabric:sofa", x0, x1, -d / 2 + back_t - 0.02, d / 2, seat - 0.16, seat, "sps", r=0.055, puff=0.025)
        soft(f"pillow{i}", "fabric:sofa", x0 + 0.005, x1 - 0.005, -d / 2 + back_t - 0.05, -d / 2 + back_t + 0.17, seat - 0.01, h,
             "sse", r=0.08, lean=0.06)
    for i, (sx, look) in enumerate(((-1, "cushion:caramel"), (1, "cushion:caramel"))):
        xc = sx * (w / 2 - arm - 0.21)
        soft(f"throw{i}", look, xc - 0.2, xc + 0.2, -d / 2 + back_t + 0.13, -d / 2 + back_t + 0.26, seat + 0.01, seat + 0.38,
             "eee", r=0.06, lean=0.08)


def bed(w, h, d):
    """침대: 세로로 골이 진 패브릭 헤드, 천을 씌운 낮은 틀, 도톰한 이불과 발치 담요, 베개 넷."""
    leg, frame_top, mat_top = 0.07, 0.3, 0.55
    for i, (sx, sz) in enumerate(CORNERS):
        x, z = sx * (w / 2 - 0.12), sz * (d / 2 - 0.14)
        part(f"leg{i}", "leg:black", x - 0.03, x + 0.03, z - 0.03, z + 0.03, 0, leg + 0.01, "eee", 0.006)
    soft("frame", "frame:headboard", -w / 2, w / 2, -d / 2 + 0.06, d / 2, leg, frame_top, "sps", r=0.035)
    # 헤드: 세로로 긴 쿠션을 나란히 세운 모양
    n = 6
    for i in range(n):
        x0 = -w / 2 + i * w / n
        soft(f"head{i}", "head:headboard", x0 + 0.002, x0 + w / n - 0.002, -d / 2, -d / 2 + 0.11, leg, h, "sse", r=0.04, cuts=5)
    soft("mattress", "linen", -w / 2 + 0.04, w / 2 - 0.04, -d / 2 + 0.12, d / 2 - 0.04, frame_top - 0.02, mat_top, "sps",
         r=0.06, puff=0.008)
    soft("duvet", "bedding:duvet", -w / 2 + 0.01, w / 2 - 0.01, -d / 2 + 0.74, d / 2 - 0.02, mat_top - 0.14, mat_top + 0.055, "sps",
         r=0.05, puff=0.025)
    soft("duvet_fold", "linen", -w / 2 + 0.015, w / 2 - 0.015, -d / 2 + 0.62, -d / 2 + 0.88, mat_top + 0.005, mat_top + 0.08,
         "spe", r=0.038)
    soft("blanket", "throw:blanket", -w / 2 + 0.002, w / 2 - 0.002, d / 2 - 0.6, d / 2 - 0.18, mat_top - 0.12, mat_top + 0.1, "spe",
         r=0.03)
    for i, sx in enumerate((-1, 1)):
        x = sx * w / 4
        soft(f"pillow{i}", "linen", x - w / 4.6, x + w / 4.6, -d / 2 + 0.16, -d / 2 + 0.52, mat_top - 0.01, mat_top + 0.14, "ppe",
             r=0.065, puff=0.03)
        soft(f"sham{i}", "throw:blanket" if i == 0 else "bedding:duvet", x - w / 6, x + w / 6, -d / 2 + 0.38, -d / 2 + 0.6, mat_top,
             mat_top + 0.3, "ppe", r=0.055, lean=0.12)


def desk(w, h, d):
    """책상: 귀를 굴린 나무 상판 + 가는 철제 다리 틀, 상판 밑 얇은 서랍."""
    top, leg = 0.026, 0.018
    slab("top", "top:oak_light", -w / 2, w / 2, -d / 2, d / 2, h - top, h, "ses", corner=0.035, edge=0.006)
    for i, (sx, sz) in enumerate(CORNERS):
        x, z = sx * (w / 2 - 0.05), sz * (d / 2 - 0.05)
        part(f"leg{i}", "leg:steel_white", x - leg, x + leg, z - leg, z + leg, 0, h - top, "ese", 0.004)
    for i, sz in enumerate((-1, 1)):
        z = sz * (d / 2 - 0.05)
        part(f"rail{i}", "leg:steel_white", -w / 2 + 0.05, w / 2 - 0.05, z - 0.012, z + 0.012, h - top - 0.045, h - top, "see", 0.003)
    for i, sx in enumerate((-1, 1)):
        x = sx * (w / 2 - 0.05)
        part(f"rail_s{i}", "leg:steel_white", x - 0.012, x + 0.012, -d / 2 + 0.05, d / 2 - 0.05, h - top - 0.045, h - top, "ees", 0.003)
    part("drawer", "leg:steel_white", w / 2 - 0.52, w / 2 - 0.09, -d / 2 + 0.09, d / 2 - 0.04, h - top - 0.1, h - top - 0.003, "pse", 0.005)
    part("drawer_gap", "shadow", w / 2 - 0.515, w / 2 - 0.095, d / 2 - 0.041, d / 2 - 0.039, h - top - 0.018, h - top - 0.004, "ppe", 0.0)


def shelf(w, h, d):
    """책장: 옆판·선반 다섯 단, 칸마다 책 몇 권과 소품"""
    side = 0.02
    for i, sx in enumerate((-1, 1)):
        x0 = -w / 2 if sx < 0 else w / 2 - side
        part(f"side{i}", "body:oak_light", x0, x0 + side, -d / 2, d / 2, 0, h, "ess", 0.003)
    part("back", "body:oak_light", -w / 2 + side, w / 2 - side, -d / 2, -d / 2 + 0.008, 0, h, "sse", 0.001)
    n = 5
    ys = [0.05 + i * (h - 0.06) / (n - 1) for i in range(n)]
    for i, y in enumerate(ys):
        part(f"board{i}", "body:oak_light", -w / 2 + side, w / 2 - side, -d / 2 + 0.008, d / 2 - 0.004, y - 0.01, y + 0.01, "sps", 0.003)
    looks = ("book_a", "book_b", "book_c", "matte")
    for row, y in enumerate(ys[:-1]):
        x = -w / 2 + side + 0.03 if row % 2 == 0 else w / 2 - side - 0.03 - 0.21
        for k in range(5):
            bw, bh = 0.028 + 0.008 * ((row + k) % 3), 0.2 + 0.03 * ((row * 2 + k) % 3)
            part(f"book{row}_{k}", looks[(row + k) % 4], x, x + bw, -d / 2 + 0.03, d / 2 - 0.04, y + 0.01, y + 0.01 + bh,
                 "epe", 0.003)
            x += bw + 0.003
    cyl("vase", "ceramic", w / 2 - side - 0.12, 0, 0.045, ys[0] + 0.01, ys[0] + 0.2, "epe", 24, 0.028)


def tvstand(w, h, d):
    """거실장: 바닥에서 살짝 뜬 낮은 몸통, 세로 골이 촘촘한 템바보드 문 (손잡이 없음)."""
    base, t, cap = 0.07, 0.02, 0.022
    front = d / 2
    part("plinth", "plinth", -w / 2 + 0.06, w / 2 - 0.06, -d / 2 + 0.03, front - 0.08, 0, base, "ses", 0.003)
    part("body", "body:oak_light", -w / 2, w / 2, -d / 2, front - t, base, h - cap, "sss", 0.004)
    slab("top", "body:oak_light", -w / 2, w / 2, -d / 2, front, h - cap, h, "ses", corner=0.012, edge=0.005)
    part("door_bed", "shadow", -w / 2 + 0.004, w / 2 - 0.004, front - t, front - 0.009, base + 0.004, h - cap - 0.004, "sse", 0.001)
    n = 44
    rib = (w - 0.012) / n
    for i in range(n):
        x = -w / 2 + 0.006 + i * rib
        part(f"rib{i}", "door:oak_light", x + rib * 0.11, x + rib * 0.89, front - 0.012, front, base + 0.005, h - cap - 0.005, "sse", 0.004)


def island(w, h, d):
    """아일랜드: 손잡이 없는 문 세 짝(상판 밑 손끼움 홈), 들인 걸레받이, 사방으로 살짝 내민 상판."""
    base, top = 0.1, 0.03
    zf = d / 2 - 0.02
    part("plinth", "plinth", -w / 2 + 0.06, w / 2 - 0.06, -d / 2 + 0.06, d / 2 - 0.08, 0, base, "ses", 0.003)
    part("body", "white:matte", -w / 2 + 0.02, w / 2 - 0.02, -d / 2 + 0.02, zf - 0.02, base, h - top, "sss", 0.003)
    _channel("door", -w / 2 + 0.02, w / 2 - 0.02, h - top, zf)
    _flat_doors("door", "white:matte", -w / 2 + 0.02, w / 2 - 0.02, base, h - top - 0.03, zf, 3)
    part("top", "stone:quartz", -w / 2, w / 2, -d / 2, d / 2, h - top, h, "ses", 0.004)


def islandtable(w, h, d):
    """아일랜드 식탁: 두툼한 밝은 돌 상판 + 밝은 참나무 몸통. 주방 쪽(정면 +Z)은 손잡이 없는 문 두 짝과 서랍 세 단,
    앉는 쪽과 양옆은 세로 골이 있는 템바보드. 상판은 앉는 쪽으로 튀어나와 무릎이 들어간다.
    치수는 한샘 모디 아일랜드식탁 120cm (상판 120 x 75, 높이 89), 모양은 요즘 많이 팔리는 템바보드 홈바·아일랜드 식탁을 따랐다."""
    top, base, reveal, gap = 0.045, 0.09, 0.018, 0.003
    hang = d * 0.2            # 앉는 쪽으로 튀어나온 상판 (slot.py SEAT_RATIO와 같은 값)
    back = -d / 2 + hang      # 몸통 뒷면
    front = d / 2 - 0.035     # 문 앞면 (slot.py DOOR_BACK_M과 같은 값)
    rib = 0.011               # 템바보드 살 하나의 반폭
    proud = 0.009             # 살이 몸통에서 튀어나온 만큼
    pull = 0.02               # 문·서랍 위쪽 손끼움 홈
    x0, x1 = -w / 2 + 0.03, w / 2 - 0.03
    y1 = h - top - reveal     # 몸통 윗면. 그 위로 상판과의 사이에 어두운 틈이 한 줄 돈다
    part("plinth", "plinth", x0 + 0.045, x1 - 0.045, back + 0.045, front - 0.06, 0, base, "ses", 0.003)
    part("reveal", "plinth", x0 + 0.014, x1 - 0.014, back + 0.014, front - 0.03, y1 - 0.002, h - top + 0.002, "ses", 0.002)
    part("body", "island_wood", x0 + proud, x1 - proud, back + proud, front - 0.02, base, y1, "sss", 0.002)
    part("top", "stone", -w / 2, w / 2, -d / 2, d / 2, h - top, h, "ses", 0.014)
    # 템바보드: 앉는 쪽 한 면과 양옆에 세로 살을 촘촘히 붙인다
    n = max(2, round((x1 - x0 - 2 * rib) / (2 * rib + 0.007)))
    for i in range(n + 1):
        x = x0 + rib + (x1 - x0 - 2 * rib) * i / n
        part(f"rib_b{i}", "island_wood", x - rib, x + rib, back, back + proud + 0.004, base + 0.004, y1 - 0.002, "ssp", 0.003)
    m = max(2, round((front - 0.03 - back - 2 * rib) / (2 * rib + 0.007)))
    for sx in (-1, 1):
        for i in range(1, m + 1):
            z = back + rib + (front - 0.03 - back - 2 * rib) * i / m
            xa, xb = sorted((sx * (w / 2 - 0.03), sx * (w / 2 - 0.03 - proud - 0.004)))
            part(f"rib_s{'l' if sx < 0 else 'r'}{i}", "island_wood", xa, xb, z - rib, z + rib, base + 0.004, y1 - 0.002, "ess", 0.003)
    # 주방 쪽: 손잡이 없는 문 두 짝(왼쪽)과 서랍 세 단(오른쪽). 문·서랍 위에 손을 넣는 어두운 홈이 한 줄씩 있다
    fx0, fx1 = x0 + proud, x1 - proud
    part("groove", "plinth", fx0 + 0.002, fx1 - 0.002, front - 0.024, front - 0.012, base + 0.002, y1 - 0.002, "sse", 0.001)
    mid = fx0 + (fx1 - fx0) * 0.6
    half = (mid - fx0) / 2
    for i in range(2):
        part(f"door{i}", "island_wood", fx0 + i * half + gap, fx0 + (i + 1) * half - gap, front - 0.02, front,
             base + gap, y1 - pull, "sse", 0.0025)
    step = (y1 - base) / 3
    for i in range(3):
        y0 = base + i * step + gap
        part(f"drawer{i}", "island_wood", mid + gap, fx1 - gap, front - 0.02, front, y0, y0 + step - pull, "sse", 0.0025)


def hood(w, h, d):
    """벽 후드: 얇은 스테인리스 갓 + 벽을 타고 올라가는 덕트 덮개 (등 = -Z가 벽, 밑면이 원점 높이).
    기준 치수는 IKEA RYTMISK 60 (갓 60 x 47.1, 덕트 덮개 16.7 x 16.9). 높이를 늘리면 덕트 덮개만 길어진다."""
    lip, step = 0.045, 0.03
    part("filter", "plinth", -w / 2 + 0.04, w / 2 - 0.04, -d / 2 + 0.05, d / 2 - 0.06, -0.001, 0.006, "ses", 0.002)
    part("lamp0", "shade", -w / 2 + 0.07, -w / 2 + 0.15, d / 2 - 0.05, d / 2 - 0.025, -0.002, 0.004, "eee", 0.002)
    part("lamp1", "shade", w / 2 - 0.15, w / 2 - 0.07, d / 2 - 0.05, d / 2 - 0.025, -0.002, 0.004, "eee", 0.002)
    part("canopy", "steel", -w / 2, w / 2, -d / 2, d / 2, 0.002, lip, "ses", 0.006)
    part("shoulder", "steel", -w / 2 + 0.05, w / 2 - 0.05, -d / 2, d / 2 - 0.07, lip, lip + step, "ses", 0.008)
    part("keys", "plinth", -0.07, 0.07, d / 2 - 0.004, d / 2 + 0.001, 0.016, 0.03, "pee", 0.002)
    part("duct", "steel", -0.0835, 0.0835, -d / 2, -d / 2 + 0.169, 0.01, h, "pse", 0.004)


def islandhood(w, h, d):
    """아일랜드 후드: 조리대 위 천장에서 내려오는 네모 갓 + 가운데 덕트 덮개 (밑면이 원점 높이, 윗면이 천장)."""
    lip = 0.07
    part("filter", "plinth", -w / 2 + 0.05, w / 2 - 0.05, -d / 2 + 0.05, d / 2 - 0.05, -0.001, 0.006, "ses", 0.002)
    for i, sx in enumerate((-1, 1)):
        part(f"lamp{i}", "shade", sx * (w / 2 - 0.11) - 0.04, sx * (w / 2 - 0.11) + 0.04, -0.03, 0.03, -0.002, 0.004, "eep", 0.002)
    part("canopy", "steel", -w / 2, w / 2, -d / 2, d / 2, 0.002, lip, "ses", 0.008)
    part("keys", "plinth", -0.07, 0.07, d / 2 - 0.004, d / 2 + 0.001, 0.028, 0.042, "pee", 0.002)
    part("duct", "steel", -0.15, 0.15, -0.125, 0.125, 0.01, h, "psp", 0.004)


def rug(w, h, d):
    slab("rug", "wool", -w / 2, w / 2, -d / 2, d / 2, 0, h, "sss", corner=0.03, edge=0.004)


def lamp(w, h, d):
    """플로어 램프: 묵직한 받침, 가는 황동 기둥, 천 갓"""
    r = min(w, d) / 2
    cyl("base", "pole:black", 0, 0, r * 0.62, 0, 0.018, "eee", 40)
    cyl("base_top", "pole:black", 0, 0, r * 0.58, 0.018, 0.026, "eee", 40, r * 0.2)
    cyl("pole", "pole:black", 0, 0, 0.009, 0.026, h - 0.3, "ese", 16)
    cyl("collar", "pole:black", 0, 0, 0.02, h - 0.34, h - 0.3, "eee", 20)
    cyl("shade", "shade", 0, 0, r, h - 0.3, h, "eee", 48, r * 0.72)
    cyl("shade_rim", "pole:black", 0, 0, r + 0.002, h - 0.3, h - 0.292, "eee", 48)


def plant(w, h, d):
    """화분: 테가 있는 토분, 여러 줄기에서 뻗은 큰 잎"""
    r = min(w, d) / 2
    pot_h = h * 0.27
    cyl("pot", "pot:ceramic", 0, 0, r * 0.48, 0, pot_h, "eee", 40, r * 0.62)
    cyl("pot_rim", "pot:ceramic", 0, 0, r * 0.66, pot_h - 0.03, pot_h, "eee", 40)
    cyl("soil", "soil", 0, 0, r * 0.58, pot_h - 0.012, pot_h - 0.006, "eee", 32)
    n = 11
    for i in range(n):
        a = i * 2.39996  # 황금각으로 돌려 가며 고르게
        up = 0.55 + 0.45 * ((i * 7) % n) / n          # 줄기 높이 비율
        out = (0.6 + 0.4 * ((i * 4) % n) / n) * r     # 바깥으로 뻗는 거리
        cx, cz = math.cos(a), math.sin(a)
        root = (cx * r * 0.12, pot_h - 0.01, cz * r * 0.12)
        knee = (cx * out * 0.3, pot_h + (h - pot_h) * up * 0.62, cz * out * 0.3)
        tip = (cx * out * 0.97, min(h - 0.01, pot_h + (h - pot_h) * up), cz * out * 0.97)
        rod(f"stem{i}", "leaf_dark", root, knee, 0.006, 0.004, "eee", 8)
        leaf(f"leaf{i}", "leaf" if i % 3 else "leaf_dark", knee, tip, r * (0.5 + 0.16 * (i % 3)))


def coffee(w, h, d):
    """거실 테이블: 귀를 살짝 굴린 얇은 원목 상판, 아래 선반 한 단, 가는 다리 넷 (IKEA LISTERBY 같은 2단 소파 테이블)."""
    top, inset, leg = 0.024, 0.07, 0.019
    slab("top", "top:oak_light", -w / 2, w / 2, -d / 2, d / 2, h - top, h, "ses", corner=0.05, edge=0.006, seg=10)
    for i, (sx, sz) in enumerate(CORNERS):
        x, z = sx * (w / 2 - inset), sz * (d / 2 - inset)
        rod(f"leg{i}", "leg:oak_light", (x, 0, z), (x, h - top, z), leg * 0.8, leg, "ese")
    # 상판 바로 밑 가는 틀: 상판이 떠 보이지 않게
    for i, sz in enumerate((-1, 1)):
        z = sz * (d / 2 - inset)
        part(f"rail{i}", "leg:oak_light", -w / 2 + inset, w / 2 - inset, z - 0.008, z + 0.008, h - top - 0.035, h - top, "see", 0.003)
    for i, sx in enumerate((-1, 1)):
        x = sx * (w / 2 - inset)
        part(f"rail_s{i}", "leg:oak_light", x - 0.008, x + 0.008, -d / 2 + inset, d / 2 - inset, h - top - 0.035, h - top, "ees", 0.003)
    # 아래 선반: 다리 사이에 얇게 (잡지·리모컨 두는 단)
    slab("shelf", "top:oak_light", -w / 2 + inset - 0.006, w / 2 - inset + 0.006, -d / 2 + inset - 0.006, d / 2 - inset + 0.006,
         0.12, 0.138, "ses", corner=0.02, edge=0.004, seg=6)


def partition(w, h, d):
    """세로 살 파티션: 위아래 틀 + 살. 폭을 늘리면 살 간격이 같이 늘어난다."""
    part("bottom", "oak:oak_light", -w / 2, w / 2, -d / 2, d / 2, 0, 0.04, "ses", 0.003)
    part("top", "oak:oak_light", -w / 2, w / 2, -d / 2, d / 2, h - 0.04, h, "sps", 0.003)
    n = 12
    for i in range(n):
        x = -w / 2 + 0.025 + i * (w - 0.05) / (n - 1)
        part(f"slat{i}", "oak:oak_light", x - 0.018, x + 0.018, -d / 2 + 0.005, d / 2 - 0.005, 0.04, h - 0.04, "psp", 0.003)


def wall(w, h, d):
    part("wall", "plaster", -w / 2, w / 2, -d / 2, d / 2, 0, h, "sss", 0.004)
    part("skirt", "white", -w / 2 - 0.004, w / 2 + 0.004, -d / 2 - 0.004, d / 2 + 0.004, 0, 0.08, "ses", 0.002)


def _grooved(prefix, look, x0, x1, y0, y1, zf, rows, t=0.02, gap=0.0025, pull=0.016):
    """손잡이 없는 서랍 rows단. 서랍 위에 손을 넣는 어두운 홈이 한 줄씩 보인다."""
    part(f"{prefix}_groove", "shadow", x0 + 0.002, x1 - 0.002, zf - t - 0.004, zf - 0.012, y0 + 0.002, y1 - 0.002, "sse", 0.001)
    step = (y1 - y0) / rows
    for i in range(rows):
        part(f"{prefix}{i}", look, x0 + gap, x1 - gap, zf - t, zf, y0 + i * step + gap, y0 + (i + 1) * step - pull, "sse", 0.0025)


def dresser(w, h, d):
    """서랍장: 손잡이 없는 서랍 4단(위에 손끼움 홈), 살짝 내민 상판, 짧은 원목 다리 (정면 +Z)."""
    leg, cap, t = 0.1, 0.022, 0.02
    front = d / 2 - 0.006
    for i, (sx, sz) in enumerate(CORNERS):
        x, z = sx * (w / 2 - 0.06), sz * (d / 2 - 0.07)
        rod(f"leg{i}", "leg:oak_light", (x + sx * 0.008, 0, z), (x, leg, z), 0.012, 0.02, "eee", 16)
    part("body", "body:matte", -w / 2 + 0.004, w / 2 - 0.004, -d / 2, front - t, leg, h - cap, "sss", 0.003)
    slab("top", "top:oak_light", -w / 2, w / 2, -d / 2, d / 2, h - cap, h, "ses", corner=0.012, edge=0.006)
    _grooved("drawer", "body:matte", -w / 2 + 0.004, w / 2 - 0.004, leg, h - cap, front, 4)


def _channel(prefix, x0, x1, y_top, zf, drop=0.03):
    """상판 바로 밑 손끼움 홈 (핸들리스 주방). 문 윗선이 그만큼 내려온다."""
    part(f"{prefix}_channel", "shadow", x0 + 0.002, x1 - 0.002, zf - 0.03, zf - 0.012, y_top - drop, y_top, "sse", 0.001)


def basecab(w, h, d):
    """주방 하부장: 손잡이 없는 무광 문 두 짝(상판 밑 손끼움 홈), 들인 걸레받이, 앞으로 살짝 내민 얇은 상판."""
    base, top = 0.1, 0.03
    zf = d / 2 - 0.02
    part("plinth", "plinth", -w / 2 + 0.02, w / 2 - 0.02, -d / 2, d / 2 - 0.07, 0, base, "ses", 0.003)
    part("body", "white:matte", -w / 2, w / 2, -d / 2, zf - 0.02, base, h - top, "sss", 0.003)
    _channel("door", -w / 2, w / 2, h - top, zf)
    _flat_doors("door", "white:matte", -w / 2, w / 2, base, h - top - 0.03, zf, 2)
    part("top", "stone:quartz", -w / 2, w / 2, -d / 2, d / 2, h - top, h, "ses", 0.004)


def wardrobe(w, h, d):
    """장롱: 천장까지 닿는 손잡이 없는 무광 문 두 짝. 문이 만나는 가운데에 세로 손끼움 홈 (정면 +Z)."""
    base = 0.06
    zf = d / 2
    part("plinth", "plinth", -w / 2 + 0.02, w / 2 - 0.02, -d / 2, zf - 0.05, 0, base, "ses", 0.003)
    part("body", "white:matte", -w / 2, w / 2, -d / 2, zf - 0.02, base, h, "sss", 0.003)
    _flat_doors("door", "white:matte", -w / 2, w / 2, base, h, zf, 2)
    part("pull", "shadow", -0.011, 0.011, zf - 0.021, zf - 0.008, h * 0.36, h * 0.36 + 0.42, "ppe", 0.002)


def tallcab(w, h, d):
    """키큰장: 손잡이 없는 무광 문 위아래 두 짝, 사이에 가는 손끼움 홈 (냉장고 옆에 세우는 주방 장, 정면 +Z)."""
    base, split = 0.1, 0.62
    zf = d / 2
    part("plinth", "plinth", -w / 2 + 0.02, w / 2 - 0.02, -d / 2, zf - 0.07, 0, base, "ses", 0.003)
    part("body", "white:matte", -w / 2, w / 2, -d / 2, zf - 0.02, base, h, "sss", 0.003)
    ym = base + (h - base) * split
    part("door_channel", "shadow", -w / 2 + 0.002, w / 2 - 0.002, zf - 0.024, zf - 0.012, ym - 0.012, ym + 0.012, "sse", 0.001)
    part("door_low", "white:matte", -w / 2 + 0.0025, w / 2 - 0.0025, zf - 0.02, zf, base + 0.0025, ym - 0.012, "sse", 0.0025)
    part("door_up", "white:matte", -w / 2 + 0.0025, w / 2 - 0.0025, zf - 0.02, zf, ym + 0.012, h - 0.0025, "sse", 0.0025)


def sink(w, h, d):
    """싱크대: 손잡이 없는 하부장 + 상판에 파인 개수대(오른쪽) + 검은 무광 거위목 수전. 상판은 개수대 둘레 네 조각"""
    base, top = 0.1, 0.03
    part("plinth", "plinth", -w / 2 + 0.02, w / 2 - 0.02, -d / 2, d / 2 - 0.07, 0, base, "ses", 0.003)
    # 개수대 자리 (오른쪽 반, 뒤에 수전 놓을 턱을 남긴다). 몸통은 개수대 바닥 아래까지만, 그 위는 둘레만 채운다
    bx0, bx1, bz0, bz1, deep = 0.02, w / 2 - 0.07, -d / 2 + 0.13, d / 2 - 0.08, 0.18
    neck, zf = h - deep - 0.004, d / 2 - 0.04
    part("body", "white:matte", -w / 2, w / 2, -d / 2, zf, base, neck, "sss", 0.003)
    part("apron_l", "white:matte", -w / 2, bx0, -d / 2, zf, neck, h - top, "ses", 0.002)
    part("apron_r", "white:matte", bx1, w / 2, -d / 2, zf, neck, h - top, "ses", 0.002)
    part("apron_b", "white:matte", bx0, bx1, -d / 2, bz0, neck, h - top, "ses", 0.002)
    part("apron_f", "white:matte", bx0, bx1, bz1, zf, neck, h - top, "ses", 0.002)
    _channel("door", -w / 2, w / 2, h - top, d / 2 - 0.02)
    _flat_doors("door", "white:matte", -w / 2, w / 2, base, h - top - 0.03, d / 2 - 0.02, 2)
    part("top_left", "stone:quartz", -w / 2, bx0, -d / 2, d / 2, h - top, h, "ses", 0.004)
    part("top_right", "stone:quartz", bx1, w / 2, -d / 2, d / 2, h - top, h, "ses", 0.004)
    part("top_back", "stone:quartz", bx0, bx1, -d / 2, bz0, h - top, h, "ses", 0.004)
    part("top_front", "stone:quartz", bx0, bx1, bz1, d / 2, h - top, h, "ses", 0.004)
    t = 0.012
    part("basin_floor", "basin", bx0, bx1, bz0, bz1, h - deep, h - deep + t, "ses", 0.002)
    part("basin_l", "steel", bx0, bx0 + t, bz0, bz1, h - deep, h - 0.002, "ses", 0.002)
    part("basin_r", "steel", bx1 - t, bx1, bz0, bz1, h - deep, h - 0.002, "ses", 0.002)
    part("basin_b", "steel", bx0, bx1, bz0, bz0 + t, h - deep, h - 0.002, "ses", 0.002)
    part("basin_f", "steel", bx0, bx1, bz1 - t, bz1, h - deep, h - 0.002, "ses", 0.002)
    cxb, czb = (bx0 + bx1) / 2, (bz0 + bz1) / 2
    cyl("drain", "metal", cxb, czb, 0.035, h - deep + t, h - deep + t + 0.004, "pep", 24)
    # 수전: 뒤 턱 가운데에서 올라와 개수대 쪽으로 굽는다
    fz = -d / 2 + 0.065
    cyl("faucet_base", "faucet:black", cxb, fz, 0.024, h, h + 0.03, "pep", 28)
    bar("faucet_riser", "faucet:black", (cxb, h + 0.03, fz), (cxb, h + 0.30, fz), 0.011, "pep")
    arc = [(h + 0.30, fz), (h + 0.345, fz + 0.03), (h + 0.36, fz + 0.08), (h + 0.345, fz + 0.14), (h + 0.30, fz + 0.17)]
    for i, ((y0, z0), (y1, z1)) in enumerate(zip(arc, arc[1:])):
        bar(f"faucet_neck{i}", "faucet:black", (cxb, y0, z0), (cxb, y1, z1), 0.011, "pep")
        ball(f"faucet_joint{i}", "faucet:black", cxb, y0, z0, 0.011, "pep")
    ball("faucet_joint_end", "faucet:black", cxb, arc[-1][0], arc[-1][1], 0.011, "pep")
    bar("faucet_tip", "faucet:black", (cxb, h + 0.30, fz + 0.17), (cxb, h + 0.255, fz + 0.17), 0.012, "pep")
    bar("faucet_lever", "faucet:black", (cxb + 0.024, h + 0.02, fz), (cxb + 0.08, h + 0.038, fz), 0.006, "pep")


def door(w, h, d):
    """여닫이문: 가는 문틀(9mm 문선 느낌) + 무늬 없는 민자 문짝 + 검은 무광 레버 손잡이. 경첩은 숨긴다.
    문짝 부품 이름은 leaf로 시작한다 (웹이 경첩 축으로 돌려 연다). 경첩은 왼쪽(-x), 앞(+z)으로 열린다."""
    jamb, head, t = 0.022, 0.022, 0.04
    part("jamb_l", "frame:matte", -w / 2, -w / 2 + jamb, -d / 2, d / 2, 0, h, "ess", 0.002)
    part("jamb_r", "frame:matte", w / 2 - jamb, w / 2, -d / 2, d / 2, 0, h, "ess", 0.002)
    part("head", "frame:matte", -w / 2 + jamb, w / 2 - jamb, -d / 2, d / 2, h - head, h, "ses", 0.002)
    x0, x1, y0, y1 = -w / 2 + jamb + 0.003, w / 2 - jamb - 0.003, 0.008, h - head - 0.003
    part("leaf", "door_leaf:matte", x0, x1, -t / 2, t / 2, y0, y1, "sse", 0.003)
    hx, hy = x1 - 0.07, 1.0
    for side, s_ in (("f", 1), ("b", -1)):
        z = s_ * t / 2
        bar(f"leaf_rose_{side}", "handle:black", (hx, hy, z), (hx, hy, z + s_ * 0.008), 0.025, "eee")
        bar(f"leaf_neck_{side}", "handle:black", (hx, hy, z), (hx, hy, z + s_ * 0.048), 0.008, "eee")
        part(f"leaf_lever_{side}", "handle:black", hx - 0.125, hx + 0.01, min(z + s_ * 0.042, z + s_ * 0.054), max(z + s_ * 0.042, z + s_ * 0.054),
             hy - 0.009, hy + 0.009, "eee", 0.004)


def _glazed(w, h, d, low, handles, lock=False):
    """가는 창틀(양옆·위·아래) + 유리 + 가운데서 겹치는 미닫이 창짝 두 장 (슬림 프레임). low = 아래 틀 높이."""
    fr, sash, t = 0.035, 0.022, 0.028
    part("jamb_l", "frame:matte", -w / 2, -w / 2 + fr, -d / 2, d / 2, 0, h, "ess", 0.003)
    part("jamb_r", "frame:matte", w / 2 - fr, w / 2, -d / 2, d / 2, 0, h, "ess", 0.003)
    part("head", "frame:matte", -w / 2 + fr, w / 2 - fr, -d / 2, d / 2, h - fr, h, "ses", 0.003)
    part("sill", "frame:matte", -w / 2 + fr, w / 2 - fr, -d / 2, d / 2, 0, low, "ses", 0.003)
    part("glass", "glass", -w / 2 + fr, w / 2 - fr, -0.004, 0.004, low, h - fr, "sss", 0.0)
    # 창짝 테: 가운데 겹치는 세로대 두 개(앞뒤로 어긋남), 양옆 세로대, 위아래 가로대
    part("meet_f", "frame:matte", -sash, 0.003, 0.006, 0.006 + t, low, h - fr, "pss", 0.002)
    part("meet_b", "frame:matte", -0.003, sash, -0.006 - t, -0.006, low, h - fr, "pss", 0.002)
    part("stile_l", "frame:matte", -w / 2 + fr, -w / 2 + fr + sash, -t / 2, t / 2, low, h - fr, "ess", 0.002)
    part("stile_r", "frame:matte", w / 2 - fr - sash, w / 2 - fr, -t / 2, t / 2, low, h - fr, "ess", 0.002)
    part("rail_top", "frame:matte", -w / 2 + fr, w / 2 - fr, -t / 2, t / 2, h - fr - sash, h - fr, "ses", 0.002)
    part("rail_low", "frame:matte", -w / 2 + fr, w / 2 - fr, -t / 2, t / 2, low, low + sash, "ses", 0.002)
    for name, x, z in handles:
        part(name, "handle:black", x - 0.007, x + 0.007, min(z, z + math.copysign(0.03, z)), max(z, z + math.copysign(0.03, z)),
             0.9, 1.3, "pee", 0.005)
    if lock:  # 가운데 잠금 손잡이 (크리센트)
        part("lock", "handle:black", -0.012, 0.012, 0.006 + t, 0.006 + t + 0.016, h * 0.5 - 0.028, h * 0.5 + 0.028, "ppe", 0.005)


def window(w, h, d):
    """미닫이 창문: 벽 속에 겹쳐 단다 (웹이 벽을 뚫고 유리를 비치게 그린다)."""
    _glazed(w, h, d, 0.035, (), lock=True)


def glassdoor(w, h, d):
    """베란다 유리문: 바닥부터 달리는 큰 미닫이 유리문. 가운데 세로 손잡이. 아래 틀은 걸레받이를 가릴 만큼."""
    _glazed(w, h, d, 0.09, (("pull_f", -0.011, 0.034), ("pull_b", 0.011, -0.034)))


TEMPLATES = {  # 기준 크기 (m): 스캔에서 자주 나오는 크기 근처
    "chair": ((0.5, 0.85, 0.52), chair),
    "table": ((1.6, 0.74, 0.8), table),
    "storage": ((1.0, 1.9, 0.45), storage),
    "sofa": ((2.0, 0.85, 0.9), sofa),
    "bed": ((1.6, 0.95, 2.1), bed),
    # 공간 꾸미기 라이브러리용 (제품 정보 없는 일반 모양)
    "desk": ((1.2, 0.73, 0.6), desk),
    "shelf": ((0.8, 1.8, 0.3), shelf),
    "tvstand": ((1.6, 0.45, 0.4), tvstand),
    "island": ((1.8, 0.9, 0.9), island),
    "islandtable": ((1.2, 0.89, 0.75), islandtable),
    "hood": ((0.6, 0.62, 0.471), hood),
    "islandhood": ((0.9, 0.8, 0.6), islandhood),
    "rug": ((2.0, 0.012, 1.4), rug),
    "lamp": ((0.4, 1.6, 0.4), lamp),
    "plant": ((0.5, 1.2, 0.5), plant),
    "coffee": ((1.0, 0.4, 0.6), coffee),
    "partition": ((1.2, 2.1, 0.05), partition),
    "wall": ((2.0, 2.4, 0.1), wall),
    "dresser": ((0.8, 0.9, 0.45), dresser),
    "basecab": ((1.2, 0.85, 0.6), basecab),
    "wardrobe": ((1.0, 2.36, 0.58), wardrobe),
    "tallcab": ((0.6, 2.0, 0.6), tallcab),
    "sink": ((1.2, 0.88, 0.6), sink),
    "door": ((0.9, 2.1, 0.14), door),
    "window": ((1.2, 1.2, 0.14), window),
    "glassdoor": ((1.8, 2.1, 0.14), glassdoor),
}


def build(cat: str, out: Path) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    MATS.clear()
    (w, h, d), fn = TEMPLATES[cat]
    fn(w, h, d)
    bake_uvs()
    path = out / f"{cat}.glb"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_yup=True, export_apply=True,
                              export_extras=True, export_materials="EXPORT", export_cameras=False, export_lights=False)
    return {"file": path.name, "ref_m": {"w": w, "h": h, "d": d}}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*", help="이 종류만 다시 만든다 (나머지 파일과 목록은 그대로)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    idx_path = out / "index.json"
    kept = json.loads(idx_path.read_text(encoding="utf-8"))["models"] if a.only and idx_path.exists() else {}
    index = {"_note": "build_furniture.py로 생성. 웹이 스캔 크기에 맞춰 부품별로 늘린다 (rig: s/p/e).",
             "models": {**kept, **{cat: build(cat, out) for cat in TEMPLATES if not a.only or cat in a.only}}}
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(index["models"]))


if __name__ == "__main__":
    main()
