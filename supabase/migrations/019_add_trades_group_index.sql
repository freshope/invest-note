-- trades 그룹 조회 expression 인덱스
-- list_trades_in_group (모든 mutation 핫패스: create/patch/delete/bulk-delete/import) 의
-- WHERE 절과 동일한 표현식으로 인덱스를 만들어 Seq Scan + Filter 를 Index Scan 으로 전환한다.
--
-- 대상 쿼리 (db_ops/trades_repo.py: list_trades_in_group):
--   WHERE user_id = $1 AND account_id = $2
--     AND COALESCE(NULLIF(ticker_symbol, ''), asset_name) = $3
--     AND COALESCE(NULLIF(country_code, ''), 'KR') = $4
--   ORDER BY traded_at ASC
--
-- COALESCE(NULLIF(...)) 표현식은 일반 b-tree(trades_account_id_idx)로 닿지 않아
-- account 까지만 좁힌 뒤 나머지는 행을 메모리에서 필터한다. 인덱스 표현식은
-- 쿼리와 텍스트가 일치해야 planner 가 채택하므로 동일하게 작성한다.
-- 마지막 traded_at 컬럼은 그룹 내 ORDER BY ASC 를 인덱스로 커버한다.
create index trades_group_idx on trades (
  user_id,
  account_id,
  (COALESCE(NULLIF(ticker_symbol, ''), asset_name)),
  (COALESCE(NULLIF(country_code, ''), 'KR')),
  traded_at
);
