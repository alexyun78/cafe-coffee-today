# Cloudflare 마이그레이션 계획 — iwinv(유료) → Cloudflare(무료)

작성: 2026-07-13 · 상태: **계획 확정, Phase 0 착수 전**

## 배경 / 목표

- 현재 iwinv VPS(49.247.207.115, 유료)에서 Flask + SQLite + systemd로 운영 중.
- 하루 사용자 100명 미만 → Cloudflare 무료 티어로 충분 (Workers Free 10만 req/일, D1 Free 500만 read/일 — 여유 100배 이상).
- 목표: **월 비용 0원**, 기능 동일 유지, 이후 iwinv 해지.

## 확정된 결정 (2026-07-13)

| 항목 | 결정 |
|---|---|
| 백엔드 포팅 | **TypeScript + Hono** 재작성 (Python Workers 베타는 배제) |
| 도메인 | **92cafe.co.kr** (`.env`의 `SERVICE_DOMAIN`) — 신규가 아니라 **이미 운영 중**: NS=ns1.iwinv.kr, A→49.247.207.115, 서버 nginx+HTTPS가 roastery.html 서빙 (2026-07-13 확인, CLAUDE.md 미기재였음). 네임서버만 Cloudflare로 이전 |
| 카드 PNG (PIL 렌더) | **일단 보류** — `/api/coffee/<id>/card-token`, `card.png` 미이식. admin.html 카드 다운로드 버튼 숨김. 추후 클라이언트 canvas로 재구현 검토 |

> `.env` 신규 키 (2026-07-13): `CLOUDFLARE_EMAIL` / `CLOUDFLARE_PASSWORD` (대시보드 로그인 — CLI 자동화엔 못 씀), `SERVICE_DOMAIN`. Phase 0에서 `CLOUDFLARE_API_TOKEN` 추가 예정.

## 아키텍처 매핑

| 현재 (iwinv) | 이후 (Cloudflare + GitHub) |
|---|---|
| Flask + gunicorn :3002 | Workers (TS/Hono) — `/api/*` 는 Worker, 나머지는 Static Assets |
| SQLite `data/coffee.db` | **D1** (SQLite 호환 — 스키마 거의 그대로) |
| PIN 세션 (Flask 메모리 세션) | HMAC 서명 쿠키 (WebCrypto, 만료 12h). `FLASK_SECRET` 재사용 |
| git push → 60초 deploy 타이머 | git push → **Workers Builds** 자동 배포 (SSH/systemd 소멸) |
| `cafe-coffee-release.timer` 20:30 KST | **GitHub Actions cron** `30 11 * * *` — `release_insight.py` 그대로 실행 → commit/push → 자동 재배포 |
| `cafe-coffee-nearby.timer` 07:30 KST | GitHub Actions cron `30 22 * * *` — `collect_nearby.py` 실행 후 Worker 보호 엔드포인트로 전송 (⚠️ 리스크 1순위, 아래) |
| `/api/nearby/refresh` (서버 백그라운드 스레드) | Worker → GitHub `workflow_dispatch` API 호출로 수집 워크플로 트리거 |
| APK WebView → `http://49.247.207.115:3002` | WebView → `https://<커스텀도메인>` (version.json 증가로 업데이트 배너) |
| APK 파일 SCP → `static/downloads/` | **GitHub Releases** 업로드, `/apk` 페이지는 최신 릴리스 링크 |

## Phase 0 — 준비 (0.5일) — 🔄 진행 중 (2026-07-13)

> **진행 현황 (2026-07-13 밤)**:
> - ✅ Cloudflare 계정 이메일 인증 완료 (가입 후 6일간 미인증 상태였음 — 토큰 생성 실패의 근본 원인)
> - ✅ API 토큰 발급 (`Edit Cloudflare Workers` 템플릿 + D1:Edit + Zone:Edit) → `.env`의 `CLOUDFLARE_API_TOKEN`, verify=active 확인
> - ✅ 92cafe.co.kr 존 생성 (API 경유 — 대시보드 Add-a-site UI가 멈춰서 우회). **zone_id=`f73059debc9807dc62cd41633011e9d1`**, status=pending
> - ✅ 배정 네임서버: **`arya.ns.cloudflare.com` / `margo.ns.cloudflare.com`** ← iwinv 도메인 관리에서 이걸로 변경
> - ✅ DNS 레코드 복제 완료: A @ / A www → 49.247.207.115 (DNS-only, TTL 300)
> - ⏳ **iwinv 네임서버 변경 (유일하게 남은 사용자 작업)**: iwinv 도메인 관리 → 네임서버를 `arya.ns.cloudflare.com` / `margo.ns.cloudflare.com` 으로 변경. 전파 후 존이 pending→active 되면 Phase 0 완료
> - 참고: 대시보드 Add-a-site UI가 이 계정에서 무한 스피너로 먹통 — 존/레코드는 API로 처리했음. 이후 존 관련 작업도 API 권장

