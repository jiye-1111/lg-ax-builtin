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
| POST | `/api/projects/{pid}/style/ai` | 말로 꾸미기 `{prompt, zone_id?, apply_finishes?}` → 스타일 저장 + 벽지·바닥재 추천·적용 (`finishes.md`). 제품 조건을 말하면 `products`에 맞는 제품도 (아래 "대화로 제품 찾기") |
| GET | `/api/finishes` | 2026 트렌드 실제 벽지·바닥재 목록 |
| POST | `/api/projects/{pid}/finishes` | 벽지·바닥재 적용 `{finish_id, tone?}` |
| POST | `/api/projects/{pid}/materials` | 재질 F7 `{target, hex_color, finish?, wall_id?}` |
| POST/DELETE | `/api/projects/{pid}/placements` | 배치 미리보기 `{zone_id, sku, color?}` |
| POST | `/api/projects/{pid}/render` | 렌더 PNG |
| GET | `/api/projects/{pid}/zones/{zid}/recommendations` | 추천 F8·F9 |
| GET | `/api/projects/{pid}/results` | 결과 화면 F10 일괄 |
| GET | `/api/projects/{pid}/files/{scene.glb|render.png|room.json}` | 산출물 |
| GET | `/api/catalog?category=&zone=&q=` | 카탈로그 |
| GET | `/api/catalog/families` | 같은 모델의 색만 다른 제품을 묶은 목록. 색마다 `price_krw`(LGE.COM 판매가, 모르면 null) |
| GET | `/api/catalog/find` | 조건으로 제품 찾기 (아래) |
| GET | `/api/projects/{pid}/find?zone_id=` | 같은 찾기를 우리 집 기준으로 (아래) |

- 상태는 `core.service.Service`가 SQLite(`storage/app.sqlite3`)와 `storage/projects/<pid>/`에 저장.
- 고객 링크 `/#/c/<pid>?t=<token>` (시연용, 실제 인증 아님).

## 조건으로 제품 찾기
추천 카드와 상세 필터(용량·색상·가격대)용. 판정·순서·이유 문장은 서버가 계산한다 (규칙: `fit-rules.md` "조건으로 찾기").

`GET /api/catalog/find` · `GET /api/projects/{pid}/find` 쿼리 (모두 선택)

| 이름 | 값 |
|---|---|
| `category` | refrigerator, kimchi_refrigerator … |
| `use` | 공간 용도 kitchen, living … |
| `install` | `built_in`(빌트인 핏 포함) \| `freestanding` |
| `capacity_min`, `capacity_max` | 용량 L |
| `color` | 화이트 \| 베이지 \| 실버·그레이 \| 블랙 \| 그린 \| 기타 |
| `price_min`, `price_max` | 원 |
| `space_w`, `space_h`, `space_d` | 설치 공간 mm. 넣은 축만 본다 |
| `fits_only` | true면 안 들어가는 제품을 뺀다 |
| `sort` | `recommended`(기본) \| `size` \| `price` |
| `limit` | 1~500 |
| `zone_id` | 프로젝트용만. 안 주면 제품 용도에 맞는 영역을 고른다 |

- 프로젝트용은 공간 치수를 안 넣으면 그려 둔 영역에 들어가는지로 판정한다(`fit.source: "zone"`). 치수를 넣으면 그 값이 먼저다(`"typed"`). 영역도 치수도 없으면 `fit: null`.
- 응답
```json
{"items": [{"product": {…카탈로그 제품…}, "family_id": "G646GBB031", "family_name": "…", "variants": 4, "thumb": "img/products/G646GBB031.webp",
            "color_group": "베이지", "reasons": ["폭 950 mm 공간에 들어가요 (여유 28 mm)", "용량 650 L"],
            "fit": {"verdict": "fit", "label": "적합", "source": "typed", "dims": {"width": {"available_mm": 950, "required_mm": 922, "slack_mm": 28, …}}, "notes": []}}],
 "total": 31,
 "facets": {"capacity": [{"label": "400L 이하", "max": 400, "count": 12}, {"label": "400~600L", "min": 400, "max": 600, "count": 20}, {"label": "600L 이상", "min": 600, "count": 85}],
            "color": [{"label": "화이트", "count": 30}, …],
            "price": {"min": 250000, "max": 10500000, "known": 117, "buckets": [{"label": "100만 원 이하", "max": 1000000, "count": 20}, …]}},
 "zone_id": null, "margins_mm": {"scanned": 30, "measured": 5}}
```
- 같은 모델의 색만 다른 제품은 가장 앞선 것 하나만 나온다(`variants` = 그 모델의 색 수). `total`은 모델 수.
- `facets`는 종류·용도·설치 방식까지만 반영하고 고른 용량·색상·가격은 반영하지 않는다(다른 값을 고를 수 있게). `facets.price`가 null이면 가격대 필터를 숨긴다.
- 예: 추천 카드 3개 `…/find?category=refrigerator&limit=3`, 600L 이상 베이지 300만 원 이하에 폭 950 `…/find?category=refrigerator&capacity_min=600&color=베이지&price_max=3000000&space_w=950`.

