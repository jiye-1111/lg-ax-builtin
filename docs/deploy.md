# 서버 배포 (LG HouseTwin)

수업 자료(클라우드 01~10교시) 방식대로 올린다. 웹 화면은 Cloudflare Pages, API는 AWS Lightsail, 주소는 axworks.site 서브도메인.

| 구분 | 어디에 | 주소 |
|---|---|---|
| 웹 (apps/web, 빌드 없는 정적 SPA) | Cloudflare Pages `housetwin` | https://housetwin.axworks.site (임시: https://housetwin.pages.dev) |
| API (FastAPI) | Lightsail `AX_PRACTICE` (시드니, 2 GB) 고정 IP 13.238.79.150 | https://api-housetwin.axworks.site |
| HTTPS | Lightsail 안 Caddy → 127.0.0.1:8000 | 인증서 자동 발급·갱신 |

팀 PC에서 `start.bat`으로 돌리는 방식은 그대로다. `apps/web/config.js`의 `LGB_API`가 비어 있으면 웹과 API가 같은 서버에서 돈다.

## 1. API 서버 (Lightsail)

방화벽: 22(내 IP만), 80, 443. 8000은 열지 않는다 (Caddy만 안에서 부른다).

처음 한 번:

```bash
curl -fsSL https://raw.githubusercontent.com/jiye-1111/lg-ax-builtin/main/deploy/setup-server.sh -o s.sh
bash s.sh api-housetwin.axworks.site https://housetwin.axworks.site,https://housetwin.pages.dev
```

`setup-server.sh`가 하는 일: git·Caddy·uv 설치 → `~/apps/lg-ax-builtin`에 clone → `uv sync` → `.env` 생성(chmod 600) → systemd `lgb-api` 등록 → `/etc/caddy/Caddyfile` 적용.

서버 `.env`에서 배포용으로 바뀌는 값:

| 키 | 값 |
|---|---|
| `API_HOST` / `API_PORT` | `127.0.0.1` / `8000` |
| `PUBLIC_BASE_URL` | `https://housetwin.axworks.site` (고객 링크에 쓰임) |
| `CORS_ORIGINS` | `https://housetwin.axworks.site,https://housetwin.pages.dev` |
| `USE_BLENDER` | `0` (서버엔 Blender 없음, 렌더는 Python 폴백) |

MCP HTTP는 서버에서 열지 않는다.

코드를 고친 뒤 반영 (10교시):

```bash
bash ~/apps/lg-ax-builtin/deploy/update-server.sh
```

상태·로그: `sudo systemctl status lgb-api`, `journalctl -u lgb-api -n 100`, `journalctl -u caddy -n 50`.

## 2. 웹 (Cloudflare Pages)

GitHub 연결로 만들고, main에 push하면 자동 배포된다.

| 설정 | 값 |
|---|---|
| 프로젝트 이름 | `housetwin` |
| Production branch | `main` |
| Framework preset | 없음(None) |
| Root directory | (비움, 저장소 루트) |
| Build command | `bash deploy/pages-build.sh` |
| Build output directory | `apps/web` |
| 환경변수 | `API_BASE` = `https://api-housetwin.axworks.site` |

`pages-build.sh`는 `API_BASE`를 `apps/web/config.js`에 적기만 한다. 환경변수를 바꾸면 Deployments에서 다시 배포해야 적용된다.

사용자 정의 도메인: Pages 프로젝트 → Custom domains → `housetwin.axworks.site`.

## 3. 도메인 (08교시)

axworks.site DNS는 강사님이 등록한다. 노션 08교시 표에 이름·프로젝트명(`housetwin`)·pages.dev 주소·고정 IP(13.238.79.150)를 적는다.

- `api-housetwin.axworks.site` → A 레코드 13.238.79.150
- `housetwin.axworks.site` → Cloudflare Pages 사용자 도메인

확인: `nslookup api-housetwin.axworks.site`, 브라우저에서 https://api-housetwin.axworks.site/api/health

## 4. Google 로그인(OAuth) 준비

아직 로그인 기능은 없다. 나중에 붙일 때 Google Cloud 콘솔에 넣을 값:

**OAuth 동의 화면 (Google 인증 플랫폼 → 브랜딩)**

| 항목 | 값 |
|---|---|
| 앱 이름 | LG HouseTwin |
| 앱 홈페이지 | https://housetwin.axworks.site |
| 승인된 도메인 | `axworks.site` |
| 범위 | `openid`, `email`, `profile` |
| 게시 상태 | 테스트 (테스트 사용자에 팀원 Gmail 추가) |

**OAuth 클라이언트 ID (클라이언트 → 웹 애플리케이션)**

| 항목 | 값 |
|---|---|
| 승인된 자바스크립트 원본 | `https://housetwin.axworks.site`, `https://housetwin.pages.dev`, `http://localhost:8010` |
| 승인된 리디렉션 URI | `https://api-housetwin.axworks.site/api/auth/google/callback`, `http://localhost:8010/api/auth/google/callback` |

- 로그인 처리는 API 서버가 한다(코드 교환은 서버에서). 그래서 리디렉션 URI는 api- 주소다.
- 클라이언트 보안 비밀은 서버 `.env`(`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)에만 둔다. 웹 코드나 GitHub에 올리지 않는다.
- 웹(housetwin.axworks.site)과 API(api-housetwin.axworks.site)는 같은 사이트(axworks.site)라서 로그인 쿠키는 `SameSite=Lax`로 충분하다.
- 테스트 상태에서는 등록한 테스트 사용자(최대 100명)만 로그인된다. 정식 게시(누구나 로그인)하려면 개인정보처리방침 페이지가 필요하고, `axworks.site` 소유 확인(Search Console)은 도메인 주인(강사님)만 할 수 있다. 정식 게시가 필요하면 우리 도메인을 따로 사는 게 낫다.
- 이 OAuth는 고객이 Google 계정으로 로그인하는 용도다. 서버가 팀원 구독 계정으로 LLM을 부르는 데 쓰지 않는다(기획 §7).
