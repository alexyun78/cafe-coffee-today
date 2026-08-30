-- 원두 종류 정합성 복구 — 2026-08-31
--
-- 배경: bean_type 도입 직후(첫 배포)에는 로스팅 폼의 '원두 사용 타입'이 배치별로만 저장되어
--       생두 마스터로 올라가지 않았다. 그래서 "로스팅 기록에서 블랜드로 지정했는데
--       생두/재고/구매에는 싱글로 보인다"는 어긋남이 생겼다.
--       두 번째 배포부터는 어디서 바꾸든 생두 마스터에 write-through 되지만,
--       그 사이에 남은 기존 데이터는 아래로 한 번 맞춰준다.
--
-- 실행 (1회):
--   cd worker && node_modules/.bin/wrangler d1 execute cafe-coffee --remote --file ../scripts/bean_type_reconcile.sql
--
-- 멱등: 여러 번 돌려도 결과가 같다.

-- 1) 로스팅 기록에서 지정한 종류를 생두 마스터로 끌어올린다 (블랜드 우선)
UPDATE green_beans
   SET bean_type = '블랜드', is_decaf = 0,
       updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
 WHERE bean_type <> '블랜드'
   AND EXISTS (SELECT 1 FROM roasting_logs r
                WHERE r.green_bean_id = green_beans.id AND r.usage_type = '블랜드');

UPDATE green_beans
   SET bean_type = '디카페인', is_decaf = 1,
       updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
 WHERE bean_type = '싱글'
   AND EXISTS (SELECT 1 FROM roasting_logs r
                WHERE r.green_bean_id = green_beans.id AND r.usage_type = '디카페인');

-- 2) 생두 종류를 유일한 창구로 삼아 그 생두의 모든 로스팅 기록을 통일
UPDATE roasting_logs
   SET usage_type = (SELECT gb.bean_type FROM green_beans gb WHERE gb.id = roasting_logs.green_bean_id)
 WHERE EXISTS (SELECT 1 FROM green_beans gb
                WHERE gb.id = roasting_logs.green_bean_id AND gb.bean_type <> roasting_logs.usage_type);

-- 3) 블랜드 생두는 오늘의 커피 연동 불가 — 남아 있는 연동 플래그를 모두 해제
UPDATE roasting_logs
   SET make_coffee = 0
 WHERE make_coffee <> 0
   AND green_bean_id IN (SELECT id FROM green_beans WHERE bean_type = '블랜드');
