# 카탈로그 스펙 (기획 §8.4)

- 실데이터: `data/catalog/products.json` · 가상 데이터: `data/catalog/demo_fixture.json` (`demo_only: true`, 이름 앞 `[가상]`)
- 스키마: `core.models.Product` (정의에 없는 필드 거부). 치수 mm.
- 규칙
  1. 값은 **LGE.COM 제품 페이지에 적힌 것만** 옮긴다. 확인 못한 값은 `null`. 추정·다른 모델 값 차용 금지.
  2. `source_url`(제품 페이지), `source_checked_at`(YYYY-MM-DD) 필수. 설치 가이드 등 추가 출처는 `docs/catalog-sources.md`에.
  3. `required_space_mm`는 제조사가 "설치 공간"으로 명시한 경우에만. 없으면 null (판정은 제품 치수 + 이격으로).
  4. `hex_approx`는 제품 이미지 근사값 (공식 아님).
- 우선순위(기획 Q4 미정): 냉장고·김치냉장고(핏 앤 맥스, 오브제컬렉션 컨버터블) → 식기세척기 → 오븐·인덕션 → 정수기.
- `CATALOG_INCLUDE_DEMO=0`이면 가상 데이터를 끈다 (실데이터 10종 이상 확보 후 발표용).
