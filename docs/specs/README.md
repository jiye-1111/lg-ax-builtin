# 구성요소 스펙 (docs/specs)

| 파일 | 대상 | 테스트 |
|------|------|--------|
| [room-json.md](room-json.md) | 내부 표준 방 데이터 `room.json` | `tests/unit/test_converter.py` |
| [usdz-converter.md](usdz-converter.md) | USDZ → room.json 변환기, USDZ 구조 분석 절차 | `tests/unit/test_converter.py` |
| [sim.md](sim.md) | 채광·와이파이·동선 근사 모델 | `tests/unit/test_solar.py` 외 |
| [usdz-analysis-2026-11-18.md](usdz-analysis-2026-11-18.md) | 실제 UGScan 내보내기 구조 분석 (첫 샘플) | `tests/unit/test_converter_real.py` |
| [fit-rules.md](fit-rules.md) | 빌트인 적합 판정 규칙 | `tests/unit/test_fit.py` |
| [builtin-kitchen.md](builtin-kitchen.md) | 빌트인 주방: 가전 맞춤장·주방 모듈·마감·문 열림 근사 | `tests/unit/test_cabinet*.py`, `tests/integration/test_cabinet_api.py`, `tests/web/cabinet.test.mjs` |
| [cmf.md](cmf.md) | 색상·재질 매칭 | `tests/unit/test_cmf.py` |
| [finishes.md](finishes.md) | 벽지·바닥재, 말로 꾸미기(AI 추천) | `tests/unit/test_finishes.py`, `tests/unit/test_ai_style.py`, `tests/integration/test_finish_api.py` |
| [catalog.md](catalog.md) | 제품 카탈로그 스키마·수집 규칙 | `core.models.Product` 검증 |
| [api.md](api.md) | REST API | `tests/integration/test_api_flow.py` |
| [mcp-tools.md](mcp-tools.md) | MCP 도구·전송·인증 | `tests/integration/test_mcp_*.py` |
| [web.md](web.md) | 기사·고객 웹 화면 | 수동 (manual-qa.md) |
| [scene.md](scene.md) | 3D 씬·Blender 워커 | `tests/unit/test_glb.py` + 수동 |
| [manual-qa.md](manual-qa.md) | 시연 전 수동 점검표 | — |