1. **네임서버 이전 (무중단, 가장 먼저 시작 — 전파 최대 24h)**: Cloudflare 대시보드에 92cafe.co.kr 추가 → 기존 DNS 레코드 자동 스캔 확인 (A→49.247.207.115 **그대로 유지**, 일단 DNS-only 회색 구름) → iwinv 도메인 관리에서 NS를 Cloudflare 지정 값으로 변경. 트래픽은 계속 iwinv 서버로 가므로 서비스 영향 0.
   - ⚠️ **도메인 등록기관 확인**: 등록 자체가 iwinv라면 **서버 해지 시 도메인 등록은 유지**해야 함 (등록비는 별도 소액). Cloudflare Registrar는 .co.kr 미지원 — 원하면 가비아 등 국내 등록기관으로 기관 이전.
2. API 토큰 발급: dash → My Profile → API Tokens → "Edit Cloudflare Workers" 템플릿. `.env`에 `CLOUDFLARE_API_TOKEN=` 추가 (대시보드 로그인 정보로는 wrangler 자동화 불가).
3. `worker/` 디렉터리에 Hono 프로젝트 생성 (`npm create hono@latest`), `wrangler.jsonc`에 D1 바인딩 + Static Assets(`run_worker_first: ["/api/*"]`) 구성.
4. GitHub repo ↔ Workers Builds 연동 (push 시 자동 배포).

## Phase 1 — DB 이관 (0.5일) — ✅ 완료 (2026-07-13)

- **D1 DB**: `cafe-coffee`, database_id=`89f4749f-7999-4410-8090-606b9ff1d90c`, 리전 APAC/ICN(서울)
- 절차: `migrate-remote.sh pull` → python `iterdump` 기반 커스텀 덤프 → `wrangler d1 execute --remote --file`
- **주의(재실행 시)**: ① sqlite3 `.dump` 그대로는 실패 — `BEGIN/COMMIT/PRAGMA`, `sqlite_sequence` 제거 필요 ② **FK 의존 순서로 INSERT 재배열 필수** (coffees가 green_beans 참조 — 원본 생성 순서대로면 "no such table" 에러) + `PRAGMA defer_foreign_keys=true` 선두 삽입 ③ D1은 compound SELECT(UNION) 항 수 제한 있음 — 검증 쿼리는 테이블별로
- **검증 완료**: 17개 테이블 전 건수 일치 (coffees 208 · green_beans 69 · purchases 91 · roasting_logs 712 · nearby_reviews 1,346 · visits 4,998 등) + 한글 텍스트 바이트 일치 확인
- 컷오버 밤에 같은 절차로 **최종 재임포트** 필요 (병행 기간 중 서버 쓰기 반영)

## Phase 2 — API 포팅 — ✅ 완료 (2026-07-13 밤)

> **프리뷰 URL = https://cafe-coffee.92cafe.workers.dev** · [worker/](../worker/) (Hono + TS, 6모듈)
> - ✅ **전 엔드포인트(~60개) 포팅 + 실서비스 대조 검증 통과** — 조회 16종 exact-match
>   (유일한 차이 = Python float 표기 `20.0` vs JS `20`, JSON 파싱 후 동일값이라 무영향)
> - ✅ 인증: Flask 세션 → HMAC 서명 쿠키 `adm`(WebCrypto, 7일) + Bearer 토큰(APK) 병행.
>   `SESSION_SECRET`=구 FLASK_SECRET 동일 값 → feedback ip_hash 연속성 유지.
>   PIN 레이트리밋(D1 pin_attempts) 동일 동작 확인 (locked/attempts_left)
> - ✅ 쓰기 왕복 검증: coffee POST→PUT→DELETE, supplier CRUD (D1에서, 흔적 제거)
> - ✅ visits 방문 집계 미들웨어(쿠키 vid·봇 제외·waitUntil 비동기), suyochek RSS(Workers Cache 10분),
>   insights, app-version(version.json 번들 import), ADMIN_ALIAS_PATH 대응
> - ✅ 페이지 렌더링 브라우저 확인 (/today 데이터·휴무팝업·디카페인 배너, / 로스터리, /insight 오늘 글)
> - 미이식(결정대로): 카드 PNG(501), /downloads(404 — Phase 4에서 GitHub Releases)
> - ⚠️ 시크릿(설정 완료): `wrangler secret put` — ADMIN_PIN, SESSION_SECRET. 추가 예정: GITHUB_DISPATCH_TOKEN(주변 수집 수동 트리거용, 선택)
> - ⚠️ 재배포: `cd worker && npx wrangler deploy` (env CLOUDFLARE_API_TOKEN/CLOUDFLARE_ACCOUNT_ID)
> - ⚠️ D1 재임포트 시 Phase 1 주의사항 + **덤프 파일은 `newline='\n'`으로 쓸 것** (Windows 텍스트모드 \r\n 오염 — 실제 발생, 재임포트로 복구)

