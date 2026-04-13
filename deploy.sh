#!/bin/bash
# cafe-today-coffee 자동 배포 (server-side)
# 호출: systemd timer (cafe-coffee-deploy.timer → .service)
# 동작: git fetch → reset --hard → pip install → restart (변경 있을 때만)
set -e
cd /root/92cafe/cafe-today-coffee

git fetch origin main --quiet
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

echo "[$(date -Iseconds)] 변경 감지: $LOCAL → $REMOTE"
git reset --hard origin/main

# requirements.txt가 변경되면 설치
if git diff --name-only "$LOCAL" HEAD | grep -q '^requirements.txt$'; then
  echo "requirements.txt 변경됨, pip install 실행"
  .venv/bin/pip install -r requirements.txt --quiet
fi

systemctl restart cafe-coffee.service
echo "[$(date -Iseconds)] 재시작 완료"
