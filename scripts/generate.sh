#!/bin/bash
# 서버 측 일일 Coffee Insight 자체 생성 (Drive 비의존 경로)
# 호출: systemd timer (cafe-coffee-generate.timer → .service), 매일 20:30 KST
# 동작: git pull → generate_insight.py(Claude API+웹검색) → git add/commit/push
#
# 사전 조건 (.env 또는 systemd EnvironmentFile):
#   ANTHROPIC_API_KEY    — 필수
#   INGEST_GITHUB_TOKEN  — push 권한이 있는 fine-grained PAT
#   INSIGHT_MODEL        — 선택(기본 claude-opus-4-8)
set -e

REPO_ROOT=/root/92cafe/cafe-today-coffee
cd "$REPO_ROOT"

# deploy.sh / ingest.sh 와 같은 락 공유 — git reset --hard 충돌 방지
exec 9>/var/lock/cafe-coffee-ops.lock
if ! flock -w 120 9; then
  echo "[generate] $(date -Iseconds) flock 획득 실패 (120s) — skip"
  exit 0
fi

echo "[generate] $(date -Iseconds) 시작"

# 1) 원격 최신 상태로
git fetch origin main --quiet
git reset --hard origin/main --quiet

# 2) python 의존성 확인 (없으면 설치 — 멱등)
if ! .venv/bin/python -c "import jinja2, anthropic" 2>/dev/null; then
  echo "[generate] jinja2 / anthropic 설치"
  .venv/bin/pip install --quiet jinja2==3.1.4 anthropic
fi

# 3) 생성 실행 (env 는 systemd 가 EnvironmentFile 로 주입)
.venv/bin/python scripts/generate_insight.py

# 4) 변경 있으면 commit + push
git add static/insights/ 2>/dev/null || true

if git diff --cached --quiet; then
  echo "[generate] 변경 없음 — commit skip"
  exit 0
fi

TODAY=$(TZ=Asia/Seoul date +"%Y-%m-%d")
git -c user.name="cafe-coffee-generate" \
    -c user.email="generate@cafe-coffee.local" \
    commit -m "content(insights): 자체 생성 일일 인사이트 (${TODAY})" --quiet

if [ -z "${INGEST_GITHUB_TOKEN:-}" ]; then
  echo "[generate] ERROR: INGEST_GITHUB_TOKEN 미설정 — push 불가."
  exit 1
fi

git push "https://x-access-token:${INGEST_GITHUB_TOKEN}@github.com/alexyun78/cafe-coffee-today.git" HEAD:main --quiet
echo "[generate] $(date -Iseconds) push 완료"
