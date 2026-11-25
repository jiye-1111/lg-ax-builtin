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
from furn_parts import MATS, ball, bar, bowed, cyl, leaf, part, rod, soft  # noqa: E402


# ---------- 종류별 모양 ----------
CORNERS = [(-1, 1), (1, 1), (-1, -1), (1, -1)]  # 다리 네 개: (좌우, 앞뒤)


def chair(w, h, d):
    """원목 식탁 의자: 가늘어지는 둥근 다리, 볼록한 천 방석, 몸을 감싸듯 굽은 등판."""
    seat, pad = 0.45, 0.05
    under = seat - pad  # 방석 밑 = 틀 윗면
    # 앞다리: 아래로 갈수록 가늘고 살짝 벌어진다
    for i, sx in enumerate((-1, 1)):
        rod(f"leg_f{i}", "oak", (sx * (w / 2 - 0.028), 0, d / 2 - 0.035), (sx * (w / 2 - 0.055), under, d / 2 - 0.06),
            0.013, 0.019, "ese")
    # 뒷다리는 등판까지 한 줄로 올라가며 뒤로 눕는다
    for i, sx in enumerate((-1, 1)):
        rod(f"leg_b{i}", "oak", (sx * (w / 2 - 0.03), 0, -d / 2 + 0.03), (sx * (w / 2 - 0.05), under, -d / 2 + 0.085),
            0.013, 0.019, "ese")
        rod(f"post{i}", "oak", (sx * (w / 2 - 0.05), under, -d / 2 + 0.085), (sx * (w / 2 - 0.06), h - 0.06, -d / 2 + 0.04),
            0.019, 0.014, "ese")
    # 방석 틀과 방석
    part("frame", "oak", -w / 2 + 0.03, w / 2 - 0.03, -d / 2 + 0.06, d / 2 - 0.03, under - 0.04, under, "sps", 0.008)
    soft("seat", "seat", -w / 2, w / 2, -d / 2 + 0.05, d / 2, under, seat, "sps", r=0.024, puff=0.012)
    # 굽은 등판 (가운데가 가장 뒤 = 깊이 끝)
    t, bow = 0.02, 0.045
    bowed("back", "oak", -w / 2 + 0.035, w / 2 - 0.035, h - 0.2, h, -d / 2 + bow + t / 2, bow, t, "sse")
    bowed("back_low", "oak", -w / 2 + 0.05, w / 2 - 0.05, seat + 0.16, seat + 0.2, -d / 2 + bow + t / 2 + 0.01, bow, 0.016,
          "sse")
    # 옆 가로대
    for i, sx in enumerate((-1, 1)):
        rod(f"rail{i}", "oak", (sx * (w / 2 - 0.04), 0.19, -d / 2 + 0.05), (sx * (w / 2 - 0.04), 0.19, d / 2 - 0.045),
            0.009, 0.009, "ees", 12)


def table(w, h, d):
    """원목 식탁: 모서리를 굴린 두툼한 상판, 안쪽으로 들인 틀, 가늘어지는 둥근 다리."""
    top, inset = 0.036, 0.09
    part("top", "oak", -w / 2, w / 2, -d / 2, d / 2, h - top, h, "ses", 0.014)
    for i, (sx, sz) in enumerate(CORNERS):
        rod(f"leg{i}", "oak", (sx * (w / 2 - 0.055), 0, sz * (d / 2 - 0.055)),
            (sx * (w / 2 - inset), h - top, sz * (d / 2 - inset)), 0.017, 0.028, "ese")
    for i, sz in enumerate((-1, 1)):
        z = sz * (d / 2 - inset)
        part(f"apron{i}", "oak", -w / 2 + inset, w / 2 - inset, z - 0.011, z + 0.011, h - top - 0.07, h - top, "see", 0.004)
    for i, sx in enumerate((-1, 1)):
        x = sx * (w / 2 - inset)
        part(f"apron_s{i}", "oak", x - 0.011, x + 0.011, -d / 2 + inset, d / 2 - inset, h - top - 0.07, h - top, "ees", 0.004)


