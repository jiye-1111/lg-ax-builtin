"""제품 겉면: LGE.COM 스펙 표의 재질(도어스타일/재질)과 색 이름으로 문짝이 어떻게 빛날지 정한다.

웹 3D의 apps/web/js/surface.js와 같은 규칙이다. 한쪽을 고치면 다른 쪽도 같이 고친다.
재질이 적혀 있지 않은 제품은 None: 모델에 들어 있는 값을 그대로 둔다.
"""
from __future__ import annotations

import re

# 메탈 문짝 중 금속 결이 그대로 보이는 색. 그 밖의 메탈(흰색·베이지 등)은 칠한 강판이라 매끈하게 빛난다
_BARE_METAL = re.compile("퓨어|실버|그라파이트|샤인|샤이니|스테인")

LOOKS = {
    "stainless": {"metallic": 1.0, "roughness": 0.2, "coat": 0.0, "coat_roughness": 0.0},
    "stone": {"metallic": 0.9, "roughness": 0.42, "coat": 0.0, "coat_roughness": 0.0},
    "brushed": {"metallic": 0.9, "roughness": 0.22, "coat": 0.0, "coat_roughness": 0.0},
    "coated": {"metallic": 0.05, "roughness": 0.3, "coat": 1.0, "coat_roughness": 0.06},
    "glass": {"metallic": 0.0, "roughness": 0.1, "coat": 1.0, "coat_roughness": 0.02},
    "mist": {"metallic": 0.0, "roughness": 0.48, "coat": 0.35, "coat_roughness": 0.4},
}
_COVERS_CASE = {"stainless", "stone", "brushed", "coated"}  # 금속 문짝은 몸통도 같은 강판이다


def surface_kind(material: str | None, color: str | None) -> str | None:
    m = material or ""
    if "스테인리스" in m:
        return "stone" if "스톤" in m else "stainless"
    if "미스트" in m:
        return "mist"
    if "글라스" in m or "미러" in m:
        return "glass"
    if "메탈" in m:
        return "brushed" if _BARE_METAL.search(color or "") else "coated"
    return None


def material_label(product) -> str:
    """카탈로그 제품의 재질 글자 (없으면 "")"""
    cmf = product.cmf_options[0] if product.cmf_options else None
    return str(product.options.get("door_material") or (cmf.material if cmf else None) or "")


def surface_for(product) -> dict | None:
    """렌더에 넘길 겉면 값. 재질을 모르면 None"""
    cmf = product.cmf_options[0] if product.cmf_options else None
    kind = surface_kind(material_label(product), cmf.color if cmf else None)
    return {"kind": kind, **LOOKS[kind], "case": kind in _COVERS_CASE} if kind else None
