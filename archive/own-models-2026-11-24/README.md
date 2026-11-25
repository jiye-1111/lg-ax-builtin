# 직접 만든 제품 모델 보관 (2026-11-24까지)

2026-11-25부터 화면은 전달받은 모델 묶음(LG-HANDOFF-01, 56개)만 쓴다.
그 전에 직접 만든 모델과 그 모델로 렌더한 사진은 지우지 않고 여기로 옮겨 두었다.

- `models/products/` 모델 294개, `index.json`(모델명 1,150개 → 파일), `companions.json`(정수기 파우셋 위치)
- `img/products/` 목록 사진 1,119장

만드는 코드는 그대로 있다: `services/blender-worker/worker/`(shapes, archetypes, bpy_scripts), `tools/models/plan.py`, `data/models/features.json`, `data/fusion/`, `data/drawings/`.
카탈로그(`data/catalog/products.json`)에서도 제품을 지우지 않았다. 목록에 나오는 것만 `data/catalog/lineup.json`으로 고른다.

## 다시 쓰려면

1. 이 폴더의 `models/products/*`, `img/products/*`를 `apps/web/models/products/`, `apps/web/img/products/`로 되돌린다.
   전달받은 56개는 `index.json`에서 `layout`이 `handoff`인 줄을 그대로 두고 나머지 줄만 합친다.
2. 서버 `.env`에 `CATALOG_LINEUP=all`을 넣으면 카탈로그 전체가 다시 목록에 나온다.
