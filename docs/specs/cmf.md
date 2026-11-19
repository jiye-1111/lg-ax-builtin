# CMF 매칭 스펙 (기획 §9.2)

코드: `services/recommender/recommender/cmf.py` · 테스트: `tests/unit/test_cmf.py`

- 영역 스타일 = `palette`(#RRGGBB 1~8개) + `materials`(키워드). LLM이 프롬프트·이미지를 해석해 MCP `set_style`로 저장한다.
- 옵션 점수 = **0.6 × 색 점수 + 0.4 × 재질 점수**
  - 색 점수 = max(0, 1 − min ΔE2000(옵션 `hex_approx`, 팔레트 각 색) / 50) — sRGB → CIELAB(D65)
  - 재질 점수 = 영역 키워드 중 옵션(재질·마감·색상명)에 들어 있는 비율. 한/영 동의어 표(`SYNONYMS`)로 정규화 (우드=wood, 매트/무광=matte ...)
  - `hex_approx`가 null이면 재질 점수만 쓰고 `color_unknown` 표시. 스타일이 비어 있으면 0점.
- 상위 3개 반환. `reasons`(점수 근거 문장)를 함께 준다. LLM 설명은 reasons를 벗어나지 않는다.
- `hex_approx`는 제품 이미지에서 뽑은 **근사값**이다 → UI에 "근사색" 표시.
