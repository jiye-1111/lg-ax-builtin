# 인계 메모: 빌트인/일반 필터, 단계별 옵션 필터, 사진 렌더 (2026-11-20)

브랜치: `claude/project-thread-99vfxq` (jiye-1111/lg-ax-builtin). main에 합쳐지면 `scripts/sync-team.sh`로 팀 저장소 jiye 브랜치에 반영.

## 실행
```bash
uv sync --extra dev
uv run pytest -q                 # 전체
API_PORT=8011 uv run lgb-api     # http://127.0.0.1:8011  (스캔 올리기: data/samples/*.usdz)
```

## 끝난 것
- LGE.COM 생활가전 1,150종 카탈로그·도면·3D 모델 (267개 모델로 묶임).
- 설치 방식에 따른 판정 (`recommender/fit.py`, `pose.py`, 규칙 `docs/specs/fit-rules.md`)
  - 빌트인·빌트인 핏(Fit & Max): 장 안에 들어가는지.
  - 일반: 놓을 자리 + 앞쪽 문 열림 공간. `door_swing_mm`이 없고 문 있는 종류면 `FIT_FRONT_DEFAULT_MM`(600)을 가정하고 조건부.
- 카탈로그에 `options`(종류·도어 수·용량·화면 크기 등)와 `door_swing_mm`(183종) 추가. 출처 `docs/catalog-sources.md` 맨 아래.
  다시 만들 때: `python3 tools/catalog/add_options.py . tools/catalog/lgecom_options.json` (lgecom_options.json은 LGE.COM 스펙 표에서 뽑은 원본 값).
- 웹 제품 서랍 (`apps/web/js/remodel.js`, `js/options.js`, 설명 `docs/specs/web.md`)
  - "이 공간을 어떤 용도로 쓰실 건가요?" → 용도에 맞는 가전 종류 칩.
  - 단계별 옵션 필터: 설치 방식(빌트인/일반) → 종류 → 도어 수 → 용량 → 화면 크기 → 문 여는 방향 → 도어 재질 → 색상. LGE.COM·삼성닷컴 필터 순서를 참고.
  - 상세 창: "놓는 곳" 줄을 빼고 옵션 줄을 넣음. "빌트인 느낌" → "빌트인 핏 (Fit & Max)".
- 판매 상태(`sale_status`)를 넣고 지금 파는 제품(판매중·일시품절 830종)만 목록·추천에 나옴. 42종은 값을 못 읽어 null이라 목록에서 빠져 있음 (다시 확인 필요).
- 3D 모델 12건(로봇청소기 재질·치수, 미니 냉장고 손잡이) 고침.
- 서비스 워커 v20.

## 남은 것
1. 제품 사진 1,150장은 모두 렌더했다. 모델을 바꾸면 그 사진을 지우고 `BPY=<bpy 깔린 파이썬> tools/catalog/thumbs_rest.sh`로 다시 만든다.
2. 옵션 필터 다듬기
   - TV 화면 크기를 cm 대신 인치(형)로도 보여 주기 (LGE.COM 스펙 표에는 cm만 있음. 모델명 앞 숫자가 인치).
   - 에어컨은 평형(냉방 면적) 축이 아직 없음. LGE.COM 스펙 표에서 '냉방면적' 값을 다시 뽑아 `options`에 넣기.
   - 추천 탭(영역 추천)에도 같은 용도 질문 흐름 연결.
3. 일반 냉장고의 문 열림 깊이는 LGE.COM 스펙 표에 없어 기본값 600을 가정한다. 설치가이드에서 값을 찾으면 `door_swing_mm`에 넣기.
4. PR 열고 main에 합치기 → 사이트(housetwin.pages.dev) 자동 배포 → 팀 저장소 동기화.