## 자유 배치
| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/projects/{pid}/placements` | `{sku, center_xz, yaw_rad, snap, color}` 그 자리에 놓기. `zone_id`만 주면 예전처럼 영역 자동 배치 |
| POST | `/api/projects/{pid}/pose-check` | 저장 없이 판정만 (`placement_id`를 주면 그 배치는 장애물에서 뺌) |
| PATCH | `/api/projects/{pid}/placements/{plid}` | 옮기기·돌리기·색 |
| DELETE | `/api/projects/{pid}/placements/{plid}` | 빼기 |
| PUT | `/api/projects/{pid}/objects/{oid}/hidden` | `{hidden}` 기존 가구 치우기 |
| GET | `/api/samples/{name}` | 샘플 스캔 (`apt_living_kitchen.usdz`, `studio_living.usdz`, `synthetic_room.usdz`, `ugscan_2026-11-18.usdz`) |
| PUT | `/api/projects/{pid}/openings/{oid}/hidden` | 스캔한 창문 없애기·되돌리기 (`{hidden}`). 문은 안 된다 |

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

## 대화로 제품 찾기
말로 꾸미기(`POST /api/projects/{pid}/style/ai`)에 제품 조건을 적으면 같은 응답의 `products`에 맞는 제품이 온다. 따로 부르는 추천 API는 없다.

예: "600L 이상 베이지 냉장고, 폭 950 안에 들어가는 걸로, 300만 원 이하"

- AI(또는 키가 없을 때 규칙)는 말을 조건으로 옮기기만 한다 (`core/ai_products.py`). 읽는 조건: 종류, 빌트인/일반형, 용량(L), 색 묶음, 가격(원), 놓을 자리 폭·높이·깊이(mm), 정렬.
- 고르고 줄 세우는 건 "조건으로 제품 찾기"와 같은 코드다 (`Service.find`). 놓을 자리 치수를 말했으면 거기 들어가는 것만, 말하지 않았으면 그려 둔 영역 기준으로 판정한다.
- 제품만 물었으면 벽지·바닥재와 저장된 스타일은 그대로 두고 `applied = {}`, `finishes = {wall: [], floor: []}`, `summary = products.message`.
- 분위기와 제품을 같이 말하면 둘 다 한다. 분위기만 말하면 `products = null`.

```
products: {
  engine,            // claude | openai | rules
  conditions,        // 말에서 읽은 조건만. 예: {category, capacity_min, color, space_w, price_max}
  sort,              // recommended | size | price
  items,             // 최대 5개. /find의 items와 같은 모양 (product, fit, reasons, color_group, family_id, thumb …)
  total,             // 조건에 맞는 전체 수 (같은 모델의 색은 하나로)
  zone_id,
  message            // 대화창에 그대로 보여 줄 한 줄. 코드가 만든다
}
```

규칙으로 읽을 때: "600L 이상/이하", "800L"(그쯤, ±10%), "300만 원 이하", "150만 원 넘는", "200만원대"(200~300만), 금액만 말하면 상한, "폭 950"·"가로 95cm"·"60cm 폭"·"높이 1.8m"(단위가 없으면 크기로 짐작).
