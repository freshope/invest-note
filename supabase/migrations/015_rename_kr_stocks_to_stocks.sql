-- kr_stocks → stocks: 한국 전용 마스터를 다국적 마스터로 일반화.
-- KIND 데이터 소스로의 전환에 맞춰 메타데이터 컬럼을 추가하고,
-- (country_code, ticker) 복합 PK 로 향후 해외 주식 ticker 충돌을 원천 차단한다.

alter table public.kr_stocks rename to stocks;

alter index public.kr_stocks_asset_name_idx rename to stocks_asset_name_idx;

alter table public.stocks add column country_code  text not null default 'KR';
alter table public.stocks add column currency      text not null default 'KRW';
alter table public.stocks add column exchange      text;
alter table public.stocks add column sector        text;
alter table public.stocks add column main_products text;
alter table public.stocks add column listed_at     date;
alter table public.stocks add column fiscal_month  text;
alter table public.stocks add column ceo_name      text;
alter table public.stocks add column homepage      text;
alter table public.stocks add column region        text;

-- 기존 PK / CHECK constraint 는 inline 정의된 자동 생성 이름을 가지므로,
-- 이름을 추측하지 말고 pg_constraint 에서 조회해 동적으로 제거한다.
do $$
declare
    r record;
begin
    for r in
        select conname
        from pg_constraint
        where conrelid = 'public.stocks'::regclass
          and contype in ('p', 'c')
    loop
        execute format('alter table public.stocks drop constraint %I', r.conname);
    end loop;
end $$;

alter table public.stocks add primary key (country_code, ticker);

comment on table public.stocks is '주식 마스터 (종목명→ticker 변환용). 한국+해외 통합. KIND/KRX 시드.';
