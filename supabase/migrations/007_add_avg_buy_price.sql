-- SELL 거래의 매도 시점 평균 매수가 저장 컬럼
-- profit_loss와 함께 계산·저장되며 BUY 거래는 항상 null
ALTER TABLE trades ADD COLUMN IF NOT EXISTS avg_buy_price numeric;
