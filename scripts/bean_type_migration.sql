-- green_beans 에 원두 종류(싱글 / 블랜드 / 디카페인) 컬럼 추가 — 2026-08-30
--
-- 실행 (1회):
--   cd worker && node_modules/.bin/wrangler d1 execute cafe-coffee --remote --file ../scripts/bean_type_migration.sql
--
-- ⚠️ ALTER TABLE ADD COLUMN 은 멱등이 아니다. 이미 적용된 DB 에 다시 돌리면
--    "duplicate column name: bean_type" 로 실패한다(그 경우 아래 UPDATE 만 따로 실행).
--
-- is_decaf 는 기존 코드/레거시 Flask 호환을 위해 남겨두고 API 가 bean_type 과 함께 동기화한다.
-- (bean_type='디카페인' ⇔ is_decaf=1)

ALTER TABLE green_beans ADD COLUMN bean_type TEXT NOT NULL DEFAULT '싱글';

-- 기존 디카페인 플래그 이관
UPDATE green_beans SET bean_type = '디카페인' WHERE is_decaf = 1;

-- 이름에 블랜드/블렌드가 들어간 생두는 블랜드로 초기 분류 (이후 관리 폼에서 수정 가능)
UPDATE green_beans
   SET bean_type = '블랜드'
 WHERE is_decaf = 0
   AND (name LIKE '%블랜드%' OR name LIKE '%블렌드%' OR name LIKE '%Blend%');

-- 로스팅 배치별 사용 타입. 관리 폼에 예전부터 있었지만 D1 에는 컬럼이 없어
-- 저장되지 않고 버려지고 있었다(레거시 Flask 스키마에만 존재). 여기서 맞춘다.
-- 기본값은 저장 시 생두의 bean_type 으로 채워지고, 배치 단위로 덮어쓸 수 있다.
ALTER TABLE roasting_logs ADD COLUMN usage_type TEXT NOT NULL DEFAULT '싱글';

UPDATE roasting_logs
   SET usage_type = (SELECT gb.bean_type FROM green_beans gb WHERE gb.id = roasting_logs.green_bean_id)
 WHERE EXISTS (SELECT 1 FROM green_beans gb WHERE gb.id = roasting_logs.green_bean_id);
