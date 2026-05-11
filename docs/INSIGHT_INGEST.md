# Coffee Insight 자동 게시 운영 가이드

매일 07:00 KST 에 `Coffee-Daily-Digest` 클라우드 루틴이 Drive 에 한 편의 인사이트 JSON 을 올리면, 30분 뒤(07:30 KST = 22:30 UTC) GitHub Actions 워커 `Ingest Coffee Insights` 가 자동으로:

1. Drive 에서 새 `cafe-insight YYYY-MM-DD — …` 파일을 찾아 본문(JSON)을 다운로드
2. OA fulltext 가 있으면 PDF 에서 figure 를 추출하여 PNG 로 저장
3. Jinja2 템플릿으로 standalone HTML 을 생성
4. `static/insights/<id>.json`, `static/insights/<id>.html`, `static/insights/index.json`, `static/img/insights/articles/<id>/*` 을 repo 에 커밋·푸시
5. 기존 60초 deploy timer 가 서버에 배포 → 홈페이지에 노출

이 문서는 그 파이프라인이 처음 동작하기 위한 일회성 세팅을 정리한다.

---

## 0. 사전 확인

- 카페 측 코드: 이 PR 또는 이후 머지 시점에 `static/insights/`, `static/img/insights/`, `scripts/ingest_insights.py`, `.github/workflows/ingest-insights.yml` 가 main 에 들어와 있어야 한다.
- 발행자 측 코드: `D:\python\Coffee-Daily-Digest\docs\SCHEDULE_PROMPT.md` 의 8.5 단계 (sidecar JSON 저장) 가 반영되어야 한다.
- 시드 인사이트: `2026-05-11-peru-fermentation-starter-cultures` 가 이미 들어 있어 워크플로가 처음 도는 날에는 이 시드 이후의 새 sidecar 만 처리한다.

---

## 1. Google Cloud OAuth 클라이언트 만들기 (1회)

워커가 `alexyun@gmail.com` 의 Drive 를 읽기 위해 OAuth 가 필요하다. 보안 토큰을 영구 보관할 필요가 없으므로 **refresh token** 방식을 쓴다.

### 1-1. GCP 프로젝트 + Drive API 활성화

1. https://console.cloud.google.com/ 에 `alexyun@gmail.com` 으로 로그인.
2. **새 프로젝트** 생성. 이름 예: `coffee-insight-ingest`.
3. 좌측 **API 및 서비스 → 라이브러리** → `Google Drive API` 검색 → **사용** 클릭.

### 1-2. OAuth 동의 화면 설정

1. **API 및 서비스 → OAuth 동의 화면**
2. User Type = **External** 선택 → 만들기.
3. 앱 이름 `coffee-insight-ingest`, 사용자 지원 이메일 = `alexyun@gmail.com`, 개발자 이메일 = `alexyun@gmail.com`. 그 외는 비워두고 저장.
4. **범위(Scopes)** → 추가/삭제 → `https://www.googleapis.com/auth/drive.readonly` 만 선택 → 저장.
5. **테스트 사용자** → `alexyun@gmail.com` 추가 → 저장.
6. (게시 상태는 `테스트` 로 유지해도 무방. 동일 계정에서만 토큰 발급할 거라 production 승인은 불필요.)

### 1-3. OAuth 클라이언트 ID 발급

1. **API 및 서비스 → 사용자 인증 정보 → 사용자 인증 정보 만들기 → OAuth 클라이언트 ID**
2. 애플리케이션 유형 = **데스크톱 앱**. 이름 `coffee-insight-cli`. → 만들기.
3. **클라이언트 ID** 와 **클라이언트 보안 비밀** 메모. 이후 단계에서 사용.

### 1-4. Refresh token 발급 (로컬 1회)

PowerShell 또는 bash 에서 한 번만 실행. 브라우저가 열리며 동의 화면 후 콘솔에 refresh token 이 찍힌다.

```bash
pip install google-auth google-auth-oauthlib
python -c "
from google_auth_oauthlib.flow import InstalledAppFlow
flow = InstalledAppFlow.from_client_config(
    {
        'installed': {
            'client_id': '여기에 클라이언트ID',
            'client_secret': '여기에 클라이언트보안비밀',
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': ['http://localhost'],
        }
    },
    scopes=['https://www.googleapis.com/auth/drive.readonly'],
)
creds = flow.run_local_server(port=0)
print('REFRESH_TOKEN =', creds.refresh_token)
"
```

브라우저에서 `alexyun@gmail.com` 으로 로그인 → "이 앱은 Google 에서 인증되지 않음" 경고가 뜨면 `고급 → 안전하지 않음(이동)` 으로 진행 (테스트 사용자 본인 계정이라 안전). 콘솔에 찍힌 `REFRESH_TOKEN = 1//…` 값을 메모.

### 1-5. (선택) 1회 점검

같은 셸에서 토큰이 동작하는지 검증:

```bash
curl -s -X POST https://oauth2.googleapis.com/token \
  -d "client_id=<CLIENT_ID>" \
  -d "client_secret=<CLIENT_SECRET>" \
  -d "refresh_token=<REFRESH_TOKEN>" \
  -d "grant_type=refresh_token"
```

