-- holdings 재계산 트리거 수정: is_cancelled=true 시에도 재계산 실행
-- 기존 트리거는 is_cancelled=true일 때 즉시 return하여 보유 수량이 갱신되지 않는 버그가 있었음
-- WAC 쿼리 자체가 이미 is_cancelled=false 거래만 합산하므로, 취소 시에도 재계산하면 올바르게 제거됨
create or replace function recalc_holding()
returns trigger as $$
declare
  v_account_id uuid;
  v_ticker text;
  v_user_id uuid;
  v_total_qty integer;
  v_avg_price numeric;
  v_name text;
  v_market market_type;
begin
  -- 취소된 거래가 아닌 경우에만 메타데이터 사용 (취소 시에도 ticker/account로 재계산)
  v_account_id := new.account_id;
  v_ticker     := new.ticker;
  v_user_id    := new.user_id;
  v_name       := new.name;
  v_market     := new.market;

  -- WAC 재계산: 유효한(is_cancelled=false) 매수 거래 기준
  select
    coalesce(sum(case when trade_type = 'buy' then quantity else -quantity end), 0),
    case
      when sum(case when trade_type = 'buy' then quantity else 0 end) > 0
      then sum(case when trade_type = 'buy' then (price * quantity + fee) else 0 end)
           / sum(case when trade_type = 'buy' then quantity else 0 end)
      else 0
    end
  into v_total_qty, v_avg_price
  from trades
  where account_id = v_account_id
    and ticker = v_ticker
    and is_cancelled = false;

  if v_avg_price is null then
    v_avg_price := 0;
  end if;

  insert into holdings (user_id, account_id, ticker, name, market, quantity, avg_price)
  values (v_user_id, v_account_id, v_ticker, v_name, v_market, v_total_qty, v_avg_price)
  on conflict (account_id, ticker) do update set
    quantity   = v_total_qty,
    avg_price  = v_avg_price,
    name       = coalesce(excluded.name, holdings.name),
    updated_at = now();

  return new;
end;
$$ language plpgsql;
