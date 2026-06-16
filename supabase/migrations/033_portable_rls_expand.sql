-- 포터블 RLS — EXPAND (무중단 1/2단계). 구 BE(auth.uid)·신 BE(current_user_id) 동시 동작.
--
-- Supabase 고유 객체(auth.uid()/authenticated 역할/request.jwt.claims)를 자체 public 객체로
-- 옮기되, 이 단계는 "추가만" 한다: 정책은 두 메커니즘을 OR 로 모두 허용하고 FK 는 아직
-- auth.users 를 유지한다 → 신 BE 배포 전/중/후, 롤백(구 BE 복귀) 모두 안전.
-- 완전 디커플(auth.uid 분기·auth.users FK 제거)은 신 BE 전면 배포 확인 후 CONTRACT 단계에서.
-- (Supabase Auth(JWT 발급/검증)는 별개 축 — 그대로 유지.)

-- 1) RLS 적용 역할 — Supabase 'authenticated' 대체 (additive). 앱은 owner(postgres)로 접속해
--    user 데이터 접근 시에만 이 역할로 내려간다(owner 는 RLS 우회).
do $$ begin
  if not exists (select from pg_roles where rolname = 'app_authenticated') then
    create role app_authenticated nologin;
  end if;
end $$;

grant app_authenticated to postgres;  -- 앱 접속 role 이 SET ROLE 가능하도록

grant usage on schema public to app_authenticated;
grant select, insert, update, delete on all tables in schema public to app_authenticated;
grant usage, select on all sequences in schema public to app_authenticated;
alter default privileges in schema public
  grant select, insert, update, delete on tables to app_authenticated;
alter default privileges in schema public
  grant usage, select on sequences to app_authenticated;

-- 2) auth.uid() 대체 함수 (additive). 미설정 시 NULL → fail-closed.
create or replace function public.current_user_id() returns uuid
  language sql stable as $$
  select nullif(current_setting('app.current_user_id', true), '')::uuid
$$;

-- 3) public.users — 사용자 식별 FK 타깃 (additive). 신원은 Supabase Auth 가 소유.
--    이 단계에서는 FK 를 옮기지 않는다(auth.users 유지). 신 BE 의 acquire_for_user 가
--    첫 요청 시 owner 로 프로비저닝하며, contract 에서 재백필 후 FK 를 재지정한다.
create table public.users (
  id         uuid primary key,
  created_at timestamptz not null default now()
);
insert into public.users (id) select id from auth.users on conflict (id) do nothing;

-- kis_tokens 와 동일 패턴: RLS enable + 정책 없음 → app_authenticated/authenticated 차단,
-- owner(프로비저닝·재백필·계정삭제)만 통과.
alter table public.users enable row level security;
comment on table public.users is
  '사용자 식별 FK 타깃 (신원은 Supabase Auth 소유). RLS enable + 정책 없음 = owner 만 접근.';

-- 4) RLS 정책 — 구/신 두 메커니즘 모두 허용 (auth.uid() OR public.current_user_id()).
--    구 BE: request.jwt.claims 주입 → auth.uid() 통과. 신 BE: app.current_user_id 주입 → current_user_id() 통과.
-- accounts
drop policy "accounts: 본인만 조회" on accounts;
drop policy "accounts: 본인만 삽입" on accounts;
drop policy "accounts: 본인만 수정" on accounts;
drop policy "accounts: 본인만 삭제" on accounts;
create policy "accounts: 본인만 조회" on accounts
  for select using (auth.uid() = user_id or public.current_user_id() = user_id);
create policy "accounts: 본인만 삽입" on accounts
  for insert with check (auth.uid() = user_id or public.current_user_id() = user_id);
create policy "accounts: 본인만 수정" on accounts
  for update using (auth.uid() = user_id or public.current_user_id() = user_id)
  with check (auth.uid() = user_id or public.current_user_id() = user_id);
create policy "accounts: 본인만 삭제" on accounts
  for delete using (auth.uid() = user_id or public.current_user_id() = user_id);

-- trades
drop policy "trades: 본인만 조회" on trades;
drop policy "trades: 본인만 삽입" on trades;
drop policy "trades: 본인만 수정" on trades;
drop policy "trades: 본인만 삭제" on trades;
create policy "trades: 본인만 조회" on trades
  for select using (auth.uid() = user_id or public.current_user_id() = user_id);
create policy "trades: 본인만 삽입" on trades
  for insert with check (auth.uid() = user_id or public.current_user_id() = user_id);
create policy "trades: 본인만 수정" on trades
  for update using (auth.uid() = user_id or public.current_user_id() = user_id)
  with check (auth.uid() = user_id or public.current_user_id() = user_id);
create policy "trades: 본인만 삭제" on trades
  for delete using (auth.uid() = user_id or public.current_user_id() = user_id);

-- custom_tags (update 정책 없음)
drop policy "custom_tags: 본인만 조회" on custom_tags;
drop policy "custom_tags: 본인만 삽입" on custom_tags;
drop policy "custom_tags: 본인만 삭제" on custom_tags;
create policy "custom_tags: 본인만 조회" on custom_tags
  for select using (auth.uid() = user_id or public.current_user_id() = user_id);
create policy "custom_tags: 본인만 삽입" on custom_tags
  for insert with check (auth.uid() = user_id or public.current_user_id() = user_id);
create policy "custom_tags: 본인만 삭제" on custom_tags
  for delete using (auth.uid() = user_id or public.current_user_id() = user_id);
