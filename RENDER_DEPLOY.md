# 🚀 Render 배포 가이드 - 오늘의 커피

## 📋 목차
1. [준비사항](#준비사항)
2. [파일 준비](#파일-준비)
3. [GitHub 저장소 생성](#github-저장소-생성)
4. [Render 배포](#render-배포)
5. [QR 코드 생성](#qr-코드-생성)
6. [문제 해결](#문제-해결)

---

## 준비사항

### 필요한 계정
- [x] GitHub 계정 (무료)
- [x] Render 계정 (무료) - https://render.com

### 준비할 정보
- [x] Notion Integration Token
- [x] Notion Database ID

---

## 파일 준비

이미 제공된 파일들을 GitHub에 올릴 준비가 되어 있습니다!

### ✅ 이미 준비된 파일들:
- `app.py` - Flask 앱
- `index.html` - 웹 페이지
- `requirements.txt` - Python 패키지
- `render.yaml` - Render 설정 (자동 생성 예정)
- `.gitignore` - Git 제외 파일 (자동 생성 예정)

---

## GitHub 저장소 생성

### 1단계: GitHub에 로그인
1. https://github.com 접속
2. 로그인

### 2단계: 새 저장소 생성
1. 우측 상단의 `+` 버튼 클릭
2. `New repository` 선택
3. 저장소 설정:
   - **Repository name**: `cafe-today-coffee` (원하는 이름)
   - **Description**: 오늘의 커피 웹 앱
   - **Public** 선택 (무료 배포를 위해)
   - **Initialize this repository with**: 아무것도 체크 안 함
4. `Create repository` 클릭

### 3단계: 로컬에서 Git 초기화

터미널/명령 프롬프트를 열고 프로젝트 폴더로 이동:

```bash
cd /path/to/your/project

# Git 초기화
git init

# GitHub 원격 저장소 연결 (본인의 GitHub 계정명과 저장소명으로 변경)
git remote add origin https://github.com/YOUR_USERNAME/cafe-today-coffee.git

# 모든 파일 추가
git add .

# 커밋
git commit -m "Initial commit: 오늘의 커피 웹 앱"

# GitHub에 푸시
git branch -M main
git push -u origin main
```

**⚠️ 중요:** `YOUR_USERNAME`을 본인의 GitHub 사용자명으로 변경하세요!

---

## Render 배포

### 1단계: Render 계정 생성

1. https://render.com 접속
2. `Get Started` 또는 `Sign Up` 클릭
3. **GitHub 계정으로 가입** (추천!) 또는 이메일로 가입
4. GitHub로 가입하면 자동으로 저장소 연결 가능

### 2단계: 새 Web Service 생성

1. Render 대시보드에서 `New +` 버튼 클릭
2. `Web Service` 선택
3. GitHub 저장소 연결:
   - `Connect a repository` 클릭
   - 방금 만든 `cafe-today-coffee` 저장소 선택
   - `Connect` 클릭

### 3단계: 서비스 설정

다음과 같이 입력하세요:

#### 기본 설정:
- **Name**: `cafe-today-coffee` (원하는 이름)
- **Region**: `Singapore (Southeast Asia)` (한국과 가까움) 또는 `Oregon (US West)`
- **Branch**: `main`
- **Root Directory**: 비워둠 (공백)
- **Runtime**: `Python 3`

#### 빌드 설정:
- **Build Command**: 
  ```
  pip install -r requirements.txt
  ```

#### 시작 설정:
- **Start Command**: 
  ```
  gunicorn app:app
  ```

#### 인스턴스 타입:
- **Instance Type**: `Free` 선택 ✅

### 4단계: 환경 변수 설정 (중요! ⚠️)

스크롤을 내려 `Environment` 섹션에서 `Add Environment Variable` 클릭:

**추가할 환경 변수:**

| Key | Value |
|-----|-------|
| `NOTION_TOKEN` | `ntn_YOUR_ACTUAL_NOTION_TOKEN_HERE` |
| `DATABASE_ID` | `YOUR_DATABASE_ID_HERE` |
| `PYTHON_VERSION` | `3.11.0` |

**⚠️ 주의:** 본인의 실제 Notion Token과 Database ID를 입력하세요!

### 5단계: 배포 시작

1. `Create Web Service` 버튼 클릭
2. 배포가 자동으로 시작됩니다 (약 2-3분 소요)
3. 로그를 확인하며 대기

**성공적인 배포 로그 예시:**
```
==> Installing dependencies
==> Collecting flask
==> Successfully installed flask-3.0.0
==> Build successful
==> Starting service with 'gunicorn app:app'
```

### 6단계: 배포 완료 확인

1. 상단에 녹색 `Live` 표시가 나타남
2. URL이 표시됨: `https://cafe-today-coffee.onrender.com`
3. URL을 클릭해서 웹사이트 확인!

---

## 환경 변수를 사용하도록 app.py 수정

현재 `app.py`에 토큰이 하드코딩되어 있으므로, 환경 변수를 사용하도록 수정해야 합니다.

**업데이트된 app.py 파일은 별도로 제공됩니다!**

---

## QR 코드 생성

### 1단계: 배포된 URL 복사

Render에서 제공한 URL을 복사하세요:
```
https://cafe-today-coffee.onrender.com
```

### 2단계: QR 코드 생성 사이트 접속

다음 중 하나를 선택:
- https://www.qr-code-generator.com/
- https://qr.io/
- https://www.the-qrcode-generator.com/

### 3단계: QR 코드 생성

1. URL 입력란에 Render URL 붙여넣기
2. 디자인 커스터마이징 (선택사항):
   - 색상 변경
   - 로고 추가 (커피 아이콘)
   - 프레임 추가 ("오늘의 커피")
3. `Download` 또는 `생성` 버튼 클릭
4. PNG 또는 SVG 형식으로 다운로드

### 4단계: 매장에 게시

1. QR 코드 인쇄 또는 디지털 표시
2. "오늘의 커피 확인하기" 문구 추가
3. 테이블, 카운터, 입구 등에 배치

---

## 문제 해결

### ❌ 빌드 실패: "No module named 'gunicorn'"

**문제:** `requirements.txt`에 gunicorn이 없음

**해결:**
1. 로컬에서 `requirements.txt` 수정:
   ```
   Flask==3.0.0
   flask-cors==4.0.0
   requests==2.31.0
   gunicorn==21.2.0
   ```
2. GitHub에 푸시:
   ```bash
   git add requirements.txt
   git commit -m "Add gunicorn"
   git push
   ```
3. Render가 자동으로 재배포

### ❌ "Application failed to start"

**문제:** 환경 변수가 설정되지 않음

**해결:**
1. Render 대시보드 → 해당 서비스 선택
2. 왼쪽 메뉴에서 `Environment` 클릭
3. `NOTION_TOKEN`과 `DATABASE_ID` 확인
4. 없으면 추가하고 `Save Changes` 클릭

### ❌ "Service is sleeping"

**문제:** 무료 플랜은 15분 비활성 시 슬립 모드

**해결:**
- 정상 작동입니다! 첫 요청 시 자동으로 깨어남 (15초 소요)
- 손님이 QR 코드를 스캔하면 자동 활성화
- 활성 상태를 유지하려면 유료 플랜 필요

**대안:** 
- 주기적으로 ping하는 서비스 사용 (예: UptimeRobot)
- 하지만 카페 운영 시간에만 필요하므로 슬립 모드도 괜찮습니다!

### ❌ Notion API 오류

**문제:** Token 또는 Database ID가 잘못됨

**해결:**
1. Render 대시보드 → Environment
2. `NOTION_TOKEN`과 `DATABASE_ID` 값 재확인
3. Notion에서 올바른 값 복사
4. `Save Changes` 클릭
5. 서비스 자동 재시작

---

## 🎯 배포 체크리스트

배포 전 확인사항:

- [ ] GitHub 저장소 생성 완료
- [ ] 코드 푸시 완료 (`git push`)
- [ ] Render 계정 생성
- [ ] GitHub 저장소 연결
- [ ] 환경 변수 설정 (`NOTION_TOKEN`, `DATABASE_ID`)
- [ ] Build Command: `pip install -r requirements.txt`
- [ ] Start Command: `gunicorn app:app`
- [ ] 배포 성공 (녹색 `Live` 표시)
- [ ] 웹사이트 접속 테스트
- [ ] QR 코드 생성 완료

모든 항목에 체크가 되면 배포 완료! 🎉

---

## 💡 추가 팁

### 자동 배포 (CD)
GitHub에 푸시하면 Render가 자동으로 재배포합니다!

```bash
# 코드 수정 후
git add .
git commit -m "Update coffee display"
git push
# → Render가 자동으로 감지하고 재배포!
```

### 커스텀 도메인 연결 (선택사항)

무료 플랜에서도 커스텀 도메인 연결 가능:
1. 도메인 구매 (예: cafe-coffee.com)
2. Render 대시보드 → Settings → Custom Domain
3. 도메인 추가 및 DNS 설정
4. `https://cafe-coffee.com`으로 접속 가능!

### 로그 확인

문제 발생 시:
1. Render 대시보드 → 해당 서비스
2. 왼쪽 메뉴 → `Logs`
3. 실시간 로그 확인

### 성능 모니터링

Render 대시보드에서:
- CPU 사용량
- 메모리 사용량
- 요청 수
- 응답 시간

무료 플랜도 충분히 모니터링 가능합니다!

---

## 🎉 완료!

이제 전 세계 어디서나 QR 코드로 "오늘의 커피"에 접속할 수 있습니다!

**배포된 URL 예시:**
```
https://cafe-today-coffee.onrender.com
```

**QR 코드를 스캔하면:**
1. 손님의 스마트폰에서 자동으로 웹사이트 열림
2. 오늘의 커피 정보 표시
3. 자동 새로고침으로 항상 최신 정보 유지

---

## 📞 도움이 필요하신가요?

- Render 공식 문서: https://render.com/docs
- Render 커뮤니티: https://community.render.com
- 문제 발생 시: Render 로그를 확인하세요!