- `app.py`(1,356줄) 약 40개 엔드포인트 + `db.py`(2,306줄) CRUD를 Hono로 1:1 포팅.
- **불변 조건 (프런트 무수정을 위해)**:
  - 한글 JSON 키 유지 (`커피`, `로스터리`, `로스팅` `{start,end}` 객체 등)
  - `{success, items/error}` 응답 형태, HTTP 상태 코드 동일
  - 재고 computed query (`SUM(purchases) - SUM(roasting)/1000 + stock_adjustment_kg`) 동일
- 인증: `/api/admin/verify` → HMAC 쿠키 발급, `requirePin` 미들웨어. 로그아웃 = 쿠키 삭제.
- `rev N · <hash>` 빌드 표시: git 명령 불가 → Workers Builds 환경변수(`WORKERS_CI_COMMIT_SHA`)로 대체.
- 미이식(보류): `card-token` / `card.png` (501 반환), admin.html 버튼 숨김.
- 정적 자산: `index.html`, `static/`(22MB, 인사이트 87건 포함) → Static Assets. 파일당 25MiB 제한 내 확인.
- **페이지 라우트 재현** (app.py 1096~1131, CLAUDE.md 기재와 다름 — 실측 기준):
  - `/` → `static/roastery.html` (도메인 루트 = 로스터리 홈)
  - `/today` → `index.html` (오늘의커피 + 누가쏠까 탭)
  - `/admin` + `ADMIN_ALIAS_PATH` 비공개 별칭 (서버 .env에만 존재 — 이전 시 Worker 환경변수로) → `static/admin.html`
  - `/roastery`, `/apk`, `/insight(...)`, `/game(...)` 등 — app.py 115줄 정규식 참고

## Phase 3 — 크론 이전 — 🔄 구축 완료, 실행 검증 중 (2026-07-13 밤)

1. ✅ [.github/workflows/insight-release.yml](../.github/workflows/insight-release.yml) — cron `40 11 * * *`(=**20:40 KST** — 서버 20:30 릴리스보다 늦게 잡아 병행 기간 멱등 skip): `release_insight.py` → commit/push(`GITHUB_TOKEN`). 컷오버 후 서버 release.timer disable → 이게 1차 발행 경로.
2. ✅ [.github/workflows/nearby-collect.yml](../.github/workflows/nearby-collect.yml) — cron `30 22 * * *`(=07:30 KST) + workflow_dispatch: [scripts/collect_nearby_d1.py](../scripts/collect_nearby_d1.py)가 collect_nearby.py 파싱 재사용 → `POST /api/nearby/ingest`(Bearer, ADMIN_PIN으로 verify). GH Secrets 설정 완료(ADMIN_PIN·NAVER_CLIENT_ID/SECRET).
   - ✅ **리스크 1순위 해소 (2026-07-13 실측)**: 네이버가 GitHub Actions IP를 차단하지 않음 — 30/30곳 수집 성공, 표본 528건·별점·키워드·블로그검색 전부 정상, D1 인제스트 589문 적용.
3. ✅ [.github/workflows/deploy-worker.yml](../.github/workflows/deploy-worker.yml) — push(worker/·static/·index.html 변경) 시 `wrangler deploy` 자동 실행. 구 서버 60초 deploy 타이머 대응 — **인사이트 발행이 사이트에 반영되는 경로**. GH Secret `CLOUDFLARE_API_TOKEN` 설정 완료, 실행 검증 완료.
4. ⏳ 관리자 "⟳ 리뷰 수집" 버튼: Worker `/api/nearby/refresh`가 GitHub `workflow_dispatch` 호출하도록 구현됨 — `GITHUB_DISPATCH_TOKEN`(fine-grained PAT, actions:write) Worker secret만 추가하면 활성.

