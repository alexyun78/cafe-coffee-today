# CLAUDE.md — 오늘의 커피 (cafe-today-coffee)

이 프로젝트를 다룰 때 필요한 운영 정보와 자원 위치.
**비밀값(토큰/PIN/비밀번호)은 이 파일에 절대 기록하지 말 것.** 모두 `.env`에 있음.

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
- [deploy.sh](deploy.sh) (루트 레벨) — 서버에서 실행되는 배포 스크립트: `git fetch/reset → pip install(조건부) → systemctl restart`

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
| [app.py](app.py) | Flask 앱, 라우트, PIN 미들웨어 |
| [db.py](db.py) | SQLite 래퍼, 스키마 초기화, CRUD |
| [migrate_notion.py](migrate_notion.py) | Notion → SQLite 일회성 이전 |
| [index.html](index.html) | 탭 기반 공개 뷰 (오늘의커피 + 누가쏠까?: 손가락 게임, 룰렛) |
| [static/admin.html](static/admin.html) | 관리 추가/편집 폼 |
| [requirements.txt](requirements.txt) | 파이썬 의존성 |
| [deploy.sh](deploy.sh) | 서버 자동 배포 스크립트 |
| [systemd/](systemd/) | systemd 유닛 파일 |
| [cafe-coffee-apk/](cafe-coffee-apk/) | Capacitor 안드로이드 래퍼 |
| [.env](.env) | 비밀 환경 변수 (커밋 금지) |
