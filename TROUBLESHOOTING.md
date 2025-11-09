# 🔧 "Failed to fetch" 오류 해결 가이드

## 문제 진단

"Failed to fetch" 오류는 다음과 같은 이유로 발생합니다:

### 1️⃣ Flask 서버가 실행되지 않음 (가장 흔한 원인)
- HTML 파일만 열었고 Flask 서버를 시작하지 않았습니다.

### 2️⃣ 잘못된 접속 방법
- `index.html` 파일을 더블클릭해서 직접 열었습니다.
- 이 경우 `file:///` 프로토콜로 열려서 API 호출이 불가능합니다.

### 3️⃣ 포트 충돌
- 5000번 포트가 이미 다른 프로그램에서 사용 중입니다.

---

## ✅ 올바른 실행 방법

### 방법 1: 자동 실행 스크립트 사용 (추천)

**Windows:**
```cmd
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

### 방법 2: 수동 실행

#### 단계 1: 패키지 설치 (최초 1회만)
```bash
pip install -r requirements.txt
```

#### 단계 2: Flask 서버 실행
```bash
python app.py
```

다음과 같은 메시지가 나타나야 합니다:
```
==================================================
☕ 오늘의 커피 웹 앱 서버 시작
==================================================
🌐 접속 주소: http://localhost:5000
📡 API 엔드포인트: http://localhost:5000/api/coffee
🔧 Notion Database ID: YOUR_DATABASE_ID_HERE
==================================================
서버를 종료하려면 Ctrl+C를 누르세요

 * Serving Flask app 'app'
 * Debug mode: on
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.x.x:5000
```

#### 단계 3: 브라우저에서 접속
- **올바른 방법:** http://localhost:5000 으로 접속
- **잘못된 방법:** ~~index.html 파일 더블클릭~~

---

## 🔍 상세 문제 해결

### 문제 A: "pip: command not found"

**해결책:**
```bash
# Python이 설치되어 있는지 확인
python --version
python3 --version

# pip 대신 다음 사용
python -m pip install -r requirements.txt
# 또는
python3 -m pip install -r requirements.txt
```

### 문제 B: "Address already in use" (포트 충돌)

**해결책 1: 다른 포트 사용**

`app.py` 파일의 마지막 줄 수정:
```python
app.run(host='0.0.0.0', port=8080, debug=True)  # 5000 → 8080으로 변경
```

그리고 브라우저에서 `http://localhost:8080` 으로 접속

**해결책 2: 기존 프로세스 종료**

Windows:
```cmd
netstat -ano | findstr :5000
taskkill /PID [프로세스ID] /F
```

Linux/Mac:
```bash
lsof -ti:5000 | xargs kill -9
```

### 문제 C: "ModuleNotFoundError: No module named 'flask'"

**해결책:**
```bash
pip install flask flask-cors requests
# 또는
pip install -r requirements.txt --break-system-packages
```

### 문제 D: Notion API 오류

터미널에 다음과 같은 오류가 표시됩니다:
```
Notion API 오류: 401 Unauthorized
```

**해결책:**
1. `app.py` 파일을 열어주세요
2. Notion Token과 Database ID를 확인하세요:
```python
NOTION_TOKEN = "ntn_..." # 올바른 토큰으로 변경
DATABASE_ID = "..." # 올바른 데이터베이스 ID로 변경
```
3. Notion 통합(Integration)이 데이터베이스에 연결되어 있는지 확인하세요

---

## 📋 체크리스트

실행 전에 다음을 확인하세요:

- [ ] Python 3.7 이상 설치됨
- [ ] pip가 정상 작동함
- [ ] requirements.txt의 패키지들이 설치됨
- [ ] app.py의 Notion Token과 Database ID가 올바름
- [ ] Flask 서버가 실행 중임 (터미널에 메시지 표시됨)
- [ ] 브라우저에서 `http://localhost:5000` 으로 접속함 (파일 직접 열기 ❌)

---

## 🆘 여전히 문제가 있나요?

### 디버깅 모드 활성화

터미널에서 Flask 서버를 실행하면 다음과 같은 로그가 표시됩니다:
```
API 요청 수신됨
총 12개 페이지 로드됨
진행 중인 커피: 2개
127.0.0.1 - - [날짜] "GET /api/coffee HTTP/1.1" 200 -
```

이 로그를 확인하여:
- API 요청이 도달하는지
- Notion에서 데이터를 정상적으로 가져오는지
- 어디서 오류가 발생하는지 파악할 수 있습니다.

### 브라우저 개발자 도구 확인

1. 브라우저에서 F12 키를 눌러 개발자 도구 열기
2. "Console" 탭에서 에러 메시지 확인
3. "Network" 탭에서 `/api/coffee` 요청 상태 확인

---

## 💡 성공적인 실행 예시

**1. 터미널 (Flask 서버):**
```
☕ 오늘의 커피 웹 앱 서버 시작
🌐 접속 주소: http://localhost:5000
서버를 종료하려면 Ctrl+C를 누르세요

* Running on http://127.0.0.1:5000
API 요청 수신됨
총 12개 페이지 로드됨
진행 중인 커피: 2개
```

**2. 브라우저:**
- 주소창: `http://localhost:5000`
- 페이지에 "오늘의 커피" 제목과 커피 정보가 표시됨
- 에러 메시지가 없음

---

## 📞 추가 도움말

문제가 계속되면:
1. 터미널의 전체 에러 메시지를 캡처하세요
2. 브라우저 개발자 도구의 Console 탭 내용을 확인하세요
3. `app.py`의 Notion Token과 Database ID가 정확한지 다시 확인하세요

필요한 경우 이 정보들을 제공하면 더 구체적인 도움을 드릴 수 있습니다.
