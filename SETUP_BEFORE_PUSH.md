# ⚠️ GitHub 푸시 전 필독!

## 🔒 보안 문제 해결됨

GitHub가 코드에 포함된 API 토큰을 감지하여 푸시를 차단했습니다.
이제 모든 실제 토큰이 제거되고 안전하게 설정되었습니다! ✅

---

## 📝 로컬 개발 설정

### 1단계: 환경 변수 파일 생성

`.env.local` 파일을 `.env`로 **이름 변경**하세요:

**Windows:**
```cmd
copy .env.local .env
```

**Linux/Mac:**
```bash
cp .env.local .env
```

### 2단계: 로컬 서버 실행

```bash
python app.py
```

또는

```bash
./start.sh      # Linux/Mac
start.bat       # Windows
```

---

## 🚀 GitHub 푸시

### 준비 완료!

이제 안전하게 GitHub에 푸시할 수 있습니다:

```bash
./deploy_to_github.sh      # Linux/Mac
deploy_to_github.bat        # Windows
```

또는 수동으로:

```bash
git add .
git commit -m "Initial commit: Cafe Today Coffee Web App"
git push -u origin main
```

---

## 📋 .gitignore가 다음 파일들을 자동으로 제외합니다:

✅ `.env` - 실제 토큰이 포함된 파일  
✅ `.env.local` - 로컬 개발용 실제 토큰  
✅ `__pycache__/` - Python 캐시  
✅ `*.log` - 로그 파일  

---

## 🎯 Render 배포 시 설정

Render에서는 다음 환경 변수를 **수동으로** 입력해야 합니다:

| Key | Value |
|-----|-------|
| `NOTION_TOKEN` | 본인의 실제 Notion Token |
| `DATABASE_ID` | 본인의 실제 Database ID |

**중요:** 실제 값은 로컬의 `.env` 파일에 있습니다!

---

## ✅ 확인 사항

푸시 전에 다음을 확인하세요:

- [ ] `.env.local` 파일을 `.env`로 복사했습니다
- [ ] 로컬에서 `python app.py`가 정상 작동합니다
- [ ] `.gitignore`가 존재합니다 (자동 생성됨)
- [ ] `app.py`에 실제 토큰이 하드코딩되어 있지 않습니다 ✅

---

## 🎉 완료!

이제 GitHub에 안전하게 푸시하고 Render에 배포할 수 있습니다!

**다음 단계:**
1. GitHub 푸시 (위의 명령어 사용)
2. `RENDER_DEPLOY.md` 가이드 따라 Render 배포
3. QR 코드 생성 및 매장에 게시

---

## 💡 왜 이렇게 해야 하나요?

**문제:**
- 실제 API 토큰이 코드에 포함되면 보안 위험
- GitHub가 자동으로 감지하고 차단
- 악의적 사용자가 토큰을 탈취할 수 있음

**해결:**
- `.env` 파일에만 실제 토큰 저장
- `.gitignore`로 `.env` 파일을 GitHub에서 제외
- Render에서는 환경 변수로 별도 설정
- 코드에는 플레이스홀더만 포함

**결과:**
- ✅ 코드는 공개 가능
- ✅ 토큰은 안전하게 보관
- ✅ GitHub 보안 검사 통과
- ✅ Render 배포 가능