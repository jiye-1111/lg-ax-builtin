# 서버 배포 (LG HouseTwin)

웹 화면은 Cloudflare Pages, API는 AWS Lightsail에 올린다. 도메인을 따로 사지 않고, 웹은 `pages.dev`, API는 고정 IP를 이름에 담는 무료 와일드카드 DNS `sslip.io`를 쓴다. 누구 도움 없이 바로 HTTPS까지 열린다.

| 구분 | 어디에 | 주소 |
|---|---|---|
| 웹 (apps/web, 빌드 없는 정적 SPA) | Cloudflare Pages `housetwin` | https://housetwin.pages.dev |
| API (FastAPI) | Lightsail `AX_PRACTICE` (시드니, 2 GB) 고정 IP 13.238.79.150 | https://api-housetwin.13-238-79-150.sslip.io |
| HTTPS | Lightsail 안 Caddy → 127.0.0.1:8000 | Let's Encrypt 인증서 자동 발급·갱신 |

`api-housetwin.13-238-79-150.sslip.io`는 sslip.io가 이름 속 IP(13.238.79.150)를 그대로 돌려줘서 DNS 등록이 필요 없다. 나중에 우리 도메인을 사면 Caddyfile 주소, Pages `API_BASE`, 서버 `.env` 세 군데만 바꾸면 된다.

팀 PC에서 `start.bat`으로 돌리는 방식은 그대로다. `apps/web/config.js`의 `LGB_API`가 비어 있으면 웹과 API가 같은 서버에서 돈다.

## 1. API 서버 (Lightsail)

방화벽: 22(내 IP만), 80, 443. 8000은 열지 않는다 (Caddy만 안에서 부른다).

처음 한 번:

```bash
curl -fsSL https://raw.githubusercontent.com/jiye-1111/lg-ax-builtin/main/deploy/setup-server.sh -o s.sh
bash s.sh api-housetwin.13-238-79-150.sslip.io https://housetwin.pages.dev
```

`setup-server.sh`가 하는 일: git·Caddy·uv 설치 → `~/apps/lg-ax-builtin`에 clone → `uv sync` → `.env` 생성(chmod 600) → systemd `lgb-api` 등록 → `/etc/caddy/Caddyfile` 적용.

서버 `.env`에서 배포용으로 바뀌는 값:

| 키 | 값 |
|---|---|
| `API_HOST` / `API_PORT` | `127.0.0.1` / `8000` |
| `PUBLIC_BASE_URL` | `https://housetwin.pages.dev` (고객 링크에 쓰임) |
| `CORS_ORIGINS` | `https://housetwin.pages.dev` |
| `USE_BLENDER` | `0` (서버엔 Blender 없음, 렌더는 Python 폴백) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | 기사 승인용 관리자 계정. 비밀번호는 서버 `.env`에만 둔다 ([accounts.md](specs/accounts.md)) |

MCP HTTP는 서버에서 열지 않는다.

코드를 고친 뒤 반영:

```bash
bash ~/apps/lg-ax-builtin/deploy/update-server.sh
```

상태·로그: `sudo systemctl status lgb-api`, `journalctl -u lgb-api -n 100`, `journalctl -u caddy -n 50`.

확인: https://api-housetwin.13-238-79-150.sslip.io/api/health 가 `{"ok":true,...}`

### 서버에서 Blender 쓰기

실사 버튼은 이미지 AI가 먼저 그리고, AI를 못 쓰거나 10분 한도를 넘기면 서버의 Blender가 보던 시점 그대로 그린다.
도면으로 만든 집도 같다. 화면 없이 돌아가므로 서버에 모니터나 GPU가 없어도 된다.

```bash
sudo snap install blender --classic
sudo apt-get install -y libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libsm6 libxkbcommon0 libegl1
/snap/bin/blender -b --version
```

`.env`에 아래 값을 넣고 `sudo systemctl restart lgb-api`. `/api/health`의 `blender`에 경로가 나오면 켜진 것이다.

```
BLENDER_BIN=/snap/bin/blender
USE_BLENDER=1
BLENDER_WIDTH=960
BLENDER_SAMPLES=16
```

메모리 2GB 서버에서 기본 크기(1600px, 64샘플)로 돌리면 메모리가 모자라 중간에 꺼진다. 위처럼 줄여서 쓴다.
렌더는 한 번에 하나만 돌고, 도는 동안에도 웹 요청이 밀리지 않게 우선순위를 낮춰 실행한다.

## 2. 웹 (Cloudflare Pages)

GitHub 연결로 만들었고, main에 push하면 자동 배포된다.

| 설정 | 값 |
|---|---|
| 프로젝트 이름 | `housetwin` |
| Production branch | `main` |
| Framework preset | 없음(None) |
| Root directory | (비움, 저장소 루트) |
| Build command | `bash deploy/pages-build.sh` |
| Build output directory | `apps/web` |
| 환경변수 | `API_BASE` = `https://api-housetwin.13-238-79-150.sslip.io` |

`pages-build.sh`는 `API_BASE`를 `apps/web/config.js`에 적기만 한다. 환경변수를 바꾸면 다시 배포해야 적용된다.

## 3. Google 로그인(OAuth) 준비

아직 로그인 기능은 없다. 나중에 붙일 때 Google Cloud 콘솔에 넣을 값:

**OAuth 동의 화면 (Google 인증 플랫폼 → 브랜딩)**

| 항목 | 값 |
|---|---|
| 앱 이름 | LG HouseTwin |
| 앱 홈페이지 | https://housetwin.pages.dev |
| 승인된 도메인 | `housetwin.pages.dev`, `13-238-79-150.sslip.io` |
| 범위 | `openid`, `email`, `profile` |
| 게시 상태 | 테스트 (테스트 사용자에 팀원 Gmail 추가) |

**OAuth 클라이언트 ID (클라이언트 → 웹 애플리케이션)**

| 항목 | 값 |
|---|---|
| 승인된 자바스크립트 원본 | `https://housetwin.pages.dev`, `http://localhost:8010` |
| 승인된 리디렉션 URI | `https://api-housetwin.13-238-79-150.sslip.io/api/auth/google/callback`, `http://localhost:8010/api/auth/google/callback` |

- 로그인 처리는 API 서버가 한다(코드 교환은 서버에서). 그래서 리디렉션 URI는 api 주소다.
- 클라이언트 보안 비밀은 서버 `.env`(`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)에만 둔다. 웹 코드나 GitHub에 올리지 않는다.
- 웹(pages.dev)과 API(sslip.io)는 서로 다른 사이트다. 로그인 쿠키를 쓰면 `SameSite=None; Secure`가 필요하고, 브라우저가 제3자 쿠키를 막을 수 있으니 토큰을 응답 본문으로 받아 `Authorization` 헤더로 보내는 쪽이 안전하다(CORS에 이미 허용돼 있음).
- 테스트 상태에서는 등록한 테스트 사용자(최대 100명)만 로그인된다. 정식 게시(누구나 로그인)하려면 개인정보처리방침과 도메인 소유 확인이 필요해서, 그때는 우리 도메인을 사서 옮긴다.
- 이 OAuth는 고객이 Google 계정으로 로그인하는 용도다. 서버가 팀원 구독 계정으로 LLM을 부르는 데 쓰지 않는다(기획 §7).
