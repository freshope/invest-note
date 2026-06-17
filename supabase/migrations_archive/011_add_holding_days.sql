-- SELL 거래의 FIFO 가중평균 보유일 저장 컬럼
-- profit_loss, avg_buy_price와 함께 계산·저장되며 BUY 거래는 항상 null
ALTER TABLE trades ADD COLUMN IF NOT EXISTS holding_days integer;

-- 기존 SELL 거래의 보유일을 배포 시점에 백필한다.
-- 이후 런타임 분석은 조회 시 FIFO 계산을 하지 않고 저장된 holding_days만 사용한다.
DO $$
DECLARE
  r record;
  current_key text := null;
  fifo_qty numeric[] := ARRAY[]::numeric[];
  fifo_time timestamptz[] := ARRAY[]::timestamptz[];
  fifo_strategy strategy_type[] := ARRAY[]::strategy_type[];
  remaining numeric;
  consume numeric;
  total_consumed numeric;
  weighted_seconds numeric;
  consumed_strategy strategy_type;
  strategy_keys strategy_type[];
  strategy_qty numeric[];
  strategy_idx integer;
  best_strategy strategy_type;
  best_qty numeric;
  i integer;
BEGIN
  FOR r IN
    SELECT
      id,
      user_id,
      account_id,
      COALESCE(country_code, 'KR') AS country_code,
      COALESCE(ticker_symbol, asset_name) AS ticker_symbol,
      trade_type,
      quantity,
      traded_at,
      created_at,
      strategy_type
    FROM trades
    ORDER BY
      user_id,
      account_id,
      COALESCE(country_code, 'KR'),
      COALESCE(ticker_symbol, asset_name),
      traded_at,
      CASE WHEN trade_type = 'BUY' THEN 0 ELSE 1 END,
      created_at
  LOOP
    IF current_key IS DISTINCT FROM (
      r.user_id::text || ':' || r.account_id::text || ':' || r.country_code || ':' || r.ticker_symbol
    ) THEN
      current_key := r.user_id::text || ':' || r.account_id::text || ':' || r.country_code || ':' || r.ticker_symbol;
      fifo_qty := ARRAY[]::numeric[];
      fifo_time := ARRAY[]::timestamptz[];
      fifo_strategy := ARRAY[]::strategy_type[];
    END IF;

    IF r.trade_type = 'BUY' THEN
      fifo_qty := array_append(fifo_qty, r.quantity);
      fifo_time := array_append(fifo_time, r.traded_at);
      fifo_strategy := array_append(fifo_strategy, r.strategy_type);
    ELSE
      remaining := r.quantity;
      total_consumed := 0;
      weighted_seconds := 0;
      strategy_keys := ARRAY[]::strategy_type[];
      strategy_qty := ARRAY[]::numeric[];

      WHILE remaining > 0 AND COALESCE(array_length(fifo_qty, 1), 0) > 0 LOOP
        consume := LEAST(fifo_qty[1], remaining);
        total_consumed := total_consumed + consume;
        weighted_seconds := weighted_seconds + EXTRACT(EPOCH FROM (r.traded_at - fifo_time[1])) * consume;

        consumed_strategy := COALESCE(fifo_strategy[1], 'UNKNOWN'::strategy_type);
        strategy_idx := array_position(strategy_keys, consumed_strategy);
        IF strategy_idx IS NULL THEN
          strategy_keys := array_append(strategy_keys, consumed_strategy);
          strategy_qty := array_append(strategy_qty, consume);
        ELSE
          strategy_qty[strategy_idx] := strategy_qty[strategy_idx] + consume;
        END IF;

        fifo_qty[1] := fifo_qty[1] - consume;
        remaining := remaining - consume;
        IF fifo_qty[1] <= 0 THEN
          fifo_qty := fifo_qty[2:];
          fifo_time := fifo_time[2:];
          fifo_strategy := fifo_strategy[2:];
        END IF;
      END LOOP;

      IF total_consumed > 0 THEN
        best_strategy := null;
        best_qty := -1;
        FOR i IN 1..COALESCE(array_length(strategy_keys, 1), 0) LOOP
          IF strategy_qty[i] > best_qty THEN
            best_strategy := strategy_keys[i];
            best_qty := strategy_qty[i];
          END IF;
        END LOOP;

        UPDATE trades
        SET
          holding_days = COALESCE(holding_days, FLOOR(weighted_seconds / total_consumed / 86400 + 0.5)::integer),
          strategy_type = COALESCE(strategy_type, best_strategy)
        WHERE id = r.id;
      END IF;
    END IF;
  END LOOP;
END $$;
