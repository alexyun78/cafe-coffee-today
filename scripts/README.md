# scripts/

운영 스크립트. 모두 프로젝트 루트에서 실행. `.env` 파일이 필요하며 `HOST`, `ID`, `PASSWORD` 값을 읽는다.

## 사전 요구사항 (Windows)

1. **PuTTY 설치** (plink, pscp 포함): https://www.chiark.greenend.org.uk/~sgtatham/putty/
2. PATH에 PuTTY 디렉토리 추가 (`plink -V`가 작동해야 함)
3. Git Bash (Git for Windows에 포함)

## 스크립트

### `bootstrap-server.sh` — 최초 1회 서버 설치

서버에 `/root/92cafe/cafe-today-coffee` 클론, venv + 의존성 설치, systemd 유닛 등록, 로컬 DB 업로드(있으면).

```bash
bash scripts/bootstrap-server.sh https://github.com/<user>/<repo>.git
```

실행 후:
- `http://49.247.207.115:3002` 접속 가능
- systemd 타이머가 60초 간격으로 git pull + 재시작 자동 실행

### `deploy.sh` — 강제 재배포

보통 `git push` 후 60초 안에 자동 반영된다. 기다리기 싫거나 즉시 확인하고 싶을 때 사용.

```bash
bash scripts/deploy.sh            # 서버에서 cafe-coffee-deploy.service 즉시 실행
bash scripts/deploy.sh --restart  # 앱만 강제 재시작 (git pull 없음)
```

### `logs.sh` — 로그 조회

```bash
bash scripts/logs.sh           # 앱 로그 50줄
bash scripts/logs.sh deploy    # 배포 로그 30줄
bash scripts/logs.sh follow    # 실시간 스트리밍
bash scripts/logs.sh status    # systemd 상태
```

### `migrate-remote.sh` — 로컬 ↔ 서버 DB 동기화

```bash
bash scripts/migrate-remote.sh push   # 로컬 DB → 서버 (서버는 백업 후 덮어쓰기)
bash scripts/migrate-remote.sh pull   # 서버 DB → 로컬 (로컬은 백업 후 덮어쓰기)
```

**주의**: `push`는 서버에서 앱을 잠시 중단시킨다. 트래픽이 있으면 영향 있음.

## APK 빌드 (GitHub Actions)

**로컬에 Android Studio나 SDK를 설치하지 않는다.**

1. `cafe-coffee-apk/` 내용을 수정 (`capacitor.config.json`, `www/version.json` 등)
2. 버전 올리려면 `cafe-coffee-apk/www/version.json`의 `version` 필드 증가
3. `git push` — `.github/workflows/build-apk.yml`이 자동 실행
4. Actions 탭에서 빌드 진행 확인
5. 완료 시 서버의 `/root/92cafe/cafe-today-coffee/static/downloads/` 에 배포됨
6. `http://49.247.207.115:3002/apk` 에서 다운로드 페이지 접근

### GitHub Secrets 설정 (최초 1회)

CI가 서버에 SCP하려면 SSH 키페어가 필요. 비밀번호는 CI에서 사용하지 않는다.

**서버에서:**
```bash
ssh-keygen -t ed25519 -f ~/.ssh/cafe-coffee-ci -N ""
cat ~/.ssh/cafe-coffee-ci.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/cafe-coffee-ci         # 이 개인키를 복사
ssh-keyscan 49.247.207.115 2>/dev/null | grep -v '^#'  # known_hosts 라인 복사
```

**GitHub 저장소 → Settings → Secrets and variables → Actions:**
- `SERVER_SSH_KEY`: 위에서 복사한 개인키 전체 (여러 줄)
- `SERVER_SSH_KNOWN_HOST`: `ssh-keyscan` 출력 라인

이후 푸시할 때마다 자동으로 APK가 빌드되고 서버로 배포된다.
