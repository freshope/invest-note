-- 종목별 시가총액(시총)·시총순위 기록.
-- data.go.kr 주식시세(getStockPriceInfo)·증권상품시세(getETF/ETNPriceInfo)에서 적재한다.
-- marcap 은 매 적재마다 갱신(시총은 매일 변동)되며, coverage fingerprint-skip 을 우회하는 별도 단계에서 채운다.
-- marcap_rank 는 주식(KOSPI+KOSDAQ) 대상 시총 내림차순 순위(window 재계산). ETF/ETN 은 NULL.

alter table public.stocks
    add column marcap      bigint,   -- 시가총액(원). 삼성전자 ≈ 4e14 → bigint 필수. NULL=미적재.
    add column marcap_rank integer,  -- 시총순위(주식만, 1=최대). ETF/ETN·미적재는 NULL.
    add column marcap_as_of date;    -- 시세 기준일(basDt, 직전 영업일).
