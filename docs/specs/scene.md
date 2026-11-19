# 3D 씬 · Blender 워커 스펙

| 단계 | Blender 있음 (`BLENDER_BIN` 또는 PATH) | Blender 없음 (폴백) |
|------|------|------|
| 씬 | `bpy_scripts/build_scene.py`: USDZ import (원본 메시) | `glb.py`: room.json 치수 박스 |
| 재질 | 이름 규칙(Wall*, Floor*, Door*, Window*, Storage*)에 Principled BSDF | 박스 baseColor |
| 제품 배치 | 치수 박스 + CMF 색 | 동일 |
| 렌더 | EEVEE 1280×720 PNG | `plan_render.py`: 등각 컷어웨이 PNG |
| 출력 | scene.glb, render.png, scene.blend | scene.glb, render.png |

- 씬 상태(`project.scene_state`): `materials{target: hex}`, `wall_colors{wall_id: hex}`, `finish`, `placements[]`.
- 상태가 바뀔 때마다 glb를 다시 만든다(웹 뷰어가 version 폴링으로 다시 로드).
- Blender 실패 시 `storage/projects/<pid>/scene/blender.log` 남기고 폴백.
- ⚠️ bpy 스크립트는 개발 클라우드 환경에 Blender가 없어 **미검증**. 팀 PC에서 manual-qa.md 3번으로 확인.
- 3D 모델이 없으면 치수 박스로 대체 (기획 §8.4).
