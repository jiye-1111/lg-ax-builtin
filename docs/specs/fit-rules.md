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
```
여유 = 가용 − 필요;  margin = 실측 5mm / 스캔 30mm (.env)
여유 < 0           → 불가 (no_fit)
0 ≤ 여유 < margin  → 조건부 (conditional)
여유 ≥ margin      → 적합 (fit). 단 스캔값이면 조건부로 한 단계 낮춤
가용 또는 필요 null → 판정 불가 (unknown)
```
## 최종
- 세 축 중 가장 나쁜 값: 불가 > 판정 불가 > 조건부 > 적합.
- 영역의 벽이 여럿이면 가장 좋은 벽을 고른다(같으면 최소 여유가 큰 벽).
- 결과에 축별 `available_mm`, `required_mm`, `slack_mm`, `margin_mm`, `source`(scanned/measured), `notes`, 배치 위치(`placement`) 포함.
- 미구현(2차): 문 열림 반경 간섭, 같은 영역 여러 제품의 공간 공유.
