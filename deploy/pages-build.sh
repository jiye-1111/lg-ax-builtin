#!/usr/bin/env bash
# Cloudflare Pages 빌드 명령. 웹은 빌드할 게 없어서 API 주소만 config.js에 적는다.
# Pages 환경변수 API_BASE = https://api-<프로젝트명>.axworks.site
set -euo pipefail
OUT="${CONFIG_OUT:-apps/web/config.js}"
BASE="${API_BASE:-}"
BASE="${BASE%/}"
printf 'window.LGB_API = "%s";\n' "$BASE" > "$OUT"
echo "config.js: API_BASE=${BASE:-(같은 서버)}"
