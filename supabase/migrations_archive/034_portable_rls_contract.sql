-- 포터블 RLS — CONTRACT (무중단 2/2단계).
--
-- expand(033) + 신 BE 운영 배포·스모크 확인 후 적용하는 단계 (2026-06-16). 무중단을 위해
-- expand 와 동시 적용되지 않도록 migrations_pending/ 에 보류했다가 이 시점에 migrations/ 로
-- 옮겨 적용한다.
--
-- 이 단계는 구 BE 호환 장치를 제거해 Supabase 고유 객체 의존을 끝낸다:
--   ① auth.uid() OR 분기 제거 → public.current_user_id() 단일
--   ② FK auth.users → public.users 재지정
-- 적용 후에는 구 BE 로 롤백 불가(auth.uid 분기 없음). 그래서 신 BE 안정 확인이 전제.

-- 1) 윈도우 중 신규 가입자까지 public.users 동기화 (FK 재지정 전 보강 — 누락 user 방지).
insert into public.users (id) select id from auth.users on conflict (id) do nothing;

-- 2) FK 재지정 auth.users → public.users.
alter table accounts drop constraint accounts_user_id_fkey;
alter table accounts add constraint accounts_user_id_fkey
  foreign key (user_id) references public.users(id) on delete cascade;

alter table trades drop constraint trades_user_id_fkey;
alter table trades add constraint trades_user_id_fkey
  foreign key (user_id) references public.users(id) on delete cascade;

alter table custom_tags drop constraint custom_tags_user_id_fkey;
alter table custom_tags add constraint custom_tags_user_id_fkey
  foreign key (user_id) references public.users(id) on delete cascade;

-- 3) RLS 정책에서 auth.uid() 분기 제거 → public.current_user_id() 단일.
-- accounts
drop policy "accounts: 본인만 조회" on accounts;
drop policy "accounts: 본인만 삽입" on accounts;
drop policy "accounts: 본인만 수정" on accounts;
drop policy "accounts: 본인만 삭제" on accounts;
create policy "accounts: 본인만 조회" on accounts
  for select using (public.current_user_id() = user_id);
create policy "accounts: 본인만 삽입" on accounts
  for insert with check (public.current_user_id() = user_id);
create policy "accounts: 본인만 수정" on accounts
  for update using (public.current_user_id() = user_id)
  with check (public.current_user_id() = user_id);
create policy "accounts: 본인만 삭제" on accounts
  for delete using (public.current_user_id() = user_id);

-- trades
drop policy "trades: 본인만 조회" on trades;
drop policy "trades: 본인만 삽입" on trades;
drop policy "trades: 본인만 수정" on trades;
drop policy "trades: 본인만 삭제" on trades;
create policy "trades: 본인만 조회" on trades
  for select using (public.current_user_id() = user_id);
create policy "trades: 본인만 삽입" on trades
  for insert with check (public.current_user_id() = user_id);
create policy "trades: 본인만 수정" on trades
  for update using (public.current_user_id() = user_id)
  with check (public.current_user_id() = user_id);
create policy "trades: 본인만 삭제" on trades
  for delete using (public.current_user_id() = user_id);

-- custom_tags (update 정책 없음)
drop policy "custom_tags: 본인만 조회" on custom_tags;
drop policy "custom_tags: 본인만 삽입" on custom_tags;
drop policy "custom_tags: 본인만 삭제" on custom_tags;
create policy "custom_tags: 본인만 조회" on custom_tags
  for select using (public.current_user_id() = user_id);
create policy "custom_tags: 본인만 삽입" on custom_tags
  for insert with check (public.current_user_id() = user_id);
create policy "custom_tags: 본인만 삭제" on custom_tags
  for delete using (public.current_user_id() = user_id);
