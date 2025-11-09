# ⚡ 빠른 배포 체크리스트

## 5분 안에 배포하기!

### ✅ 1단계: GitHub 준비 (2분)

**방법 A: 자동 스크립트 (추천)**
```bash
# Linux/Mac
./deploy_to_github.sh

# Windows
deploy_to_github.bat
```

**방법 B: 수동**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

---

### ✅ 2단계: Render 배포 (3분)

1. ✓ https://render.com 접속
2. ✓ GitHub 계정으로 가입/로그인
3. ✓ `New +` → `Web Service` 클릭
4. ✓ GitHub 저장소 연결
5. ✓ 다음 설정 입력:

```
Name: cafe-today-coffee
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

6. ✓ 환경 변수 추가:

| Key | Value |
|-----|-------|
| NOTION_TOKEN | (본인의 토큰) |
| DATABASE_ID | (본인의 DB ID) |

7. ✓ `Create Web Service` 클릭
8. ✓ 배포 완료 대기 (2-3분)

---

### ✅ 3단계: QR 코드 생성 (30초)

1. ✓ Render URL 복사: `https://your-app.onrender.com`
2. ✓ https://www.qr-code-generator.com 접속
3. ✓ URL 입력 → QR 코드 생성
4. ✓ 다운로드 → 매장에 게시

---

## 🎯 완료!

전체 소요 시간: **약 5분**

**배포 후 확인사항:**
- [ ] URL 접속 시 "오늘의 커피" 페이지 표시
- [ ] 진행 중인 커피가 올바르게 표시됨
- [ ] 히스토리 테이블이 정렬되어 표시됨
- [ ] QR 코드 스캔 시 정상 작동

---

## 🔧 문제 발생 시

**"Build failed"**
→ 로그 확인 → `RENDER_DEPLOY.md` 참조

**"Application failed to start"**
→ 환경 변수 확인 → `NOTION_TOKEN`, `DATABASE_ID` 재설정

**"Service is sleeping"**
→ 정상입니다! 첫 요청 시 자동 활성화 (15초)

---

## 📱 손님 접속 흐름

```
손님이 QR 코드 스캔
    ↓
자동으로 웹 브라우저 실행
    ↓
오늘의 커피 페이지 로드
    ↓
커피 정보 확인 완료!
```

**배포 성공!** 🎉☕
