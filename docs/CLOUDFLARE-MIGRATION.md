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
| 도메인 | **보유 커스텀 도메인** 연결 (도메인명 TBD — Phase 0에서 확정, 네임서버를 Cloudflare로 이전) |
| 카드 PNG (PIL 렌더) | **일단 보류** — `/api/coffee/<id>/card-token`, `card.png` 미이식. admin.html 카드 다운로드 버튼 숨김. 추후 클라이언트 canvas로 재구현 검토 |

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

## Phase 0 — 준비 (0.5일)

1. 도메인명 확정, Cloudflare 대시보드에 사이트 추가 → 등록기관에서 네임서버 변경 (**전파 최대 24h — 가장 먼저 시작**).
2. API 토큰 발급: dash → My Profile → API Tokens → "Edit Cloudflare Workers" 템플릿. `.env`에 `CLOUDFLARE_API_TOKEN=` 추가 (대시보드 로그인 정보로는 wrangler 자동화 불가).
3. `worker/` 디렉터리에 Hono 프로젝트 생성 (`npm create hono@latest`), `wrangler.jsonc`에 D1 바인딩 + Static Assets(`run_worker_first: ["/api/*"]`) 구성.
4. GitHub repo ↔ Workers Builds 연동 (push 시 자동 배포).

## Phase 1 — DB 이관 (0.5일)

```bash
bash scripts/migrate-remote.sh pull            # 서버 최신 DB 로컬로
sqlite3 data/coffee.db .dump > /tmp/dump.sql   # PRAGMA/트랜잭션 문 정리 필요할 수 있음
wrangler d1 create cafe-coffee
wrangler d1 execute cafe-coffee --remote --file=/tmp/dump.sql
```

- `seed_green_beans.sql` / `seed_nearby_shops.sql` 은 dump에 데이터가 포함되므로 별도 실행 불필요 (init_schema 시드 로직은 이식 안 함).
- 검증: 건수 대조 — coffees / green_beans(44) / purchases(54+) / roasting_logs(202+) / nearby_*.

## Phase 2 — API 포팅 (2~4일, 최대 공수)

- `app.py`(1,356줄) 약 40개 엔드포인트 + `db.py`(2,306줄) CRUD를 Hono로 1:1 포팅.
- **불변 조건 (프런트 무수정을 위해)**:
  - 한글 JSON 키 유지 (`커피`, `로스터리`, `로스팅` `{start,end}` 객체 등)
  - `{success, items/error}` 응답 형태, HTTP 상태 코드 동일
  - 재고 computed query (`SUM(purchases) - SUM(roasting)/1000 + stock_adjustment_kg`) 동일
- 인증: `/api/admin/verify` → HMAC 쿠키 발급, `requirePin` 미들웨어. 로그아웃 = 쿠키 삭제.
- `rev N · <hash>` 빌드 표시: git 명령 불가 → Workers Builds 환경변수(`WORKERS_CI_COMMIT_SHA`)로 대체.
- 미이식(보류): `card-token` / `card.png` (501 반환), admin.html 버튼 숨김.
- 정적 자산: `index.html`, `static/`(22MB, 인사이트 87건 포함) → Static Assets. 파일당 25MiB 제한 내 확인.

## Phase 3 — 크론 이전 (1일)

1. `.github/workflows/insight-release.yml` — cron `30 11 * * *`(=20:30 KST): checkout → `release_insight.py` → commit/push (`GITHUB_TOKEN` 사용, 서버 PAT 불필요) → push가 Workers Builds 재배포 유발. 멱등 로직 그대로라 중복 발행 없음.
2. `.github/workflows/nearby-collect.yml` — cron `30 22 * * *`(=07:30 KST):
   - **선 테스트 필수**: GH Actions에서 `collect_nearby.py --dry <place_id>` 1곳 → 네이버가 GitHub IP를 차단하는지 확인. **이것이 전체 계획의 리스크 1순위.**
   - 통과 시: 수집 결과를 Worker 보호 엔드포인트 `POST /api/nearby/ingest`(PIN 헤더)로 전송하는 어댑터 추가 (파이썬 수집 코드 재사용).
   - 차단 시 폴백: 로컬 PC 작업 스케줄러에서 실행 (기존 로컬 IP 429 이력 있으므로 간격 늘려서), 또는 수집 주기 축소.
3. 관리자 "⟳ 리뷰 수집" 버튼: Worker가 GitHub `workflow_dispatch` REST API 호출 (fine-grained PAT `actions:write` 1개 필요 → Worker secret).

## Phase 4 — APK 전환 (0.5일)

1. `cafe-coffee-apk/capacitor.config.json` `server.url` → `https://<커스텀도메인>` (cleartext 허용 설정 제거 가능).
2. `cafe-coffee-apk/www/version.json` 증가 → 기존 사용자에게 업데이트 배너.
3. `build-apk.yml`: SCP 스텝 제거 → GitHub Release에 APK 업로드. `/apk` 페이지는 최신 릴리스로 링크.

## Phase 5 — 병행 운영 → 컷오버 (실작업 0.5일 + 관찰 1~2주)

1. **병행 검증** (iwinv 유지 상태에서 새 도메인으로): 공개 페이지/게임, admin 4탭 CRUD 전체, 인사이트 목록·상세, 릴리스 1회 실발행, 수집 1회, 새 APK 설치 동작.
2. **컷오버 밤**: iwinv admin 쓰기 중단 → 최종 `dump → D1 재임포트` (병행 기간 중 쓰기 유실 방지) → APK 릴리스 공지.
3. **구 URL 브리지**: 구 APK가 IP URL을 보므로, iwinv를 즉시 끄지 말고 `http://49.247.207.115:3002/* → https://<도메인>` **301 리다이렉트 전용 초경량 모드**로 마지막 결제 주기 동안 유지. WebView는 리다이렉트를 따라가므로 미업데이트 사용자도 무중단.
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
