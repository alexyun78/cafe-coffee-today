#!/usr/bin/env bash
# bootstrap-server.sh — 49.247.207.115에 cafe-today-coffee를 최초 설치.
#
# 필요:
#   - Windows Git Bash (또는 bash)
#   - plink + pscp (PuTTY 설치: https://www.chiark.greenend.org.uk/~sgtatham/putty/)
#   - .env 파일 (HOST, ID, PASSWORD, NOTION_TOKEN 등)
#   - Git 리포지토리가 이미 GitHub에 push되어 있어야 함
#
# 사용:
#   bash scripts/bootstrap-server.sh https://github.com/<user>/<repo>.git
#
# 이 스크립트는 한 번만 실행. 이후 배포는 systemd 타이머가 자동 처리.
set -e

REPO_URL="${1:-}"
if [ -z "$REPO_URL" ]; then
  echo "사용법: bash scripts/bootstrap-server.sh <git-repo-url>"
  exit 1
fi

# .env 로드
if [ ! -f .env ]; then
  echo "ERROR: .env 파일을 찾을 수 없습니다. 프로젝트 루트에서 실행하세요."
  exit 1
fi
set -a; source .env; set +a

: "${HOST:?HOST가 .env에 없습니다}"
: "${ID:?ID가 .env에 없습니다}"
: "${PASSWORD:?PASSWORD가 .env에 없습니다}"

HOSTKEY="SHA256:Sx4sZ7vZuxxRTEabRiapTqjZuNx2Omi8VTezM9qIq+E"
SSH="plink -ssh -batch -hostkey $HOSTKEY -pw $PASSWORD $ID@$HOST"
SCP="pscp -batch -hostkey $HOSTKEY -pw $PASSWORD"

echo "==> 서버 연결 확인: $HOST"
$SSH "echo connected: \$(hostname)"

echo "==> /root/92cafe 디렉토리 확보"
$SSH "mkdir -p /root/92cafe"

echo "==> 기존 설치 확인"
EXISTS=$($SSH "[ -d /root/92cafe/cafe-today-coffee/.git ] && echo yes || echo no")
if [ "$EXISTS" = "yes" ]; then
  echo "   이미 설치됨. git pull로 갱신합니다."
  $SSH "cd /root/92cafe/cafe-today-coffee && git fetch origin main && git reset --hard origin/main"
else
  echo "   신규 클론: $REPO_URL"
  $SSH "cd /root/92cafe && git clone $REPO_URL cafe-today-coffee"
fi

echo "==> Python venv + 의존성"
$SSH "cd /root/92cafe/cafe-today-coffee && \
    (python3 -m venv .venv 2>/dev/null || true) && \
    .venv/bin/pip install --quiet --upgrade pip && \
    .venv/bin/pip install --quiet -r requirements.txt"

echo "==> .env 업로드 (서버에는 .env가 없으므로 로컬 파일 복사)"
$SCP .env "$ID@$HOST:/root/92cafe/cafe-today-coffee/.env"

echo "==> data/ 디렉토리 및 권한"
$SSH "mkdir -p /root/92cafe/cafe-today-coffee/data/backup && chmod 700 /root/92cafe/cafe-today-coffee/data"

echo "==> 로컬 DB 업로드 (있으면)"
if [ -f data/coffee.db ]; then
  $SCP data/coffee.db "$ID@$HOST:/root/92cafe/cafe-today-coffee/data/coffee.db"
  echo "   data/coffee.db 업로드 완료"
else
  echo "   data/coffee.db 없음, 서버에서 빈 DB로 시작됨. 나중에 migrate_notion.py 필요할 수 있음."
fi

echo "==> systemd 유닛 설치"
$SSH "cp /root/92cafe/cafe-today-coffee/systemd/cafe-coffee.service /etc/systemd/system/ && \
      cp /root/92cafe/cafe-today-coffee/systemd/cafe-coffee-deploy.service /etc/systemd/system/ && \
      cp /root/92cafe/cafe-today-coffee/systemd/cafe-coffee-deploy.timer /etc/systemd/system/ && \
      chmod +x /root/92cafe/cafe-today-coffee/deploy.sh && \
      systemctl daemon-reload && \
      systemctl enable --now cafe-coffee.service && \
      systemctl enable --now cafe-coffee-deploy.timer"

echo "==> 상태 확인"
$SSH "systemctl --no-pager is-active cafe-coffee.service"
$SSH "systemctl --no-pager list-timers cafe-coffee-deploy.timer | head -5"

echo ""
echo "완료. 다음 단계:"
echo "  - 상태 로그:  plink -ssh -pw '***' $ID@$HOST 'journalctl -u cafe-coffee -n 30'"
echo "  - API 확인:  curl http://$HOST:3002/api/coffee"
echo "  - 관리 페이지: http://$HOST:3002/admin (PIN은 .env의 ADMIN_PIN)"
echo "  - 이후 배포: git push → 60초 내 자동 반영. 강제 트리거: bash scripts/deploy.sh"
