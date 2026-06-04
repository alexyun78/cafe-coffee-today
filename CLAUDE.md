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
- [systemd/cafe-coffee-ingest.service](systemd/cafe-coffee-ingest.service) — `scripts/ingest.sh` 1회 실행
- [systemd/cafe-coffee-ingest.timer](systemd/cafe-coffee-ingest.timer) — **매일 21:00 KST** 인사이트 인제스트
- [deploy.sh](deploy.sh) (루트 레벨) — 서버에서 실행되는 배포 스크립트: `git fetch/reset → pip install(조건부) → systemctl restart`. `flock` 으로 ingest 와 충돌 방지.
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

### Coffee Insight 발행 파이프라인

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
  - ☕ **오늘의 커피** — 에스프레소→캐러멜 그라디언트, 상단 광택.
  - 🎲 **누가쏠까** — 브라스(황동) shimmer 애니메이션(3.2s 주기).
- **탭 자동 전환**: 누가쏠까 탭 진입 후 **3초간 게임 미선택 시** 자동으로 오늘의 커피 탭으로 복귀. 게임 닫기(X)로 돌아왔을 때도 재무장.
- **탭 하이라이트 제거**: 전역 `-webkit-tap-highlight-color: transparent` — 터치 시 반투명 사각형 잔상 제거.

### 손가락 게임

- **상단 대형 상태 텍스트** ([.finger-game-status](index.html)): "손가락을 대세요" / "2명 이상 필요해요" / "그대로 유지하세요" / 카운트다운 숫자 / "🎉 [동물] 당첨!"
- **동물 풀 (13종)**: 사자, 호랑이, 양, 고양이, 강아지, 얼룩말, 기린, 낙타, 사슴, 악어, 코끼리, 공작새, 고래. 동시에 같은 동물 중복 금지.
- **색상 풀 (13색)**: `FINGER_COLORS`. 동시에 같은 색 중복 금지.
- **동작**:
  - 터치 다운 → 110px 원 + 원 **바깥 위쪽**에 동물 라벨 (1.35rem).
  - 터치 이동 → 원/라벨 따라 이동.
  - 터치 업 → 원·라벨 제거 (단, 당첨 확정 후에는 `fingerWinnerShown` 플래그로 제거 차단).
- **진행 타이머**:
  - 2초 무변화(추가 원 없음) → 3·2·1 카운트다운(700Hz 비프) → 당첨.
  - 당첨 원 280px로 확대, 동물 라벨 2.8rem, 상단 "🎉 [동물] 당첨!".
- **Idle 종료 타이머**: 터치 0개 상태 5초 무반응 → 상단 "3초 뒤 종료" 카운트(480Hz 비프) → 닫고 오늘의 커피로.

### 누가쏠까 룰렛 게임

- **Phase 1 (인원 설정)**: 2명 이상 선택, START 버튼.
- **Phase 2 (카드)**:
  - 카드 크기 256×352 (모바일 232×320) — 매우 큼, 줄바꿈으로 수직 배치.
  - 카드 앞면 "?" (6rem), 뒷면 숫자 (7rem).
  - **카드 숫자는 항상 1..N 범위**(N = 참여 인원). 매 라운드 순서를 셔플하되 직전 라운드와 동일 순서면 재셔플(최대 20회).
  - **카드 뒷면 색상 = 휠 세그먼트 색상** (`COLORS[i % COLORS.length]`).
  - 터치 정확도: 3D 변환 중 이벤트 누수 방지 위해 `.roulette-card-inner/-front/-back`에 `pointer-events: none`, 래퍼만 `pointerup` 수신, `touch-action: manipulation`.
- **Phase 3 (휠)**: 휠 컨테이너 `min(92vw, 75vh)`, SVG viewBox로 컨테이너 꽉 채움. 포인터 26/44px.
- **Idle 종료 타이머 (모든 Phase 공통)**: 5초 무반응 → 상단 주황 뱃지(.close-hint)로 "3초 뒤 종료" 카운트 → 닫고 오늘의 커피로. 무장/해제 포인트:
  - 무장: `startRouletteGame`, `changeRouletteCount(±)`, `startRouletteCards`, 카드 플립(다음 카드 대기).
  - 해제: 모든 카드 플립 완료(휠 시작), `closeRouletteGame`.

### 관리자 폼 ([static/admin.html](static/admin.html))

