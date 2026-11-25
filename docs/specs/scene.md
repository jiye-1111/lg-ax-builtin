# 3D 씬 · Blender 워커 스펙

| 단계 | Blender 있음 (`BLENDER_BIN` 또는 PATH) | Blender 없음 (폴백) |
|------|------|------|
| 웹 3D 파일 | `glb.py`: room.json 치수 박스 (둘 다 같음) | 동일 |
| 렌더 입력 | `glb.py` 상자 목록 (옮긴·치운 가구 반영) + 제품·가구 모델 | room.json |
| 벽·바닥 | 창·문 자리는 구멍(Boolean), 걸레받이, 마루 무늬 × 바닥 색, 무광 페인트 | 박스 색 |
| 스캔 가구 | `models/furniture/<종류>.glb`를 스캔 크기에 맞춰 부품별로 늘림 (웹과 같은 rig 규칙) | 박스 |
| 제품 배치 | `models/products/index.json`에 적힌 모델 파일 + 고른 색 | 박스 + 색 |
| 렌더 | Cycles CPU 64샘플 + 노이즈 제거, 1600×900, AgX (`BLENDER_ENGINE=EEVEE`로 바꿀 수 있음) | `plan_render.py`: 등각 컷어웨이 PNG |
| 출력 | scene.glb, render.png, scene.blend | scene.glb, render.png |

- 웹 3D 파일은 Blender가 있어도 `glb.py`가 만든다. 웹이 노드 이름(o1, w1, floor)과 extras(kind, category),
  단위 상자 scale로 가구 집기·모델 바꾸기·벽 흐리게 하기를 하기 때문이다 (`tests/unit/test_runner.py`).
- Blender는 렌더 이미지를 누를 때만 띄운다. 가구를 옮기거나 색을 바꿀 때는 glb만 새로 만든다 (바로 반영).
- `scene.engine`은 렌더를 누가 맡는지다: Blender가 켜져 있으면 `blender`, 렌더가 실패하면 그 렌더는 `fallback`.
- 렌더 카메라는 웹 기본 시점과 같은 쪽에서 방 전체가 들어오게 맞추고, 카메라 쪽 벽은 낮게 자른다.
- 씬 상태(`project.scene_state`): `materials{target: hex}`, `wall_colors{wall_id: hex}`, `finish`, `placements[]`,
  `object_poses{object_id: {center_xz, yaw_rad}}`, `hidden_objects[]`.
- 상태가 바뀔 때마다 glb를 다시 만든다(웹 뷰어가 version 폴링으로 다시 로드).
- Blender 실패·시간 초과 시 `storage/projects/<pid>/scene/blender.log` 남기고 폴백 렌더.
- 실제 Blender 확인: `tests/integration/test_blender_render.py` (Blender 없는 PC는 건너뜀). i7-10700 CPU 기준 30초 안팎.
- 3D 모델이 없으면 치수 박스로 대체 (기획 §8.4).

## 실제 채광 (해 빛)

- `sim.daylight.sun_light(site, when)`: 날짜·시각·위도·경도(기본 서울)·집의 북쪽 → 해 쪽 단위 벡터(웹 3D 좌표),
  색, 세기. 해 위치는 `sim.solar`(NOAA 식), 수평 방향은 바닥 볕 자리(`sun_patches`)와 같은 식을 쓴다.
- 색: 해 높이 25° 이상은 6500 K(중립 흰빛), 낮아질수록 따뜻해져 지평선에서 약 2000 K. 노랗게 칠하지 않는다.
- `GET /sim/daylight?...&heatmap=false`: 하루 직사광 격자 없이 해만 (시간 슬라이더용, 빠름).
- 웹 3D: 채광을 켜면 DirectionalLight를 그 방향·색·세기로 두고, 화면에는 안 보이는 그림자 껍데기
  (창·문 자리를 뺀 벽 조각 + 천장, `room3d.js shadowShell`)를 켠다. 해는 창으로만 들어온다.
  노란 하루 직사광 히트맵은 "하루 햇빛 시간 겹쳐 보기"로 켤 때만 (기본 꺼짐).
- Blender 렌더: 채광을 보고 있을 때 `POST /render {date, time}` → `state.sun` → job `sun`. 같은 방향·색으로 해를 두고,
  카메라에 안 보이는 천장·앞벽(창 구멍 포함)이 그림자를 낸다. 유리는 그림자에서 뺀다(Cycles 유리는 해를 막는다).
