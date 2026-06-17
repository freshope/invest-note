-- 종목 마스터 다중 소스 적재 효율화.
-- 변경이 드문 데이터이므로, 소스별 내용 fingerprint 를 저장해 무변경 소스의 재적재를 건너뛴다.

create table public.seed_source_state (
    source      text primary key,             -- 'data_go_kr' | 'fdr' | ...
    fingerprint text not null,                -- 정렬된 (ticker|name|market) 의 sha256
    row_count   integer not null default 0,
    updated_at  timestamptz not null default now()
);

comment on table public.seed_source_state is '종목 적재 소스별 마지막 fingerprint — 무변경 시 적재 skip.';
