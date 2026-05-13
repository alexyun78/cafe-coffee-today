#!/usr/bin/env bash
# ingest-now.sh — 서버의 cafe-coffee-ingest.service 를 즉시 트리거.
#
# 정상 플로우: 매일 21:00 KST 에 systemd timer 가 자동 실행.
# 이 스크립트: 그 사이에 Drive 에 sidecar 가 새로 올라왔거나, 21:00 인제스트가 sidecar 가 늦게 도착해 놓친 날 따라잡기용.
#
# 사용 (Git Bash):
#   bash scripts/ingest-now.sh        # 프로젝트 루트에서
#   bash ./ingest-now.sh              # scripts/ 안에서도 OK (자동으로 루트로 이동)
set -e

# 어디서 호출되든 프로젝트 루트로 이동 (이 스크립트는 scripts/ 아래 있음)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

if [ ! -f .env ]; then
  echo "ERROR: .env 파일을 찾을 수 없습니다. ($PWD)"
  exit 1
fi
set -a; source .env; set +a

: "${HOST:?HOST가 .env에 없습니다}"
: "${ID:?ID가 .env에 없습니다}"
: "${PASSWORD:?PASSWORD가 .env에 없습니다}"

HOSTKEY="SHA256:Sx4sZ7vZuxxRTEabRiapTqjZuNx2Omi8VTezM9qIq+E"
SSH="plink -ssh -batch -hostkey $HOSTKEY -pw $PASSWORD $ID@$HOST"

echo "==> 서버의 cafe-coffee-ingest.service 즉시 실행"
$SSH "systemctl start cafe-coffee-ingest.service && sleep 3 && journalctl -u cafe-coffee-ingest.service -n 40 --no-pager"

echo ""
echo "==> 인제스트가 push 했다면 ~60초 내 deploy timer 가 자동으로 따라옴."
echo "    즉시 확인: curl http://$HOST:3002/api/insights | head"
