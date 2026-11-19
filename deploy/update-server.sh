#!/usr/bin/env bash
# 코드를 고친 뒤 서버에 반영: GitHub main 받기 → 패키지 맞추기 → 재시작 → 상태 확인
set -euo pipefail
APP_DIR="${APP_DIR:-$HOME/apps/lg-ax-builtin}"
BRANCH="${BRANCH:-main}"
export PATH="$HOME/.local/bin:$PATH"
cd "$APP_DIR"
git pull --ff-only origin "$BRANCH"
uv sync --frozen
sudo systemctl restart lgb-api
sleep 3
sudo systemctl is-active lgb-api
curl -fsS http://127.0.0.1:8000/api/health && echo
git log --oneline -1
