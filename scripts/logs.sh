#!/usr/bin/env bash
# logs.sh — 서버 로그 조회.
#
# 사용:
#   bash scripts/logs.sh         # 앱 로그 마지막 50줄
#   bash scripts/logs.sh deploy  # 배포 로그 마지막 30줄
#   bash scripts/logs.sh follow  # 실시간 스트리밍 (Ctrl+C 종료)
set -e

if [ ! -f .env ]; then
  echo "ERROR: .env 파일을 찾을 수 없습니다. 프로젝트 루트에서 실행하세요."
  exit 1
fi
set -a; source .env; set +a
: "${HOST:?}"; : "${ID:?}"; : "${PASSWORD:?}"

HOSTKEY="SHA256:Sx4sZ7vZuxxRTEabRiapTqjZuNx2Omi8VTezM9qIq+E"
SSH="plink -ssh -batch -hostkey $HOSTKEY -pw $PASSWORD $ID@$HOST"

case "${1:-app}" in
  app|"")
    $SSH "journalctl -u cafe-coffee.service -n 50 --no-pager"
    ;;
  deploy)
    $SSH "journalctl -u cafe-coffee-deploy.service -n 30 --no-pager"
    ;;
  follow|f|tail)
    echo "실시간 로그 (Ctrl+C 종료)..."
    $SSH "journalctl -u cafe-coffee.service -f"
    ;;
  status|s)
    $SSH "systemctl --no-pager status cafe-coffee.service cafe-coffee-deploy.timer"
    ;;
  *)
    echo "사용: $0 [app|deploy|follow|status]"
    exit 1
    ;;
esac
