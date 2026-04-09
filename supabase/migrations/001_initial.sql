-- Enum 타입
create type trade_type as enum ('buy', 'sell');
create type market_type as enum ('KR', 'US');

-- 계좌 테이블
create table accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  broker text not null,
  account_number text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

-- 거래 내역 (immutable ledger — 삭제 대신 soft cancel)
create table trades (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  account_id uuid not null references accounts(id) on delete cascade,
  ticker text not null,
  name text,
  market market_type not null default 'KR',
  trade_type trade_type not null,
  quantity integer not null check (quantity > 0),
  price numeric(18, 2) not null check (price > 0),
  fee numeric(18, 2) not null default 0 check (fee >= 0),
  traded_at date not null,
  memo text,
  is_cancelled boolean not null default false,
  created_at timestamptz not null default now()
);

-- 매매일지
create table journals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  trade_id uuid references trades(id) on delete set null,
  ticker text not null,
  name text,
  market market_type not null default 'KR',
  reason text,                   -- 1단계: 매수 이유
  target_price numeric(18, 2),   -- 1단계: 목표가
  stop_loss_price numeric(18, 2),-- 1단계: 손절가
  reflection text,               -- 2단계: 매도 후 회고
  tags text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 보유 종목 캐시 (DB 트리거로 자동 갱신)
create table holdings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  account_id uuid not null references accounts(id) on delete cascade,
  ticker text not null,
  name text,
  market market_type not null default 'KR',
  quantity integer not null default 0 check (quantity >= 0),
  avg_price numeric(18, 2) not null default 0,
  updated_at timestamptz not null default now(),
  unique (account_id, ticker)
);

-- RLS 활성화
alter table accounts enable row level security;
alter table trades enable row level security;
alter table journals enable row level security;
alter table holdings enable row level security;

-- RLS 정책 (본인 데이터만 접근)
create policy "accounts: own data" on accounts
  for all using (auth.uid() = user_id);

create policy "trades: own data" on trades
  for all using (auth.uid() = user_id);

create policy "journals: own data" on journals
  for all using (auth.uid() = user_id);

create policy "holdings: own data" on holdings
  for all using (auth.uid() = user_id);

-- 인덱스
create index trades_user_id_idx on trades(user_id);
create index trades_account_id_idx on trades(account_id);
create index trades_ticker_idx on trades(ticker);
create index trades_traded_at_idx on trades(traded_at desc);
create index holdings_account_id_idx on holdings(account_id);
create index journals_user_id_idx on journals(user_id);
create index journals_ticker_idx on journals(ticker);

-- updated_at 자동 갱신 함수
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger accounts_updated_at before update on accounts
  for each row execute function update_updated_at();
create trigger journals_updated_at before update on journals
  for each row execute function update_updated_at();

-- 거래 후 holdings 자동 갱신 트리거
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
  -- 취소된 거래는 무시
  if new.is_cancelled then
    return new;
  end if;

  v_account_id := new.account_id;
  v_ticker     := new.ticker;
  v_user_id    := new.user_id;
  v_name       := new.name;
  v_market     := new.market;

  -- WAC 재계산: 유효한 매수 거래 기준
  select
    sum(case when trade_type = 'buy' then quantity else -quantity end),
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

  if v_total_qty is null then
    v_total_qty := 0;
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

create trigger trades_recalc_holding
  after insert or update on trades
  for each row execute function recalc_holding();
