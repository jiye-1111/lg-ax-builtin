# 제품 도면 (Figma → Blender)

가전·가구 모델은 Figma에서 정면·옆면 도면을 먼저 그리고, 그 도면대로 Blender가 3D를 만든다.

- Figma 파일: [LG 빌트인 제품 도면](https://www.figma.com/design/obpzTCmt78Xh379BQk2LYl) · 페이지 하나 = 제품 종류
- 프레임 이름 `<SKU> / 정면`, `<SKU> / 옆면`. 안쪽 `parts` 프레임 = 모델에 쓰는 사각형, `annotations` = 치수선(모델에 안 씀)
- 1px = 1mm. 정면 `parts` 크기 = 카탈로그 폭 × 높이, 옆면 `parts` 폭 = 카탈로그 깊이 (1mm 넘게 다르면 만들지 않음)
- 사각형 이름: `body`, `door/<번호>`, `handle/<문 번호>/<v|h>`, `vent`, `display`. 옆면은 `door/side`, `handle/side`, `body` 가 앞뒤 범위를 정한다 (왼쪽이 앞)
- 내보낸 값은 `data/drawings/<SKU>.json`. `build_products.py`가 이 파일이 있으면 도면대로, 없으면 종류별 기본 모양으로 만든다 (index.json `layout: "drawing"`)
- 전체 치수만 LGE.COM 값이다. 문 나눔·손잡이 위치는 제품 사진을 보고 그린 화면용 표현이다.

```bash
python services/blender-worker/worker/bpy_scripts/build_products.py \
  --catalog data/catalog/products.json --out apps/web/models/products --sku G646GBB031
```

지금 그린 것: G646GBB031(냉장고 4도어), DUE6BGE(식기세척기). 나머지 제품은 같은 규칙으로 페이지를 늘려 가면 된다.
