-- SELL `result` legacy NULL 백필
-- SOT 통합 이전 SELL row는 `result`가 NULL이라 분석(NULL 제외)과 summary(fallback) 사이에 dual-truth 발생.
-- `derive_result_from_pnl` (api/src/invest_note_api/domain/realized_pnl.py)과 동일 규칙으로 일괄 채워 SoT 통합.
-- profit_loss=NULL row는 대상 외 — 양쪽 모두 NULL로 일관 처리됨. `result IS NULL`로 idempotent.

UPDATE trades
SET result = CASE
  WHEN profit_loss > 0 THEN 'SUCCESS'::trade_result
  WHEN profit_loss < 0 THEN 'FAIL'::trade_result
  ELSE 'BREAKEVEN'::trade_result
END
WHERE trade_type = 'SELL'
  AND result IS NULL
  AND profit_loss IS NOT NULL;
