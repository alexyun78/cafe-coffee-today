-- 회원 3단계 — 원두 감상 (좋아요 / 중간 / 싫어요 + 감상평)
-- 적용: cd worker && node_modules/.bin/wrangler d1 execute cafe-coffee --remote --file ../scripts/members_notes_migration.sql
-- 멱등.
--
-- 맛본 날짜는 이미 bean_unlocks.unlocked_at 에 있다 (QR 을 찍은 시각).
-- 감상은 그 원두를 실제로 찍은 사람만 쓸 수 있고, 본인만 볼 수 있다.
-- 관리자만 전체를 모아 볼 수 있다 (GET /api/member/admin/notes).

CREATE TABLE IF NOT EXISTS bean_notes (
  member_id  INTEGER NOT NULL REFERENCES members(id),
  bean_id    TEXT NOT NULL,
  rating     TEXT,                      -- 좋아요 | 중간 | 싫어요 (NULL 이면 별점 없이 글만)
  body       TEXT,                      -- 감상평 (본인만 열람)
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (member_id, bean_id)
);
CREATE INDEX IF NOT EXISTS idx_notes_bean    ON bean_notes(bean_id);
CREATE INDEX IF NOT EXISTS idx_notes_updated ON bean_notes(updated_at);