- **필수 필드** (하나라도 비면 저장 차단, `*` 표시 + 필드별 에러 메시지):
  1. 원두 이름
  2. 로스터리
  3. 로스팅 일자
  4. 프로세싱
  5. 컵노트
- **목록 항목 메타**: `로스터리 · 🫘 로스팅일 · ☕ 제공일` — 제공일은 있을 때만 표시.
- **복제 동작** ([openDuplicate](static/admin.html)):
  - 복사: 원두이름, 로스터리, 프로세싱, **컵노트**, **감상**.
  - 비움: **제공일**.
  - 기본값: **로스팅일자 = 오늘 날짜** (원본 복사하지 않음).
  - 상태: 원본 무관하게 항상 **"예정"**.
  - 포커스: 로스팅일 필드, 토스트 "복제 — 로스팅일을 확인하세요".

---

## 생두 관리 시스템 (2026-05-27 추가)

구글 스프레드시트 기반 생두 관리를 DB + 관리자 UI로 이전. 스프레드시트는 더 이상 사용하지 않음.

### 생두 관리 DB 테이블

| 테이블 | 역할 | 비고 |
|---|---|---|
| `suppliers` | 생두 공급업체 (레햄코리아, 커피리브레 등 7곳) | `short_name`으로 UI 접두어 `[레햄]` 표시 |
| `green_beans` | 생두 마스터 (이름, 공급처, 가공, 등급, 컵노트) | **단일 소스 of truth** — 44종 |
| `purchases` | 구매 이력 (날짜, 수량kg, 단가, 할인, 총액) | 54건 이전됨 |
| `roasting_logs` | 로스팅 배치 (투입g, 배출g, 수분손실%) | 202건 이전됨 |
| `pricing` | 소매/도매 단가표 (중량별) | Phase 5 예정 |
| `blends` + `blend_components` | 블렌드 구성비 | Phase 5 예정 |

- `coffees.green_bean_id` (nullable FK → green_beans) — 오늘의커피와 생두 마스터 연결
- **재고 = computed query**: `SUM(purchases.qty) - SUM(roasting_logs.input/1000) + green_beans.stock_adjustment_kg` — 테이블이 아님. `stock_adjustment_kg`는 생두 목록에서 "최종 수량"을 직접 설정할 때만 갱신되는 보정값(`PUT /api/green-beans/<id>/stock`). 보정 후에도 구매(+)·로스팅(-)은 합계에 자연히 반영됨.
- 스프레드시트 데이터는 `scripts/seed_green_beans.sql`로 `init_schema()`에서 자동 시드 (서버 배포 시 수동 작업 불필요)

### 생두 관리 API (모두 `@require_pin`)

| 그룹 | 경로 | 메서드 |
|---|---|---|
| 공급업체 | `/api/suppliers[/<id>]` | GET/POST/PUT/DELETE |
| 생두 | `/api/green-beans[/<id>]` | GET/POST/PUT/DELETE |
| | `/api/green-beans/suggestions` | GET |
| | `/api/green-beans/<id>/for-coffee` | GET (오늘의커피 폼 자동완성용) |
| | `/api/green-beans/<id>/stock` | PUT (최종 수량 직접 설정 → stock_adjustment_kg 보정) |
| 구매 | `/api/purchases[/<id>]` | GET/POST/PUT/DELETE |
| | ↳ POST/PUT 은 `green_bean_id` 대신 생두 정보(name+process+supplier_name+origin_country+grade+cup_notes)를 보내면 `db.find_or_create_green_bean()`으로 생두를 찾거나 새로 만든 뒤 연결 | |
| 로스팅 | `/api/roasting-logs[/<id>]` | GET/POST/PUT/DELETE |
| 재고 | `/api/inventory` | GET |
| 가격 | `/api/pricing[/<id>]` | GET/POST/DELETE |
| | `/api/pricing/cost-analysis/<gb_id>` | GET |
| 이미지 | `/api/coffee/<id>/card-token` | POST (APK용 1회용 다운로드 토큰) |

### 관리자 UI 탭 구조 (admin.html)

```
[ ☕ 오늘의 커피 ] [ 🫘 생두 관리 ] [ 📦 재고 ]
```

