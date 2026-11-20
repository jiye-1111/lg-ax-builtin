"""실제 교실 스캔에 오차를 일부러 넣고, 보정하면 얼마나 돌아오는지 본다.

    uv run python docs/research/scan_correction_experiment.py

정답이 없어서(줄자 실측 없음) 실제 스캔을 '정답'으로 두고, 문헌 수준의 오차를 넣은 가짜 스캔을
200번 만든다. 오차 모델은 lidar-error-correction.md §2 참고.
"""
from __future__ import annotations

import argparse
import math
import random
import statistics as st

from core import config
from recommender.scan_correction import angle_deviation_deg, fit_scale, snap_manhattan
from worker.converter import convert_usdz

SAMPLE = config.ROOT / "data" / "samples" / "ugscan_2026-11-18.usdz"


def perturb(room, rng, scale_sd, angle_sd_deg, len_sd_mm, wall_rel_sd=0.0):
    s = rng.gauss(1.0, scale_sd)
    walls = []
    for w in room.walls:
        mx, my = (w.start[0] + w.end[0]) / 2 * s, (w.start[1] + w.end[1]) / 2 * s
        L = w.scanned.length_m * s * rng.gauss(1.0, wall_rel_sd) + rng.gauss(0, len_sd_mm / 1000)
        t = math.atan2(w.end[1] - w.start[1], w.end[0] - w.start[0]) + math.radians(rng.gauss(0, angle_sd_deg))
        dx, dy = math.cos(t) * L / 2, math.sin(t) * L / 2
        walls.append(w.model_copy(update={
            "start": (mx - dx, my - dy), "end": (mx + dx, my + dy),
            "scanned": w.scanned.model_copy(update={"length_m": L}),
        }))
    return room.model_copy(update={"walls": walls})


def run(trials, scale_sd, angle_sd, len_sd, tape_sd_mm, wall_rel_sd=0.0, seed=7):
    truth = convert_usdz(SAMPLE)
    true_len = {w.wall_id: w.scanned.length_m for w in truth.walls}
    ref_id = max(truth.walls, key=lambda w: w.scanned.length_m).wall_id  # 가장 긴 벽 하나만 잰다
    rng = random.Random(seed)
    e_raw, e_cal, a_raw, a_snap = [], [], [], []
    for _ in range(trials):
        r = perturb(truth, rng, scale_sd, angle_sd, len_sd, wall_rel_sd)
        meas = {w.wall_id: w.scanned.length_m for w in r.walls}
        fit = fit_scale([(meas[ref_id], true_len[ref_id] + rng.gauss(0, tape_sd_mm / 1000))])
        for wid, L in true_len.items():
            if wid == ref_id or L < 1.0:
                continue
            e_raw.append(abs(meas[wid] - L) * 1000)
            e_cal.append(abs(meas[wid] * fit.scale - L) * 1000)
        a_raw.append(max(angle_deviation_deg(r).values()))
        a_snap.append(max(angle_deviation_deg(snap_manhattan(r)).values()))

    def p95(x):
        return sorted(x)[int(len(x) * 0.95)]

    print(f"오차 모델: 배율 σ {scale_sd*100:.1f}%, 벽마다 따로 σ {wall_rel_sd*100:.1f}%, 벽 각도 σ {angle_sd}°, 벽 길이 σ {len_sd} mm, 줄자 σ {tape_sd_mm} mm, {trials}회")
    print(f"벽 길이 오차 (1 m 이상 벽, 기준 벽 제외) 평균/95%: 보정 전 {st.mean(e_raw):.1f} / {p95(e_raw):.1f} mm"
          f" → 실측 1개로 배율 보정 후 {st.mean(e_cal):.1f} / {p95(e_cal):.1f} mm")
    print(f"가장 많이 기운 벽 평균: 보정 전 {st.mean(a_raw):.2f}° → 직각 맞춤 후 {st.mean(a_snap):.3f}°")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--scale-sd", type=float, default=0.01)
    ap.add_argument("--angle-sd", type=float, default=1.0)
    ap.add_argument("--len-sd", type=float, default=10.0)
    ap.add_argument("--tape-sd", type=float, default=2.0)
    ap.add_argument("--wall-rel-sd", type=float, default=0.0, help="벽마다 다른 비례 오차 (드리프트 흉내)")
    a = ap.parse_args()
    run(a.trials, a.scale_sd, a.angle_sd, a.len_sd, a.tape_sd, a.wall_rel_sd)
