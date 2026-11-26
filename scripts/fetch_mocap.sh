#!/usr/bin/env bash
# 동선 사람 걷기에 쓰는 모션 캡처(CMU Graphics Lab, cgspeed BVH 변환본)를 받는다. 자유롭게 써도 되는 데이터.
# 사용: scripts/fetch_mocap.sh [저장 폴더]  (기본 .cache/mocap)
set -euo pipefail
REV=09a07f54f3bbb58797325f009282d0b2048a2871
DEST=${1:-.cache/mocap}
mkdir -p "$DEST"
curl -fsSL "https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/$REV/data/035/35_01.bvh" -o "$DEST/35_01.bvh"
curl -fsSL "https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/$REV/READMEFIRST.txt" -o "$DEST/READMEFIRST.txt"
echo "받음: $DEST"