def storage(w, h, d):
    """수납장: 걸레받이, 문 두 짝, 얇은 덮개 판 (정면 +Z, 다른 장과 같은 방향)"""
    base, hd, cap = 0.08, 0.018, 0.02  # 걸레받이 높이, 손잡이가 앞으로 나온 길이 (깊이 d 안에), 덮개 두께
    front = d / 2 - hd  # 문 앞면
    part("plinth", "plinth", -w / 2 + 0.02, w / 2 - 0.02, -d / 2, front - 0.05, 0, base, "ses", 0.003)
    part("body", "white", -w / 2, w / 2, -d / 2, front - 0.02, base, h - cap, "sss", 0.004)
    part("cap", "stone", -w / 2, w / 2, -d / 2, front + 0.004, h - cap, h, "ses", 0.005)
    gap = 0.003
    for i in range(2):
        x0, x1 = -w / 2 + i * w / 2 + gap, -w / 2 + (i + 1) * w / 2 - gap
        part(f"door{i}", "white", x0, x1, front - 0.02, front, base + gap, h - cap - gap, "sse", 0.004)
        hx = x1 - 0.04 if i == 0 else x0 + 0.04
        part(f"handle{i}", "brass", hx - 0.005, hx + 0.005, front, d / 2, h * 0.45, h * 0.45 + 0.16, "ppe", 0.005)


def sofa(w, h, d):
    """패브릭 소파: 둥근 팔걸이, 볼록한 방석 두 장, 뒤로 살짝 누운 등쿠션, 포인트 쿠션, 원목 발."""
    arm, foot, seat, back_t = 0.17, 0.09, 0.44, 0.16
    for i, (sx, sz) in enumerate(CORNERS):
        x, z = sx * (w / 2 - 0.07), sz * (d / 2 - 0.08)
        rod(f"foot{i}", "walnut", (x, 0.002, z), (x - sx * 0.012, foot, z - sz * 0.012), 0.014, 0.022, "eee", 16)
    soft("base", "sofa", -w / 2 + 0.02, w / 2 - 0.02, -d / 2 + 0.02, d / 2 - 0.03, foot, seat - 0.13, "sss", r=0.03)
    for i, sx in enumerate((-1, 1)):
        x0 = -w / 2 if sx < 0 else w / 2 - arm
        soft(f"arm{i}", "sofa", x0, x0 + arm, -d / 2 + 0.01, d / 2 - 0.015, foot + 0.01, 0.63, "ess", r=0.07)
    soft("back", "sofa", -w / 2 + 0.03, w / 2 - 0.03, -d / 2, -d / 2 + back_t, foot + 0.01, h - 0.07, "sse", r=0.06)
    inner = w - 2 * arm
    for i in range(2):
        x0 = -w / 2 + arm + i * inner / 2 + 0.004
        x1 = x0 + inner / 2 - 0.008
        soft(f"cushion{i}", "sofa_seat", x0, x1, -d / 2 + back_t - 0.02, d / 2, seat - 0.14, seat, "sps", r=0.05, puff=0.022)
        soft(f"pillow{i}", "sofa_seat", x0 + 0.01, x1 - 0.01, -d / 2 + back_t - 0.03, -d / 2 + back_t + 0.15, seat - 0.01, h,
             "sse", r=0.065, lean=0.05)
    # 포인트 쿠션 (크기는 그대로, 양 끝 팔걸이 옆)
    for i, (sx, look) in enumerate(((-1, "sage"), (1, "clay"))):
        xc = sx * (w / 2 - arm - 0.2)
        soft(f"throw{i}", look, xc - 0.19, xc + 0.19, -d / 2 + back_t + 0.12, -d / 2 + back_t + 0.25, seat + 0.01, seat + 0.36,
             "eee", r=0.06, lean=0.07)