- **오늘의 커피**: 기존 기능 그대로
- **생두 관리**: 생두 목록(재고 색상코딩) + 등록/편집 폼 + 구매 기록 폼 + 로스팅 기록 폼
  - **구매 폼은 생두 입력 폼을 겸함**: 공급업체·원두명·원산지·가공방식·등급·컵노트를 직접 입력하고 구입일·수량·단가·할인을 함께 기록. 저장 시 (name+supplier+process) 기준으로 기존 생두를 찾거나 새로 만들어 연결 → 생두 목록·재고·로스팅 드롭다운에 즉시 반영. 원두명을 고르면 정보 자동 입력
  - **공급업체·원두명은 공용 콤보 드롭다운**(`createComboSelect`, `.combo-select`): 기존 목록 표시 + 숨김 보기 토글/항목별 숨기기 + "직접 입력"(검색창에 새 값 입력 후 선택). 구매 폼·생두 폼이 같은 컴포넌트를 공유. 공급처 숨김은 `suppliers.hidden`(`PUT /api/suppliers/<id>` `{hidden}`), 원두 숨김은 기존 `green_beans.hidden`
- **재고**: 최근구매일→재고량 정렬, 30개 페이징, 1년 이상 미구매+재고0 접힘

### 생두 이름 규칙

DB에서 분리 저장, UI에서 조합 표시:
- `green_beans.name` = `브라질 세하도` (순수 원두명)
- `suppliers.short_name` = `레햄` (접두어)
- UI 표시 = `[레햄] 브라질 세하도`

### 남은 Phase

| Phase | 내용 | 상태 |
|---|---|---|
| 1+2 | DB + API + 관리자 UI + 마이그레이션 | ✅ 완료 |
| 3 | 재고 탭 고도화 (저재고 알림, 필터) | 미착수 |
| 4 | 오늘의커피 폼에 "생두 선택" 드롭다운 연동 | 미착수 |
| 5 | 가격 탭 (원가분석, 블렌드, 소매/도매) | 미착수 |
| 6 | 대시보드 + 리포트 + CSV 내보내기 | 미착수 |

---

## 주의사항

- `.env`, `data/`, `__pycache__/`, `.venv/`, `node_modules/`, `cafe-coffee-apk/android/`는 gitignore 대상.
- API 응답의 한글 키(`커피`, `로스팅` 등)는 기존 프런트 호환성을 위한 것. 섣불리 영문화하지 말 것.
- 날짜 필드(`roast_date`, `serve_date`)는 API에서 `{"start": "YYYY-MM-DD", "end": null}` 객체로 반환 (Notion 호환).
- PIN 인증은 세션 쿠키 기반. 서버 재시작 시 세션 무효화됨 (FLASK_SECRET 유지되어도 메모리 세션 사용).
- 절대 `--no-verify`로 커밋 우회하지 말 것.
- 운영 DB에 직접 SQL 수정 전 반드시 `data/backup/`에 덤프 생성.

---

## 파일 맵

| 파일 | 역할 |
|---|---|
| [app.py](app.py) | Flask 앱, 라우트, PIN 미들웨어, 생두 관리 API (24개 엔드포인트) |
| [db.py](db.py) | SQLite 래퍼, 스키마 초기화 (coffees + 생두 7테이블), CRUD |
| [generate_bean_images.py](generate_bean_images.py) | 커피 카드 이미지 생성 (PIL) |
| [migrate_notion.py](migrate_notion.py) | Notion → SQLite 일회성 이전 |
| [index.html](index.html) | 탭 기반 공개 뷰 (오늘의커피 + 누가쏠까?: 손가락 게임, 룰렛) |
| [static/admin.html](static/admin.html) | 관리 폼 — 3탭 (오늘의커피 / 생두관리 / 재고) |
| [static/roastery.html](static/roastery.html) | 92도씨 로스터리 메인 공개 페이지 |
| [scripts/seed_green_beans.sql](scripts/seed_green_beans.sql) | 생두 초기 데이터 (init_schema에서 자동 실행) |
| [scripts/migrate_spreadsheet.py](scripts/migrate_spreadsheet.py) | 구글 스프레드시트 → DB 마이그레이션 스크립트 |
| [requirements.txt](requirements.txt) | 파이썬 의존성 |
| [deploy.sh](deploy.sh) | 서버 자동 배포 스크립트 |
| [systemd/](systemd/) | systemd 유닛 파일 |
| [cafe-coffee-apk/](cafe-coffee-apk/) | Capacitor 안드로이드 래퍼 |
| [.env](.env) | 비밀 환경 변수 (커밋 금지) |
