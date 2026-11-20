"""원본 깊이 융합 + 평면 맞춤이 RoomPlan 치수 오차를 얼마나 줄이는지 합성 주방(3.0 × 2.4 m)으로 본다.

    uv run python docs/research/rawdepth_experiment.py

실제 원본 깊이 캡처가 아직 없어서 합성 데이터다. 깊이 노이즈는 거리의 1%, RoomPlan 오차는 배율 +1.5%와 3 cm 격자.
"""
from __future__ import annotations

import statistics as st

from worker.rawdepth import fuse_points, refine_room
from worker.rawdepth_synth import BOX, roomplan_with_error, synth_frames

TRUE = {"x": BOX[1][0] - BOX[0][0], "z": BOX[1][2] - BOX[0][2]}


def run(label, trials=10, **kw):
    before, after, fails = [], [], 0
    for seed in range(trials):
        room = roomplan_with_error(scale=1.015, grid=0.03)
        out = refine_room(room, fuse_points(synth_frames(n=24, seed=seed, **kw)), seed=seed)
        if not out.spans:
            fails += 1
            continue
        for s in out.spans:
            before.append(abs(s.scanned_m - TRUE[s.axis]) * 1000)
            after.append(abs(s.refined_m - TRUE[s.axis]) * 1000)
    print(f"{label}: RoomPlan {st.mean(before):.1f} mm → 원본 깊이 평면 {st.mean(after):.1f} mm (최대 {max(after):.1f}), 못 맞춘 경우 {fails}/{trials}")


if __name__ == "__main__":
    run("깊이 노이즈 1%, 위치 밀림 없음")
    run("깊이 노이즈 2%, 위치 밀림 없음", noise_m=0.02)
    run("깊이 노이즈 1%, 프레임마다 1 mm씩 밀림", drift_m=0.001)
    run("깊이 노이즈 1%, 프레임마다 3 mm씩 밀림", drift_m=0.003)
    run("깊이 노이즈 1%, 프레임마다 10 mm씩 밀림", drift_m=0.010)