def bed(w, h, d):
    """침대: 천을 씌운 머리판, 낮은 원목 틀, 둥근 매트리스, 접어 내린 이불과 발치 담요, 베개 넷."""
    leg, frame_top, mat_top = 0.12, 0.3, 0.54
    for i, (sx, sz) in enumerate(CORNERS):
        x, z = sx * (w / 2 - 0.09), sz * (d / 2 - 0.1)
        rod(f"leg{i}", "walnut", (x, 0, z), (x, leg, z), 0.018, 0.028, "eee", 16)
    part("frame", "walnut", -w / 2, w / 2, -d / 2 + 0.07, d / 2, leg, frame_top, "sps", 0.014)
    soft("headboard", "headboard", -w / 2, w / 2, -d / 2, -d / 2 + 0.09, leg, h, "sse", r=0.04)
    soft("mattress", "linen", -w / 2 + 0.035, w / 2 - 0.035, -d / 2 + 0.1, d / 2 - 0.03, frame_top - 0.02, mat_top, "sps",
         r=0.06, puff=0.008)
    soft("duvet", "duvet", -w / 2 + 0.015, w / 2 - 0.015, -d / 2 + 0.72, d / 2 - 0.015, mat_top - 0.12, mat_top + 0.05, "sps",
         r=0.045, puff=0.02)
    soft("duvet_fold", "linen", -w / 2 + 0.02, w / 2 - 0.02, -d / 2 + 0.6, -d / 2 + 0.86, mat_top + 0.005, mat_top + 0.075,
         "spe", r=0.035)
    soft("blanket", "blanket", -w / 2 + 0.005, w / 2 - 0.005, d / 2 - 0.62, d / 2 - 0.16, mat_top - 0.1, mat_top + 0.092, "spe",
         r=0.03)
    for i, sx in enumerate((-1, 1)):
        x = sx * w / 4
        soft(f"pillow{i}", "linen", x - w / 4.6, x + w / 4.6, -d / 2 + 0.13, -d / 2 + 0.5, mat_top - 0.01, mat_top + 0.13, "ppe",
             r=0.06, puff=0.03)
        soft(f"sham{i}", "sage" if i == 0 else "headboard", x - w / 6, x + w / 6, -d / 2 + 0.36, -d / 2 + 0.6, mat_top,
             mat_top + 0.3, "ppe", r=0.055, lean=0.12)


def desk(w, h, d):
    """책상: 둥근 모서리 상판, 가늘어지는 다리, 오른쪽 서랍"""
    top = 0.028
    part("top", "ash", -w / 2, w / 2, -d / 2, d / 2, h - top, h, "ses", 0.012)
    for i, (sx, sz) in enumerate(CORNERS):
        rod(f"leg{i}", "ash", (sx * (w / 2 - 0.045), 0, sz * (d / 2 - 0.045)),
            (sx * (w / 2 - 0.07), h - top, sz * (d / 2 - 0.07)), 0.014, 0.024, "ese")
    part("drawer", "white", w / 2 - 0.5, w / 2 - 0.1, -d / 2 + 0.08, d / 2 - 0.03, h - top - 0.12, h - top - 0.005, "pse", 0.006)
    part("pull", "brass", w / 2 - 0.36, w / 2 - 0.24, d / 2 - 0.03, d / 2 - 0.018, h - top - 0.07, h - top - 0.058, "ppe", 0.004)


def shelf(w, h, d):
    """책장: 옆판·선반 다섯 단, 칸마다 책 몇 권과 소품"""
    side = 0.022
    for i, sx in enumerate((-1, 1)):
        x0 = -w / 2 if sx < 0 else w / 2 - side
        part(f"side{i}", "oak", x0, x0 + side, -d / 2, d / 2, 0, h, "ess", 0.004)
    part("back", "oak", -w / 2 + side, w / 2 - side, -d / 2, -d / 2 + 0.01, 0, h, "sse", 0.002)
    n = 5
    ys = [0.05 + i * (h - 0.07) / (n - 1) for i in range(n)]
    for i, y in enumerate(ys):
        part(f"board{i}", "oak", -w / 2 + side, w / 2 - side, -d / 2 + 0.01, d / 2, y - 0.011, y + 0.011, "sps", 0.003)
    looks = ("book_a", "book_b", "book_c", "white")
    for row, y in enumerate(ys[:-1]):
        x = -w / 2 + side + 0.03 if row % 2 == 0 else w / 2 - side - 0.03 - 0.21
        for k in range(5):
            bw, bh = 0.028 + 0.008 * ((row + k) % 3), 0.2 + 0.03 * ((row * 2 + k) % 3)
            part(f"book{row}_{k}", looks[(row + k) % 4], x, x + bw, -d / 2 + 0.03, d / 2 - 0.04, y + 0.011, y + 0.011 + bh,
                 "epe", 0.003)
            x += bw + 0.003
    cyl("vase", "pot", w / 2 - side - 0.12, 0, 0.045, ys[0] + 0.011, ys[0] + 0.2, "epe", 24, 0.028)


