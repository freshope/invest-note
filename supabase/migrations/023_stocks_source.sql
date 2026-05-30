-- 종목별 출처 기록.
-- 다중 소스 순차 병합에서 canonical(종목명·시장)을 소유한 authority 소스를 기록한다.
-- (별칭 source 와 동일 의미 — 어느 소스 분류를 신뢰 중인지 추적. 교차검증 불일치 판단에 활용.)
-- 이름을 덮어쓴 소스(authority)가 source 를 갱신하고, 하위 소스의 preserve-upsert 는 보존한다.

alter table public.stocks
    add column source text;  -- 'data_go_kr' | 'fdr' | ... (NULL=레거시/미기록)
