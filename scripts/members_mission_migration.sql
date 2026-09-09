-- 회원 2단계 — 미션 원두(시크릿 카드)와 해금 기록
-- 적용: cd worker && node_modules/.bin/wrangler d1 execute cafe-coffee --remote --file ../scripts/members_mission_migration.sql
-- 멱등. invite_codes.bean_id 는 ALTER 라 두 번째 실행에서 "duplicate column" 이 나는데,
-- 그건 이미 적용됐다는 뜻이므로 그 에러만 무시하면 된다.

-- 시크릿으로 잠글 원두. bean_id = static/beans/index.json 의 항목 id (ASCII slug).
-- 여기 없는 원두는 지금처럼 누구에게나 공개된다.
CREATE TABLE IF NOT EXISTS bean_missions (
  bean_id    TEXT PRIMARY KEY,
  sort_order INTEGER NOT NULL DEFAULT 0,   -- 마이페이지 그리드 순서
  active     INTEGER NOT NULL DEFAULT 1,   -- 0 이면 잠금 해제 (다시 공개)
  created_at TEXT NOT NULL
);

-- 회원이 연 원두. 카드 QR 한 장이 원두 하나를 연다.
CREATE TABLE IF NOT EXISTS bean_unlocks (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  member_id   INTEGER NOT NULL REFERENCES members(id),
  bean_id     TEXT NOT NULL,
  invite_code TEXT,                        -- 어느 카드로 열었는지
  unlocked_at TEXT NOT NULL,
  UNIQUE (member_id, bean_id)
);
CREATE INDEX IF NOT EXISTS idx_unlocks_member ON bean_unlocks(member_id);
CREATE INDEX IF NOT EXISTS idx_unlocks_bean   ON bean_unlocks(bean_id);

-- 초대 코드에 원두를 묶는다. QR 한 장 = 초대장이자 그 원두의 열쇠.
-- bean_id 가 NULL 인 코드는 원두 없이 가입만 시키는 순수 초대장이다.
ALTER TABLE invite_codes ADD COLUMN bean_id TEXT;