def tvstand(w, h, d):
    """거실장: 월넛 몸통에 문 세 짝, 가는 다리. 위에 얇은 TV 한 대"""
    leg = 0.13
    for i, (sx, sz) in enumerate(CORNERS):
        x, z = sx * (w / 2 - 0.07), sz * (d / 2 - 0.06)
        rod(f"leg{i}", "walnut", (x + sx * 0.012, 0, z), (x, leg, z), 0.011, 0.018, "eee", 16)
    part("body", "walnut", -w / 2, w / 2, -d / 2, d / 2 - 0.012, leg, h, "sps", 0.008)
    gap = 0.004
    for i in range(3):
        x0 = -w / 2 + i * w / 3 + gap
        part(f"door{i}", "oak", x0, x0 + w / 3 - 2 * gap, d / 2 - 0.012, d / 2, leg + 0.012, h - 0.012, "sse", 0.004)


def island(w, h, d):
    part("plinth", "plinth", -w / 2 + 0.05, w / 2 - 0.05, -d / 2 + 0.05, d / 2 - 0.05, 0, 0.1, "ses", 0.003)
    part("body", "white", -w / 2 + 0.02, w / 2 - 0.02, -d / 2 + 0.02, d / 2 - 0.02, 0.1, h - 0.03, "sss", 0.004)
    part("top", "stone", -w / 2, w / 2, -d / 2, d / 2, h - 0.03, h, "ses", 0.006)


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
    part("rug", "wool", -w / 2, w / 2, -d / 2, d / 2, 0, h, "sss", 0.004)


def lamp(w, h, d):
    """플로어 램프: 묵직한 받침, 가는 황동 기둥, 천 갓"""
    r = min(w, d) / 2
    cyl("base", "metal", 0, 0, r * 0.62, 0, 0.018, "eee", 40)
    cyl("base_top", "metal", 0, 0, r * 0.58, 0.018, 0.026, "eee", 40, r * 0.2)
    cyl("pole", "brass", 0, 0, 0.009, 0.026, h - 0.3, "ese", 16)
    cyl("collar", "brass", 0, 0, 0.02, h - 0.34, h - 0.3, "eee", 20)
    cyl("shade", "shade", 0, 0, r, h - 0.3, h, "eee", 48, r * 0.72)
    cyl("shade_rim", "brass", 0, 0, r + 0.002, h - 0.3, h - 0.292, "eee", 48)


def plant(w, h, d):
    """화분: 테가 있는 토분, 여러 줄기에서 뻗은 큰 잎"""
    r = min(w, d) / 2
    pot_h = h * 0.27
    cyl("pot", "pot", 0, 0, r * 0.48, 0, pot_h, "eee", 40, r * 0.62)
    cyl("pot_rim", "pot", 0, 0, r * 0.66, pot_h - 0.03, pot_h, "eee", 40)
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
    """낮은 탁자: 둥근 모서리 상판, 아래 선반, 가늘어지는 다리"""
    top = 0.03
    part("top", "oak", -w / 2, w / 2, -d / 2, d / 2, h - top, h, "ses", 0.013)
    part("shelf", "oak", -w / 2 + 0.09, w / 2 - 0.09, -d / 2 + 0.09, d / 2 - 0.09, 0.11, 0.128, "sps", 0.006)
    for i, (sx, sz) in enumerate(CORNERS):
        rod(f"leg{i}", "oak", (sx * (w / 2 - 0.045), 0, sz * (d / 2 - 0.045)),
            (sx * (w / 2 - 0.075), h - top, sz * (d / 2 - 0.075)), 0.012, 0.021, "ese", 16)


def partition(w, h, d):
    """세로 살 파티션: 위아래 틀 + 살. 폭을 늘리면 살 간격이 같이 늘어난다."""
    part("bottom", "oak", -w / 2, w / 2, -d / 2, d / 2, 0, 0.04, "ses", 0.003)
    part("top", "oak", -w / 2, w / 2, -d / 2, d / 2, h - 0.04, h, "sps", 0.003)
    n = 12
    for i in range(n):
        x = -w / 2 + 0.025 + i * (w - 0.05) / (n - 1)
        part(f"slat{i}", "oak", x - 0.018, x + 0.018, -d / 2 + 0.005, d / 2 - 0.005, 0.04, h - 0.04, "psp", 0.003)


def wall(w, h, d):
    part("wall", "plaster", -w / 2, w / 2, -d / 2, d / 2, 0, h, "sss", 0.004)
    part("skirt", "white", -w / 2 - 0.004, w / 2 + 0.004, -d / 2 - 0.004, d / 2 + 0.004, 0, 0.08, "ses", 0.002)


