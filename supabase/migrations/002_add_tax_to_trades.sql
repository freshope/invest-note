-- 제세금 컬럼 추가
alter table trades add column tax numeric(18, 2) not null default 0 check (tax >= 0);
