# 탈-Supabase Auth — 운영 cutover Runbook (B안: 심사-cutover 디커플)

Phase 2 BE 토큰-브로커로의 **운영 전환** 절차. 코드·마이그레이션·바이너리 출시는 완료(dormant)된 상태에서,
실제 전환을 **서버 플래그 flip**으로 수행한다. 순서 자체가 gapless(데이터 무손실)의 핵심이다.

> 운영 명령은 직접 실행하지 않고 제시·확인 후 사용자가 실행한다. DB 접근은 [project_prod_db_access].

## 0. 전제 (모두 충족돼야 시작)

- [x] 마이그레이션 `0004_auth_identities` / `0005_user_profiles` / `0006_auth_token_store` 운영 적용
- [x] secure-storage shell 바이너리(`app-v1.3.0_31`) 스토어 **승인·배포(LIVE)**
- [x] 라이브 바이너리에서 **디바이스 BE 로그인 1회 성공**(crypto.subtle S256 + secure storage round-trip)
- [x] BE dormant 코드 운영 배포 (auth 라우터 mount, flag default OFF)
- [x] IdP redirect URI 등록: `https://invest-note-api.pixelwave.app/auth/callback` (Google/Kakao/Apple, additive)
- [x] `api/.env.production` BE 블록 스테이징 (Coolify 미주입)
- [ ] **보급률** — 새 바이너리가 충분히 깔린 뒤 진행(저보급 시 검증표본 적고 구앱 신규가입 갭만 길어짐)

## 핵심 불변식 (왜 이 순서인가)

1. **`/auth/*` 라우터는 `BE_AUTH_ENABLED`를 무시한다** (플래그는 FE app-config 게이트일 뿐).
   `/auth/callback`을 기능 활성화하는 건 **Coolify에 signing key + provider secret이 존재하느냐**다.
   → BE env 주입은 **freeze + 백필 이후**에만.
2. **백필 importer는 insert-only** (`INSERT ... ON CONFLICT (provider, provider_id) DO NOTHING`).
   대상 `auth_identities`에 (provider, sub)가 이미 있으면 **틀린 user를 가리켜도 교정하지 않는다.**
   → 백필 시점 `auth_identities`는 **반드시 비어 있어야** 하고, 그 전에 **어떤 BE 로그인도 발생하면 안 된다**
   (런타임 신규생성 2b-3이 행을 남기면 백필이 불가역 오염 → 기존자 고아화).
3. **freeze가 백필보다 먼저** — 동결~export 사이 신규가입자가 생기면 매핑 없이 남아 고아화.

## 1. freeze — Supabase 신규가입 동결

Supabase 대시보드 → Authentication → **Allow new signups OFF** (클라우드가 SSOT, [project_supabase_oauth_only]).
기존 로그인은 유지, 신규 신원 생성만 거부.

## 2. export — 운영 Supabase → CSV 2개

`api/scripts/export_supabase_auth.sql`의 [1]·[2] 쿼리를 운영 Supabase에 실행(SQL Editor Download CSV 또는 psql `\copy`).
산출: `identities.csv`(provider, provider_id, user_id) / `users.csv`(user_id, email, display_name, avatar_url, email_verified, providers, last_sign_in_at).

## 3. 선행 점검 (commit 전 필수)

```sql
-- (앱 DB) auth_identities 가 비어 있는가 — 불변식 #2. 0이어야 함.
SELECT count(*) FROM auth_identities;

-- (앱 DB) Supabase 신원 없는 public.users — 데모/직접 seed 계정 탐지([project_review_demo_account]).
-- 운영 export 의 user_id 집합과 비교. 있으면 백필 abort → cutover 전 정리하거나 export 에 수동 매핑 추가.
SELECT id FROM public.users
WHERE id NOT IN ( <identities.csv 의 user_id 목록> );
```

## 4. dry-run (profiles 먼저)

```bash
cd api
poetry run python scripts/import_user_profiles.py   users.csv      --dry-run   # export ⊆ public.users
poetry run python scripts/import_auth_identities.py identities.csv --dry-run   # public.users ⊆ export(coverage)
```
둘 다 통과해야 commit. (⚠️ identities dry-run은 INSERT를 건너뛰므로 FK/오염은 commit 시에만 드러남 → 불변식 #2 사전 확인이 그래서 중요)

## 5. commit (identities → profiles)

```bash
poetry run python scripts/import_auth_identities.py identities.csv --commit
poetry run python scripts/import_user_profiles.py   users.csv      --commit
```
검증: `auth_identities` distinct user_id == public.users 수, freshope 등 실 유저가 **자기 실제 sub로** 매핑됐는지 확인.

## 6. BE env 주입 (Coolify, 플래그는 아직 false)

`api/.env.production`의 BE 블록 값을 Coolify env에 주입([project_env_production_drift] — Coolify가 SSOT):
`BE_TOKEN_SIGNING_KEY`(운영 전용 ES256)·`BE_TOKEN_KID`·`BE_TOKEN_ISSUER`·`BE_TOKEN_AUDIENCE`(=`invest-note-app`, 비면 기동 실패)·
`BE_OAUTH_REDIRECT_BASE`(=`https://invest-note-api.pixelwave.app`)·`GOOGLE_*`·`KAKAO_*`·`APPLE_*`(.p8 포함).
**`BE_AUTH_ENABLED`은 아직 false 유지.**

## 7. flip — `BE_AUTH_ENABLED=true` (gapless 임계점)

Coolify env `BE_AUTH_ENABLED=true`. **반드시 5(백필) 완료 후**(hard precondition).
즉시·원자적으로 플러그인 보유 기기가 BE flow로 전환. 직후 **freshope 기기로 로그인 라운드트립 1회 확인.**
이상 시 즉시 `BE_AUTH_ENABLED=false`로 롤백.

## 롤백

- `BE_AUTH_ENABLED=false` → 클라이언트 즉시 Supabase flow 복귀.
- 필요 시 Supabase 신규가입 재허용(freeze 해제).
- 백필(auth_identities/user_profiles)은 additive라 원복 불필요(무해).
- ⚠️ flip~롤백 사이 BE flow로 가입한 진짜 신규는 앱DB-only → Supabase flow 로그인 불가(저트래픽 시 거의 0).

## cutover 후 상태

- 네이티브(새 바이너리) = BE 토큰-브로커 인증. 웹·구 바이너리 = Supabase(2c까지 공존).
- 기존자 데이터 보존(auth_identities sub→원래 UUID), flip 시 **1회 재로그인** 필요.
- 신규 가입: 새 바이너리는 BE 런타임 생성(2b-3), 구 바이너리는 막힘(2c force-update로 해소).
- Supabase 존속(default fallback + 웹). 물리 제거는 **2c**(force-update 양 스토어 승인 후, 비가역).

## 2c (별도, 신앱 안정 후)

force-update([project_force_update]) 양 스토어 승인 → Supabase default fallback 제거 · supabase-js 물리 제거 ·
`SUPABASE_*` env·`supabase/` 디렉토리·클라우드 정리 · 웹 BE flow 복구(딥링크 대체) · PIPA 고지.

---
관련: `docs/spec-history/2026-06-20-auth-decoupling-phase2b3-2b4.md`(설계 원본), `_workspace/auth-phase2-design.md`, `docs/decisions.md`(2026-06-19~20).
