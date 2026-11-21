#!/usr/bin/env bash
# 내 저장소 main을 팀 저장소(2Jaegon/LG_P3_digitaltwin)의 jiye 브랜치로 올린다.
# 팀 저장소 main에는 절대 올리지 않는다.
set -euo pipefail

TEAM_URL="${TEAM_REPO_URL:-https://github.com/2Jaegon/LG_P3_digitaltwin}"
TEAM_BRANCH="${TEAM_BRANCH:-jiye}"

if [ "$TEAM_BRANCH" = "main" ] || [ "$TEAM_BRANCH" = "master" ]; then
  echo "팀 저장소 $TEAM_BRANCH 에는 올리지 않습니다." >&2
  exit 1
fi

git remote get-url team >/dev/null 2>&1 || git remote add team "$TEAM_URL"
git fetch origin main
if [ "$(git rev-parse --is-shallow-repository)" = "true" ]; then
  git fetch --unshallow origin
fi
git push team "origin/main:refs/heads/$TEAM_BRANCH"
echo "팀 저장소 $TEAM_BRANCH 브랜치 = $(git rev-parse --short origin/main)"
