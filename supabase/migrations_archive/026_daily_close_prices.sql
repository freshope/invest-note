-- 일별 종가 저장 — 자산 변화 페이지(계좌별/종목별 일별 평가액 추이)의 과거 종가 출처.
--
-- 일별 자산 = 그 날 보유 수량 × 그 날 종가. 종가는 2년치를 여기 저장하고, 결측일은
-- 진입 시 data.go.kr getStockPriceInfo 범위 조회로 watermark 증분 적재한다(당일은 라이브 시세).
-- 전역 참조 데이터(특정 user 소유 아님) — stocks 마스터(020_recreate_stocks.sql)와 동일하게
-- RLS 미적용(public read-only). user 데이터가 아니므로 RLS/grant 문 없이 테이블만 생성한다.
-- (stocks 와 동일 패턴 — 별도 policy/grant 정의 없음.)

create table public.daily_close_prices (
    country_code  text not null default 'KR',
    ticker        text not null,                     -- 6자리 종목코드(앞자리 'A' 없음).
    close_date    date not null,                     -- 거래일(주말/휴장 제외 — 거래일만 적재).
    close_price   numeric(15, 2) not null,           -- 종가(clpr).
    updated_at    timestamptz not null default now(),
    primary key (country_code, ticker, close_date)
);

-- 종목별 최신 종가(watermark = max(close_date)) 조회와 범위 조회를 위한 인덱스.
create index daily_close_prices_ticker_date_idx
    on public.daily_close_prices (ticker, close_date desc);

comment on table public.daily_close_prices is '일별 종가 (자산 변화 페이지용). 전역 참조 데이터, RLS 미적용. data.go.kr getStockPriceInfo 증분 적재.';
