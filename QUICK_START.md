# 🚀 빠른 시작 가이드 - 오늘의 커피

## ⚡ 3단계로 시작하기

### 1단계: 설정 확인 ✓

터미널/명령 프롬프트를 열고 프로젝트 폴더로 이동한 후:

```bash
python check_setup.py
```

이 명령어는 다음을 확인합니다:
- ✓ Python 설치 여부
- ✓ 필요한 패키지 설치 여부  
- ✓ Notion Token과 Database ID 설정 여부
- ✓ 포트 5000 사용 가능 여부
- ✓ Notion API 연결 테스트

**모든 항목에 ✓ 표시가 나타나야 합니다!**

---

### 2단계: 서버 실행 🖥️

#### Windows 사용자:
```
start.bat 파일을 더블클릭
```

#### Mac/Linux 사용자:
```bash
chmod +x start.sh
./start.sh
```

#### 또는 직접 실행:
```bash
python app.py
```

**성공하면 다음과 같은 메시지가 표시됩니다:**

```
==================================================
☕ 오늘의 커피 웹 앱 서버 시작
==================================================
🌐 접속 주소: http://localhost:5000
📡 API 엔드포인트: http://localhost:5000/api/coffee
🔧 Notion Database ID: 211692fc...
==================================================
서버를 종료하려면 Ctrl+C를 누르세요

 * Running on http://127.0.0.1:5000
```

---

### 3단계: 브라우저에서 접속 🌐

웹 브라우저를 열고 주소창에 입력:

```
http://localhost:5000
```

**올바른 방법:**
- ✓ 브라우저 주소창에 `http://localhost:5000` 입력
- ✓ 서버가 실행 중인 상태에서 접속

**잘못된 방법:**
- ✗ `index.html` 파일을 더블클릭해서 열기
- ✗ 서버를 실행하지 않고 접속
- ✗ `file:///...` 경로로 열기

---

## 🎉 성공!

페이지가 정상적으로 표시되면:
- "오늘의 커피" 제목이 보입니다
- 진행 중인 커피 카드가 표시됩니다
- 하단에 커피 히스토리 테이블이 표시됩니다

---

## ❌ 오류가 발생한다면?

### "Failed to fetch" 오류

**원인:** Flask 서버가 실행되지 않았거나, HTML 파일을 직접 열었습니다.

**해결:**
1. 터미널을 확인하세요 - Flask 서버가 실행 중인가요?
2. 브라우저 주소창을 확인하세요 - `http://localhost:5000` 인가요?
3. `index.html`을 직접 열었다면, 브라우저를 닫고 위의 주소로 다시 접속하세요

### "Address already in use" 오류

**원인:** 포트 5000이 이미 사용 중입니다.

**해결:**
1. 다른 Flask 앱을 종료하세요
2. 또는 `app.py`에서 포트를 변경하세요:
   ```python
   app.run(host='0.0.0.0', port=8080, debug=True)
   ```

### "ModuleNotFoundError" 오류

**원인:** 필요한 Python 패키지가 설치되지 않았습니다.

**해결:**
```bash
pip install -r requirements.txt
```

### "Notion API 오류"

**원인:** Token이나 Database ID가 잘못되었습니다.

**해결:**
1. `app.py` 파일을 텍스트 에디터로 엽니다
2. `NOTION_TOKEN`과 `DATABASE_ID`를 확인합니다
3. Notion에서 올바른 값을 복사해서 붙여넣습니다
4. 서버를 재시작합니다

---

## 📱 QR 코드로 제공하기

### 로컬 테스트 완료 후:

1. **ngrok 설치** (외부 접속을 위해)
   - https://ngrok.com 에서 다운로드
   
2. **ngrok 실행**
   ```bash
   ngrok http 5000
   ```
   
3. **생성된 URL 확인**
   ```
   Forwarding: https://abc123.ngrok.io -> http://localhost:5000
   ```
   
4. **QR 코드 생성**
   - https://www.qr-code-generator.com/ 접속
   - ngrok URL 입력 (예: https://abc123.ngrok.io)
   - QR 코드 다운로드
   
5. **매장에 게시**
   - "오늘의 커피 확인하기" 문구와 함께 QR 코드 부착
   - 손님들이 스캔하면 바로 접속됩니다!

---

## 💡 유용한 팁

### 자동 새로고침
페이지는 5분마다 자동으로 새로고침되므로 노션 DB를 업데이트하면 자동으로 반영됩니다.

### 서버 백그라운드 실행 (Linux/Mac)
```bash
nohup python app.py > server.log 2>&1 &
```

### 서버 중지
터미널에서 `Ctrl + C` 를 누르세요.

---

## 📞 도움이 더 필요하세요?

- **설정 문제:** `TROUBLESHOOTING.md` 참조
- **API 문제:** Notion 통합 설정 확인
- **기능 문의:** `README.md` 참조

---

## ✅ 체크리스트

시작하기 전에 확인하세요:

- [ ] Python 3.7 이상 설치됨
- [ ] `check_setup.py` 실행했고 모두 ✓ 표시
- [ ] Flask 서버가 실행 중 (터미널에 메시지 표시됨)
- [ ] 브라우저에서 `http://localhost:5000` 으로 접속함
- [ ] "오늘의 커피" 페이지가 정상적으로 표시됨

모든 항목에 체크가 되었다면 성공입니다! 🎉
