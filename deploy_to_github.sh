#!/bin/bash

echo "======================================"
echo "GitHub에 코드 업로드"
echo "======================================"
echo ""

# Git 설치 확인
if ! command -v git &> /dev/null; then
    echo "❌ Git이 설치되어 있지 않습니다."
    echo "   https://git-scm.com/downloads 에서 설치하세요."
    exit 1
fi

echo "✓ Git이 설치되어 있습니다."
echo ""

# Git 초기화 여부 확인
if [ ! -d .git ]; then
    echo "📦 Git 저장소를 초기화합니다..."
    git init
    echo ""
fi

# GitHub 사용자 정보 입력
echo "GitHub 저장소 정보를 입력하세요:"
echo ""
read -p "GitHub 사용자명: " username
read -p "저장소 이름 (예: cafe-today-coffee): " repo_name

# 원격 저장소 설정
echo ""
echo "🔗 원격 저장소를 연결합니다..."
git remote remove origin 2>/dev/null
git remote add origin "https://github.com/$username/$repo_name.git"

# 파일 추가
echo "📝 파일을 추가합니다..."
git add .

# 커밋
echo "💾 커밋합니다..."
git commit -m "Initial commit: 오늘의 커피 웹 앱"

# 푸시
echo "🚀 GitHub에 업로드합니다..."
git branch -M main
git push -u origin main

echo ""
echo "======================================"
echo "✅ 완료!"
echo "======================================"
echo ""
echo "다음 단계:"
echo "1. https://render.com 에 접속"
echo "2. GitHub 저장소 연결"
echo "3. 환경 변수 설정 (NOTION_TOKEN, DATABASE_ID)"
echo "4. 배포!"
echo ""
echo "자세한 내용은 RENDER_DEPLOY.md를 참조하세요."
