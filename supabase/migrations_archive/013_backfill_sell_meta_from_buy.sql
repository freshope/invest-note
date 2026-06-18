-- SELL 거래의 reasoning_tags / emotion 백필
-- 정책: 두 컬럼은 거래 mutation 시 직전 BUY로부터 자동 산출되어 SELL row에 저장된다.
-- 분석은 SELL의 저장값만 사용하므로, 기존 SELL 데이터를 일괄 재계산해 정합화한다.
-- 011_add_holding_days.sql과 동일한 PL/SQL FIFO 패턴.
-- "가장 최근(traded_at 최대, 동률 시 BUY 입력 순서 최대) 소비 BUY"의 값을 그대로 복사.
-- 사용자가 직접 입력한 SELL의 기존 값은 무조건 덮어쓴다.

DO $$
DECLARE
  r record;
  current_key text := null;
  fifo_qty numeric[] := ARRAY[]::numeric[];
  fifo_time timestamptz[] := ARRAY[]::timestamptz[];
  fifo_order integer[] := ARRAY[]::integer[];
  fifo_tags_csv text[] := ARRAY[]::text[];
  fifo_emotion emotion_type[] := ARRAY[]::emotion_type[];
  buy_order integer := 0;
  remaining numeric;
  consume numeric;
  consumed_any boolean;
  latest_time timestamptz;
  latest_order integer;
  latest_tags reasoning_tag[];
  latest_emotion emotion_type;
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
      reasoning_tags,
      emotion
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
      fifo_order := ARRAY[]::integer[];
      fifo_tags_csv := ARRAY[]::text[];
      fifo_emotion := ARRAY[]::emotion_type[];
      buy_order := 0;
    END IF;

    IF r.trade_type = 'BUY' THEN
      fifo_qty := array_append(fifo_qty, r.quantity);
      fifo_time := array_append(fifo_time, r.traded_at);
      fifo_order := array_append(fifo_order, buy_order);
      -- enum 배열을 PL/PGSQL 배열로 안전히 보관하기 위해 CSV로 직렬화.
      -- 전제: reasoning_tag enum 값에는 ','가 포함되지 않음 (TECHNICAL/FUNDAMENTAL/NEWS/FEELING).
      -- 향후 enum 추가 시 이 가정을 깨면 silent corruption 발생 — composite type 전환 검토.
      fifo_tags_csv := array_append(fifo_tags_csv, COALESCE(array_to_string(r.reasoning_tags, ','), ''));
      fifo_emotion := array_append(fifo_emotion, r.emotion);
      buy_order := buy_order + 1;
    ELSE
      remaining := r.quantity;
      consumed_any := false;
      latest_time := null;
      latest_order := -1;
      latest_tags := ARRAY[]::reasoning_tag[];
      latest_emotion := null;

      WHILE remaining > 0 AND COALESCE(array_length(fifo_qty, 1), 0) > 0 LOOP
        consume := LEAST(fifo_qty[1], remaining);
        consumed_any := true;

        -- 가장 최근(traded_at 최대, 동률 시 입력 순서 최대) 소비 BUY 추적
        IF latest_time IS NULL
           OR fifo_time[1] > latest_time
           OR (fifo_time[1] = latest_time AND fifo_order[1] > latest_order) THEN
          latest_time := fifo_time[1];
          latest_order := fifo_order[1];
          IF fifo_tags_csv[1] = '' THEN
            latest_tags := ARRAY[]::reasoning_tag[];
          ELSE
            latest_tags := string_to_array(fifo_tags_csv[1], ',')::reasoning_tag[];
          END IF;
          latest_emotion := fifo_emotion[1];
        END IF;

        fifo_qty[1] := fifo_qty[1] - consume;
        remaining := remaining - consume;
        IF fifo_qty[1] <= 0 THEN
          fifo_qty := fifo_qty[2:];
          fifo_time := fifo_time[2:];
          fifo_order := fifo_order[2:];
          fifo_tags_csv := fifo_tags_csv[2:];
          fifo_emotion := fifo_emotion[2:];
        END IF;
      END LOOP;

      IF consumed_any THEN
        UPDATE trades
        SET
          reasoning_tags = latest_tags,
          emotion = latest_emotion
        WHERE id = r.id;
      ELSE
        -- 소비 BUY 없음(oversell 등 비정상): 기본값으로 초기화
        UPDATE trades
        SET
          reasoning_tags = ARRAY[]::reasoning_tag[],
          emotion = NULL
        WHERE id = r.id;
      END IF;
    END IF;
  END LOOP;
END $$;