`{"access_token": "ya29....", "expires_in": 3599, ...}` 가 돌아오면 OK.

---

## 2. GitHub Secrets 등록

1. https://github.com/alexyun78/cafe-coffee-today (또는 실제 repo URL) → **Settings → Secrets and variables → Actions → New repository secret**
2. 다음 3개를 그대로 추가:

| 이름 | 값 |
|---|---|
| `GOOGLE_CLIENT_ID` | 1-3 의 클라이언트 ID |
| `GOOGLE_CLIENT_SECRET` | 1-3 의 클라이언트 보안 비밀 |
| `GOOGLE_REFRESH_TOKEN` | 1-4 에서 발급된 토큰 |

> `GITHUB_TOKEN` 은 Actions 가 자동 발급하므로 추가하지 않는다. 워크플로의 `permissions.contents: write` 만 켜져 있으면 충분.

---

## 3. /schedule 클라우드 루틴 업데이트

`SCHEDULE_PROMPT.md` 의 8.5 단계가 추가되었으므로, 현재 운영 중인 `/schedule` 루틴을 갱신해야 한다.

1. Claude Code 대화창에서 `/schedule list` → `coffee-daily` 루틴의 ID 확인.
2. `/schedule update <ID>` 또는 스킬이 안내하는 update 명령 실행.
3. 새 프롬프트 = `SCHEDULE_PROMPT.md` 의 `---PROMPT_BEGIN---` ~ `---PROMPT_END---` 사이 본문 전체. `<<TG_BOT_TOKEN>>`, `<<TG_CHAT_ID>>` placeholder 는 `secrets.local.md` 의 실제 값으로 치환.
4. 업데이트 후 `/schedule list` 로 정상 등록 확인.

> 업데이트 전에 한 번 드라이런(새 대화에서 프롬프트 본문 붙여넣고 즉시 실행)을 돌려, Drive 에 `cafe-insight <오늘> — <slug>` 파일이 정상 생성되는지 확인한다.

---

## 4. 첫 동작 점검

다음 중 하나로 워크플로를 검증:

### 4-A. 수동 실행

GitHub repo → **Actions → Ingest Coffee Insights → Run workflow** (main 브랜치).

성공 시 로그에 `Drive 후보 파일: N개`, `신규 인사이트: 2026-…` 가 찍히고, 마지막에 `chore(insights): ingest daily coffee insight` 커밋이 생긴다.

### 4-B. 다음 날 새벽 자동 실행

`30 22 * * *` (UTC) 에 자동 트리거. KST 로 07:30. 결과는 동일하게 commit 한 줄 + 카페 홈에 새 카드 노출.

---

## 5. 실패 처리

| 증상 | 점검 포인트 |
|---|---|
| `access token 획득 실패` | `GOOGLE_REFRESH_TOKEN` 만료/회수 가능. 1-4 재실행 후 secret 갱신. |
| `Drive 검색 실패: 403` | 동의 화면 범위에 `drive.readonly` 가 있는지, 테스트 사용자에 `alexyun@gmail.com` 이 있는지 확인. |
| `JSON 파싱 실패` | sidecar 본문 첫 글자가 `{` 가 아닐 가능성. /schedule 프롬프트 8.5 단계 재검토. |
| `figure 추출 생략` | OA PDF 가 없거나 PyMuPDF 가 PDF 파싱 실패. `source_basis: abstract_only` 면 정상. |
| `변경 없음 — commit skip` | 새 sidecar 가 없거나, id 가 이미 index 에 있음. 정상. |
| Actions 가 push 실패 | repo Settings → Actions → General → Workflow permissions = **Read and write** 인지 확인. |

---

## 6. 카테고리 → hero 이미지 매핑 추가/변경

`scripts/ingest_insights.py` 의 `CATEGORY_HERO` 딕셔너리. SVG 파일은 `static/img/insights/hero/` 에 추가하고 매핑만 갱신. 매핑이 없으면 `default.svg` 가 쓰인다.

---

## 7. 관련 파일 맵

| 파일 | 역할 |
|---|---|
| `static/insights/index.json` | 게시된 인사이트 인덱스 (날짜 내림차순) |
| `static/insights/<id>.json` | 단일 인사이트 메타데이터 (워커 출력) |
| `static/insights/<id>.html` | 단일 인사이트 standalone 페이지 (워커 출력) |
| `static/img/insights/hero/*.svg` | 10 카테고리 + default 히어로 이미지 |
| `static/img/insights/articles/<id>/*.png` | PDF 에서 추출된 figure (있을 때만) |
| `static/insight-list.html` | `/insight` 리스트 페이지 (정적, JS 가 `/api/insights` 호출) |
| `scripts/ingest_insights.py` | 워커 본체 |
| `scripts/insight_template.html.j2` | standalone HTML Jinja2 템플릿 |
| `.github/workflows/ingest-insights.yml` | 매일 22:30 UTC cron + 수동 실행 |
| `app.py` `/insight`, `/insight/<id>`, `/api/insights` | 카페 Flask 라우트 |
