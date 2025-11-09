# 오늘의 커피 웹 앱

카페의 "오늘의 커피" 정보를 손님들에게 QR 코드로 제공하는 웹 애플리케이션입니다.

## 🚀 빠른 시작

### 1️⃣ 설정 검증 (권장)
먼저 모든 것이 올바르게 설정되었는지 확인하세요:
```bash
python check_setup.py
```

### 2️⃣ 서버 실행
**Windows:**
```cmd
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

**또는 수동 실행:**
```bash
pip install -r requirements.txt
python app.py
```

### 3️⃣ 브라우저에서 접속
```
http://localhost:5000
```

⚠️ **중요:** `index.html` 파일을 직접 열지 마세요! 반드시 위 주소로 접속해야 합니다.

---

## 📋 기능

- **오늘의 커피**: 현재 제공 중인 커피 정보를 카드 형태로 표시
- **커피 히스토리**: 과거 제공된 커피들의 목록을 테이블로 표시
- **자동 정렬**: 제공일 최신순 → 로스팅일 최신순으로 자동 정렬
- **자동 새로고침**: 5분마다 자동으로 최신 정보 업데이트
- **반응형 디자인**: 모바일, 태블릿, PC 모두 최적화

## 🚀 설치 및 실행 방법

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 서버 실행

```bash
python app.py
```

서버가 시작되면 다음 주소로 접속:
- http://localhost:5000

### 3. 외부 접속 설정 (QR 코드용)

외부에서 접속하려면 다음 중 하나를 선택하세요:

#### 방법 A: ngrok 사용 (추천)
```bash
# ngrok 설치 (https://ngrok.com)
ngrok http 5000
```

생성된 URL로 QR 코드를 만들어 손님들에게 제공하세요.

#### 방법 B: 서버에 배포
- AWS, Google Cloud, Azure 등의 클라우드 서버에 배포
- 도메인 연결 후 QR 코드 생성

## 📁 파일 구조

```
.
├── app.py              # Flask 백엔드 서버
├── index.html          # 프론트엔드 (HTML/CSS/JS 통합)
├── requirements.txt    # Python 패키지 의존성
└── README.md          # 설명서
```

## 🔧 설정

### Notion API 정보 변경
`app.py` 파일에서 다음 정보를 수정하세요:

```python
NOTION_TOKEN = "your_notion_token_here"
DATABASE_ID = "your_database_id_here"
```

### 포트 변경
기본 포트는 5000입니다. 변경하려면 `app.py` 마지막 줄 수정:

```python
app.run(host='0.0.0.0', port=원하는포트번호, debug=True)
```

## 🎨 커스터마이징

### 색상 변경
`index.html`의 `<style>` 섹션에서 색상 코드를 수정하세요:

```css
.header h1 {
    color: #6F4E37;  /* 커피 브라운 색상 */
}
```

### 자동 새로고침 주기 변경
`index.html` 하단의 JavaScript에서 수정:

```javascript
// 5분(300000ms)을 원하는 시간으로 변경
setInterval(loadCoffeeData, 5 * 60 * 1000);
```

## 📱 QR 코드 생성

1. 서버를 실행하고 외부 접속 URL을 확보
2. QR 코드 생성 사이트 이용:
   - https://www.qr-code-generator.com/
   - https://www.the-qrcode-generator.com/
3. URL을 입력하고 QR 코드 다운로드
4. 매장에 QR 코드 게시

## 🔍 트러블슈팅

### "Failed to fetch" 오류가 발생하나요?

이 오류는 Flask 서버가 실행되지 않았거나 HTML 파일을 직접 열어서 발생합니다.

**해결 방법:**
1. 터미널에서 `python app.py` 명령으로 서버를 먼저 실행하세요
2. 브라우저에서 `http://localhost:5000` 으로 접속하세요 (파일 직접 열기 ❌)

자세한 문제 해결 방법은 **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** 파일을 참조하세요.

### 포트가 이미 사용 중일 때
```bash
# 다른 포트로 실행 (예: 8080)
# app.py에서 port=8080으로 변경 후 실행
```

### Notion API 오류
- Notion Token이 올바른지 확인
- Database ID가 정확한지 확인
- Notion 통합(Integration)이 데이터베이스에 연결되어 있는지 확인

### CORS 오류
- Flask-CORS가 설치되어 있는지 확인
- `pip install flask-cors`로 재설치

## 💡 유용한 팁

1. **운영 서버 배포 시**: `debug=False`로 변경
2. **HTTPS 사용**: SSL 인증서 적용 권장 (Let's Encrypt 무료)
3. **성능 최적화**: Gunicorn이나 uWSGI 같은 프로덕션 서버 사용

## 📞 문의

문제가 발생하면 Notion 데이터베이스 구조와 에러 메시지를 확인하세요.
