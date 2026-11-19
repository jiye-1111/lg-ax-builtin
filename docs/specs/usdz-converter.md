# USDZ → room.json 변환기 스펙

코드: `services/blender-worker/worker/converter.py` (usd-core, Blender 불필요)

## 처리
1. Stage 열기 → `metersPerUnit`으로 m 환산, `upAxis` Z면 Y-up으로 회전.
2. 프림 순회. **이름에 숫자가 있고 `CLASSIFY_RULES`에 맞는 첫 프림**을 요소 1개로 보고 자손은 건너뜀.
   - `^wall` → 벽, `^door` → 문, `^window` → 창, `^opening` → 개구부, `^(floor|ceiling)` → 무시, 그 밖 `이름+숫자` → 오브젝트(분류 = 이름 snake_case).
3. 요소 아래 모든 지오메트리의 로컬 extent 8꼭짓점 × 월드 변환 → 평면 투영 PCA로 방향 박스(OBB).
   - 벽: 주축 = 벽 방향, 길이·두께·높이. 개구부: 가장 가까운 벽, offset. 오브젝트: bbox·위치·yaw.

## 현재 상태 — ⚠️ 실제 UGScan 구조 미확인
- 합성 픽스처(`worker/fixtures.py`)는 Apple RoomPlan 내보내기 관례를 **가정**한 구조다:
  `/Room/Architecture/Walls/Wall0 (Xform) └ Wall0_geom (Cube|Mesh)`, `Doors/Door0`, `Windows/Window0`, `/Room/Object/Storage/Storage0`.
- 테스트: 회전(23°, −40°)·원점 이동·cm 단위·Cube/Mesh 지오메트리에서 치수가 1mm 이내로 복원되는지.

## 실제 샘플 분석 절차 (plan.md T0.4 → T1.6)
1. UGScan RoomPlan 모드로 스캔 → USDZ 내보내기 → `data/samples/<공간명>.usdz`.
2. 같은 공간의 핵심 벽을 줄자로 재서 `data/samples/<공간명>.measurements.json`:
   ```json
   {"space": "교육장 A", "measured_at": "2026-11-20", "by": "이름",
    "walls": [{"desc": "싱크대 벽", "length_m": 3.205, "height_m": 2.31}],
    "openings": [{"desc": "현관문", "width_m": 0.90, "height_m": 2.10}]}
   ```
3. `uv run python -m worker.inspect_usdz data/samples/<공간명>.usdz > docs/specs/usdz-analysis-<공간명>.txt`
   → 프림 이름·타입·분류 결과·변환 요약이 나온다. 분류가 `-`로 나오는 요소, 이중으로 잡히는 요소를 확인.
4. 차이를 `CLASSIFY_RULES` 또는 OBB 계산에 반영하고, 줄자값과의 오차를 테스트로 고정 (`tests/unit/test_converter_real.py`).
5. 스캔값과 줄자값 차이 분포 → `FIT_MARGIN_SCANNED_MM` 기본값 결정 (기획 Q7).

막히면 Apple RoomPlan 샘플 앱의 JSON 내보내기로 전환 (기획 §12) — 변환기만 추가하면 이후 단계는 그대로.