def dresser(w, h, d):
    """서랍장: 서랍 4단, 가운데 손잡이 (정면 +Z, 거실장과 같은 방향)"""
    base, gap, n = 0.06, 0.004, 4
    part("plinth", "plinth", -w / 2 + 0.02, w / 2 - 0.02, -d / 2, d / 2 - 0.03, 0, base, "ses", 0.003)
    part("body", "oak", -w / 2, w / 2, -d / 2, d / 2 - 0.02, base, h, "sss", 0.004)
    step = (h - base) / n
    for i in range(n):
        y0 = base + i * step + gap
        part(f"drawer{i}", "oak", -w / 2 + gap, w / 2 - gap, d / 2 - 0.02, d / 2, y0, y0 + step - 2 * gap, "sse", 0.003)
        yc = y0 + step / 2
        part(f"pull{i}", "metal", -0.08, 0.08, d / 2, d / 2 + 0.015, yc - 0.008, yc + 0.008, "ppe", 0.004)


def basecab(w, h, d):
    """주방 하부장: 걸레받이 + 문 2짝 + 위 상판(앞으로 살짝 나옴)"""
    base, top, gap = 0.1, 0.03, 0.003
    part("plinth", "plinth", -w / 2 + 0.02, w / 2 - 0.02, -d / 2, d / 2 - 0.06, 0, base, "ses", 0.003)
    part("body", "white", -w / 2, w / 2, -d / 2, d / 2 - 0.04, base, h - top, "sss", 0.004)
    for i in range(2):
        x0, x1 = -w / 2 + i * w / 2 + gap, -w / 2 + (i + 1) * w / 2 - gap
        part(f"door{i}", "white", x0, x1, d / 2 - 0.04, d / 2 - 0.02, base + gap, h - top - gap, "sse", 0.003)
        hx = x1 - 0.05 if i == 0 else x0 + 0.05
        part(f"handle{i}", "metal", hx - 0.006, hx + 0.006, d / 2 - 0.02, d / 2 - 0.005, h - top - 0.2, h - top - 0.06, "ppe", 0.004)
    part("top", "stone", -w / 2, w / 2, -d / 2, d / 2, h - top, h, "ses", 0.006)


def wardrobe(w, h, d):
    """장롱: 걸레받이 + 키 큰 여닫이문 2짝, 가운데에 긴 손잡이 (정면 +Z)"""
    base, gap = 0.07, 0.003
    part("plinth", "plinth", -w / 2 + 0.02, w / 2 - 0.02, -d / 2, d / 2 - 0.05, 0, base, "ses", 0.003)
    part("body", "white", -w / 2, w / 2, -d / 2, d / 2 - 0.02, base, h, "sss", 0.004)
    for i in range(2):
        x0, x1 = -w / 2 + i * w / 2 + gap, -w / 2 + (i + 1) * w / 2 - gap
        part(f"door{i}", "white", x0, x1, d / 2 - 0.02, d / 2, base + gap, h - gap, "sse", 0.003)
        hx = x1 - 0.035 if i == 0 else x0 + 0.035
        part(f"handle{i}", "metal", hx - 0.005, hx + 0.005, d / 2, d / 2 + 0.014, h * 0.42, h * 0.42 + 0.3, "ppe", 0.004)


def tallcab(w, h, d):
    """키큰장: 걸레받이 + 위아래 문 2짝 (냉장고 옆에 세우는 주방 장, 정면 +Z)"""
    base, gap, split = 0.1, 0.003, 0.62
    part("plinth", "plinth", -w / 2 + 0.02, w / 2 - 0.02, -d / 2, d / 2 - 0.06, 0, base, "ses", 0.003)
    part("body", "white", -w / 2, w / 2, -d / 2, d / 2 - 0.02, base, h, "sss", 0.004)
    ym = base + (h - base) * split
    part("door_low", "white", -w / 2 + gap, w / 2 - gap, d / 2 - 0.02, d / 2, base + gap, ym - gap, "sse", 0.003)
    part("door_up", "white", -w / 2 + gap, w / 2 - gap, d / 2 - 0.02, d / 2, ym + gap, h - gap, "sse", 0.003)
    hx = w / 2 - 0.04
    part("handle_low", "metal", hx - 0.005, hx + 0.005, d / 2, d / 2 + 0.014, ym - 0.3, ym - 0.06, "epe", 0.004)
    part("handle_up", "metal", hx - 0.005, hx + 0.005, d / 2, d / 2 + 0.014, ym + 0.06, ym + 0.3, "epe", 0.004)


