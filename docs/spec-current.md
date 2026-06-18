# Spec: RLS 제거 — 보안 경계를 앱 레이어 user_id 필터로 단일화

## 배경 / 문제

1인 개발 초기 단계에서 RLS(Row Level Security)가 주는 보안 이득보다 운영/개발 복잡도가 더 크다.
- 데이터 backfill 마이그레이션이 FORCE RLS에 막혀 **silent no-op** (GUC 미설정 시 `current_user_id()`=NULL → 0 rows).
- 마이그레이션·어드민에 superuser/BYPASSRLS 별도 연결(`MIGRATION_DATABASE_URL`, `ADMIN_DATABASE_URL`)을 운용.
- 매 요청 GUC 주입(`acquire_for_user`)·RLS 정책·`current_user_id()` 함수라는 간접 레이어.

조사 결과 user-scoped 쿼리 47개 중 41개는 이미 `WHERE user_id=$1`을 명시(중복 방어)하고 있어, RLS는 사실상 6곳만 떠받친다. 그 6곳을 명시 필터로 메우면 RLS를 안전하게 걷어낼 수 있다.

## 목표

accounts/trades/custom_tags의 RLS를 완전히 제거하고 보안 경계를 앱 레이어의 명시적 `user_id` 필터로 단일화한다. RLS 제거로 redundant해진 admin 전용 BYPASSRLS 풀(`ADMIN_DATABASE_URL`/`invest_note_admin`)도 메인 풀로 통합한다. (BE only)

## 설계

### 핵심 결정
- **순서의 철칙:** RLS는 *맨 마지막에* 내린다. 앱 코드의 `user_id` 필터를 먼저 전부 메운 뒤 DB의 RLS를 끈다.
- **배포 순서 제약:** GUC를 안 set하는데 RLS가 켜져 있으면 `current_user_id()`=NULL → 전 행 거부. `current_user_id()` 드롭 전 `accounts` INSERT의 함수 호출을 먼저 제거해야 함. → P0 코드 → RLS-drop 마이그레이션 → GUC-set 제거 코드 순.
- **마이그레이션 권한:** 0002_drop_rls는 superuser(postgres)로 실행한다. 함수 owner가 postgres라 `DROP FUNCTION`이 owner/superuser를 요구하고(app role은 거부 실증됨), `alembic_version`도 postgres 소유라 alembic 자체가 superuser 필요 — baseline과 동일. 정책 DROP·DISABLE·NO FORCE만이면 table owner로 충분하나 함수 DROP 때문에 superuser 경로로 통일.
- admin 통합: RLS 제거 후 메인 풀(`invest_note_app`, owner) plain 연결로 cross-user 조회 가능. 게이트는 allowlist(`require_admin`)만 유지.
- 마이그레이션 히스토리 클린: 0002_admin_role은 운영 미반영 → 새 드롭 리비전 대신 0002 롤백·삭제. 최종 체인 `0001_baseline ← 0002_drop_rls`.

### 주요 변경 파일
- `api/src/invest_note_api/db_ops/accounts_repo.py` — `list_accounts`/`patch_account`에 user_id 명시
- `api/src/invest_note_api/db_ops/trades_repo.py` — `assert_account_exists`에 user_id
- `api/src/invest_note_api/routers/accounts.py` — L120/L126 user_id 필터, L48 INSERT 파라미터화, 호출부 갱신
- `api/src/invest_note_api/db.py` — `acquire_for_user` GUC set 제거, `get_admin_pool`/`acquire_admin` 제거
- `api/src/invest_note_api/auth/constants.py` — `DB_GUC_USER_ID` 제거
- `api/src/invest_note_api/routers/admin.py` — 메인 풀(`get_pool`+plain acquire) 사용, 503 분기 제거
- `api/src/invest_note_api/main.py`, `config.py` — `admin_pool` lifespan·`admin_database_url` 제거
- `api/alembic/versions/0002_admin_role.py` — 삭제(롤백 후)
- `api/alembic/versions/0002_drop_rls.py` — 신규 (정책/FORCE/함수 드롭, down_revision=0001_baseline, +downgrade)
- `api/tests/test_admin_crud.py` — `get_pool` override 전환, 503 테스트 제거
- 신규 실DB cross-user 격리 테스트 + CI `migrate-verify` 단계
- 운영: Coolify `ADMIN_DATABASE_URL` 제거 (안내)

## 구현 체크리스트
- [x] P0: accounts_repo / trades_repo / routers/accounts(+portfolio) 7곳 user_id 명시 + 호출부 갱신
- [x] P0: `cd api && poetry run pytest -q` 그린 확인 (RLS 아직 on, 동작 불변)
- [x] P1: db.py GUC set 제거 + constants 정리 (transaction 래퍼는 유지)
- [x] P2: 0002_admin_role 롤백(로컬 0001)·파일 삭제 → `0002_drop_rls` 신규 작성 (+downgrade 왕복 검증)
- [x] P3: admin 라우트 메인 풀 통합 + main/config/db 정리
- [x] 테스트: admin 테스트 전환 + 실DB 격리 테스트 신설 + CI 단계 추가
- [x] `alembic upgrade head` 빈 PG 성공 + 체인 `0001_baseline ← 0002_drop_rls` 확인
- [x] 메모리 갱신: project_portable_rls / project_admin_panel / project_alembic_migrations
- [ ] (운영) prod 롤아웃 + Coolify `ADMIN_DATABASE_URL` 제거 — 사용자 실행

## 배포(롤아웃) 순서 — 운영 적용 시
운영은 0002_admin_role 미적용(=0001_baseline)이라 롤백 단계 불필요. **prod api 컨테이너엔 alembic이 없으므로**(Dockerfile은 src/만 COPY) alembic이 아니라 `psql -U postgres`로 적용한다(baseline stamp와 동일 관행).
1. P0 코드 배포 (명시 user_id, RLS on) — 동작 불변.
2. prod DB에 0002_drop_rls upgrade SQL 적용 + 버전 갱신 (superuser):
   ```
   docker exec -i <prod_db> psql -U postgres -d invest_note -v ON_ERROR_STOP=1 < (0002_drop_rls.py upgrade() 의 SQL)
   docker exec <prod_db> psql -U postgres -d invest_note -c "UPDATE public.alembic_version SET version_num='0002_drop_rls';"
   ```
   → RLS off.
3. P1+P3 코드 배포 (GUC set 제거, admin 통합).
4. Coolify에서 `ADMIN_DATABASE_URL` 제거 (있다면).
- dev/로컬: superuser MIGRATION_DATABASE_URL로 `alembic downgrade 0001_baseline`(0002_admin_role 적용 상태였음) → 파일 삭제 → `alembic upgrade head`. (이미 완료)
- 운영 DB 명령은 직접 실행하지 않고 사용자에게 제시 (feedback_no_prod_command_execution).

## 우려사항 / 리스크
- **(높음, 비대칭) 보안 백스톱 상실:** RLS 제거 후 user_id 필터 누락 한 번이 cross-user 금융데이터 유출. 완화: P0 6곳 + 실DB 격리 테스트 영구 회귀 가드.
- **(중) 배포 순서:** 1→2→3 위반 시(특히 P1을 마이그레이션 전 배포) 전 행 거부로 앱 깨짐. 완화: 순서 명시, dev 단일 검증 선행.
- **(중) admin 활성화 모델 변경:** 통합 후 admin 항상 활성, allowlist가 유일 게이트(권한 경계 한 겹 감소).
- **(낮음) 가역성:** 0002_drop_rls downgrade로 RLS 복원 (정책 문구는 baseline_schema.sql과 일치).
