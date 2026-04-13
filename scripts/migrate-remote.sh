#!/usr/bin/env bash
# migrate-remote.sh — 로컬의 SQLite DB를 서버로 푸시.
#
# 언제 쓰는가:
#   - 최초 배포 후 로컬에서 Notion 마이그레이션을 돌린 결과를 서버로 올릴 때
#   - 서버 DB를 로컬 스냅샷으로 덮어쓸 때 (주의: 서버 쪽 변경사항 손실)
#
# 사용:
#   bash scripts/migrate-remote.sh push   # 로컬 → 서버 (덮어쓰기, 백업 후)
#   bash scripts/migrate-remote.sh pull   # 서버 → 로컬 (덮어쓰기)
set -e

if [ ! -f .env ]; then
  echo "ERROR: .env 파일을 찾을 수 없습니다."
  exit 1
fi
set -a; source .env; set +a
: "${HOST:?}"; : "${ID:?}"; : "${PASSWORD:?}"

HOSTKEY="SHA256:Sx4sZ7vZuxxRTEabRiapTqjZuNx2Omi8VTezM9qIq+E"
SSH="plink -ssh -batch -hostkey $HOSTKEY -pw $PASSWORD $ID@$HOST"
SCP="pscp -batch -hostkey $HOSTKEY -pw $PASSWORD"

REMOTE_DB="/root/92cafe/cafe-today-coffee/data/coffee.db"
LOCAL_DB="data/coffee.db"

case "${1:-}" in
  push)
    if [ ! -f "$LOCAL_DB" ]; then
      echo "ERROR: 로컬 $LOCAL_DB 가 없습니다."
      exit 1
    fi
    TS=$(date +%Y%m%d-%H%M%S)
    echo "==> 서버 기존 DB 백업 ($TS)"
    $SSH "[ -f $REMOTE_DB ] && cp $REMOTE_DB /root/92cafe/cafe-today-coffee/data/backup/coffee-pre-$TS.db || echo '기존 DB 없음'"
    echo "==> 앱 중지"
    $SSH "systemctl stop cafe-coffee.service"
    echo "==> 로컬 DB 업로드: $LOCAL_DB -> $REMOTE_DB"
    $SCP "$LOCAL_DB" "$ID@$HOST:$REMOTE_DB"
    echo "==> 앱 재시작"
    $SSH "systemctl start cafe-coffee.service"
    echo "완료"
    ;;
  pull)
    TS=$(date +%Y%m%d-%H%M%S)
    mkdir -p data/backup
    if [ -f "$LOCAL_DB" ]; then
      cp "$LOCAL_DB" "data/backup/coffee-pre-$TS.db"
      echo "로컬 DB 백업: data/backup/coffee-pre-$TS.db"
    fi
    echo "==> 서버 DB 다운로드"
    $SCP "$ID@$HOST:$REMOTE_DB" "$LOCAL_DB"
    echo "완료: $LOCAL_DB"
    ;;
  *)
    echo "사용: $0 [push|pull]"
    exit 1
    ;;
esac
