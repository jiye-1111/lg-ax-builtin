# CLAUDE.md — 프로젝트 규칙 (AGENTS.md와 같은 내용 유지)

LiDAR 스캔 기반 LG 빌트인 가전 공간 설계 서비스. **시연 전용 프로토타입**, 팀 PC에서 전부 로컬 실행.
기획: `기획.md` · 구현 계획: `plan.md` · 구성요소 스펙: `docs/specs/`

## 실행 명령
```bash
uv sync --extra dev                       # 설치 (Python 3.11+)
uv run pytest                             # 전체 테스트
uv run lgb-api                            # 웹 + API  → http://localhost:8000
uv run python -m mcp_server               # MCP stdio (Claude Code·Codex가 자동 실행)
uv run python -m mcp_server --http        # MCP Streamable HTTP → http://127.0.0.1:8765/mcp (MCP_HTTP_TOKEN 필요)
uv run python -m worker.converter X.usdz  # USDZ → room.json 출력
```

## 구조
- `services/core` 모델(`models.py`)·저장소(SQLite)·서비스 계층. **api와 mcp-server는 반드시 `core.service.Service`를 통해서만 상태를 바꾼다** (채팅 ↔ 웹 동기화).
- `services/recommender` 적합 판정(`fit.py`)·CMF(`cmf.py`). 순수 Python, 테스트 우선.
- `services/blender-worker` USDZ→room.json(`converter.py`, usd-core), glb(`glb.py`), 미리보기 렌더(`plan_render.py`), Blender 스크립트(`bpy_scripts/`).
- `services/api` FastAPI + 웹 정적 서빙. `services/mcp-server` MCP 도구.
- `apps/web` 빌드 없는 정적 SPA (three.js 0.160.0을 apps/web/vendor에 포함, 오프라인 시연 가능).

## 코딩 규칙
- 변환기·recommender 변경은 **테스트 먼저**(RED → GREEN → REFACTOR). 판정 규칙은 `docs/specs/fit-rules.md`와 일치해야 한다.
- 판정·점수는 코드가 계산한다. LLM 프롬프트나 도구 설명에 계산을 맡기지 않는다.
- room.json 단위 m, 카탈로그 단위 mm. 평면 좌표 (x, y) = 3D (x, z), Y-up.
- 모든 주소·포트·토큰은 `.env` (`.env.example` 참고). 코드에 하드코딩 금지.
- MCP 도구는 표준 MCP만, 입력은 엄격한 스키마, 설명은 짧고 모델 중립. 새 도구는 Claude Code와 Codex **둘 다**에서 호출해 본 뒤 완료.

## 금지 사항
- 카탈로그(`data/catalog/products.json`)에 LGE.COM에서 확인하지 않은 값을 넣지 않는다. 모르면 `null`. 모든 항목에 `source_url`, `source_checked_at`. 출처는 `docs/catalog-sources.md`에 기록.
- `demo_fixture.json`은 가상 데이터다. 발표 화면에서 실제 제품처럼 보이게 하지 않는다(웹에 "가상" 배지가 뜬다).
- 서버가 팀원의 Claude/ChatGPT **구독 로그인(OAuth 토큰)으로 LLM을 호출하는 코드**를 만들지 않는다 (기획 §7).
- 시연 경로에 임의 Python/Blender 코드 실행 도구를 넣지 않는다.
- 공개 주소로 MCP를 열 때 `MCP_HTTP_TOKEN` 없이 열지 않는다 (서버가 시작을 거부함).
