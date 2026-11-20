# 빌트인 적합 판정 규칙 (기획 §9.1)

코드: `services/recommender/recommender/fit.py` · 테스트: `tests/unit/test_fit.py`

## 입력
- 방(`Room`), 영역(`Zone`: 다각형 + `wall_ids`, 비어 있으면 영역 경계와 15cm 이내로 겹치는 벽 자동 감지), 제품(`Product`).

## 필요 치수 (mm)
| 축 | `required_space_mm` 있으면 | 없으면 |
|----|----|----|
| 폭 | 그 값 | 제품 w + 2 × side 이격 |
| 높이 | 그 값 | 제품 h + top 이격 |
| 깊이 | 그 값 | 제품 d + back 이격 |
- 이격값이 null이면 제품 치수만 쓰고 `clearance_unknown` 표시, 최종 판정을 **조건부 이하**로 제한.
- 제품 치수도 null이면 그 축은 `unknown`(판정 불가).

## 가용 치수
- **폭**: 영역이 덮는 벽 구간(영역 꼭짓점을 벽 축에 투영, `[0, 벽 길이]`로 자름) − 문·개구부 구간 − 창문 구간(창 하단 `sill_m` ≥ 제품 필요 높이면 제외) − 기존 오브젝트 점유 구간(벽에서 필요 깊이 안쪽에 걸친 것) → **가장 긴 연속 구간**.
  벽 길이는 실측 `length_m` 우선.
- **높이**: 실측 `height_m` 우선, 없으면 스캔.
- **깊이**: 실측 `depth_m` 우선, 없으면 폭 구간 중앙에서 벽 법선 방향으로 영역 경계까지 거리(스캔 기반).

## 축별 판정
스캔은 1~3 cm, 길이의 약 1%씩 틀린다 (근거: `docs/research/lidar-error-correction.md`).
그래서 스캔값의 마진은 길이에 따라 커지고, 스캔 오차 안의 자리는 "확인 필요"(조건부 + `needs_measure`)로 둔다.
```
σ(L) = √(FIT_SCAN_SIGMA_ABS_MM² + (FIT_SCAN_SIGMA_REL · L)²)     기본 10 mm, 1%
스캔 margin m = max(FIT_MARGIN_SCANNED_MM, 2σ(가용 길이))        0.6 m → 30, 3 m → 63 mm
실측 margin m = FIT_MARGIN_MEASURED_MM (5 mm)

여유 = 가용 − 필요
실측: 여유 < 0 → 불가,  0 ≤ 여유 < m → 조건부,  여유 ≥ m → 적합
스캔: 여유 < −m → 불가, −m ≤ 여유 < m → 조건부(확인 필요, notes에 measure_needed), 여유 ≥ m → 적합
                     (FIT_SCANNED_MAX_CONDITIONAL=1이면 스캔값은 조건부까지만)
가용 또는 필요 null → 판정 불가 (unknown)
```
## 최종
- 세 축 중 가장 나쁜 값: 불가 > 판정 불가 > 조건부 > 적합.
- 영역의 벽이 여럿이면 가장 좋은 벽을 고른다(같으면 최소 여유가 큰 벽).
- 결과에 축별 `available_mm`, `required_mm`, `slack_mm`, `margin_mm`, `source`(scanned/measured), `notes`, 배치 위치(`placement`) 포함.
- 미구현(2차): 문 열림 반경 간섭, 같은 영역 여러 제품의 공간 공유.

## 자유 배치 (`recommender/pose.py`)
고객이 고른 위치·방향(`center_xz`, `yaw_rad` = 제품 정면 방향)에 놓았을 때의 판정.

| 사각형 | 범위 |
|---|---|
| 본체 F | 제품 폭 × 깊이 |
| 필요 공간 R | F + 양옆 `clearance.side` + 뒤 `clearance.back` |
| 여유 M | R을 사방으로 스캔 마진 max(30 mm, 2σ(제품 폭 + 양옆 이격))만큼 확장 |

| 검사 | 결과 |
|---|---|
| 치수 null | 판정 불가 |
| 중심이 방 밖 (네 방향 광선 중 셋 이상이 벽에 닿아야 방 안) | 불가 |
| F가 벽·기존 가구·다른 제품과 겹침 | 불가 (`hits_wall`, `overlaps_object`, `overlaps_placement`) |
| R만 겹침 | 불가 (`clearance_blocked`) |
| M만 겹침 | 조건부 (`tight`) |
| 가장 가까운 벽 높이 < 제품 높이 + 위 이격 | 불가, 마진 이내면 조건부 |
| 문 열림 범위(문 폭 × 문 폭, 벽 양쪽) | 한쪽만 걸리면 조건부(반대로 열린다고 가정), 양쪽 다면 불가 |
| 창턱보다 높은 제품이 창 앞 0.3 m 띠에 걸침 | 조건부 (`covers_window`) |
| 이격 정보 null | 조건부 이하 (`clearance_unknown`) |

- 천장 검사 마진은 max(30 mm, 2σ(벽 높이)).
- 넣을 자리 실측(선택, `placement.measured_mm` = {w, h, d} mm): 폭·깊이를 다 재면 벽·스캔 가구 겹침 검사 대신, 높이를 재면 천장 검사 대신 잰 값으로 판정한다. 필요 = 제품 + 이격, 실측 마진 5 mm (`measured_short` 불가, `measured_tight` 조건부). 다른 제품·문·창 검사는 그대로.
- 치운 가구(`hidden_objects`)는 검사에서 뺀다.
- 벽 붙이기: 가장 가까운 벽까지 `거리 − 벽두께/2 − 깊이/2 − 뒤 이격`이 `FIT_SNAP_M`(0.3) 이하면, 뒷면을 벽 안쪽 면 + 뒤 이격 + 마진에 맞추고 정면을 방 안으로 돌린다.
- 한 제품을 옮기거나 가구를 치우면 나머지 자유 배치도 다시 판정한다.
