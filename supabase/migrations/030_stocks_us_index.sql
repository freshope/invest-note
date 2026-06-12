-- US 종목 인덱스 편입(S&P 500 등) 멤버십. NULL=미편입.
-- seed_us 에서 구성종목 fetch 로 갱신 → 유동성-상위 alias 타깃·향후 편입 뱃지에 사용.
-- KR 의 marcap_rank 와 의미가 다르므로(시총 순위 아님) 별도 컬럼으로 둔다.
alter table public.stocks
    add column us_index text;  -- 'SP500' 등 인덱스 코드
