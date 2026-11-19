# plan.md — 빌트인 가전 공간 설계 서비스 구현 계획

> 근거: `기획.md` v3.1 (2026-11-18). 작성: 2026-11-19.
> 진행 방식: **plan → spec → TDD(RED→GREEN→REFACTOR) → review**.
> 이 계획은 "얇은 세로 흐름 먼저"(기획 §10.3) 원칙으로, 방 1개 → 영역 2개 → 제품 몇 종을 끝까지 관통시킨 뒤 넓힌다.

---

## 0. 목표와 완료 기준

| 구분 | 내용 |
|------|------|
| 목표 | 기획 §4 시연 시나리오 1~10단계가 팀 PC 한 대에서 한 흐름으로 동작 |
| 완료 기준 | ① USDZ 업로드 → `room.json` + `scene.glb` 생성 ② 웹에서 3D·평면도·벽 치수 표시 ③ 실측 보정 ④ 영역 지정 ⑤ 스타일 저장(MCP) ⑥ 영역별 적합 판정·CMF 추천 카드 ⑦ Claude Code·Codex에서 같은 MCP 도구 호출 |
| 범위 밖 | 기획 §5.3 그대로 (자체 iOS 앱, 실제 접수·배정, 결제, 사내 데이터) |
| 금지 | 서버가 팀원 구독 OAuth 토큰으로 LLM을 호출하는 구조 (기획 §7). 카탈로그 값 추정 입력 (기획 §8.4) |

## 1. 아키텍처 결정 (ADR 요약)

| # | 결정 | 이유 | 대안 |
|---|------|------|------|
| ADR-1 | 백엔드는 Python 3.11+ 단일 패키지(`pyproject.toml`), 구성요소는 `services/*` 하위 패키지 | 팀 PC 한 대에서 설치·테스트가 한 번에 끝남 | 서비스별 venv (복잡) |
| ADR-2 | USDZ 파싱은 **usd-core(`pxr`)** 로 Blender 없이 수행 → `room.json` | 변환기를 Blender 없이 TDD 가능, CI·팀원 PC 모두 동일 | Blender USD import 후 bpy로 추출 (느리고 테스트 어려움) |
| ADR-3 | Blender는 **선택 의존**. `blender` 실행 파일이 있으면 bpy 스크립트로 씬·재질·렌더·glb. 없으면 `room.json`에서 순수 Python으로 박스 glb 생성(폴백) | Blender 미설치 PC에서도 웹 3D 뷰어가 동작 | Blender 필수 (환경 리스크) |
| ADR-4 | DB는 SQLite(표준 `sqlite3`) + 파일 저장소 `storage/` | 시연 전용, 설치 0 | Postgres |
| ADR-5 | 판정·점수는 **결정론적 코드**(recommender), LLM은 해석·설명만 | 기획 §6.2 | — |
| ADR-6 | MCP 서버는 공식 Python SDK(FastMCP), **stdio + Streamable HTTP** 동시 지원, HTTP는 Bearer 토큰 검사 | 기획 §6.2 클라이언트 중립 | SSE (구식) |
| ADR-7 | MCP 서버는 api와 **같은 상태 저장소**(SQLite·storage)를 직접 사용하는 서비스 계층(`core`)을 공유 | 채팅 ↔ 웹 상태 동기화 (기획 §6.2) | MCP → api HTTP 호출 (프로세스 2개 필수) |
| ADR-8 | 웹은 빌드 도구 없는 정적 SPA(ES 모듈 + three.js 0.160.0 로컬 포함), api가 서빙 | Node 빌드 의존 제거, 인터넷 없이도 `uvicorn` 하나로 시연 | Vite/React (설정 비용) |
| ADR-9 | 모든 주소·포트·토큰은 `.env` | 기획 §6.3 이식성 | — |

## 2. 작업 단위 (Phase · Task)

각 Task는 **테스트 먼저 → 구현 → 리뷰** 순서. ✅ = 이번 착수에서 완료 목표.

### Phase 0 — 골격 (기획 1주차)
- ✅ T0.1 저장소 골격(§10.2), `pyproject.toml`, `.env.example`
- ✅ T0.2 `CLAUDE.md` / `AGENTS.md`(동일 내용), `.mcp.json`, `.codex/config.toml`
- ✅ T0.3 `docs/specs/` 구성요소별 스펙 (room-json, fit-rules, cmf, mcp-tools, api)
- ✅ T0.4 UGScan 실제 샘플 USDZ → `data/samples/`
  - `ugscan_2026-11-18.usdz` (강의실 약 7×10.9 m). **줄자 실측은 하지 않고 스캔값만 쓴다** (2026-11-19 결정)

### Phase 1 — 변환기 (blender-worker) TDD
- ✅ T1.1 합성 RoomPlan형 USDZ 픽스처 생성기 (`data/samples/synthetic_room.usdz`)
  - Apple RoomPlan 내보내기 관례(`Architecture/Walls/Wall0`, `Doors`, `Windows`, `Object/...`)를 흉내낸 **가정 구조** → 실제 파일과 다른 점은 `docs/specs/usdz-analysis-2026-11-18.md`
