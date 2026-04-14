-- holdings 재계산 트리거 수정: ticker/account_id 변경 시 OLD 버킷도 재계산
-- database.ts Update 타입이 ticker/market/trade_type 수정을 허용하므로,
-- ticker나 account_id가 바뀌면 OLD 버킷의 보유 수량도 갱신해야 함
-- 그렇지 않으면 이전 ticker의 holding이 잘못된 수량으로 남음
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
  v_account_id := new.account_id;
  v_ticker     := new.ticker;
  v_user_id    := new.user_id;
  v_name       := new.name;
  v_market     := new.market;

  -- WAC 재계산: 유효한(is_cancelled=false) 거래 기준
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

  -- ticker 또는 account_id가 바뀐 경우 OLD 버킷도 재계산
  -- (예: 거래 ticker 수정 시 이전 ticker의 holding이 갱신되지 않는 버그 방지)
  if tg_op = 'UPDATE' and (
    old.ticker is distinct from new.ticker or
    old.account_id is distinct from new.account_id
  ) then
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
    where account_id = old.account_id
      and ticker = old.ticker
      and is_cancelled = false;

    if v_avg_price is null then
      v_avg_price := 0;
    end if;

    insert into holdings (user_id, account_id, ticker, name, market, quantity, avg_price)
    values (old.user_id, old.account_id, old.ticker, old.name, old.market, v_total_qty, v_avg_price)
    on conflict (account_id, ticker) do update set
      quantity   = v_total_qty,
      avg_price  = v_avg_price,
      updated_at = now();
  end if;

  return new;
end;
$$ language plpgsql;
