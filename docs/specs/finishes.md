# 마감재(벽지·바닥재)와 말로 꾸미기 스펙

코드: `services/recommender/recommender/finishes.py`, `services/core/core/ai_style.py`, `apps/web/js/finishes.js`
테스트: `tests/unit/test_finishes.py`, `tests/unit/test_ai_style.py`, `tests/integration/test_finish_api.py`
데이터: `data/finishes/finishes.json` (조사: `docs/finish-trends-2026.md`)

## 데이터
항목마다 `id, kind(wall|floor), brand, line, pattern, name, texture(plaster|fabric|stone|wood|paint), keywords, trend, facts, spec, tones[{name,hex}], tone_basis(official|approx), source_url, source_checked_at`.
출처에서 확인하지 않은 값은 넣지 않는다. `spec`은 출처에 있을 때만 (`plank_width_mm`, `tile_mm`).

## 순위 (코드가 계산)
점수 = 0.6 × 색 점수 + 0.4 × 키워드 점수 (CMF와 같은 규칙, `cmf.md`)
- 색 점수 = max(0, 1 − min ΔE00(톤, 팔레트) / 50). 마감재마다 팔레트에 가장 가까운 톤을 고른다.
- 키워드 점수 = 원하는 키워드(재질 + 선호 질감) 중 마감재 키워드·질감에 있는 비율. 한·영 동의어는 `cmf.SYNONYMS`.
- 이유 문장은 쉬운 말로 ("원하는 색과 거의 같아요", "질감·분위기 일치: 회벽·무광"). ΔE 값은 `min_delta_e`로만 준다.

## 말로 꾸미기
1. 고객이 원하는 분위기를 적는다 (최대 500자).
2. Claude(`claude-opus-5-5`, structured output `StyleIntent`)가 팔레트 2~5색, 재질 키워드, 벽·바닥 선호 질감, 짧은 설명으로 **옮기기만** 한다. 점수·제품명은 만들지 않는다.
   - 거절되면 서버 측 fallback(`fallbacks: "default"`)이 다른 모델로 다시 돌린다.
   - `ANTHROPIC_API_KEY` 대신 `OPENAI_API_KEY`만 있으면 OpenAI(`STYLE_AI_OPENAI_MODEL`, 기본 gpt-5-mini) structured output으로 같은 `StyleIntent`를 받는다 (`engine: "openai"`). 둘 다 있으면 `STYLE_AI_PROVIDER`로 고른다.
   - 키가 하나도 없거나 실패하면 키워드 규칙(`rule_based_style`)으로 해석하고 `engine: "rules"`로 알린다. 화면에는 "키워드로 해석" 배지.
3. 스타일을 `set_style`로 저장 → 가전 CMF 추천이 바로 이 스타일을 따른다.
4. 벽지·바닥재 상위 3개를 계산하고, 점수가 0보다 크면 1위를 적용한다(`apply_finishes=false`면 안 함).

## API
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/finishes` | 마감재 목록 |
| POST | `/api/projects/{pid}/finishes` | `{finish_id, tone?}` 적용. `scene_state.finish_ids[kind] = {id, tone}`, `materials[kind] = tone` |
| POST | `/api/projects/{pid}/style/ai` | `{prompt, zone_id?, apply_finishes=true}` → `{engine, summary, style, intent, finishes{wall,floor}, applied, products}`. `products`는 제품 조건을 말했을 때만 (`api.md` "대화로 제품 찾기") |

## 3D
`viewer.setFinishes({wall, floor})` → `dressRoom`이 벽·바닥에 질감 텍스처를 입힌다. 무늬는 회색조, 색은 톤(재질 색)이 곱해진다.
무늬 크기: 마루 = 판 폭 × 8줄(강 텍스처 165mm), 타일 = 타일 크기(진 그란데 805mm), 직물 0.35 m, 회벽·도장 0.9 m.
