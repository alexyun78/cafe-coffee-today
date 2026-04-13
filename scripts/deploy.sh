#!/usr/bin/env bash
# deploy.sh — 서버의 자동 배포 타이머를 즉시 트리거.
#
# 일반 플로우: git push → 최대 60초 내 서버가 자동으로 pull + restart.
# 이 스크립트: 기다리기 싫을 때 즉시 트리거.
#
# 사용:
#   bash scripts/deploy.sh           # 즉시 배포 트리거 + 로그
#   bash scripts/deploy.sh --restart # 앱 강제 재시작만 (git pull 없음)
set -e

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

case "${1:-}" in
  --restart)
    echo "==> 앱 강제 재시작 (git pull 건너뜀)"
    $SSH "systemctl restart cafe-coffee.service && systemctl --no-pager status cafe-coffee.service | head -10"
    ;;
  *)
    echo "==> 원격 저장소 HEAD 확인"
    REMOTE_HEAD=$(git rev-parse origin/main 2>/dev/null || echo "unknown")
    echo "   origin/main: $REMOTE_HEAD"

    echo "==> 서버의 cafe-coffee-deploy.service 즉시 실행"
    $SSH "systemctl start cafe-coffee-deploy.service && sleep 2 && journalctl -u cafe-coffee-deploy.service -n 15 --no-pager"

    echo ""
    echo "==> 앱 상태"
    $SSH "systemctl --no-pager is-active cafe-coffee.service && git -C /root/92cafe/cafe-today-coffee rev-parse --short HEAD"
    ;;
esac

echo ""
echo "완료. 확인:"
echo "  curl http://$HOST:3002/api/coffee | head"