def sink(w, h, d):
    """싱크대: 하부장 + 상판에 파인 개수대(오른쪽) + 거위목 수전. 상판은 개수대 둘레 네 조각"""
    base, top, gap = 0.1, 0.03, 0.003
    part("plinth", "plinth", -w / 2 + 0.02, w / 2 - 0.02, -d / 2, d / 2 - 0.06, 0, base, "ses", 0.003)
    # 개수대 자리 (오른쪽 반, 뒤에 수전 놓을 턱을 남긴다). 몸통은 개수대 바닥 아래까지만, 그 위는 둘레만 채운다
    bx0, bx1, bz0, bz1, deep = 0.02, w / 2 - 0.07, -d / 2 + 0.13, d / 2 - 0.08, 0.18
    neck, zf = h - deep - 0.004, d / 2 - 0.04
    part("body", "white", -w / 2, w / 2, -d / 2, zf, base, neck, "sss", 0.004)
    part("apron_l", "white", -w / 2, bx0, -d / 2, zf, neck, h - top, "ses", 0.002)
    part("apron_r", "white", bx1, w / 2, -d / 2, zf, neck, h - top, "ses", 0.002)
    part("apron_b", "white", bx0, bx1, -d / 2, bz0, neck, h - top, "ses", 0.002)
    part("apron_f", "white", bx0, bx1, bz1, zf, neck, h - top, "ses", 0.002)
    for i in range(2):
        x0, x1 = -w / 2 + i * w / 2 + gap, -w / 2 + (i + 1) * w / 2 - gap
        part(f"door{i}", "white", x0, x1, d / 2 - 0.04, d / 2 - 0.02, base + gap, h - top - gap, "sse", 0.003)
        hx = x1 - 0.05 if i == 0 else x0 + 0.05
        part(f"handle{i}", "metal", hx - 0.006, hx + 0.006, d / 2 - 0.02, d / 2 - 0.005, h - top - 0.2, h - top - 0.06, "ppe", 0.004)
    part("top_left", "stone", -w / 2, bx0, -d / 2, d / 2, h - top, h, "ses", 0.004)
    part("top_right", "stone", bx1, w / 2, -d / 2, d / 2, h - top, h, "ses", 0.004)
    part("top_back", "stone", bx0, bx1, -d / 2, bz0, h - top, h, "ses", 0.004)
    part("top_front", "stone", bx0, bx1, bz1, d / 2, h - top, h, "ses", 0.004)
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
    cyl("faucet_base", "steel", cxb, fz, 0.026, h, h + 0.035, "pep", 28)
    bar("faucet_riser", "steel", (cxb, h + 0.03, fz), (cxb, h + 0.30, fz), 0.012, "pep")
    arc = [(h + 0.30, fz), (h + 0.345, fz + 0.03), (h + 0.36, fz + 0.08), (h + 0.345, fz + 0.14), (h + 0.30, fz + 0.17)]
    for i, ((y0, z0), (y1, z1)) in enumerate(zip(arc, arc[1:])):
        bar(f"faucet_neck{i}", "steel", (cxb, y0, z0), (cxb, y1, z1), 0.012, "pep")
        ball(f"faucet_joint{i}", "steel", cxb, y0, z0, 0.012, "pep")
    ball("faucet_joint_end", "steel", cxb, arc[-1][0], arc[-1][1], 0.012, "pep")
    bar("faucet_tip", "steel", (cxb, h + 0.30, fz + 0.17), (cxb, h + 0.255, fz + 0.17), 0.013, "pep")
    bar("faucet_lever", "steel", (cxb + 0.026, h + 0.022, fz), (cxb + 0.085, h + 0.04, fz), 0.007, "pep")


