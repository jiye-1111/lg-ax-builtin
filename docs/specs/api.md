# REST API 스펙

코드: `services/api/api/main.py` · 오류: 404 없음 / 422 입력 오류 (`{"detail": "..."}`)

| 메서드 | 경로 | 기능 (기획 F#) |
|--------|------|------|
| GET | `/api/health` | Blender 경로, 카탈로그 수(가상 데이터 수) |
| POST | `/api/requests` | 상담 요청 F1 (목업) `{name, contact, address, preferred_at}` |
| GET | `/api/requests` | 요청 목록 (승인된 기사·관리자만) |
| POST | `/api/auth/signup` | 회원가입 `{email, password, name, role: customer\|technician, phone?, center?, employee_no?}` → `{token, user}` |
| POST | `/api/auth/login` | 로그인 `{email, password}` → `{token, user}` |
| POST | `/api/auth/logout` | 로그아웃 (토큰 폐기) |
| GET | `/api/auth/me` | 내 계정 |
| GET | `/api/me/projects` | 내 집(고객) · 맡은 집(기사) |
| GET·PATCH | `/api/admin/technicians[/{uid}]` | 기사 목록 · 상태 바꾸기 `{status}` (관리자) |
| POST | `/api/projects/{pid}/claim` | 로그인 전에 꾸민 집 가져오기 `{share_token}` |
| GET·POST | `/api/projects/{pid}/saves` | 저장본 목록 · 저장 `{kind: manual\|auto, label?}` |
| POST | `/api/projects/{pid}/saves/{sid}/restore` | 저장본으로 되돌리기 |
| DELETE | `/api/projects/{pid}/saves/{sid}` | 저장본 지우기 |

계정·저장 규칙은 [accounts.md](accounts.md).
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

## 자유 배치
| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/projects/{pid}/placements` | `{sku, center_xz, yaw_rad, snap, color}` 그 자리에 놓기. `zone_id`만 주면 예전처럼 영역 자동 배치 |
| POST | `/api/projects/{pid}/pose-check` | 저장 없이 판정만 (`placement_id`를 주면 그 배치는 장애물에서 뺌) |
| PATCH | `/api/projects/{pid}/placements/{plid}` | 옮기기·돌리기·색 |
| DELETE | `/api/projects/{pid}/placements/{plid}` | 빼기 |
| PUT | `/api/projects/{pid}/objects/{oid}/hidden` | `{hidden}` 기존 가구 치우기 |
| GET | `/api/samples/{name}` | 샘플 스캔 (`synthetic_room.usdz`, `ugscan_2026-11-18.usdz`) |

## 도면 (선택)
| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/projects/{pid}/floorplan` | multipart `file` (PNG·JPG·WEBP·PDF). 참고 자료로만 보관, 판정에는 쓰지 않음 → 201 프로젝트 |
| DELETE | `/api/projects/{pid}/floorplan` | 도면 삭제 |
| GET | `/api/projects/{pid}/files/floorplan` | 도면 파일 |

실측 `PUT /api/projects/{pid}/walls/{wid}/measured`의 `by`는 `technician` 또는 `customer`. 고객도 직접 넣을 수 있다.

## 살아 보기 (참고용 근사, `services/sim`)
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/regions` | 시·도 대표 위도·경도 |
| PUT | `/api/projects/{pid}/site` | `{north_deg, region}` |
| GET | `/api/projects/{pid}/sim/daylight?date=YYYY-MM-DD&time=HH:MM` | 해 위치, 그 시각 볕 드는 사각형, 하루 직사 시간 격자(0.25 m), 제품 자리 값, 가정 |
| PUT | `/api/projects/{pid}/router` | `{center_xz, band: "5" \| "2.4"}` |
| GET | `/api/projects/{pid}/sim/wifi?band=` | 신호 격자(dBm), 비율, 영역별, 가정 |
| GET | `/api/projects/{pid}/sim/wifi/best?band=` | 가장 약한 곳이 제일 센 공유기 자리 |
| PUT/DELETE | `/api/projects/{pid}/marks/{sink\|entrance}` | 싱크·현관 위치 |
| GET | `/api/projects/{pid}/sim/flow` | 현관 → 제품 앞(정면 0.35 m) 경로, 길이, 가장 좁은 폭, 좁은 점, 작업 삼각형 |
