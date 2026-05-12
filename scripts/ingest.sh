#!/bin/bash
# 서버 측 일일 Coffee Insight 인제스트
# 호출: systemd timer (cafe-coffee-ingest.timer → .service), 매일 21:00 KST
# 동작: git pull → ingest_insights.py → git add/commit/push
#
# 사전 조건 (.env 또는 systemd EnvironmentFile):
#   GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN
#   INGEST_GITHUB_TOKEN  — push 권한이 있는 fine-grained PAT
set -e

REPO_ROOT=/root/92cafe/cafe-today-coffee
cd "$REPO_ROOT"

# deploy.sh 와 락 공유. 우리가 commit/push 하는 동안
# deploy.sh 가 `git reset --hard origin/main` 으로 우리 commit 을
# 날리지 않도록 보호.
exec 9>/var/lock/cafe-coffee-ops.lock
if ! flock -w 120 9; then
  echo "[ingest] $(date -Iseconds) flock 획득 실패 (120s) — skip"
  exit 0
fi

echo "[ingest] $(date -Iseconds) 시작"

# 1) 원격 최신 상태로
git fetch origin main --quiet
git reset --hard origin/main --quiet

# 2) python 의존성 확인 (없으면 설치 — 멱등)
if ! .venv/bin/python -c "import jinja2, fitz" 2>/dev/null; then
  echo "[ingest] jinja2 / PyMuPDF 설치"
  .venv/bin/pip install --quiet jinja2==3.1.4 PyMuPDF==1.24.10
fi

# 3) 인제스트 실행 (env 는 systemd 가 EnvironmentFile 로 주입)
.venv/bin/python scripts/ingest_insights.py

# 4) 변경 있으면 commit + push
git add static/insights/ 2>/dev/null || true
if [ -d static/img/insights/articles ]; then
  git add static/img/insights/articles/ 2>/dev/null || true
fi

if git diff --cached --quiet; then
  echo "[ingest] 변경 없음 — commit skip"
  exit 0
fi

TODAY=$(date -u +"%Y-%m-%d")
git -c user.name="cafe-coffee-ingest" \
    -c user.email="ingest@cafe-coffee.local" \
    commit -m "chore(insights): ingest daily coffee insight (${TODAY})" --quiet

# push 토큰 확인
if [ -z "${INGEST_GITHUB_TOKEN:-}" ]; then
  echo "[ingest] ERROR: INGEST_GITHUB_TOKEN 미설정 — push 불가."
  echo "[ingest] 로컬 commit 은 다음 deploy timer 의 reset --hard 로 사라질 수 있음."
  exit 1
fi

# token 은 임시 URL 로만 사용. .git/config 에 영구 저장 안 됨.
git push "https://x-access-token:${INGEST_GITHUB_TOKEN}@github.com/alexyun78/cafe-coffee-today.git" HEAD:main --quiet
echo "[ingest] $(date -Iseconds) push 완료"
