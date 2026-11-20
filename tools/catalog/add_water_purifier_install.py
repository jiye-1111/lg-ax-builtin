"""LGE.COM 정수기 설치가이드의 설치 규격을 정수기 29종에 넣는다.

출처: https://www.lge.co.kr/story/user-guide/lg-water-purifiers-install-guide (2026-11-20 확인)
가이드는 데스크·스탠드·빌트인 유형별로 적혀 있어, 유형에 해당하는 값을 그 유형의 모든 모델에 넣는다.
사용: python tools/catalog/add_water_purifier_install.py <저장소 경로>
"""
import json, sys
from pathlib import Path

GUIDE = "https://www.lge.co.kr/story/user-guide/lg-water-purifiers-install-guide"
NOTES = {
    "데스크": f"설치 여유: 제품 위 15cm 이상, 벽면 쪽 10mm, 옆면 쪽 100mm 이상 (미확보 시 설치 불가). 싱크대 타공 약 9~10mm, 원수·배수 모두 연결하면 약 15mm: 정수기 설치가이드 {GUIDE}",
    "스탠드": f"설치 여유: 벽면과 10~15cm. 가구장 안에 놓으면 상부 35cm 이상, 바닥에 직접 닿게 (슬라이딩 선반 위 불가): 정수기 설치가이드 {GUIDE}",
    "빌트인": f"하부장 안 본체: 벽 쪽 10mm, 옆 쪽 100mm 여유. 출수구: 타공 지름 28mm, 데코링 52mm, 싱크볼 하판 가로 102mm × 세로 70mm, 출수구-본체 최대 730mm, 원수에서 5m 이내, 콘센트 없으면 55mm 타공: 정수기 설치가이드 {GUIDE}",
}
DRAIN_WORDS = ("냉동얼음", "라이트온", "음성인식", "상하좌우")  # 가이드: 배수호스 연결 위해 타공 필수

root = Path(sys.argv[1])
path = root / "data/catalog/products.json"
raw = json.loads(path.read_text(encoding="utf-8"))
n = 0
for p in raw["products"]:
    if p["category"] != "water_purifier":
        continue
    sku = p["sku"]
    form = "빌트인" if sku.startswith("WU") else "스탠드" if sku.startswith("WS") else "데스크"
    p["install_form"] = form
    if form == "데스크":
        p["clearance_mm"] = {"side": None, "side_total": 100, "top": 150, "back": 10}
        drain = any(w in p["name"] for w in DRAIN_WORDS)
        p["needs_drain"] = True if drain else None
        p["install_mm"] = {"hose_hole_dia": 15 if drain else 10}
    elif form == "스탠드":
        p["clearance_mm"] = {"side": None, "side_total": None, "top": None, "back": 100}
        p["install_mm"] = {"cabinet_top_min": 350}
    else:
        p["install_type"] = "built_in"   # 가이드의 빌트인 정수기: WU9*3 / 8*3 / 5*3
        p["clearance_mm"] = {"side": None, "side_total": 100, "top": None, "back": 10}
        p["install_mm"] = {"faucet_hole_dia": 28, "faucet_ring_dia": 52, "faucet_under_w": 102, "faucet_under_d": 70,
                           "faucet_to_body_max": 730, "water_source_max": 5000, "cord_hole_dia": 55, "hose_hole_dia": 15}
    p["spec_notes"] = [s for s in p.get("spec_notes", []) if "정수기 설치가이드" not in s] + [NOTES[form]]
    n += 1
path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(n, "개")
