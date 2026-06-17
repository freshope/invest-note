create table if not exists public.kr_stocks (
    ticker      text primary key,
    asset_name  text not null,
    market      text not null check (market in ('KOSPI', 'KOSDAQ', 'KONEX')),
    updated_at  timestamptz not null default now()
);

create index if not exists kr_stocks_asset_name_idx on public.kr_stocks (asset_name);

comment on table public.kr_stocks is 'KRX 상장 종목 마스터 (종목명→ticker 변환용)';
