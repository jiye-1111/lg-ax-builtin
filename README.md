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
1. `http://localhost:8000` → USDZ 파일을 올리거나 **샘플 집으로 체험하기**
2. 왼쪽에서 LG 제품을 고르고 평면을 눌러 놓기 → 들어가는지 바로 판정 (끌어서 옮기기, R 키로 돌리기)
3. 위쪽 **살아 보기**에서 채광·와이파이·동선 확인, 오른쪽 **마감재**에서 벽·바닥 색 바꾸기
4. 도면이나 줄자로 잰 값이 있으면 오른쪽 **도면·실측** 탭에 넣기 (선택)
5. Claude Code 또는 Codex를 이 폴더에서 열면 MCP 서버 `lg-builtin`이 자동 등록됩니다 (`.mcp.json`, `.codex/config.toml`).
   예: "주방을 화이트 우드 톤 미니멀로 꾸며 주고, 들어가는 냉장고 추천해 줘" → 웹 화면이 2초 안에 갱신

### 앱처럼 설치하기
- PC 크롬·엣지: 상단 **앱 설치** 버튼(또는 주소창 오른쪽 설치 아이콘).
- 휴대폰: PC와 같은 와이파이에서 `http://<PC IP>:8000`을 열고, 아이폰은 Safari **공유 → 홈 화면에 추가**, 안드로이드는 크롬 메뉴 **홈 화면에 추가**.
  `.env`의 `API_HOST`를 `0.0.0.0`으로 바꿔야 휴대폰에서 열립니다. 오프라인 캐시는 `localhost`나 HTTPS에서만 켜집니다.

Blender가 설치돼 있으면 `.env`의 `BLENDER_BIN`을 지정하세요. 없으면 치수 박스 3D·미리보기 렌더로 동작합니다.

## 주의
- `data/catalog/demo_fixture.json`은 **가상 데이터**입니다(웹에 "가상" 배지). 실제 값은 LGE.COM에서 `products.json`으로 수집합니다.
- `data/samples/synthetic_room.usdz`는 RoomPlan 구조를 가정한 합성 파일입니다. 실제 UGScan 샘플은 `data/samples/ugscan_2026-11-18.usdz`(강의실 한 칸)이고, 첫 화면 샘플 체험이 이 파일을 씁니다.