- ✅ T1.2 USDZ → `room.json` 변환기: 프림 이름 기반 분류, 월드 변환 bbox → 벽 시작/끝/길이/높이, 개구부의 벽 할당·offset, 오브젝트 bbox
- ✅ T1.3 `room.json` 스키마 검증 (pydantic)
- ✅ T1.4 glb 생성: Blender 있으면 bpy, 없으면 순수 Python 박스 glb
- ✅ T1.5 bpy 스크립트: USDZ import → 재질 적용 → 렌더 PNG → glb export (Blender 설치 PC에서 실행)
- ✅ T1.6 실제 UGScan 샘플로 변환기 보정: `_grp` 컨테이너 처리, 같은 그룹 벽에 문·창 할당, `Section_grp` 제외

### Phase 2 — recommender TDD
- ✅ T2.1 치수 선택: measured 우선, 출처 표시
- ✅ T2.2 가용 폭: 벽 길이 − 개구부 구간 − 오브젝트 점유 구간 → 최대 연속 구간
- ✅ T2.3 가용 깊이: 벽 앞쪽 영역 다각형 깊이 (또는 실측 깊이)
- ✅ T2.4 판정 규칙 §9.1 (margin 스캔 30mm / 실측 5mm, 스캔 기반 적합 → 조건부, null → 판정 불가, 최악값 채택)
- ✅ T2.5 CMF: hex → CIELAB, ΔE2000, 재질 키워드 일치, 상위 3개 + 점수 근거
- ✅ T2.6 영역 추천: 영역 × 카탈로그 → 판정 + CMF 정렬

### Phase 3 — 카탈로그
- ✅ T3.1 `products.json` 스키마 + 검증 (모든 값 출처 URL, 미확인 값 null)
- ✅ T3.2 LGE.COM에서 16종 수집 (`docs/catalog-sources.md` 기록). 남은 것: 식기세척기 설치 공간, 오븐, 거실 제품
- ✅ T3.3 시연·테스트용 `data/catalog/demo_fixture.json` (명시적으로 "가상 데이터" 표기, 시연 화면에 배지)

### Phase 4 — api (FastAPI)
- ✅ T4.1 상담 요청 F1 (목업)
- ✅ T4.2 스캔 업로드 F2 → 프로젝트 생성 → 변환 → 고객 링크
- ✅ T4.3 실측 보정 F3 (원본 scanned 보존)
- ✅ T4.4 영역 CRUD F5
- ✅ T4.5 스타일 저장 F6, 추천 F8·F9, 결과 F10
- ✅ T4.6 웹 정적 서빙, glb·png 파일 서빙

### Phase 5 — mcp-server
- ✅ T5.1 도구: `get_room`, `list_zones`, `set_style`, `search_catalog`, `check_fit`, `recommend`, `apply_material`, `place_product`, `render`
- ✅ T5.2 stdio 실행 + Streamable HTTP 실행 + Bearer 검사
- ✅ T5.3 도구 계약 테스트 (in-memory 클라이언트)
- ⏳ T5.4 Claude Code·Codex 양쪽 수동 검증 (팀 PC)

### Phase 6 — web
- ✅ T6.1 기사 화면: 업로드, 벽 목록, 실측 입력
- ✅ T6.2 고객 화면: 상담 요청, 평면도 영역 지정(사각형/다각형), 3D 뷰어, 추천 카드
- ✅ T6.3 상태 폴링으로 채팅 ↔ 웹 동기화

### Phase 7 — 통합·시연
- ✅ T7.1 E2E 테스트: 업로드 → 실측 → 영역 → 스타일 → 추천
- ⏳ T7.2 Claude 앱 커넥터(공개 HTTPS, Q8 결정 후), 리허설, 백업 영상

## 3. 테스트 전략

| 층 | 대상 | 도구 | 목표 |
|----|------|------|------|
| 단위 | recommender 규칙, CMF, 변환기 기하 | pytest | 판정 분기 100% |
| 계약 | MCP 도구 입출력 스키마 | pytest + MCP in-memory 세션 | 모든 도구 |
| 통합 | api 엔드포인트 | FastAPI TestClient | 시나리오 1~10 |
| 수동 | Claude Code·Codex 실제 호출, Blender 렌더 | 체크리스트 `docs/specs/manual-qa.md` | 시연 전 |

## 4. 리스크 (계획 관점)

| 리스크 | 대응 |
|--------|------|
| 실제 UGScan USDZ 구조가 가정과 다름 | 변환기는 이름 규칙을 설정(`CLASSIFY_RULES`)으로 분리. 실제 샘플 확보 즉시 픽스처 교체 + 테스트 정답 갱신 |
| LGE.COM 설치 치수 누락 | null 유지 → "판정 불가" 표시. 데이터 충분한 제품 위주 |
| Blender 미설치/느림 | 폴백 glb, 사전 렌더 캐시 |
| Codex Streamable HTTP 문제 | Codex는 stdio 기본 |

## 5. 미결 사항 → 구현 영향

- Q7(스캔-실측 차이) → 줄자 실측 없이 진행하므로 RoomPlan 공개 오차 수준을 가정한 기본값을 그대로 쓴다. margin 기본값은 `.env`(`FIT_MARGIN_SCANNED_MM=30`, `FIT_MARGIN_MEASURED_MM=5`)로 조정 가능
- Q8(공개 방식) → 코드 영향 없음. HTTP MCP는 `MCP_HTTP_TOKEN` 필수
- Q9(메인 클라이언트) → 양쪽 설정 파일 모두 제공
