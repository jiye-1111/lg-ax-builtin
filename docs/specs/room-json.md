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

## 문·창 자리 바로잡기

스캔(`converter.py`)과 도면(`plan_room.py`) 모두 room.json을 만들 때 `worker/tidy.py`의 `tidy_openings`를 거친다. 예전에 만든 집은 불러올 때 한 번 고쳐서 다시 써 둔다.

- 다른 벽이 와 닿거나 가로지르는 자리에는 문·창을 두지 않는다. 걸치면 같은 벽에서 가까운 빈자리로 옮긴다 (0.6 m까지).
- 한 벽에서 문·창끼리 겹치지 않는다 (틈 0.05 m). 같은 종류가 절반 넘게 겹치면 두 번 읽은 것으로 보고 하나만 남긴다.
- 모서리에서 두 벽의 문이 모서리를 같이 쓰지 않는다.
- 옮길 자리가 없는 문은 뺀다. 창은 빼지 않고 그대로 둔다.
- 넓은 문부터 자리를 잡고, 창은 문 다음에 본다.

