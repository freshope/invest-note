-- 사용자 정의 분석 태그 레지스트리 — 선택 가능한 태그 카탈로그.
-- trades.custom_tags(031) 가 "거래에 선택된 라벨"이라면, 이 테이블은 사용자가 만든
-- "선택 가능한 태그 목록"이다(거래 부착 없이도 영속). 등록/수정 폼의 분석 태그 그리드는
-- 프리셋 4종 + 이 레지스트리 태그를 함께 노출한다.
-- 거래는 라벨(text)을 저장하므로 레지스트리 행을 삭제해도 과거 거래 라벨은 불변(분석 안전).
create table public.custom_tags (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  label      text not null,
  created_at timestamptz not null default now(),
  unique (user_id, label)
);

create index custom_tags_user_id_label_idx on custom_tags (user_id, label);

-- RLS: 본인 데이터만 접근 (trades 정책 미러). update 는 없음(생성/조회/삭제만).
alter table custom_tags enable row level security;

create policy "custom_tags: 본인만 조회" on custom_tags
  for select using (auth.uid() = user_id);

create policy "custom_tags: 본인만 삽입" on custom_tags
  for insert with check (auth.uid() = user_id);

create policy "custom_tags: 본인만 삭제" on custom_tags
  for delete using (auth.uid() = user_id);