def door(w, h, d):
    """여닫이문: 문틀(양옆·위) + 문짝 + 손잡이·경첩. 문짝 부품 이름은 leaf로 시작한다 (웹이 경첩 축으로 돌려 연다).
    경첩은 왼쪽(-x), 앞(+z)으로 열린다."""
    jamb, head, t = 0.045, 0.045, 0.04
    part("jamb_l", "white", -w / 2, -w / 2 + jamb, -d / 2, d / 2, 0, h, "ess", 0.004)
    part("jamb_r", "white", w / 2 - jamb, w / 2, -d / 2, d / 2, 0, h, "ess", 0.004)
    part("head", "white", -w / 2 + jamb, w / 2 - jamb, -d / 2, d / 2, h - head, h, "ses", 0.004)
    x0, x1, y0, y1 = -w / 2 + jamb + 0.003, w / 2 - jamb - 0.003, 0.008, h - head - 0.003
    part("leaf", "door_leaf", x0, x1, -t / 2, t / 2, y0, y1, "sse", 0.003)
    # 문짝 무늬: 앞뒤로 얕게 도드라진 판 두 장
    for side, z in (("f", t / 2), ("b", -t / 2 - 0.004)):
        part(f"leaf_panel_top_{side}", "door_leaf", x0 + 0.09, x1 - 0.09, z, z + 0.004, 1.12, y1 - 0.1, "sse", 0.002)
        part(f"leaf_panel_low_{side}", "door_leaf", x0 + 0.09, x1 - 0.09, z, z + 0.004, y0 + 0.12, 0.98, "sse", 0.002)
    hx, hy = x1 - 0.06, 1.0
    for side, s in (("f", 1), ("b", -1)):
        z = s * t / 2
        bar(f"leaf_rose_{side}", "steel", (hx, hy, z), (hx, hy, z + s * 0.01), 0.026, "eee")
        bar(f"leaf_neck_{side}", "steel", (hx, hy, z), (hx, hy, z + s * 0.05), 0.009, "eee")
        bar(f"leaf_lever_{side}", "steel", (hx + 0.008, hy, z + s * 0.05), (hx - 0.11, hy, z + s * 0.05), 0.009, "eee")
        ball(f"leaf_lever_end_{side}", "steel", hx - 0.11, hy, z + s * 0.05, 0.009, "eee")
    for i, y in enumerate((0.25, 1.05, 1.85)):
        bar(f"hinge{i}", "metal", (x0 - 0.002, y - 0.045, t / 2 + 0.004), (x0 - 0.002, y + 0.045, t / 2 + 0.004), 0.007, "ees")


def _glazed(w, h, d, low, handles):
    """창틀(양옆·위·아래) + 유리 + 가운데서 겹치는 미닫이 창짝 두 장. low = 아래 틀 높이."""
    fr, sash, t = 0.05, 0.035, 0.03
    part("jamb_l", "white", -w / 2, -w / 2 + fr, -d / 2, d / 2, 0, h, "ess", 0.004)
    part("jamb_r", "white", w / 2 - fr, w / 2, -d / 2, d / 2, 0, h, "ess", 0.004)
    part("head", "white", -w / 2 + fr, w / 2 - fr, -d / 2, d / 2, h - fr, h, "ses", 0.004)
    part("sill", "white", -w / 2 + fr, w / 2 - fr, -d / 2, d / 2, 0, low, "ses", 0.004)
    part("glass", "glass", -w / 2 + fr, w / 2 - fr, -0.004, 0.004, low, h - fr, "sss", 0.0)
    # 창짝 테: 가운데 겹치는 세로대 두 개(앞뒤로 어긋남), 위아래 가로대
    part("meet_f", "white", -sash, 0.004, 0.006, 0.006 + t, low, h - fr, "pss", 0.003)
    part("meet_b", "white", -0.004, sash, -0.006 - t, -0.006, low, h - fr, "pss", 0.003)
    part("rail_top", "white", -w / 2 + fr, w / 2 - fr, -t / 2, t / 2, h - fr - sash, h - fr, "ses", 0.003)
    part("rail_low", "white", -w / 2 + fr, w / 2 - fr, -t / 2, t / 2, low, low + sash, "ses", 0.003)
    for name, x, z in handles:
        bar(name, "steel", (x, 0.95, z), (x, 1.2, z), 0.008, "pee")
        ball(name + "_a", "steel", x, 0.95, z, 0.008, "pee")
        ball(name + "_b", "steel", x, 1.2, z, 0.008, "pee")


def window(w, h, d):
    """미닫이 창문: 벽 속에 겹쳐 단다 (웹이 벽을 뚫고 유리를 비치게 그린다)."""
    _glazed(w, h, d, 0.05, ())


def glassdoor(w, h, d):
    """베란다 유리문: 바닥부터 달리는 큰 미닫이 유리문. 가운데 세로 손잡이. 아래 틀은 걸레받이를 가릴 만큼."""
    _glazed(w, h, d, 0.09, (("pull_f", -0.016, 0.045), ("pull_b", 0.016, -0.045)))


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
