"""원본 깊이(Stray Scanner 내보내기)로 RoomPlan 벽 치수 다듬기 — 테스트 먼저.
근거: docs/research/lidar-error-correction.md §8

합성 주방(3.0 × 2.4 m, 높이 2.4 m)을 만들고, RoomPlan 결과에는 일부러 오차(배율 +2%, 3 cm 격자)를 넣는다.
원본 깊이 프레임(1 cm 노이즈, 신뢰도)으로 평면을 맞춰 벽 사이 거리를 되찾는지 본다.
"""
import math

import numpy as np
import pytest

from worker.rawdepth import (
    fuse_points, fit_planes, load_stray, refine_room, frame_points, vertical_spans,
)
from worker.rawdepth_synth import BOX, roomplan_with_error, synth_frames, write_stray


@pytest.fixture(scope="module")
def frames():
    return synth_frames(n=24, seed=1)


def test_write_and_load_stray_roundtrip(tmp_path, frames):
    write_stray(tmp_path, frames[:3])
    got = load_stray(tmp_path)
    assert len(got) == 3
    f0, g0 = frames[0], got[0]
    assert g0.depth_m.shape == (192, 256) and g0.conf.shape == (192, 256)
    assert np.allclose(g0.T_wc, f0.T_wc, atol=1e-5)
    assert np.allclose(g0.K, f0.K, atol=1e-3)
    assert np.nanmax(np.abs(g0.depth_m - f0.depth_m)) <= 0.0006  # mm 정수 저장


def test_points_land_on_box_faces(frames):
    pts = frame_points(frames[0], min_conf=2)
    lo, hi = np.array(BOX[0]), np.array(BOX[1])
    d = np.minimum(np.abs(pts - lo), np.abs(pts - hi)).min(axis=1)
    assert np.median(d) < 0.02  # 노이즈 1 cm 수준으로 면 위에


def test_low_confidence_is_dropped(frames):
    f = frames[0]
    assert len(frame_points(f, min_conf=2)) < len(frame_points(f, min_conf=0))


def test_fused_planes_recover_room_size(frames):
    pts = fuse_points(frames, voxel_m=0.01)
    planes = fit_planes(pts, seed=0)
    spans = vertical_spans(planes)
    (sx, sz) = (BOX[1][0] - BOX[0][0], BOX[1][2] - BOX[0][2])
    assert spans["x"] == pytest.approx(sx, abs=0.005)
    assert spans["z"] == pytest.approx(sz, abs=0.005)


def test_refine_room_fixes_roomplan_error(frames):
    room = roomplan_with_error(scale=1.02, grid=0.03)
    out = refine_room(room, fuse_points(frames, voxel_m=0.01), seed=0)
    assert out.matched >= 4
    true = {"x": BOX[1][0] - BOX[0][0], "z": BOX[1][2] - BOX[0][2]}
    for s in out.spans:
        err_before = abs(s.scanned_m - true[s.axis])
        err_after = abs(s.refined_m - true[s.axis])
        assert err_before > 0.03 and err_after < 0.005, s


def test_refine_room_works_in_another_session_frame(frames):
    """RoomPlan(UGScan)과 원본 깊이 캡처는 따로 찍어서 좌표계가 다르다 → 회전·이동을 스스로 맞춘다."""
    room = roomplan_with_error(scale=1.02, grid=0.03, yaw_deg=37.0, shift=(1.3, -0.4))
    out = refine_room(room, fuse_points(frames, voxel_m=0.01), seed=0)
    assert out.matched >= 4
    true = {BOX[1][0] - BOX[0][0], BOX[1][2] - BOX[0][2]}
    for s in out.spans:
        assert min(abs(s.refined_m - t) for t in true) < 0.005, s


def test_refine_room_reports_nothing_when_capture_is_elsewhere(frames):
    """다른 방을 찍은 캡처면 억지로 맞추지 않는다."""
    room = roomplan_with_error(scale=2.0, grid=0.03)
    out = refine_room(room, fuse_points(frames, voxel_m=0.01), seed=0)
    assert out.matched < 4 and out.spans == []
