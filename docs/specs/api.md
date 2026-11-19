# REST API 스펙

코드: `services/api/api/main.py` · 오류: 404 없음 / 422 입력 오류 (`{"detail": "..."}`)

| 메서드 | 경로 | 기능 (기획 F#) |
|--------|------|------|
| GET | `/api/health` | Blender 경로, 카탈로그 수(가상 데이터 수) |
| POST | `/api/requests` | 상담 요청 F1 (목업) `{name, contact, address, preferred_at}` |
| GET | `/api/requests` | 요청 목록 |
| POST | `/api/projects` | 스캔 업로드 F2·F4 (multipart `file`, `request_id?`, `scanned_by=technician|customer`) → 프로젝트 + `customer_url` |
| GET | `/api/projects`, `/api/projects/{pid}` | 프로젝트 |
| GET | `/api/projects/{pid}/version` | 상태 버전 (웹 폴링, 채팅 동기화) |
| GET | `/api/projects/{pid}/room` | room.json |
| PUT/DELETE | `/api/projects/{pid}/walls/{wid}/measured` | 실측 보정 F3 `{length_m?, height_m?, depth_m?}` — scanned 보존 |
| GET/POST | `/api/projects/{pid}/zones` | 영역 F5 `{purpose, polygon_m, wall_ids?, name?}` |
| PATCH/DELETE | `/api/projects/{pid}/zones/{zid}` | 영역 수정·삭제 |
| PUT | `/api/projects/{pid}/style` | 스타일 F6 `{prompt?, palette?, materials?, zone_id?}` |
| POST | `/api/projects/{pid}/materials` | 재질 F7 `{target, hex_color, finish?, wall_id?}` |
| POST/DELETE | `/api/projects/{pid}/placements` | 배치 미리보기 `{zone_id, sku, color?}` |
| POST | `/api/projects/{pid}/render` | 렌더 PNG |
| GET | `/api/projects/{pid}/zones/{zid}/recommendations` | 추천 F8·F9 |
| GET | `/api/projects/{pid}/results` | 결과 화면 F10 일괄 |
| GET | `/api/projects/{pid}/files/{scene.glb|render.png|room.json}` | 산출물 |
| GET | `/api/catalog?category=&zone=&q=` | 카탈로그 |

- 상태는 `core.service.Service`가 SQLite(`storage/app.sqlite3`)와 `storage/projects/<pid>/`에 저장.
- 고객 링크 `/#/c/<pid>?t=<token>` (시연용, 실제 인증 아님).

## 도면 (선택)
| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/projects/{pid}/floorplan` | multipart `file` (PNG·JPG·WEBP·PDF). 참고 자료로만 보관, 판정에는 쓰지 않음 → 201 프로젝트 |
| DELETE | `/api/projects/{pid}/floorplan` | 도면 삭제 |
| GET | `/api/projects/{pid}/files/floorplan` | 도면 파일 |

실측 `PUT /api/projects/{pid}/walls/{wid}/measured`의 `by`는 `technician` 또는 `customer`. 고객도 직접 넣을 수 있다.
