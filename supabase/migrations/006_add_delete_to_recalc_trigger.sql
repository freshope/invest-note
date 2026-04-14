-- recalc_holding trigger에 DELETE 이벤트 추가
-- 거래 삭제 시 holdings 자동 재계산을 위해 필요
-- 주의: 005에서 추가한 ticker/account_id 변경 시 OLD 버킷 재계산 로직도 포함
create or replace function recalc_holding()
returns trigger as $$
declare
  v_account_id uuid;
  v_ticker     text;
  v_user_id    uuid;
  v_total_qty  integer;
  v_avg_price  numeric;
  v_name       text;
  v_market     market_type;
begin
  -- DELETE는 OLD, INSERT/UPDATE는 NEW 사용
  if TG_OP = 'DELETE' then
    v_account_id := old.account_id;
    v_ticker     := old.ticker;
    v_user_id    := old.user_id;
    v_name       := old.name;
    v_market     := old.market;
  else
    v_account_id := new.account_id;
    v_ticker     := new.ticker;
    v_user_id    := new.user_id;
    v_name       := new.name;
    v_market     := new.market;
  end if;

  -- WAC 재계산 (삭제된 거래는 이미 테이블에서 제거됨)
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

  if v_avg_price is null then v_avg_price := 0; end if;
  -- 음수 수량 방지 (데이터 불일치 시 holdings 제약 위반 방어)
  if v_total_qty < 0 then v_total_qty := 0; end if;

  insert into holdings (user_id, account_id, ticker, name, market, quantity, avg_price)
  values (v_user_id, v_account_id, v_ticker, v_name, v_market, v_total_qty, v_avg_price)
  on conflict (account_id, ticker) do update set
    quantity   = v_total_qty,
    avg_price  = v_avg_price,
    name       = coalesce(excluded.name, holdings.name),
    updated_at = now();

  -- UPDATE 시 ticker 또는 account_id가 바뀐 경우 OLD 버킷도 재계산
  -- (005에서 추가된 로직: ticker 수정 시 이전 ticker의 holding 수량 오염 방지)
  if TG_OP = 'UPDATE' and (
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

    if v_avg_price is null then v_avg_price := 0; end if;
    if v_total_qty < 0 then v_total_qty := 0; end if;

    insert into holdings (user_id, account_id, ticker, name, market, quantity, avg_price)
    values (old.user_id, old.account_id, old.ticker, old.name, old.market, v_total_qty, v_avg_price)
    on conflict (account_id, ticker) do update set
      quantity   = v_total_qty,
      avg_price  = v_avg_price,
      updated_at = now();
  end if;

  return case when TG_OP = 'DELETE' then old else new end;
end;
$$ language plpgsql;

-- 트리거 재생성 (DELETE 추가)
drop trigger if exists trades_recalc_holding on trades;
create trigger trades_recalc_holding
  after insert or update or delete on trades
  for each row execute function recalc_holding();
