-- 국민연금(NPS) 보유 종목 표시용 — 종목별 국민연금 보유 여부·기준일.
-- 출처(odcloud OpenAPI, data.go.kr serviceKey):
--   국내주식 투자정보(3070507, 전체보유, 연1회) + 대량보유주식 보고내역(15106890, 5%+, 분기).
-- NPS 응답에 종목코드가 없어 종목명→ticker 매칭으로 채우며, 미매칭 종목명은 nps_unmatched 에 쌓아
-- 관리자가 reconcile 한다. 자세한 배경/판정 정정은 docs/decisions.md 2026-06-02 참고.

alter table public.stocks
    add column nps_holding text,   -- NULL=미보유 / 'held'=전체보유(3070507) / 'major'=5%+ 대량보유(15106890)
    add column nps_as_of   date;   -- 전체보유(3070507) 스냅샷 기준일. 지연 스냅샷이라 UI 에 "기준일" 명시용.

-- 종목명→ticker 매칭 실패분 reconcile 큐. ticker 가 없어 stock_aliases(ticker PK·FK)엔 못 넣고 별도 테이블로 둔다.
-- 관리자가 확인 후 resolved_ticker 매핑(또는 stocks/stock_aliases 보강)으로 해소한다.
create table public.nps_unmatched (
    nps_name        text not null,                  -- NPS 원본 종목명/발행기관명(미정제 원본)
    nps_as_of       date not null,                  -- 해당 스냅샷 기준일
    holding_level   text not null,                  -- 'held' | 'major'
    resolved_ticker text,                           -- 관리자가 매핑하면 채움(NULL=미해소)
    created_at      timestamptz not null default now(),
    primary key (nps_name, nps_as_of)
);

comment on table public.nps_unmatched is '국민연금 적재 시 종목명→ticker 매칭 실패분 reconcile 큐. 관리자가 확인 후 조치.';
