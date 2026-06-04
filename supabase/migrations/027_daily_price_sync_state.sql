-- 일별 종가 동기화 상태 — backfill 이 "어디까지 data.go.kr 를 조회했는지" 기록.
--
-- daily_close_prices 는 "데이터가 있는 거래일"만 적재한다. 그래서 휴장일 구간을 조회하면
-- 응답이 비어(거래일 없음) watermark(max(close_date))가 전진하지 못하고, backfill skip 조건
-- (begin > yesterday)이 영영 거짓이라 매 요청마다 같은 빈 범위를 data.go.kr 에 재질의한다.
-- (stocks 의 naver_checked_at 과 동일한 "빈 응답도 확인으로 기록" 패턴이 필요.)
--
-- 이 테이블은 종목별 "checked_through_date(이 날까지 조회 완료, 빈 응답 포함) + checked_at"
-- 를 보관해, 조회한 빈 범위를 다시 묻지 않게 한다(쿨다운 경과 시에만 재probe — 늦은 발행 대응).
-- 전역 참조 데이터(특정 user 소유 아님) — daily_close_prices(026)와 동일하게 RLS 미적용.

create table public.daily_price_sync_state (
    country_code        text not null default 'KR',
    ticker              text not null,                  -- 6자리 종목코드(앞자리 'A' 없음).
    checked_through_date date not null,                 -- 이 날까지 data.go.kr 조회 완료(빈 응답 포함).
    checked_at          timestamptz not null default now(), -- 마지막 조회 시각(쿨다운 재probe 판정).
    primary key (country_code, ticker)
);

comment on table public.daily_price_sync_state is '일별 종가 backfill 동기화 상태(종목별 조회 완료일). 전역 참조 데이터, RLS 미적용. 빈 응답 재질의 방지.';
