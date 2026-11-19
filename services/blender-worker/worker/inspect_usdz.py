"""USDZ 구조 분석 도구 (기획 §15-2, plan.md T1.6).

UGScan 샘플을 받으면:  uv run python -m worker.inspect_usdz data/samples/<파일>.usdz > docs/specs/usdz-analysis.txt
프림 트리(경로·타입·변환·extent), 커스텀 속성, 현재 변환 규칙으로 어떻게 분류되는지를 출력한다.
"""
from __future__ import annotations

import sys

from pxr import Usd, UsdGeom

from .converter import classify, convert_stage


def main(path: str) -> None:
    st = Usd.Stage.Open(path)
    print(f"# {path}")
    print(f"upAxis={UsdGeom.GetStageUpAxis(st)} metersPerUnit={UsdGeom.GetStageMetersPerUnit(st)} "
          f"defaultPrim={st.GetDefaultPrim().GetPath() if st.GetDefaultPrim() else None}")
    print("\n## 프림 트리 (경로 | 타입 | 분류 | 추가 속성)")
    for p in st.Traverse():
        depth = len(p.GetPath().pathString.split("/")) - 2
        c = classify(p.GetName())
        attrs = [a.GetName() for a in p.GetAttributes() if a.IsCustom()]
        meta = {k: v for k, v in p.GetCustomData().items() if k != "userDocBrief"}
        print(f"{'  ' * depth}{p.GetName()} | {p.GetTypeName()} | {c[1] if c else '-'}"
              f"{' | custom=' + ','.join(attrs) if attrs else ''}{' | customData=' + str(meta) if meta else ''}")
    print("\n## 변환 결과 요약")
    r = convert_stage(st)
    for w in r.walls:
        print(f"{w.wall_id}: len={w.scanned.length_m} h={w.scanned.height_m} t={w.thickness_m} {w.start}->{w.end}")
    for o in r.openings:
        print(f"{o.opening_id}({o.type}) wall={o.wall_id} off={o.offset_m} w={o.width_m} h={o.height_m} sill={o.sill_m}")
    for o in r.objects:
        print(f"{o.object_id}({o.category}) {o.bbox_m.model_dump()} @ {o.position}")


if __name__ == "__main__":
    main(sys.argv[1])
