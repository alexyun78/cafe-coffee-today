# 🚀 Render 배포 - 시작하기

## 📦 제공된 모든 파일

### 핵심 파일
- ✅ `app.py` - Flask 백엔드 (환경 변수 지원)
- ✅ `index.html` - 웹 페이지
- ✅ `requirements.txt` - Python 패키지 (gunicorn 포함)

### 설정 파일
- ✅ `.env` - 로컬 개발용 환경 변수
- ✅ `.env.example` - 환경 변수 템플릿
- ✅ `.gitignore` - Git 제외 파일
- ✅ `render.yaml` - Render 자동 배포 설정

### 실행 스크립트
- ✅ `start.sh` / `start.bat` - 로컬 서버 실행
- ✅ `deploy_to_github.sh` / `deploy_to_github.bat` - GitHub 푸시

### 검증 도구
- ✅ `check_setup.py` - 설정 자동 검증

### 문서
- ✅ `RENDER_DEPLOY.md` - 상세 배포 가이드 ⭐
- ✅ `DEPLOY_CHECKLIST.md` - 빠른 체크리스트 ⭐
- ✅ `QUICK_START.md` - 로컬 실행 가이드
- ✅ `TROUBLESHOOTING.md` - 문제 해결
- ✅ `README.md` - 전체 설명서

---

## ⚡ 3단계 배포 (5분)

### 1️⃣ GitHub에 업로드

**자동 (추천):**
```bash
./deploy_to_github.sh    # Linux/Mac
deploy_to_github.bat      # Windows
```

**수동:**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/USERNAME/REPO.git
git push -u origin main
```

---

### 2️⃣ Render 배포

1. https://render.com 접속
2. GitHub 계정으로 가입
3. `New +` → `Web Service`
4. 저장소 연결
5. 설정 입력:
   ```
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app
   ```
6. **환경 변수 추가 (중요!):**
   - `NOTION_TOKEN`: (본인의 토큰)
   - `DATABASE_ID`: (본인의 DB ID)
7. `Create Web Service` 클릭

---

### 3️⃣ QR 코드 생성

1. Render URL 복사
2. https://www.qr-code-generator.com
3. QR 코드 생성 → 다운로드
4. 매장에 게시

---

## 📚 문서 가이드

**처음 시작하시나요?**
→ `RENDER_DEPLOY.md` 읽기 (완전 가이드)

**빠르게 배포하고 싶으신가요?**
→ `DEPLOY_CHECKLIST.md` 보기 (5분 가이드)

**로컬에서 먼저 테스트?**
→ `QUICK_START.md` 참조

**문제가 발생했나요?**
→ `TROUBLESHOOTING.md` 확인

---

## 🎯 핵심 포인트

### ✅ DO (해야 할 것)
- ✅ 환경 변수 설정 (`NOTION_TOKEN`, `DATABASE_ID`)
- ✅ `requirements.txt`에 gunicorn 포함 (이미 포함됨!)
- ✅ GitHub에 코드 푸시
- ✅ Render에서 자동 배포

### ❌ DON'T (하지 말아야 할 것)
- ❌ `.env` 파일을 GitHub에 올리기 (자동 제외됨)
- ❌ 토큰을 코드에 하드코딩 (환경 변수 사용!)
- ❌ HTML 파일을 직접 열기 (서버 실행 필수!)

---

## 🆘 빠른 도움말

### Q: "Build failed" 오류
**A:** 로그 확인 → `requirements.txt` 확인 → gunicorn 포함 여부

### Q: "Application failed to start"
**A:** 환경 변수 확인 → `NOTION_TOKEN`, `DATABASE_ID` 재설정

### Q: "Service is sleeping"
**A:** 정상입니다! 첫 요청 시 자동 활성화 (15초)

### Q: QR 코드 스캔 시 느림
**A:** 무료 플랜의 슬립 모드 - 정상 작동
**해결:** 손님이 한 번 접속하면 그 후로는 빠름

---

## 📞 추가 지원

- **Render 공식 문서**: https://render.com/docs
- **Render 커뮤니티**: https://community.render.com
- **문제 해결**: `TROUBLESHOOTING.md` 파일 참조

---

## 🎉 배포 성공!

모든 준비가 완료되었습니다!

**다음 단계:**
1. `RENDER_DEPLOY.md` 파일을 열어 상세 가이드를 따라하세요
2. 또는 `DEPLOY_CHECKLIST.md`로 빠르게 시작하세요
3. 문제 발생 시 `TROUBLESHOOTING.md`를 확인하세요

**파이팅!** ☕🚀
