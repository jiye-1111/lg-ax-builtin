# 인계 메모: 와이파이 공유기 3D · 동선 걷는 사람 3D (2026-11-20)

브랜치: `claude/project-thread-agmmrq` (main 최신을 합쳐 둠)

## 끝난 것
- 공유기 모델 `apps/web/models/devices/router.glb` (`build_router.py`, TP-Link Archer AX55 공개 치수 261.1×134.5×41 mm)
- 사람 모델 `apps/web/models/people/walker.glb` (`build_person.py`, MakeHuman CC0 몸, 170 cm, walk·idle 동작)
- 3D에서 공유기 눌러 집기 → 옮기기·R 돌리기 → 내려놓으면 저장하고 와이파이 다시 계산 (`viewer.js` setRouter, `remodel.js` savePose)
- 공유기 방향 `yaw_rad` 저장 (`core/service.py` set_router, `api/main.py` RouterIn). 자리만 옮기면 방향 유지
- 동선: 사람이 현관에서 제품 앞까지 1.3 m/s로 걷기 (`js/walker.js` 계산, `viewer.js` setWalkers)
- 와이파이·동선 화면의 그림 문자 표시 제거 (평면도 공유기는 실제 크기 기호, 현관·싱크는 글자 표시)
- 출처 `docs/model-sources.md`, MakeHuman 받기 `scripts/fetch_makehuman.sh`
- 검증: `uv run pytest` 386 통과, `node tests/e2e/sim_3d.js` 11/11 통과, 화면 `docs/verification/`

## 남은 것 (하면 좋은 것)
- 사람 모델 다듬기: 셔츠 목선이 살짝 들쭉날쭉, 얼굴에 질감(눈썹·입술 색)이 없음, 걷기는 직접 만든 키프레임이라 모션 캡처만큼 자연스럽지는 않음
- 공유기를 가구 위(선반·책상 높이)에 올려놓기는 아직 없음. 지금은 바닥에 놓임
- `tests/e2e/demo_flow.js`는 화면 단순화 이후 벽지 견본 단계(174행)에서 멈춤. 이번 변경과 무관, 따로 손봐야 함
- MCP 도구 `set_router`는 방향 인자를 받지 않음 (필요하면 추가)

## 다시 만들기
`docs/model-sources.md` 맨 아래 명령 참고 (pip `bpy` 환경: `python3.13 -m venv`, `pip install bpy numpy`).
