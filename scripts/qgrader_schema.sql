-- Q 그레이더 훈련 관리 — D1 스키마
-- 적용: worker/node_modules/.bin/wrangler d1 execute cafe-coffee --remote --file ../scripts/qgrader_schema.sql
-- 멱등(IF NOT EXISTS). 커리큘럼 계열 테이블은 scripts/qgrader_sync.py 가 md 에서 다시 채운다.

-- 커리큘럼 원문 보관 (학습플랜 md 스냅샷 — 개정될 때마다 새 버전 행)
CREATE TABLE IF NOT EXISTS qg_curriculum (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  version    TEXT NOT NULL UNIQUE,      -- 원문 해시 앞 12자
  source     TEXT,                      -- 원본 파일 경로
  title      TEXT,
  body_md    TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- 6개월 로드맵 (월별 테마/활동/월말 목표)
CREATE TABLE IF NOT EXISTS qg_roadmap (
  month      TEXT PRIMARY KEY,          -- 'YYYY-MM'
  label      TEXT,                      -- 'M1' 등
  period     TEXT,                      -- 원문 표기 ('8월 (M1)')
  theme      TEXT,
  activities TEXT,
  goal       TEXT,
  sort_order INTEGER NOT NULL
);

-- 월별 수치 목표 (지표별) — 차트 기준선
CREATE TABLE IF NOT EXISTS qg_targets (
  metric TEXT NOT NULL,                 -- aroma | acid | tri | defect | written
  month  TEXT NOT NULL,                 -- 'YYYY-MM'
  value  REAL NOT NULL,
  note   TEXT,
  PRIMARY KEY (metric, month)
);

-- 주간 루틴 항목 정의 (md '일일·주간 훈련 루틴' 에서 생성)
CREATE TABLE IF NOT EXISTS qg_routine_items (
  id         INTEGER PRIMARY KEY,
  label      TEXT NOT NULL,
  cadence    TEXT,                      -- daily | weekly
  detail     TEXT,
  sort_order INTEGER NOT NULL,
  active     INTEGER NOT NULL DEFAULT 1
);

-- md 의 참고 표들 (시험 개요·평가 컴포넌트·준비물·유기산·희석 레시피·링크·초기 할 일)
CREATE TABLE IF NOT EXISTS qg_reference (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  section    TEXT NOT NULL,             -- exam | components | materials | acids | dilution | todo | links
  sort_order INTEGER NOT NULL,
  data       TEXT NOT NULL              -- JSON 한 행
);
CREATE INDEX IF NOT EXISTS idx_qg_reference_section ON qg_reference(section, sort_order);

-- ===== 사용자가 쌓는 데이터 (seed 로 절대 지우지 않는다) =====

-- 훈련 일지 — 하루 1행 (UPSERT)
CREATE TABLE IF NOT EXISTS qg_logs (
  date       TEXT PRIMARY KEY,          -- KST 'YYYY-MM-DD'
  aroma      INTEGER,                   -- 정답 수 /36
  acid       REAL,                      -- 유기산 정답률 %
  tri        INTEGER,                   -- 삼각 테스트 정답 /6
  cup        INTEGER,                   -- 커핑 세션 수
  defect     REAL,                      -- 생두 결함 분류 정확도 %
  written    REAL,                      -- 모의 필기 점수
  minutes    INTEGER,                   -- 총 훈련 시간(분)
  note       TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_qg_logs_date ON qg_logs(date DESC);

-- 주간 루틴 체크 (주 시작 = 월요일)
CREATE TABLE IF NOT EXISTS qg_routine_checks (
  week       TEXT NOT NULL,             -- 'YYYY-MM-DD' (월요일)
  item_id    INTEGER NOT NULL,
  done       INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (week, item_id)
);

-- 설정 (exam_date 등)
CREATE TABLE IF NOT EXISTS qg_settings (
  key        TEXT PRIMARY KEY,
  value      TEXT,
  updated_at TEXT NOT NULL
);
