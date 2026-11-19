# MCP 도구 스펙

코드: `services/mcp-server/mcp_server/server.py` (MCP Python SDK 2.x `MCPServer`)

## 전송·인증
| 방식 | 실행 | 용도 |
|------|------|------|
| stdio | `uv run python -m mcp_server` | Claude Code(`.mcp.json`), Codex(`.codex/config.toml`) 기본 |
| Streamable HTTP | `uv run python -m mcp_server --http` → `http://127.0.0.1:8765/mcp` | Claude 앱 커스텀 커넥터(공개 HTTPS 필요), Codex URL |

- HTTP는 `Authorization: Bearer $MCP_HTTP_TOKEN` 필수(16자 이상, 없으면 서버가 시작 거부). 상수 시간 비교.
- DNS 리바인딩 보호: 허용 호스트 = localhost + `MCP_ALLOWED_HOSTS`.
- Claude 앱: 커넥터 "요청 헤더"에 `Authorization: Bearer ...`. Codex: `bearer_token_env_var = "MCP_HTTP_TOKEN"`.

## 도구 (project_id 생략 시 `MCP_DEFAULT_PROJECT` 또는 최근 프로젝트)
| 도구 | 입력 | 출력 |
|------|------|------|
| `list_projects` | — | 프로젝트 목록 |
| `get_room` | project_id? | 벽(스캔·실측), 개구부, 가구, customer_url |
| `list_zones` | project_id? | 영역 목록 |
| `create_zone` | purpose, polygon_m, name? | 영역 |
| `set_style` | palette[#hex], materials[], prompt?, zone_id? | 저장된 스타일 |
| `search_catalog` | category?, zone?, query? | 제품 |
| `check_fit` | zone_id, sku | 축별 판정 |
| `recommend` | zone_id, category? | 판정 + CMF 상위 3 + reasons |
| `apply_material` | target(wall/floor/door/window/object), hex_color, finish?, wall_id? | 씬 상태 |
| `place_product` | zone_id, sku, color? | 배치 + 판정 |
| `remove_product` | zone_id, sku | 배치 목록 |
| `render` | project_id? | 텍스트 + PNG 이미지 |

- 서버 `instructions`에 규칙: 판정·점수 재계산 금지, 없는 제품·치수 금지, 스캔 기반은 '후보', 가상 데이터 고지.
- 임의 코드 실행 도구 없음 (기획 §6.2).
- 완료 기준: 같은 프롬프트로 Claude Code·Codex 양쪽 호출 성공 (manual-qa.md).

## 자유 배치 도구 (2026-11-19)
| 도구 | 입력 | 하는 일 |
|---|---|---|
| `place_at` | `sku`, `center_xz` [x, z], `yaw_rad`, `snap`, `color?` | 지정한 자리·방향에 놓고 판정·이유 반환 |
| `move_product` | `placement_id`, `center_xz?`, `yaw_rad?`, `snap`, `color?` | 옮기기·돌리기·색 바꾸기 후 다시 판정 |
| `list_placements` | - | 놓인 제품 목록 |
| `hide_object` | `object_id`, `hidden` | 기존 가구 치우기/되돌리기 |
