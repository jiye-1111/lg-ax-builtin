#!/bin/bash
# 아직 없는 제품 사진만 이어서 렌더한다 (모양·색이 같은 묶음은 대표 하나만 렌더하고 복사).
# 준비: bpy가 깔린 파이썬. 예) python3 -m venv /tmp/bpyenv && /tmp/bpyenv/bin/pip install bpy
# 실행: 저장소 루트에서  BPY=/tmp/bpyenv/bin/python tools/catalog/thumbs_rest.sh
BPY=${BPY:-/tmp/bpyenv/bin/python}
G=tools/catalog/groups.json
while true; do
  REPS=$(python3 -c "
import json,os
r=[g[0] for g in json.load(open('$G')) if not os.path.exists(f'apps/web/img/products/{g[0]}.webp')]
print(' '.join(r[:20]))")
  [ -z "$REPS" ] && break
  args=""; for s in $REPS; do args="$args --sku $s"; done
  $BPY -c "import bpy,runpy,sys; sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')" \
    services/blender-worker/worker/bpy_scripts/render_thumbs.py --models apps/web/models/products --out apps/web/img/products $args 2>&1 | grep -E "^[A-Z0-9]+$|Error|Traceback"
done
python3 - <<'PY'
import json, shutil
from pathlib import Path
I = Path("apps/web/img/products")
for g in json.load(open("tools/catalog/groups.json")):
    for s in g[1:]:
        shutil.copyfile(I / f"{g[0]}.webp", I / f"{s}.webp")
print("imgs", len(list(I.glob("*.webp"))))
PY
echo done
