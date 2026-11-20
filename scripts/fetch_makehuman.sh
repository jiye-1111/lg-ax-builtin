#!/usr/bin/env bash
# 사람 모델(build_person.py)에 쓰는 MakeHuman 데이터(CC0)만 받는다. 커밋을 고정해 같은 모델이 나오게 한다.
# 사용: scripts/fetch_makehuman.sh [저장 폴더]  (기본 .cache/makehuman)
set -euo pipefail
REV=a8bc2d54ff0ac92e78ff71431b1023eda42bf482
DEST=${1:-.cache/makehuman}
BASE=https://raw.githubusercontent.com/makehumancommunity/makehuman/$REV/makehuman/data
for f in 3dobjs/base.obj rigs/default.mhskel rigs/default_weights.mhw \
         targets/macrodetails/asian-male-young.target \
         targets/macrodetails/universal-male-young-averagemuscle-averageweight.target; do
  mkdir -p "$DEST/$(dirname "$f")"
  curl -fsSL "$BASE/$f" -o "$DEST/$f"
done
curl -fsSL https://raw.githubusercontent.com/makehumancommunity/makehuman/$REV/LICENSE.ASSETS.md -o "$DEST/LICENSE.ASSETS.md"
echo "받음: $DEST"
