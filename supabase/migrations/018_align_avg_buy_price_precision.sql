-- avg_buy_price 컬럼 precision/scale 통일
-- price 컬럼(numeric(18, 4))과 동일하게 맞춰 정밀도 일관성 확보.
-- 기존 값은 numeric(unconstrained)에서 numeric(18, 4)로 안전 캐스팅된다
-- (price * quantity로 계산된 값이므로 scale 4 이내).
ALTER TABLE trades
  ALTER COLUMN avg_buy_price TYPE numeric(18, 4);
