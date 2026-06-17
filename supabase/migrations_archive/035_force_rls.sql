-- FORCE RLS — app_authenticated 역할 제거를 위한 사전 단계 (2026-06-17).
--
-- 배경: 표준 PG 이관 후 앱 접속 역할(invest_note_app)이 테이블 owner 가 되었고,
-- owner 는 RLS 를 무조건 우회한다. 그래서 현재는 acquire_for_user 가 매 트랜잭션
-- `SET LOCAL ROLE app_authenticated`(비-owner)로 내려가 RLS 를 발동시킨다.
-- FORCE ROW LEVEL SECURITY 를 켜면 owner 도 정책 대상이 되어, SET ROLE 없이
-- GUC(app.current_user_id)만으로 격리가 성립한다 → app_authenticated 역할을 폐기 가능.
--
-- 무중단 expand/contract:
--   035(이 파일, EXPAND): FORCE 켜기. 현재 BE(SET ROLE app_authenticated)에는 무영향
--     — app_authenticated 는 비-owner라 FORCE 와 무관하게 RLS 가 이미 적용된다.
--     구/신 BE 모두와 호환(롤백 안전). prod 먼저 적용 후 신 BE 배포가 안전 순서.
--   CONTRACT(후속, 별도): BE acquire_for_user 의 SET LOCAL ROLE 제거 배포 → owner+GUC+FORCE
--     로 격리. 신 BE 안정 확인 후 app_authenticated 역할/grant 제거.
--
-- ⚠️ 역할 비대칭: FORCE 는 테이블 owner 에만 적용되고 superuser 는 항상 RLS 를 우회한다.
--   prod 앱 역할(invest_note_app)은 비-superuser owner → CONTRACT 후 정상 격리.
--   dev docker-compose 는 postgres(superuser)로 접속 → CONTRACT 적용 시 격리되지 않으므로,
--   dev 도 prod 처럼 비-superuser owner 역할로 접속하도록 바꾼 뒤 CONTRACT 를 적용해야 한다.
--
-- 대상: user_id + 정책을 가진 사용자 데이터 테이블만. kis_tokens/public.users 는
--   정책 없는 owner-only(프로비저닝·유지보수에 owner 우회 필요)라 FORCE 제외.
--
-- 적용: supabase db push 은 이관 후 폐기되어 수동 적용한다(psql -f). 추후 Alembic
--   베이스라인(라이브 pg_dump 스냅샷)에 자동 반영된다.
-- 롤백: alter table <t> no force row level security;

alter table accounts    force row level security;
alter table trades      force row level security;
alter table custom_tags force row level security;
