# 3D 모델 출처 (공유기·사람·제품)

제품·가구 모델과 같은 원칙: 남의 3D 파일을 가져다 쓰지 않고, 공개된 치수·자유 이용 데이터로 Blender 스크립트가 만든다.

## 와이파이 공유기 `apps/web/models/devices/router.glb`
- 만드는 스크립트: `services/blender-worker/worker/bpy_scripts/build_router.py`
- 기준 제품: TP-Link Archer AX55 (AX3000). 데이터시트 치수 **261.1 × 134.5 × 41.0 mm**, 고정 안테나 4개, 뒤쪽 WAN 1·LAN 4·USB 3.0 1
  - https://www.tp-link.com/en/home-networking/wifi-router/archer-ax55/
  - https://static.tp-link.com/upload/product-overview/2021/202112/20211209/Archer%20AX55(EU&US)1.0_Datasheet.pdf
  - 확인: 2026-11-20
- 안테나 길이(165 mm)와 윗면 모양은 공개 값이 없어 제품 사진 비율로 잡은 화면용 표현. 로고·상표는 넣지 않았다.
- 와이파이 신호 계산은 무지향(공유기 방향과 무관)이라 모델 방향은 화면 표시용이다.

## 동선을 걷는 사람 `apps/web/models/people/walker.glb`
- 만드는 스크립트: `services/blender-worker/worker/bpy_scripts/build_person.py`
- 몸·뼈대·가중치: MakeHuman 1.x 기본 데이터 (base.obj, default.mhskel, default_weights.mhw, 매크로 타깃)
  - https://github.com/makehumancommunity/makehuman (커밋 a8bc2d5), 에셋 라이선스 **CC0 1.0** (`LICENSE.ASSETS.md`)
  - 받기: `scripts/fetch_makehuman.sh` (필요한 파일만, 커밋 고정)
- 20대 동양인 남성, 보통 체형, 키 170 cm(신발 포함). 옷(니트·청바지·운동화)과 짧은 머리는 MakeHuman 보조 메시와 두피 면을 떼어 만들었다.
- 걷기 동작은 스크립트에서 직접 키프레임으로 만든 것(모션 캡처 데이터 아님). 한 주기 32프레임(30 fps) 동안 1.3 m/s로 1.39 m를 간다.

다시 만들기:
```bash
scripts/fetch_makehuman.sh
python services/blender-worker/worker/bpy_scripts/build_person.py --mh .cache/makehuman --out apps/web/models/people/walker.glb
python services/blender-worker/worker/bpy_scripts/build_router.py --out apps/web/models/devices/router.glb
```
(pip `bpy` 환경, 또는 `blender -b -P <스크립트> -- <인자>`)


## 제품 모델 (Fusion으로 만든 가전) `apps/web/models/products/<SKU>.glb`

### 모양·치수

- 크기: 카탈로그 `data/catalog/products.json`의 `product_dims_mm` (LGE.COM 값)
- 문 나눔·창·손잡이 위치: LGE.COM 제품 페이지의 치수도 이미지를 보고 잰 근사값. 제품별 치수도 주소와 잰 값은 `data/fusion/<SKU>/drawing.json`의 `source`에 있다
- 모델링: Autodesk Fusion에서 직접 만들었다 (`data/fusion/<SKU>/*.f3d`, 부품 STL). LG가 배포하는 CAD나 사진을 모델에 넣지 않았다

### 색

- 문·겉판 색: 카탈로그 `cmf_options[].hex_approx`
- 본체·조작부 색: 치수도 이미지에서 본 색의 근사값 (`drawing.json`의 `colors`)

### 표면 질감 (텍스처)

밖에서 가져온 텍스처는 없다. 모두 `services/blender-worker/worker/bpy_scripts/fusion_to_glb.py`의 `normal_image()`가 숫자 계산으로 만든다.

| 이름 | 쓰이는 곳 | 만드는 방법 | 크기 |
|---|---|---|---|
| hairline | 메탈·스테인리스 문, 금속 부품(선반, 줄무늬 몸통) | 난수(seed 7)로 만든 가로 방향 높낮이를 노멀맵으로 바꿈. 세로 결이 보인다 | 256×4 px, 64mm마다 반복 |
| fabric | 패브릭 느낌 겉면 (`drawing.json`의 `colors.door.texture: "fabric"`, 지금은 AS356NSMA) | 가로세로 실이 엇갈리는 사인 무늬를 노멀맵으로 바꿈 | 64×64 px, 16mm마다 반복 |

- 유리(글라스) 마감은 텍스처 없이 매끈한 코팅 반사만 쓴다
- LG 로고, 제품 사진, 조작부 글자는 넣지 않았다


## 제품 모델 (제품군 틀로 만든 가전) — 판매 중인 제품

Fusion으로 직접 만들지 않은 판매 중 제품(`sale_status`가 ACTIVE·SOLD_OUT)은 제품군 틀에 제품별 값을 넣어 만든다. 판매 종료 제품은 손대지 않았다.

### 모양·치수

- 크기: 카탈로그 `product_dims_mm` (LGE.COM 값). 만든 모델은 이 치수에 정확히 맞춘다
- 틀: `services/blender-worker/worker/archetypes.py`. 냉장고, 김치냉장고, 드럼세탁기, 워시타워, 통돌이, TV, 스탠드·벽걸이 에어컨, 공기청정기, 정수기, 청소기, 안마의자 등 제품군마다 하나
- 제품별 값: `data/models/features.json`. 문이 몇 칸인지, 문 나눔 높이, 손잡이·디스펜서·유리문 유무, TV 받침 종류와 위치 등. 2026-11-24에 LGE.COM 제품 사진과 치수도 이미지를 보고 잰 근사값이다 (`tools/models/make_features.py`에 적어 두고 여기서 json을 만든다)
- LG가 배포하는 CAD나 사진은 모델에 넣지 않았다. 로고·글자도 없다

### 색

- 겉면 색: 재질 이름이 `finish`인 면을 웹이 카탈로그 `cmf_options[].hex_approx`로 칠한다. 그래서 색만 다른 모델은 glb 하나를 같이 쓴다 (`index.json`의 `file`)
- 그 밖의 부품 색(본체, 조작부, 금속)은 `realize.py`의 `MATS` 표에 있는 근사값

> 2026-11-25부터 화면은 전달받은 모델 묶음만 쓴다 (`docs/catalog-sources.md`). 이 방법으로 만든 모델은 쓰지 않기로 해서 저장소에서 지웠다. 아래 순서는 기록으로만 남긴다.

### 만드는 순서

```bash
python3 tools/models/make_features.py                 # 제품별 값 → data/models/features.json
uv run python tools/models/plan.py                    # 무엇을 만들지 → .cache/model_plan.json
python services/blender-worker/worker/bpy_scripts/build_models.py --plan .cache/model_plan.json --out apps/web/models/products
python services/blender-worker/worker/bpy_scripts/render_thumbs.py --models apps/web/models/products --out apps/web/img/products --catalog data/catalog/products.json --list <모델명 목록>
```

`index.json`의 `layout`이 틀 이름이면 이 방법으로 만든 모델, `fusion`이면 Fusion 모델, `drawing`이면 예전 도면 방식(판매 종료 제품)이다.
