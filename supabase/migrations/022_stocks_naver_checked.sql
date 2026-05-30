-- 종목별 Naver 교차검증 추적.
-- 적재 시 각 종목을 Naver 자동완성으로 1회 조회해 이름 변형(→별칭)·시장(typeCode) 교차검증한다.
-- naver_checked_at 으로 이미 검증한 종목을 재질의하지 않는다(최소 종목당 1회, 신규만 추가 질의).

alter table public.stocks
    add column naver_checked_at timestamptz;  -- NULL=미검증. 검증 성공 시 기록.
