#!/bin/bash
# cafe-today-coffee 자동 배포 (server-side)
# 호출: systemd timer (cafe-coffee-deploy.timer → .service)
# 동작: git fetch → reset --hard → pip install → restart (변경 있을 때만)
set -e
cd /root/92cafe/cafe-today-coffee

# ingest.sh 와 락 공유. 인제스트가 commit/push 도중이면
# 그 사이에 reset --hard 가 끼어들어 commit 을 날리지 않게 skip.
exec 9>/var/lock/cafe-coffee-ops.lock
flock -n 9 || exit 0

git fetch origin main --quiet
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

# 로컬이 원격보다 앞서 있으면(아직 push 안 된 commit) reset 금지.
# 예: ingest.sh 가 commit 까지 했고 push 직전인 짧은 창에 deploy 가 끼어든 경우.
BASE=$(git merge-base HEAD origin/main)
if [ "$BASE" = "$REMOTE" ] && [ "$BASE" != "$LOCAL" ]; then
  echo "[$(date -Iseconds)] 로컬이 원격보다 앞섬 — push 대기 commit 추정, skip"
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
