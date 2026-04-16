-- ============================================================
-- Enum 타입 정의
-- ============================================================

create type market_type as enum ('STOCK', 'CRYPTO', 'ETC');
create type trade_type as enum ('BUY', 'SELL');
create type strategy_type as enum ('SCALPING', 'SWING', 'LONG_TERM', 'UNKNOWN');
create type reasoning_tag as enum ('TECHNICAL', 'FUNDAMENTAL', 'NEWS', 'FEELING');
create type emotion_type as enum ('CONFIDENT', 'ANXIOUS', 'FOMO', 'IMPULSIVE', 'CALM');
create type trade_result as enum ('SUCCESS', 'FAIL', 'BREAKEVEN');

-- ============================================================
-- accounts 테이블
-- ============================================================

create table accounts (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  name        text not null,                        -- 계좌명 (예: 키움 위탁계좌)
  broker      text,                                 -- 증권사명
  cash_balance numeric(18, 2) not null default 0,   -- 예수금 (수동 입력)
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- ============================================================
-- trades 테이블
-- ============================================================

create table trades (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  account_id      uuid not null references accounts(id) on delete cascade,

  -- 거래 기본 정보
  asset_name      text not null,                    -- 종목명
  market_type     market_type not null default 'STOCK',
  trade_type      trade_type not null,
  price           numeric(18, 4) not null,
  quantity        numeric(18, 4) not null,
  total_amount    numeric(18, 2) generated always as (price * quantity) stored,
  traded_at       timestamptz not null default now(),

  -- 매매 이유
  strategy_type   strategy_type,
  reasoning_tags  reasoning_tag[] default '{}',     -- 다중 선택
  buy_reason      text,
  sell_reason     text,

  -- 감정
  emotion         emotion_type,

  -- 복기 (SELL 거래에만 해당)
  result          trade_result,
  reflection_note text,
  improvement_note text,

  -- 손익 (SELL 시 수동 또는 계산)
  profit_loss     numeric(18, 2),

  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

-- ============================================================
-- updated_at 자동 갱신 트리거
-- ============================================================

create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger accounts_updated_at
  before update on accounts
  for each row execute function set_updated_at();

create trigger trades_updated_at
  before update on trades
  for each row execute function set_updated_at();

-- ============================================================
-- 인덱스
-- ============================================================

create index trades_user_id_traded_at_idx on trades (user_id, traded_at desc);
create index trades_account_id_idx on trades (account_id);
create index accounts_user_id_idx on accounts (user_id);

-- ============================================================
-- RLS 정책
-- ============================================================

alter table accounts enable row level security;
alter table trades enable row level security;

-- accounts: 본인 데이터만 접근
create policy "accounts: 본인만 조회" on accounts
  for select using (auth.uid() = user_id);

create policy "accounts: 본인만 삽입" on accounts
  for insert with check (auth.uid() = user_id);

create policy "accounts: 본인만 수정" on accounts
  for update using (auth.uid() = user_id);

create policy "accounts: 본인만 삭제" on accounts
  for delete using (auth.uid() = user_id);

-- trades: 본인 데이터만 접근
create policy "trades: 본인만 조회" on trades
  for select using (auth.uid() = user_id);

create policy "trades: 본인만 삽입" on trades
  for insert with check (auth.uid() = user_id);

create policy "trades: 본인만 수정" on trades
  for update using (auth.uid() = user_id);

create policy "trades: 본인만 삭제" on trades
  for delete using (auth.uid() = user_id);
