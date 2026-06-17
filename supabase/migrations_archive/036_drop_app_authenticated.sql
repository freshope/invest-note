-- Phase 3: app_authenticated 역할 제거 (FORCE RLS 전환 정리).
--
-- 전제: Phase 2(acquire_for_user 의 SET ROLE 제거 BE, api-v1.3.0) 운영 안정 확인 완료.
-- ⚠️ 비가역: 이 시점 이후 구 BE(SET ROLE app_authenticated 방식)로 롤백 불가 —
--    역할이 사라지므로. 반드시 Phase 2 베이킹(운영 안정) 후 적용한다.
--
-- invest_note_app 은 테이블 owner 라 app_authenticated 에게 부여했던 grant 가 불필요
-- (owner 권한으로 동작). drop owned by 가 그 grant + default privileges 를 제거하고,
-- drop role 이 멤버십(grant app_authenticated to ...)까지 정리한다.
--
-- 적용: superuser 권한 필요. prod 는 docker exec psql -U postgres 로 수동
--   (호스트 포트 미publish — project_prod_db_access 참조).
--   dev 도 parity 위해 동일 적용(invest_note_app 은 owner 라 무영향).

drop owned by app_authenticated;
drop role app_authenticated;
