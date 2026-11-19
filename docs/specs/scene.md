# 3D 씬 · Blender 워커 스펙

| 단계 | Blender 있음 (`BLENDER_BIN` 또는 PATH) | Blender 없음 (폴백) |
|------|------|------|
| 웹 3D 파일 | `glb.py`: room.json 치수 박스 (둘 다 같음) | 동일 |
| 렌더 입력 | `glb.py` 상자 목록 (옮긴·치운 가구 반영) + 제품·가구 모델 | room.json |
| 벽·바닥 | 창·문 자리는 구멍(Boolean), 걸레받이, 마루 무늬 × 바닥 색, 무광 페인트 | 박스 색 |
| 스캔 가구 | `models/furniture/<종류>.glb`를 스캔 크기에 맞춰 부품별로 늘림 (웹과 같은 rig 규칙) | 박스 |
| 제품 배치 | `models/products/<sku>.glb` + 고른 색 | 박스 + 색 |
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
