# 3D 모델 출처 (공유기·사람)

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
