-- 92도씨 회원 — 시크릿 QR 초대 가입 + 구글 로그인 (1단계: 로그인 뼈대)
-- 적용: cd worker && node_modules/.bin/wrangler d1 execute cafe-coffee --remote --file ../scripts/members_schema.sql
-- 멱등(IF NOT EXISTS) — 여러 번 돌려도 안전하다.

-- 회원. 구글 계정 하나당 한 행(google_sub 이 진짜 키, 이메일은 바뀔 수 있어 참고용).
CREATE TABLE IF NOT EXISTS members (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  google_sub    TEXT NOT NULL UNIQUE,       -- 구글 계정 고유 id (재사용되지 않음)
  email         TEXT,
  name          TEXT,                        -- 구글 프로필 이름
  picture       TEXT,                        -- 구글 프로필 사진 URL
  nickname      TEXT,                        -- 매장에서 부르는 이름 (본인이 정함)
  invite_code   TEXT,                        -- 가입에 쓴 초대 코드 (어느 카드로 들어왔는지)
  status        TEXT NOT NULL DEFAULT '활성', -- 활성 | 정지
  joined_at     TEXT NOT NULL,
  last_login_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_members_email  ON members(email);
CREATE INDEX IF NOT EXISTS idx_members_joined ON members(joined_at);

-- 시크릿 QR 카드에 인쇄되는 초대 코드. 가입은 이 코드가 있어야만 된다(1인 1회 소진).
CREATE TABLE IF NOT EXISTS invite_codes (
  code        TEXT PRIMARY KEY,             -- 대문자 영숫자 10자 (혼동 글자 I,O,0,1 제외)
  batch       TEXT,                          -- 인쇄 묶음 이름 ('2026-09-1차')
  note        TEXT,
  created_at  TEXT NOT NULL,
  expires_at  TEXT,                          -- NULL 이면 무기한
  redeemed_by INTEGER REFERENCES members(id),
  redeemed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_invite_batch    ON invite_codes(batch);
CREATE INDEX IF NOT EXISTS idx_invite_redeemed ON invite_codes(redeemed_by);
