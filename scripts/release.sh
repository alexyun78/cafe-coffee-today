#!/bin/bash
# 서버 측 일일 Coffee Insight 백로그 릴리스 (토큰 0 경로)
# 호출: systemd timer (cafe-coffee-release.timer → .service), 매일 20:30 KST
# 동작: git pull → release_insight.py(큐에서 1편 발행, LLM 호출 없음) → git add/commit/push
#
# 사전 조건 (.env 또는 systemd EnvironmentFile):
#   INGEST_GITHUB_TOKEN  — push 권한이 있는 fine-grained PAT (기존 재사용)
#   (ANTHROPIC_API_KEY 불필요 — 이 경로는 API 를 호출하지 않는다)
set -e

REPO_ROOT=/root/92cafe/cafe-today-coffee
cd "$REPO_ROOT"

# deploy.sh / generate.sh / ingest.sh 와 같은 락 공유 — git reset --hard 충돌 방지
exec 9>/var/lock/cafe-coffee-ops.lock
if ! flock -w 120 9; then
  echo "[release] $(date -Iseconds) flock 획득 실패 (120s) — skip"
  exit 0
fi

echo "[release] $(date -Iseconds) 시작"

# 1) 원격 최신 상태로
git fetch origin main --quiet
git reset --hard origin/main --quiet

# 2) python 의존성 확인 (jinja2 만 필요 — 없으면 설치, 멱등)
if ! .venv/bin/python -c "import jinja2" 2>/dev/null; then
  echo "[release] jinja2 설치"
  .venv/bin/pip install --quiet jinja2==3.1.4
fi

# 3) 릴리스 실행 (큐에서 1편 → 오늘 날짜로 렌더 + index 갱신 + 큐에서 삭제)
.venv/bin/python scripts/release_insight.py

# 4) 변경 있으면 commit + push (발행한 html/json + 큐 파일 삭제 모두 포함)
git add static/insights/ content/insight_queue/ 2>/dev/null || true

if git diff --cached --quiet; then
  echo "[release] 변경 없음 — commit skip (이미 오늘 발행됐거나 큐가 빔)"
  exit 0
fi

TODAY=$(TZ=Asia/Seoul date +"%Y-%m-%d")
git -c user.name="cafe-coffee-release" \
    -c user.email="release@cafe-coffee.local" \
    commit -m "content(insights): 백로그 릴리스 일일 인사이트 (${TODAY})" --quiet

if [ -z "${INGEST_GITHUB_TOKEN:-}" ]; then
  echo "[release] ERROR: INGEST_GITHUB_TOKEN 미설정 — push 불가."
  exit 1
fi

git push "https://x-access-token:${INGEST_GITHUB_TOKEN}@github.com/alexyun78/cafe-coffee-today.git" HEAD:main --quiet
echo "[release] $(date -Iseconds) push 완료"
