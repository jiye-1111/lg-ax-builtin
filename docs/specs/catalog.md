# 카탈로그 스펙 (기획 §8.4)

- 실데이터: `data/catalog/products.json` · 가상 데이터: `data/catalog/demo_fixture.json` (`demo_only: true`, 이름 앞 `[가상]`)
- 스키마: `core.models.Product` (정의에 없는 필드 거부). 치수 mm.
- 규칙
  1. 값은 **LGE.COM 제품 페이지에 적힌 것만** 옮긴다. 확인 못한 값은 `null`. 추정·다른 모델 값 차용 금지.
  2. `source_url`(제품 페이지), `source_checked_at`(YYYY-MM-DD) 필수. 설치 가이드 등 추가 출처는 `docs/catalog-sources.md`에.
  3. `required_space_mm`는 제조사가 "설치 공간"으로 명시한 경우에만. 없으면 null (판정은 제품 치수 + 이격으로).
  4. `hex_approx`는 제품 이미지 근사값 (공식 아님).
- 우선순위(기획 Q4 미정): 냉장고·김치냉장고(핏 앤 맥스, 오브제컬렉션 컨버터블) → 식기세척기 → 오븐·인덕션 → 정수기.
- 현재 실데이터 16종(2026-11-19): Fit & Max 냉장고 5 · 김치냉장고 4, 빌트인 식기세척기 2, 인덕션 3, 언더싱크 정수기 2. 출처는 `docs/catalog-sources.md`.
- 기본값 `CATALOG_INCLUDE_DEMO=0` (실데이터만). 거실 제품은 아직 가상 데이터뿐이라 거실 추천을 보여 주려면 1로.
- 테스트는 `tests/conftest.py`에서 가상 데이터를 켠다.
- 필드 추가: `cutout_mm`(상판 타공), `spec_notes`(값마다 어디서 가져왔는지).
