# lg-ax-builtin

LiDAR 스캔 기반 LG 빌트인 가전 공간 설계 서비스 — LG전자 AX School 3차 프로젝트 **시연용 프로토타입**.

기사가 UGScan(RoomPlan)으로 스캔한 USDZ → `room.json`·3D → 고객이 영역 지정 → 규칙 기반 설치 적합 판정 + CMF 추천.
Claude(Code·앱)와 Codex에서 같은 MCP 서버로 대화하며 디자인합니다.

- 기획: [기획.md](기획.md) · 구현 계획: [plan.md](plan.md) · 스펙: [docs/specs](docs/specs/README.md) · 규칙: [CLAUDE.md](CLAUDE.md)

## 빠른 시작 (Windows / macOS 공통)
```bash
# 1) uv 설치: https://docs.astral.sh/uv/  (Python 3.11+ 자동 준비)
uv sync --extra dev
cp .env.example .env          # Windows PowerShell: copy .env.example .env
uv run pytest                 # 테스트
uv run lgb-api                # http://localhost:8000
```
1. `http://localhost:8000/#/t` → **합성 샘플로 등록** (실제 UGScan 파일은 끌어다 놓기)
2. 벽 표에 실측값 입력 → **고객 화면 열기**
3. 평면도에서 드래그로 주방·거실 영역 지정
4. Claude Code 또는 Codex를 이 폴더에서 열면 MCP 서버 `lg-builtin`이 자동 등록됩니다 (`.mcp.json`, `.codex/config.toml`).
   예: "주방을 화이트 우드 톤 미니멀로 꾸며 주고, 들어가는 냉장고 추천해 줘" → 웹 화면이 2초 안에 갱신

Blender가 설치돼 있으면 `.env`의 `BLENDER_BIN`을 지정하세요. 없으면 치수 박스 3D·미리보기 렌더로 동작합니다.

## 주의
- `data/catalog/demo_fixture.json`은 **가상 데이터**입니다(웹에 "가상" 배지). 실제 값은 LGE.COM에서 `products.json`으로 수집합니다.
- `data/samples/synthetic_room.usdz`는 RoomPlan 구조를 **가정**한 합성 파일입니다. 실제 UGScan 샘플로 검증이 필요합니다.
