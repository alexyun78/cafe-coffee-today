#!/bin/bash

echo "================================"
echo "오늘의 커피 웹 앱 시작"
echo "================================"
echo ""

# 패키지 설치 확인
if ! python3 -c "import flask" 2>/dev/null; then
    echo "필요한 패키지를 설치합니다..."
    pip install -r requirements.txt
    echo ""
fi

# 서버 실행
echo "서버를 시작합니다..."
echo "접속 주소: http://localhost:5000"
echo ""
echo "종료하려면 Ctrl+C를 누르세요."
echo ""

python3 app.py
