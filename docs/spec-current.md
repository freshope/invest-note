# Spec: 탈-Supabase Auth 2c 최종 teardown

## 배경
탈-Supabase Auth cutover(2026-06-26) + 2c 가역 코드(#1 BE fallback 제거, #2 FE/admin supabase-js 물리 제거)까지
운영 배포 완료(2026-06-30). 코드상 Supabase 결합은 대부분 소멸했으나 **런타임 결합 1축**과 **config·디렉토리 잔재**가 남음.
이 spec은 마지막 코드 teardown을 수행하고, 비가역 운영 작업(Coolify env 제거·Supabase 클라우드 삭제)은 명령만 제시한다.

## 남은 결합 (스캔 확정)
- `routers/me.py`: 회원탈퇴가 `supabase_secret_key` 없으면 503 하드가드 + 항상 GoTrue `deleteUser` 호출 → **유일 런타임 Supabase 호출**.
- `auth/identity_provider.py`: GoTrue deleteUser 어댑터(위 호출의 구현).
- `config.py`: `supabase_url`(필수)·`supabase_secret_key` 필드 + `be_jwks_uri`가 `supabase_url` 파생(placeholder).
- `supabase/` 로컬 디렉토리(config.toml·migrations_archive 39파일) + docker-compose.yml stale 주석.

## 작업 단위

### U1. 회원탈퇴 DB-only 전환 (런타임 결합 제거)
- `me.py`: 503 가드(supabase_secret_key)·`idp_delete_user` 호출·`httpx`/`get_http_client`/`idp_delete_user` import 제거. 삭제는 DB 트랜잭션(감사 INSERT→users DELETE)만. docstring 갱신.
- `auth/identity_provider.py`: 파일 삭제(유일 importer가 me.py).
- 정합성: 마이그레이션 유저의 Supabase auth.users 행은 클라우드 삭제(U4)로 소멸, BE-native 유저는 애초에 없음 → DB-only 삭제가 완전.
- **검증:** `test_me.py` 삭제 테스트를 DB-only로 재작성(503/success-supabase-call/error/network 제거, 감사 테스트는 `_make_delete_client`에서 http/secret 제거 후 유지).

### U2. config Supabase 필드 제거 + be_jwks_uri 재유도
- `config.py`: `supabase_url`·`supabase_secret_key` 필드 삭제. `be_jwks_uri`를 `be_oauth_redirect_base` 기준 재유도. 관련 주석 정리.
- `extra="ignore"`라 테스트의 `Settings(supabase_url=...)` 57개소는 무해(무시) → 수정 불필요.
- **검증:** `conftest.py` TEST_JWKS_URI를 be_oauth_redirect_base 기준으로 repoint + 테스트 settings에 be_oauth_redirect_base 공급. `test_app_config.py:177` 기대 host 갱신. `cd api && poetry run pytest -q` green.

### U3. supabase/ 디렉토리 + CI/compose 잔재 정리
- `git rm -r supabase/`(config.toml·migrations_archive 등 39파일, Alembic로 대체된 이력·로컬 CLI 설정).
- `.github/workflows/ci-api.yml` SUPABASE_URL env 제거(필드 제거로 무의미).
- `docker-compose.yml` Supabase 로컬 스택 stale 주석 정정.

### U4. 운영·비가역 (실행 안 함 — 명령/절차만 제시)
- Coolify BE: `SUPABASE_URL`·`SUPABASE_SECRET_KEY` env 제거 + 재배포.
- Coolify admin(deploy-admin.yml): `NEXT_PUBLIC_SUPABASE_*` GitHub vars 정리.
- **Supabase 클라우드 프로젝트 `phynizbvzzsvprawxkvd` 삭제(비가역)** — 롤백 카드(276825a revert) 영구 소멸. 게이트: 사용자 GO.
- PIPA: user_profiles PII 고지(개인정보처리방침 문서 갱신).

## 검증 기준
- `cd api && poetry run pytest -q` 전량 green.
- `git grep -n "supabase_url\|supabase_secret_key" api/src` = 0(주석 포함 정리).
- 회원탈퇴 DELETE /v1/me → 204(Supabase 호출 없음), 감사 로그 1건.
