-- green_beans 에 품절 플래그 추가 — 2026-09-01
--
-- 실행 (1회):
--   cd worker && node_modules/.bin/wrangler d1 execute cafe-coffee --remote --file ../scripts/sold_out_migration.sql
--
-- ⚠️ ALTER TABLE ADD COLUMN 은 멱등이 아니다. 이미 적용된 DB 에 다시 돌리면
--    "duplicate column name: sold_out" 로 실패한다(그 경우 무시하면 된다).
--
-- 왜 status 를 재활용하지 않았나:
--   green_beans.status 는 이미 활성/단종(소프트 삭제)으로 쓰이고 있고,
--   생두 목록과 재고 조회가 WHERE gb.status='활성' 로 거른다.
--   status 에 '품절' 을 넣으면 품절된 생두가 목록에서 통째로 사라진다.
--   품절은 "목록에 있되 지금 안 파는 상태" 라 별도 플래그가 맞다.

ALTER TABLE green_beans ADD COLUMN sold_out INTEGER NOT NULL DEFAULT 0;
