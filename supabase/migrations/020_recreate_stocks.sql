-- stocks 마스터 재도입: 종목 검색·일괄 import 매칭을 Naver 런타임 의존에서 자체 데이터로 전환.
--
-- 2026-04-28 (016_drop_stocks.sql) 에 폐기했던 마스터를 다중 소스 주기 적재 구조로 재도입한다.
-- 폐기 사유였던 ① coverage(ETF/ETN 누락), ② matchability(약칭/부분일치 불가) 를 다음으로 해소:
--   - coverage: 공공데이터(전 종목) + KRX 정보데이터시스템(ETF/ETN). market CHECK 제거로 ETF/ETN 수용.
--   - matchability: pg_trgm 부분일치 + name_chosung 초성 + stock_aliases(약칭/교차소스 변형명/Naver 흡수).
-- 검색/import 런타임은 로컬 DB 만 조회(외부 호출 0). Naver 는 적재(batch) 단계 enrichment 로만 사용.
-- 014/015 마이그레이션 이력은 보존하고 본 마이그레이션에서 새로 생성한다.
-- trades 는 stocks 를 FK 참조하지 않아(001_initial_schema.sql) 거래 데이터에 영향 없음.
-- 마스터는 user 데이터가 아니므로 RLS 미적용(public read-only). 자세한 배경은 docs/decisions.md 참고.

create extension if not exists pg_trgm;

create table public.stocks (
    country_code  text not null default 'KR',
    ticker        text not null,
    asset_name    text not null,
    name_chosung  text,                              -- 종목명 초성 ("삼성전자"→"ㅅㅅㅈㅈ"). 적재 시 계산.
    currency      text not null default 'KRW',
    exchange      text,                              -- 'KRX' 등
    market        text not null,                     -- KOSPI/KOSDAQ/KONEX/ETF/ETN. ETF/ETN 수용 위해 CHECK 없음.
    sector        text,
    is_active     boolean not null default true,     -- 상폐 soft-delete. 검색은 true 만 노출.
    updated_at    timestamptz not null default now(),
    primary key (country_code, ticker)
);

create index stocks_name_trgm_idx on public.stocks using gin (asset_name gin_trgm_ops);
create index stocks_chosung_idx   on public.stocks (name_chosung);
create index stocks_active_idx    on public.stocks (country_code, is_active);

comment on table public.stocks is '주식 마스터 (검색/매칭용). 한국+해외 통합, 다중 소스 주기 적재. KIND/공공데이터/KRX/Naver 시드.';

-- 약칭/별칭: 공식 소스에 없는 구어체 약칭, 교차 소스 명칭 변형, Naver 흡수분을 자체 소유.
-- canonical asset_name 은 stocks 에 두고, 검색 가능한 변형 표기만 여기 적재한다.
create table public.stock_aliases (
    country_code  text not null,
    ticker        text not null,
    alias         text not null,
    alias_chosung text,                              -- 약칭 초성 ("현대차"→"ㅎㄷㅊ"). 적재 시 계산.
    source        text not null default 'manual',    -- 'manual' | 'naver' | 'data_go_kr' | 'krx' | 'fdr'
    created_at    timestamptz not null default now(),
    primary key (country_code, ticker, alias),
    foreign key (country_code, ticker) references public.stocks (country_code, ticker) on delete cascade
);

create index stock_aliases_alias_idx   on public.stock_aliases (alias);
create index stock_aliases_chosung_idx on public.stock_aliases (alias_chosung);

comment on table public.stock_aliases is '종목 약칭/변형명 (검색 전용). source 로 수급 출처 구분.';