## Phase 4 — APK 전환 — ✅ 적용 (2026-07-13 밤, v1.0.7 빌드 중)

1. ✅ `server.url` → `https://92cafe.co.kr/today`, cleartext=false. **컷오버 전에도 안전** — 도메인이 현재 iwinv nginx(HTTPS)를 가리키므로 새 APK는 즉시 동작하고, DNS 컷오버 시 자동으로 Worker로 넘어감(무중단).
2. ✅ version.json 1.0.6→1.0.7 ("서버 이전" 공지) → 기존 사용자 업데이트 배너.
3. ✅ build-apk.yml: 서버 SCP 유지(브리지 기간) + **GitHub Release `apk-latest` 업로드 추가**. Worker `/downloads/*`·`/static/downloads/*` → 릴리스로 302 리다이렉트.
4. ⚠️ 잔여: game.apk(누가쏠까 단독 앱)는 릴리스에 없음 — 서버 static/downloads에만 존재. 컷오버 전 서버에서 받아 `gh release upload apk-latest game.apk` 필요 (또는 game-apk 페이지 은퇴).

> **참고 (2026-07-13)**: 네임서버 전파 완료 — **존 status=active**, 92cafe.co.kr DNS는 이제 Cloudflare가 서비스(A레코드는 iwinv 서버 유지 → 무중단).

## Phase 5 — 병행 운영 → 컷오버 (실작업 0.5일 + 관찰 1~2주)

1. **병행 검증**: 도메인 A레코드는 iwinv를 계속 가리키는 동안, Worker는 `*.workers.dev` 프리뷰 URL로 전 기능 검증 — 공개 페이지/게임, admin 4탭 CRUD 전체, 인사이트 목록·상세, 릴리스 1회 실발행, 수집 1회, 새 APK 설치 동작.
2. **컷오버 밤 (DNS 레벨이라 즉시·무중단·즉시 롤백 가능)**: iwinv admin 쓰기 중단 → 최종 `dump → D1 재임포트` → Cloudflare DNS에서 92cafe.co.kr을 Worker 커스텀 도메인으로 전환 (A레코드 제거) → APK 릴리스 공지. 문제 시 A레코드 복원으로 즉시 원복.
3. **구 APK 브리지**: 구 APK는 도메인이 아니라 `http://49.247.207.115:3002`(IP)를 직접 보므로 DNS 전환의 영향 밖. iwinv를 즉시 끄지 말고 `IP:3002/* → https://92cafe.co.kr` **301 리다이렉트 전용 초경량 모드**로 마지막 결제 주기 동안 유지. WebView는 리다이렉트를 따라가므로 미업데이트 사용자도 무중단.
4. 관찰 1~2주 → systemd 타이머 전체 disable → **iwinv 해지**.
5. CLAUDE.md 전면 갱신 (배포/서버/크론 섹션 재작성 — iwinv 관련 내용 제거).

## 리스크 및 대응

| # | 리스크 | 대응 |
|---|---|---|
| 1 | 네이버 SSR 스크래핑이 GitHub Actions IP에서 차단 | Phase 3에서 선 테스트. 실패 시 로컬 PC 스케줄러 폴백 |
| 2 | 병행 기간 중 admin 쓰기 이원화 | 병행 중 쓰기는 iwinv에만, 컷오버 밤 최종 재임포트 |
| 3 | 구 APK 사용자 잔존 | 301 리다이렉트 브리지 + 업데이트 배너 |
| 4 | 포팅 물량 (app.py+db.py ≈ 3,700줄) | CRUD 반복이라 기계적. 엔드포인트별 응답 스냅숏 대조 테스트 |
| 5 | D1 미지원 SQL 문법 (극히 일부) | dump 임포트 시 발견 즉시 수정 — 스키마는 표준 SQLite라 위험 낮음 |

## 롤백

- 컷오버 후 문제 발생 시: iwinv 서비스 재기동(해지 전이므로 가능) + APK는 구버전이 그대로 IP를 봄 → 즉시 원복. Cloudflare 쪽은 도메인 라우트만 제거.

## 총 소요 예상

실작업 **5~7일** + 병행 관찰 1~2주 + 브리지 유지 ~1개월 후 해지.
