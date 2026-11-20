#!/usr/bin/env bash
# Lightsail Ubuntu 24.04에서 처음 한 번 실행: 코드 받기 → 파이썬 환경 → .env → systemd → Caddy(HTTPS)
# 사용: bash setup-server.sh api-housetwin.13-238-79-150.sslip.io https://housetwin.pages.dev
set -euo pipefail
API_DOMAIN="${1:?API 도메인 (예: api-housetwin.13-238-79-150.sslip.io)}"
WEB_ORIGINS="${2:?웹 주소, 쉼표 구분 (예: https://housetwin.pages.dev)}"
REPO="${REPO:-https://github.com/jiye-1111/lg-ax-builtin.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-$HOME/apps/lg-ax-builtin}"
APP_USER="$(whoami)"
WEB_MAIN="${WEB_ORIGINS%%,*}"

echo "== 1. 필요한 프로그램 (git, curl, Caddy)"
sudo apt-get update -y
sudo apt-get install -y git curl debian-keyring debian-archive-keyring apt-transport-https gnupg
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
  sudo apt-get update -y
  sudo apt-get install -y caddy
fi
if ! command -v uv >/dev/null && [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

echo "== 2. 코드 받기 ($REPO, $BRANCH)"
mkdir -p "$(dirname "$APP_DIR")"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin "$BRANCH" && git -C "$APP_DIR" checkout "$BRANCH" && git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
else
  git clone -b "$BRANCH" "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

echo "== 3. 파이썬 환경 (uv sync)"
uv sync --frozen

echo "== 4. .env (없을 때만 만든다. 있으면 그대로 둠)"
if [ ! -f .env ]; then
  cp .env.example .env
  sed -i \
    -e "s|^API_HOST=.*|API_HOST=127.0.0.1|" \
    -e "s|^API_PORT=.*|API_PORT=8000|" \
    -e "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=$WEB_MAIN|" \
    -e "s|^CORS_ORIGINS=.*|CORS_ORIGINS=$WEB_ORIGINS|" \
    -e "s|^USE_BLENDER=.*|USE_BLENDER=0|" \
    .env
fi
chmod 600 .env
mkdir -p storage

echo "== 5. systemd 서비스 (lgb-api)"
sed -e "s|APP_USER|$APP_USER|g" -e "s|APP_DIR|$APP_DIR|g" deploy/lgb-api.service | sudo tee /etc/systemd/system/lgb-api.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable lgb-api
sudo systemctl restart lgb-api

echo "== 6. Caddy (https://$API_DOMAIN → 127.0.0.1:8000)"
sed -e "s|API_DOMAIN|$API_DOMAIN|g" deploy/Caddyfile | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy || sudo systemctl restart caddy

sleep 3
echo "== 확인"
sudo systemctl is-active lgb-api caddy
curl -fsS http://127.0.0.1:8000/api/health && echo
echo "끝. 도메인 DNS가 이 서버 고정 IP를 가리키면 https://$API_DOMAIN/api/health 가 열립니다."
