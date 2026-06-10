# CLAUDE.md — 오늘의 커피 (cafe-today-coffee)

이 프로젝트를 다룰 때 필요한 운영 정보와 자원 위치.
**비밀값(토큰/PIN/비밀번호)은 이 파일에 절대 기록하지 말 것.** 모두 `.env`에 있음.

---

## ⚡ 기본 워크플로 (질문하지 말 것)

소스 수정 요청을 처리한 뒤에는 **자동으로 commit + push** 한다. 사용자에게 "푸시할까요?", "빌드할까요?" 같은 확인을 받지 않는다.

- `git add <수정파일> && git commit -m "..."` → `git push origin main`
- 푸시 후 자동으로 실행되는 것:
  1. 서버(`49.247.207.115`)가 60초 내 `cafe-coffee-deploy.timer`로 `git pull` + `systemctl restart cafe-coffee` → 웹 반영
  2. GitHub Actions `Build APK` 워크플로가 자동으로 APK 빌드 + 서버 `static/downloads/`로 SCP → [/apk](http://49.247.207.115:3002/apk)에서 다운로드 가능
- 커밋 메시지는 기존 스타일(`feat:`, `fix:`, `chore:` + 한국어 요약) 유지.
- **예외**: 파괴적 작업(`git reset --hard`, `push --force`, 브랜치 삭제 등)은 여전히 사전 확인.
- `version.json`을 올릴지 여부는 사용자가 명시하지 않으면 올리지 않는다. WebView는 서버 URL을 로드하므로 일반 수정은 APK 재빌드 없이도 반영됨. (업데이트 배너를 띄워야 할 때만 `cafe-coffee-apk/www/version.json` 증가)
- **수정버전(빌드 rev)은 자동**: 관리자 헤더에 표시되는 `rev N · <hash>`는 `app.py`의 `_build_revision()`이 `git rev-list --count HEAD`로 산출. 어떤 수정이든 커밋 1개 = rev +1 이므로 별도 버전 관리 불필요. (`/api/app-version`의 `build` 필드)

---

## 프로젝트 개요

오늘 매장에서 내리는 커피를 기록·공개하는 앱. 2026-04 이전에는 Notion DB를 읽기 전용으로 조회했으나, 현재는 **자체 서버(49.247.207.115) + SQLite**로 이전되었다.

- **백엔드**: Flask + SQLite (`data/coffee.db`)
- **프런트(웹)**: [index.html](index.html) — 탭 기반 공개 페이지 (오늘의커피 + 누가쏠까?), [static/admin.html](static/admin.html) — PIN 게이트 관리 폼
- **APK**: [cafe-coffee-apk/](cafe-coffee-apk/) — Capacitor WebView 래퍼
- **배포**: 49.247.207.115 `/root/92cafe/cafe-today-coffee/`, systemd + 60s auto-pull 타이머
- **참고 프로젝트**: `D:/python/92cafe_pick` — systemd/배포/APK 패턴의 원본

---

## 비밀값과 자원 위치 (값은 `.env` 참고)

`.env`는 `.gitignore`에 포함되어 커밋되지 않는다. 서버에도 `.env`를 직접 배포해 사용한다.

| 키 | 용도 | 위치 |
|---|---|---|
| `NOTION_TOKEN` | Notion 마이그레이션(일회성). 이전 완료 후 제거 예정 | `.env` |
| `DATABASE_ID` | Notion DB ID (마이그레이션용) | `.env` |
| `ADMIN_PIN` | 관리 폼 접근 PIN | `.env` |
| `FLASK_SECRET` | 세션 쿠키 서명 키 | `.env` |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 네이버 검색 API (주변 가게 블로그 후기 수집) | `.env` (로컬+서버) |
| `ANTHROPIC_API_KEY` | 인사이트 자체 생성(`generate_insight.py`, Claude API) | `.env` (서버) |
| `INSIGHT_MODEL` | 자체 생성 모델 ID (선택, 기본 `claude-opus-4-8`) | `.env` (서버, 선택) |
| `HOST` | 배포 서버 IP | `.env` |
| `ID` | 배포 서버 SSH 사용자 | `.env` |
| `PASSWORD` | 배포 서버 SSH 비밀번호 | `.env` |

배포 서버 SSH 정보가 필요할 때는 `.env`를 읽어서 사용한다. **대화나 문서에 노출 금지**.

---

## 데이터베이스

- 파일: `data/coffee.db` (서버에서는 `/root/92cafe/cafe-today-coffee/data/coffee.db`)
- 스키마: [db.py](db.py) `init_schema()` 참고
- 백업: `data/backup/coffee-YYYYMMDD.db` (cron 또는 수동)
- `data/`는 `.gitignore` — 서버별 상태 독립

### coffees 테이블 컬럼 ↔ Notion 필드 ↔ API 키 매핑

| DB 컬럼 | Notion 속성 | API 응답 키 (한글 유지) |
|---|---|---|
| `name` | 커피 (title) | `커피` |
| `roastery` | 로스터리 (select/text) | `로스터리` |
| `roast_date` | 로스팅 (date) | `로스팅` (`{start, end}` 객체) |
| `process` | 프로세싱 (select) | `프로세싱` |
| `status` | 상태 (select) | `상태` |
| `cup_notes` | 컵노트 (rich_text) | `컵노트` |
| `comment` | 감상 (rich_text) | `감상` |
| `serve_date` | 제공일 (date) | `제공일` (`{start, end}` 객체) |
| `notion_id` | (페이지 ID) | 응답에 포함 안 됨 |

API 응답 JSON 키는 기존 Notion 기반 응답과 **완전히 동일**하게 유지되어, 기존 [index.html](index.html) 프런트엔드가 수정 없이 호환된다.

---

## API 엔드포인트

| 메서드 | 경로 | 설명 | 인증 |
|---|---|---|---|
| GET | `/` | 공개 페이지 (index.html) | 공개 |
| GET | `/admin` | 관리 폼 (admin.html) | 공개 HTML, JS에서 PIN 모달 |
| GET | `/api/coffee` | `{today, history}` 공개 조회 | 공개 |
| GET | `/api/coffee/all` | 전체 목록 (관리 화면용) | PIN |
| GET | `/api/coffee/<id>` | 단건 | PIN |
| POST | `/api/coffee` | 추가 | PIN |
| PUT | `/api/coffee/<id>` | 편집 | PIN |
| DELETE | `/api/coffee/<id>` | 삭제 | PIN |
| GET | `/api/suggestions` | 드롭다운용 DISTINCT 값 | PIN |
| POST | `/api/admin/verify` | PIN 검증 → 세션 발급 | 공개 |
| POST | `/api/admin/logout` | 세션 제거 | PIN |
| GET | `/apk` | 최신 APK 다운로드 페이지 | 공개 |

---

## 로컬 개발

```bash
cd d:/python/92/cafe-today-coffee
python -m venv .venv
.venv/Scripts/activate       # Windows (Bash: source .venv/Scripts/activate)
pip install -r requirements.txt
python app.py                # http://localhost:5000
```

- 최초 실행 시 `data/coffee.db`가 자동 생성됨.
- 관리 폼: `http://localhost:5000/admin` → PIN 입력.

### Notion → SQLite 일회성 이전

```bash
python migrate_notion.py
# 출력 예: "이전 완료: 이전 42건, 업데이트 0건, 건너뜀(이름 없음) 3건"
```

- 멱등 (같은 `notion_id`는 UPSERT).
- 실행 후 `/api/coffee`로 개수 확인.

---

## 서버 배포 (49.247.207.115)

**경로**: `/root/92cafe/cafe-today-coffee/`
**포트**: 3002 (pick가 3000 사용 중)
**서비스 이름**: `cafe-coffee.service`
**SSH 호스트키 지문**: `SHA256:Sx4sZ7vZuxxRTEabRiapTqjZuNx2Omi8VTezM9qIq+E`

### 로컬 스크립트 (Windows + plink)

모든 배포 조작은 프로젝트 루트에서 Git Bash로 실행. PuTTY(plink/pscp)가 PATH에 있어야 함.

- [scripts/bootstrap-server.sh](scripts/bootstrap-server.sh) — 최초 1회 서버 설치
- [scripts/deploy.sh](scripts/deploy.sh) — 강제 재배포 / 강제 재시작
- [scripts/logs.sh](scripts/logs.sh) — 서버 로그 조회
- [scripts/migrate-remote.sh](scripts/migrate-remote.sh) — 로컬 ↔ 서버 DB 동기화

### 최초 설치 (1회)

1. 코드를 GitHub에 push: `git push origin main`
2. `bash scripts/bootstrap-server.sh https://github.com/alexyun78/cafe-coffee-today.git`
   - 서버에 repo 클론
   - venv + 의존성 설치
   - `.env` + 로컬 `data/coffee.db`(있으면) 업로드
   - systemd 유닛 설치 + 활성화
3. `curl http://49.247.207.115:3002/api/coffee` 로 동작 확인

### 이후 운영

- **일반 배포**: `git push` → 60초 내 `cafe-coffee-deploy.timer`가 자동 pull + restart
- **강제 배포**: `bash scripts/deploy.sh`
- **앱만 재시작**: `bash scripts/deploy.sh --restart`
- **로그 확인**: `bash scripts/logs.sh`, `bash scripts/logs.sh deploy`, `bash scripts/logs.sh follow`
- **DB 동기화**: `bash scripts/migrate-remote.sh push|pull`

### systemd 유닛 (서버 측)

- [systemd/cafe-coffee.service](systemd/cafe-coffee.service) — gunicorn 앱 구동 (127.0.0.1:3002)
- [systemd/cafe-coffee-deploy.service](systemd/cafe-coffee-deploy.service) — `deploy.sh` 1회 실행
- [systemd/cafe-coffee-deploy.timer](systemd/cafe-coffee-deploy.timer) — 60초 주기 트리거
- [systemd/cafe-coffee-generate.service](systemd/cafe-coffee-generate.service) — `scripts/generate.sh` 1회 실행 (자체 생성, 권장)
- [systemd/cafe-coffee-generate.timer](systemd/cafe-coffee-generate.timer) — **매일 20:30 KST** 인사이트 자체 생성 (Claude API)
- [systemd/cafe-coffee-ingest.service](systemd/cafe-coffee-ingest.service) — `scripts/ingest.sh` 1회 실행 (구: Drive 경유, 폴백)
- [systemd/cafe-coffee-ingest.timer](systemd/cafe-coffee-ingest.timer) — **매일 21:00 KST** 인사이트 인제스트 (폴백)
- [deploy.sh](deploy.sh) (루트 레벨) — 서버에서 실행되는 배포 스크립트: `git fetch/reset → pip install(조건부) → systemctl restart`. `flock` 으로 ingest/generate 와 충돌 방지.
- [scripts/generate.sh](scripts/generate.sh) — 서버 자체 생성 래퍼: `git pull → generate_insight.py → git commit/push`. 같은 락 공유.
- [scripts/ingest.sh](scripts/ingest.sh) — 서버 인제스트 래퍼: `git pull → ingest_insights.py → git commit/push`. deploy.sh 와 같은 락 공유.

### Coffee Insight — 친근 설명 스타일 (2026-05-20 이후 표준)

모든 인사이트 글은 **중고생도 이해할 수 있는 친근 스타일**로 발행한다. 톤·구조·시각 요소가 한 글에서 다음 글로 일관되어야 한다.

**필수 톤** — 반말, 호기심 자극, 비유 풍부 ("김치 발효", "빵 효모", "강한 불 vs 약불" 같은 일상 비유).

**섹션 구조** (이 순서 그대로):

1. **🎨 ez-hero** — 큰 이모지 + 질문 형식 제목 (예: "발효를 똑똑하게 하면 커피 맛이 더 풍부해진다고?")
2. **🤔 무슨 연구야?** — 도입과 핵심 질문
3. **🧪 핵심 개념 풀기** — 어려운 개념 2~4개를 각각 비유와 함께
4. **🎯 핵심 발견** — 메달 카드 (🥇gold·🥈silver·🥉bronze·🏅medal) 로 3~5개
5. **📊 숫자로 보기** — 가로 막대 차트 (`data_charts` 사용)
6. **🆚 비교표** 또는 **🏭 인포그래픽** — 해당될 때만 (SVG)
7. **💼 누구한테 의미가 있을까?** — 대상별 표 (농가/로스터/R&D)
8. **⚠️ 한계도 있어** — 비판적 평가
9. **💡 한 줄 요약** — 강조 박스
10. **📚 원문 정보** — 논문/저널/저자/DOI
11. **📖 어려운 말 풀이 사전** — **반드시 마지막에**. JSON 의 `glossary` 필드 그대로 렌더링됨.

**사이드카 JSON 스키마 (선택적 친근 필드)**:

기본 필드(`summary`, `key_findings`, `implications`, `limitations`, `glossary`, `data_charts`, `links`, `citation_apa` 등)는 그대로 두고, 가능한 한 다음 친근 필드를 추가:

```jsonc
{
  // 기존 학술 필드는 그대로 유지...

  // === 친근 필드 (있으면 template 이 우선 사용) ===
  "easy_hero_emoji": "🧬",                                  // ez-hero 큰 이모지
  "easy_hero_title": "발효를 똑똑하게 하면 맛이 더 풍부해진다고?",  // 질문 형식 제목
  "easy_intro_paragraphs": [                                // "🤔 무슨 연구야?" 본문 — 반말, 비유
    "커피 한 잔의 향은 사실 마법이 아니라 화학 반응의 결과야...",
    "이 연구는 이런 질문에서 시작됐어..."
  ],
  "easy_concepts": [                                         // 핵심 개념 2~4개
    {
      "title": "1️⃣ 바이오미메틱 발효란?",
      "body": "'바이오미메틱'은 자연을 따라 한다는 뜻이야...",
      "analogy": "비유: 김치 발효를 아무 균이나 들어가게 두는 게 아니라..."
    }
  ],
  "easy_findings": [                                         // 메달 카드 발견
    {"medal": "gold",   "title": "🥇 향의 재료가 1.89배 늘었다", "body": "류신·페닐알라닌이 두 배로..."},
    {"medal": "silver", "title": "🥈 로스팅 중 pH 가 안정",   "body": "ΔpH 0.17 — 마이야르 최적 창..."},
    {"medal": "bronze", "title": "🥉 과일향 3배 폭발",         "body": "에스터화 3.08배 증가..."},
    {"medal": "medal",  "title": "🏅 견과류 향도 다양화",       "body": "알킬피라진 다양성 향상..."}
  ],
  "easy_tables": [                                           // 비교표 (선택)
    {
      "title": "🆚 일반 발효 vs 바이오미메틱 발효",
      "headers": ["항목", "일반", "BF"],
      "rows": [
        ["접근 방식", "우연한 자연 발효", "정밀 설계"],
        ["아미노산 풀", "기본", "1.89배 증가"]
      ]
    }
  ],
  "easy_summary": "발효 단계에서 재료를 풍부하게 만들고 산도를 안정시키면 과일향과 견과류향이 동시에 강해진다. 처음 과학적으로 증명한 연구!"
}
```

**필드가 없을 때**: 템플릿이 `summary` / `key_findings` / `implications` / `one_liner` 같은 기본 필드를 자동으로 친근 시각 스타일(메달 카드·가로 막대 차트·비교표)로 변환해서 렌더링한다. 단 톤(반말·비유)은 사이드카 텍스트 그대로이므로, 본문이 학술 톤이면 시각만 친근하고 내용은 학술적이 됨. **반말+비유를 위해서는 위 친근 필드를 채워야 함.**

**약어 사전**은 `glossary` 필드만 채워두면 템플릿이 항상 글 끝에 친근 카드로 자동 렌더링.

### Coffee Insight 자체 생성 파이프라인 — 권장 (2026-06-11 이후, Drive 비의존)

> 📌 **운영 현황 & 다른 PC 인수인계 (2026-06-10 갱신)**
>
> - **현재 채택된 발행 경로 = 자체 생성(이 섹션).** Google Drive 경유(아래 "구: Drive 폴백")는
>   더 이상 1차 경로가 아니다. 신규 작업·디버깅은 항상 이 섹션 기준으로 한다.
> - **토큰 현실**: 매일 새 글을 LLM 이 쓰므로 생성 단계는 **Claude API(유료) 토큰을 소모**한다.
>   (claude.ai 구독 토큰이 아니라 `ANTHROPIC_API_KEY` 의 API 과금.) 렌더·인제스트 단계만 토큰 0.
>   "토큰 0" 으로 가려면 글을 LLM 으로 매일 만들지 않는 방식(예: 백로그 미리 생성 후 하루 1편 릴리스)밖에 없다.
> - **알려진 정체 원인**: repo 엔 자체 생성 코드가 있어도 **서버에 1회 셋업이 안 되어 있으면**
>   (= `.env` 의 `ANTHROPIC_API_KEY` 누락 또는 `cafe-coffee-generate.timer` 미활성)
>   서버는 여전히 망가진 Drive 폴백에 의존해 글이 멈춘다. 2026-06-03 이후 정체가 이 패턴이었다.
> - **다른 PC 에서 작업 시작할 때 순서**: ① `git pull` → ② 아래 "✅ 살아있는지 검증" 으로 서버 상태 확인
>   → ③ 미설정이면 "서버 최초 1회 셋업" 실행. SSH 정보는 `.env`(`HOST`/`ID`/`PASSWORD`) 참조, 문서엔 적지 말 것.

claude.ai Google Drive 커넥터 토큰이 조용히 만료되면 글이 멈추는 문제(아래 ⚠️ 장애 패턴)를 없애기 위해, **서버가 직접 Claude API 로 글을 생성**하는 경로로 이전. claude.ai 루틴·Google Drive 를 둘 다 거치지 않는다.

매일 자동 발행 흐름:

1. **20:30 KST** — 서버 `cafe-coffee-generate.timer` 가 `scripts/generate.sh` 실행:
   - `git fetch/reset --hard origin/main` (락 `cafe-coffee-ops.lock` 공유)
   - `.venv/bin/python scripts/generate_insight.py`:
     - 오늘 날짜(KST)+요일로 종류 결정 (화목토일=`paper`, 월수금=`trivia`)
     - `index.json` 최근 제목·토픽·DOI 로 중복 회피 컨텍스트 구성
     - **Claude API(`claude-opus-4-8`) + 서버 `web_search` 툴** 호출:
       - paper: 실제 최근 커피 논문을 웹검색으로 찾아 **실재 DOI 확인** 후 abstract 기반 사이드카 JSON 생성 (가짜 DOI 금지)
       - trivia: 상록 토픽 친근 에세이. 신선도 필요 토픽은 검색 확인, 불확실하면 상록 대체
     - 최종 JSON 추출 → 필수 필드 검증(없으면 1회 재시도) → `ingest_insights.process_one` 으로 렌더 + `index.json` 갱신 (Drive ingest 와 동일 템플릿·스키마 재사용)
   - `git add static/insights/` → commit → `git push` (`.env` 의 `INGEST_GITHUB_TOKEN`)
2. **~20:31 KST** — `cafe-coffee-deploy.timer` 가 push 감지 → `git reset --hard` → `systemctl restart`. 사이트 반영.

- **필요한 .env 키**: `ANTHROPIC_API_KEY`(필수), `INGEST_GITHUB_TOKEN`(push, 기존 재사용), `INSIGHT_MODEL`(선택, 기본 `claude-opus-4-8`).
- **종류/요일·톤·스키마는 기존과 동일** — 친근 필드(`easy_*`)·`glossary`·`data_charts`·trivia `topic` 키 모두 위 스키마 그대로.
- **수동 1회 실행/백필**: `.venv/bin/python scripts/generate_insight.py [--date YYYY-MM-DD] [--type paper|trivia]`. 같은 날짜·종류가 index 에 있으면 자동 생략(멱등).

**서버 최초 1회 셋업**:
```bash
cd /root/92cafe/cafe-today-coffee
# 1) .env 에 ANTHROPIC_API_KEY 추가
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env && chmod 600 .env
# 2) 의존성 (generate.sh 가 자동 설치하지만 수동도 가능)
.venv/bin/pip install jinja2==3.1.4 anthropic
# 3) systemd 유닛 설치 + 활성화
cp systemd/cafe-coffee-generate.service systemd/cafe-coffee-generate.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cafe-coffee-generate.timer
# 4) 즉시 1회 테스트
systemctl start cafe-coffee-generate.service
journalctl -u cafe-coffee-generate.service -n 80 --no-pager
```

**✅ 살아있는지 검증 (다른 PC/서버에서 상태 확인)**:
```bash
# 0) 로컬: 최신 발행일 확인 (오늘과 차이가 크면 정체 의심)
python -c "import json;d=json.load(open('static/insights/index.json'));print('최신:',d['items'][0]['date'],'| 총',len(d['items']),'건')"

# --- 서버에서 (SSH 후) ---
cd /root/92cafe/cafe-today-coffee
# 1) 타이머가 등록·활성인지 + 다음 실행 시각
systemctl list-timers 'cafe-coffee-*' --all
# 2) generate.timer 가 enabled 인지 (없으면 셋업 안 된 것)
systemctl is-enabled cafe-coffee-generate.timer
# 3) .env 에 키 존재 확인 (값 노출 없이 키 이름만)
grep -q '^ANTHROPIC_API_KEY=' .env && echo "ANTHROPIC_API_KEY: 있음" || echo "ANTHROPIC_API_KEY: 없음(셋업 필요)"
grep -q '^INGEST_GITHUB_TOKEN=' .env && echo "INGEST_GITHUB_TOKEN: 있음" || echo "INGEST_GITHUB_TOKEN: 없음(push 불가)"
# 4) 최근 자체 생성 로그 (성공/실패 원인)
journalctl -u cafe-coffee-generate.service -n 120 --no-pager
```
판정: `generate.timer` 가 `enabled` + 다음 실행 시각이 보이고, `ANTHROPIC_API_KEY`/`INGEST_GITHUB_TOKEN` 이 있으면 정상.
하나라도 빠지면 위 "서버 최초 1회 셋업" 을 실행한다. 셋업 후 `systemctl start cafe-coffee-generate.service` 로 즉시 1편 생성해 따라잡기 가능(멱등).

> 자체 생성 경로가 정상 동작을 확인하면, 아래 claude.ai 루틴(coffee-daily·coffee-trivia) 2개는 비활성/삭제해도 된다(같은 날짜·종류는 index 멱등으로 충돌은 안 나지만, Drive 재인증 시 양쪽이 모두 발행해 중복될 수 있으므로 한쪽만 운영 권장). 21:00 ingest 타이머는 Drive 가 비어 있으면 아무것도 안 하므로 폴백으로 남겨둬도 무해.

---

### Coffee Insight 발행 파이프라인 (구: Drive 경유, 폴백)

매일 자동 발행 흐름 (2026-05-12 이후):

1. **21:00 KST 전** — Claude `/schedule` 클라우드 루틴이 `cafe-insight YYYY-MM-DD — *` sidecar JSON 을 Google Drive 에 업로드 (보통 22:00 → 20:30 으로 앞당겨야 함, 21:00 KST ingest 전에 끝나야 함).
2. **21:00 KST** — 서버 `cafe-coffee-ingest.timer` 가 `scripts/ingest.sh` 실행:
   - `git pull --ff-only`
   - `.venv/bin/python scripts/ingest_insights.py` (Drive → static/insights/*.html|json + 차트 PNG)
   - `git add static/insights/ static/img/insights/articles/`
   - `git commit -m "chore(insights): ingest daily coffee insight (YYYY-MM-DD)"`
   - `git push` (HTTPS + .env 의 `INGEST_GITHUB_TOKEN` PAT 사용, 임시 URL 로 토큰 미저장)
3. **~21:01 KST** — `cafe-coffee-deploy.timer` 가 push 를 감지 → `git reset --hard` → `systemctl restart`. 사이트에 즉시 반영.

**백업**: GitHub Actions [.github/workflows/ingest-insights.yml](.github/workflows/ingest-insights.yml) 은 `workflow_dispatch` 만 남겨둠 (Actions UI 에서 "Run workflow" 로 수동 실행 가능). 정기 cron 은 무료 티어에서 지연이 잦아 사용 안 함.

**최초 1회 셋업 (서버에서)**:
```bash
# 1) .env 에 키 추가
cat >> /root/92cafe/cafe-today-coffee/.env <<'EOF'
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
INGEST_GITHUB_TOKEN=ghp_...   # contents:write 권한 fine-grained PAT
EOF
chmod 600 /root/92cafe/cafe-today-coffee/.env

# 2) systemd 유닛 설치 + 활성화
cd /root/92cafe/cafe-today-coffee
cp systemd/cafe-coffee-ingest.service /etc/systemd/system/
cp systemd/cafe-coffee-ingest.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cafe-coffee-ingest.timer
systemctl list-timers cafe-coffee-ingest.timer

# 3) (선택) 즉시 1회 테스트
systemctl start cafe-coffee-ingest.service
journalctl -u cafe-coffee-ingest.service -n 100 --no-pager
```

### 오늘의 커피 상식 (Trivia) — 월·수·금 (2026-06-10 추가)

인사이트 피드에 **두 종류**의 글이 흐른다. 같은 `static/insights/` + `index.json` + `/insight` 목록을 공유하되 `type` 으로 구분:

| 요일 | type | 생성 루틴 | 성격 |
|---|---|---|---|
| 화·목·토·일 | `paper` (기본) | `coffee-daily` (`trig_01541UWrc8MzYgdaNPw86sFE`, cron `47 10 * * 0,2,4,6`) | 학술 논문 분석 |
| **월·수·금** | `trivia` | `coffee-trivia` (`trig_01DbFdJC3SWsjUDxPxZqgQYs`, cron `47 10 * * 1,3,5`) | 친근한 커피 상식 에세이 |

두 루틴 모두 19:47 KST 발화 → Drive sidecar 업로드 → 21:00 KST 서버 ingest 가 동일하게 수집. **같은 Google Drive 커넥터(`d0e97970-…`)를 공유** 하므로 커넥터 재인증 한 번이면 둘 다 복구된다.

- **sidecar 파일명**: `cafe-trivia YYYY-MM-DD — <slug>` (논문은 `cafe-insight …`). `scripts/ingest_insights.py` 의 `INSIGHT_FILE_PREFIXES` 가 둘 다 수집.
- **sidecar 필수 필드**: `type:"trivia"`, `topic:<키>`, `title_ko`, `one_liner`, `categories_primary:["커피 상식"]`, `categories_secondary:[한글 라벨]`, 그리고 친근 필드(`easy_*`)·`glossary`. 첫 글자는 반드시 `{`.
- **일러스트**: 텍스트만 생성하는 크론 환경이라 AI 이미지 대신 **토픽별 큐레이션 SVG 세트**(`static/img/insights/trivia/`)를 `topic` 키로 매핑(`ingest_insights.py`의 `TRIVIA_HERO`). 키: `origin·processing·trend·terms·decaf·bestcup·competition·trade`(+`default`).
- **주제 풀**: 나라별·산지별 재배, 프로세싱, 요즘 뜨는 프로세싱, 용어 풀이, 디카페인 가공, 올해의 커피, 국내/세계 대회 소식, 무역·시장 소식. 신선도가 필요한 주제(대회/무역/올해의커피)는 루틴이 WebFetch 로 확인하고, 불확실하면 상록 주제로 대체(추측 금지).
- **렌더**: `paper`/`trivia` 모두 `scripts/insight_template.html.j2` 한 템플릿. trivia 는 eyebrow="오늘의 커피 상식", "📚 원문 정보"(DOI/저널) 대신 "📚 더 알아보기"(출처 링크, 있을 때만). 목록 카드엔 `📖 커피 상식` 배지.
- **루틴 관리 UI**: 상식 https://claude.ai/code/routines/trig_01DbFdJC3SWsjUDxPxZqgQYs · 논문 https://claude.ai/code/routines/trig_01541UWrc8MzYgdaNPw86sFE

> ⚠️ **장애 패턴(2026-06)**: 루틴은 매일 발화해도 **claude.ai Google Drive 커넥터 토큰이 만료되면 Drive 업로드만 조용히 실패** → 사이트가 멈춘다(2026-06-03 이후 6일 공백 발생). "왜 인사이트 안 떴어"류 질문 시: ① `static/insights/` 에 오늘 날짜 파일 확인 → ② 없으면 Drive 에 `cafe-insight`/`cafe-trivia` 오늘자 sidecar 가 올라왔는지 확인 → ③ sidecar 도 없으면 **루틴 재실행해도 안 생김 = 커넥터 재인증 필요**(claude.ai 루틴 UI 에서). 서버 ingest(GOOGLE_REFRESH_TOKEN, 읽기 전용)는 별개로 정상.

---

## APK ([cafe-coffee-apk/](cafe-coffee-apk/))

- **프레임워크**: Capacitor (92cafe_pick의 `pick-apk` 구조 복제)
- **앱 ID**: `com.cafe92.todaycoffee`
- **동작 방식**: Capacitor WebView가 `capacitor.config.json`의 `server.url` (=`http://49.247.207.115:3002`)을 로드. 데이터는 항상 서버 최신.
- **로컬 Android Studio/SDK 불필요.** APK는 GitHub Actions에서 빌드됨.

### 버전 올리기 → 자동 배포
1. [cafe-coffee-apk/www/version.json](cafe-coffee-apk/www/version.json)의 `version` 값 증가 (예: `1.0.0` → `1.0.1`)
2. `git push` — [.github/workflows/build-apk.yml](.github/workflows/build-apk.yml)이 자동 실행
3. CI가 Node 20 + JDK 17 + Android SDK를 세팅하고 `npx cap add android && ./gradlew assembleDebug`
4. 완성된 APK를 서버의 `/root/92cafe/cafe-today-coffee/static/downloads/` 로 SCP
5. [http://49.247.207.115:3002/apk](http://49.247.207.115:3002/apk) 에서 다운로드

### GitHub Secrets (최초 1회 설정)
CI가 서버에 SCP하려면 SSH 키페어가 필요. 비밀번호는 CI에서 사용하지 않음.

**서버에서:**
```bash
ssh-keygen -t ed25519 -f ~/.ssh/cafe-coffee-ci -N ""
cat ~/.ssh/cafe-coffee-ci.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/cafe-coffee-ci              # 개인키를 복사
ssh-keyscan 49.247.207.115 2>/dev/null | grep -v '^#'  # 호스트키 복사
```

**GitHub 저장소 → Settings → Secrets and variables → Actions:**
- `SERVER_SSH_KEY`: 개인키 전체
- `SERVER_SSH_KNOWN_HOST`: `ssh-keyscan` 출력 라인

자세한 내용은 [scripts/README.md](scripts/README.md).

---

## UX 사양 (현재 구현 상태)

### 공개 페이지 탭 ([index.html](index.html))

- **탭 바**: 다크 브라운 배경, 활성 탭만 컬러 강조.
  - ☕ **