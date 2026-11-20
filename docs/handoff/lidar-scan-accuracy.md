# 인계 메모: 라이다 스캔 오차 줄이기 (2026-11-20)

브랜치 `claude/project-thread-1hhmqu`, PR #16. 조사 내용과 수치 근거는 `docs/research/lidar-error-correction.md`.

## 끝난 것
- **조사**: 아이폰 라이다·RoomPlan 오차(작은 방 1~3 cm, 길이의 약 1~1.5%), 스캔 방법, 스캔 뒤 보정법, 원본 깊이 보정법 (출처 36개).
- **판정 반영** (`recommender/fit.py`, `pose.py`, 규칙 `docs/specs/fit-rules.md`)
  - 스캔 마진 = max(30 mm, 2σ(길이)), σ = √(10² + (1%·L)²). `.env`의 `FIT_SCAN_SIGMA_ABS_MM`, `FIT_SCAN_SIGMA_REL`.
  - 스캔 오차 안의 자리는 조건부 + `needs_measure` (화면 "확인 필요").
  - 넣을 자리 잰 값(선택): `PUT /api/projects/{pid}/placements/{plid}/measured`, `placement.measured_mm`.
- **웹**: 선택 패널의 접힌 "이 자리 줄자로 재 보기", "확인 필요" 표시, 첫 화면·기사 화면 스캔 안내. 서비스 워커 v19.
- **시험 구현 (앱에 연결 안 함)**
  - `worker/rawdepth.py`: Stray Scanner 폴더 읽기 → 신뢰도 2 점 융합 → RANSAC 평면 → UGScan 벽과 좌표 맞춤 → 마주 보는 벽 사이 거리 보정 (`refine_room`).
  - `worker/rawdepth_synth.py`: 합성 주방 캡처 (테스트·실험용).
  - `recommender/scan_correction.py`: 직각 맞추기, 잰 길이로 배율.
- 테스트 412개 통과 (`uv run pytest`). 실험: `uv run python docs/research/rawdepth_experiment.py`, `scan_correction_experiment.py`.

## 남은 것
1. **실제 Stray Scanner 캡처로 검증** (캡처는 나중에 받기로 함)
   - `load_stray(path)`로 읽고 점이 방 모양으로 모이는지 확인. 흩어지면 `camera="arkit"`로 바꿔 본다 (위치값의 카메라 축 규칙이 문서에 없다).
   - `odometry.csv`의 fx·cx가 1920 폭 기준인지 확인 (`rgb_width`).
   - 같은 방의 UGScan USDZ와 함께 `refine_room` 실행. 레이저 거리계 값이 한두 개 있으면 전후 오차 비교.
2. **Prompt Depth Anything 연결**
   - 모델 `depth-anything/prompt-depth-anything-vits-hf` (Apache-2.0, transformers). 클라우드 작업 환경은 Hugging Face가 막혀 있어 팀 PC(C:\lg-ax-builtin)에서 받는다.
   - `rgb.mp4` 프레임 + 깊이 PNG를 넣어 보정 깊이를 받고 `Frame.depth_m`에 넣는다. 해상도가 바뀌면 `Frame.K`도 같은 비율로 바꾼다. 신뢰도 맵은 최근접으로 키운다.
   - 켜고 끈 차이를 실제 캡처로 잰다. 무거운 의존성(torch)은 선택 설치(extra)로 둔다.
3. **앱 연결**: "정밀 스캔 올리기(선택)" 업로드 → `refine_room` 결과로 벽 치수 보정 → 보정된 벽은 좁은 마진. 스캔 원본값(`scanned`)은 덮어쓰지 않고 별도 필드로. 규칙 문서와 테스트 먼저.

## 알아 둘 것
- 합성 실험에서 남는 오차는 거의 위치 밀림(드리프트)이다. 프레임마다 1 mm 밀리면 3 mm, 3 mm 밀리면 10 mm. 캡처는 주방만 30초 안쪽으로.
- 깊이 노이즈가 거리의 2%면 RANSAC 임계값(`thr_m` 3 cm)이 좁아서 결과가 나빠진다. 실제 노이즈를 보고 조정.
- `refine_room`은 4면 이상 안 맞으면 아무것도 고치지 않는다 (다른 방 캡처 방지). 기둥으로 꺾인 방은 아직 시험하지 않았다.
- 문 폭·싱크대 깊이 같은 표준값은 1차 출처로 확인 못 해서 기준으로 쓰지 않는다.
- 방향: 사용자가 줄자로 재는 번거로움을 줄이는 쪽이 우선. 실측 입력은 선택으로만 둔다.
