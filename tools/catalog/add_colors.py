"""LGE.COM 제품 페이지의 '도어 색상' 값을 색상이 비어 있던 제품에 넣는다.

lgecom_colors.json: {제품 주소 끝부분(소문자): 색상 이름}. hex_approx는 색상 이름에 맞춘 근사색(공식 값 아님).
사용: python tools/catalog/add_colors.py <저장소 경로>
"""
import json, sys
from pathlib import Path

root = Path(sys.argv[1])
C = json.loads((root / "tools/catalog/lgecom_colors.json").read_text(encoding="utf-8"))
HEX = {"샌드 베이지": "#DCD2C4", "블랙틴트미러": "#3A3B3F", "클레이 브라운": "#9C7A66", "에센스 화이트": "#EFEFEF", "토프": "#9B8F84",
       "에센스 그라파이트": "#4A4B4F", "크림 그레이": "#CFCBC4", "화이트": "#F4F4F2", "딥블랙 미러": "#1C1C1E", "린넨 화이트": "#F1EEE6",
       "미스트 베이지": "#E8E1D6", "카밍 핑크": "#E3C8C2", "카밍 매트 블랙": "#292929", "미스트 크림 화이트": "#F2EFE8",
       "카밍 에센스 화이트": "#EFEFEF", "카밍 베이지": "#E6DFD5", "블랙": "#2E3036", "크리스탈 핑크": "#EBCFCB", "크리스탈 베이지": "#EAE2D6"}
path = root / "data/catalog/products.json"
raw = json.loads(path.read_text(encoding="utf-8"))
n = 0
for p in raw["products"]:
    name = C.get(p["source_url"].rstrip("/").rsplit("/", 1)[-1])
    o = p["cmf_options"][0] if p["cmf_options"] else None
    if name and o is not None and not o.get("color"):
        o["color"], o["hex_approx"] = name, HEX[name]
        n += 1
path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(n, "개 채움")
