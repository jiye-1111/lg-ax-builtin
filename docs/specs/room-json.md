# room.json 스펙 (기획 §8.2)

- 단위 **m**. 평면 좌표 `(x, y)` = USD 3D `(x, z)` (Y-up). 바닥 높이 = 0 (변환기가 가장 낮은 벽 하단으로 정규화).
- 모델 정의: `services/core/core/models.py` (`Room`, `Wall`, `Opening`, `RoomObject`). 정의에 없는 필드는 거부(`extra=forbid`).

| 필드 | 설명 |
|------|------|
| `walls[].start/end` | 벽 두께 중심선의 양 끝 |
| `walls[].scanned` | 스캔값 `length_m`, `height_m`. **절대 덮어쓰지 않는다** |
| `walls[].measured` | 기사 실측 `length_m`, `height_m`, `depth_m`(확장), `by`, `at`. null 항목은 스캔값 사용 |
| `walls[].thickness_m` | 스캔 두께 (확장) |
| `openings[]` | `type` door/window/opening, `wall_id`(가장 가까운 벽), `offset_m`(벽 start → 개구부 시작), `width_m`, `height_m`, `sill_m`(확장: 바닥→하단) |
| `objects[]` | RoomPlan 분류명을 snake_case로(`storage`, `refrigerator`, `washer_dryer` ...), `bbox_m` w(주축)·h·d, `position` (x, 높이 중심, z), `yaw_rad`(확장) |

## 확장 필드 이유
- `measured.depth_m`: 깊이는 벽 앞 공간이라 스캔 기하로만 나오고, 실측 깊이가 없으면 "적합"을 낼 수 없다 (fit-rules.md).
- `sill_m`: 높은 창문 아래 식기세척기처럼 창이 간섭하지 않는 경우 판정.
- `yaw_rad`: 회전된 가구의 벽 점유 구간 계산.
