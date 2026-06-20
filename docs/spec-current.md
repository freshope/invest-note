# Spec: 탈-Supabase Auth — 신규 가입 경로 (2b-3) + gapless cutover

## 배경 / 문제

Phase 2(BE token-broker)는 develop 머지·dormant 상태다. 운영 적용 직전 검토에서 결함을 발견했다:
BE OAuth callback이 `auth_identities` 매핑 miss 시 **무조건 401**(`api/src/invest_note_api/routers/auth.py:222-224`)이고,
런타임에 신규 user/매핑을 만드는 경로가 **전혀 없다**(`auth_identities` write는 batch 적재 스크립트뿐).

결과: 신앱(BE flow)에서 **(a) 진짜 신규 가입자**와 **(b) 백필 스냅샷 이후 Supabase로 가입한 기존자**가 모두 로그인 불가
→ 스토어 출시가 막힌다. 신규 가입 경로를 만들되, 기존자를 신규로 오판해 데이터를 고아화하지 않도록 **gapless** 해야 한다.

채택안(옵션 1): "expand 중 신원 발급 소스가 둘(Supabase+BE)"인 근본 문제를 **cutover 시 Supabase 신규가입 동결**로 제거한다.
동결 후 최종 백필 → `auth_identities`가 완전·확정 → **"매핑에 없는 sub = 무조건 진짜 신규"가 항상 참**.
email 매칭 불필요(기존 B1 정책 유지), delta 동기화·webhook 불필요.

## 목표 (완료 기준)

- BE callback이 매핑 miss 시 401 대신 **신규 user를 생성**하고 그 UUID로 BE 토큰을 발급한다.
- 기존자(매핑 hit) 흐름은 무회귀 — 원래 UUID로 발급(데이터 보존).
- 동시 첫 로그인(같은 provider+sub 다발)에도 **단일 user**만 생성된다(중복/고아 없음).
- 신규 user에 `user_profiles` 첫 레코드가 생성된다.
- 운영 cutover 순서(동결→백필→활성화→수동출시)가 문서로 확정돼 gapless가 보장된다.

## 설계

### 접근 방식

callback의 miss 분기를 "에러"에서 "신규 생성"으로 교체한다. 데이터 레이어 대부분은 기존 자산 재사용:

- **public.users 생성**: callback은 `acquire_for_user`(`db.py:30`)를 거치지 않고 `pool.acquire()`를 직접 쓰므로,
  신규 경로에서 `public.users(id)`를 **명시적으로** 먼저 insert해야 한다(`auth_identities.user_id` → `users(id)` FK).
- **매핑 write + race 가드**: `auth_identities`의 `UNIQUE (provider, provider_id)` 제약을 arbiter로 사용.
  단일 트랜잭션에서 `users` insert + `auth_identities` insert(`ON CONFLICT (provider, provider_id) DO NOTHING RETURNING user_id`).
  - RETURNING으로 행을 받으면 → 우리가 생성한 UUID 사용.
  - 충돌(행 없음)이면 → 경쟁에서 짐 → `_resolve_user_id` 재조회로 **승자 UUID 채택**, 빈 `users` 행은 같은 트랜잭션 롤백/정리로 고아 방지.
  - 대안: `kis_token_store`의 `pg_advisory_xact_lock` 패턴(hash(provider+sub))으로 직렬화 — 단순한 쪽 선택.
  - **provider는 `.lower()` 정규화** (적재기·`_resolve_user_id`(auth.py:85)와 일관 — 대소문자 drift로 인한 매핑 miss 차단).
- **profile**: 기존 `upsert_profile(...)`(`services/user_profile.py:40`, COALESCE/B6)를 신규에도 그대로 호출(첫 insert). 기존자/신규자 동일 호출.
- **신규 마이그레이션 없음**: 0004/0005/0006(head)로 테이블 이미 존재.
- **FE 변경 없음**: 신규/기존 모두 동일 OAuth 버튼·동일 flow. callback 결과만 다름(딥링크 code→token 동일).

### 안전 의존 (코드 아닌 운영 가드)

신규 생성 코드는 "매핑에 없으면 신규"라고 신뢰하므로, **BE 활성화는 반드시 완전한 백필 이후**여야 한다(아니면 미백필 기존자=중복 생성).
이 순서는 코드가 아니라 **cutover runbook으로 보장**한다(아래). 활성화 전 백필 완료가 hard precondition.

### 주요 변경 파일

- `api/src/invest_note_api/routers/auth.py` — `_handle_callback` miss 분기: 401 → 신규 생성 호출. 신규 user도 `upsert_profile` 호출 보장.
- `api/src/invest_note_api/services/auth_identity.py` (신규) — 런타임 단건 생성 함수(race-safe). batch `auth_identity_import.run_import`와 분리.
- `api/tests/test_auth_router.py` — 신규/기존/race/profile 테스트.
- `docs/decisions.md` — 신규 가입 경로 + gapless cutover(동결) 결정 기록.

## 구현 체크리스트

- [x] `auth_identity` 런타임 단건 생성 함수: advisory xact lock 내 재조회 + users insert + auth_identities insert → user_id 반환. provider 소문자. (`services/auth_identity.py`)
- [x] `_handle_callback` miss 분기를 신규 생성으로 교체(`auth.py:222-224`). 기존 hit 경로 무변경.
- [x] 신규 user에도 `upsert_profile` 호출(첫 profile) — 기존 callback 공통 호출 경로 재사용, 무회귀.
- [x] 테스트: 신규 sub → users+auth_identities 생성 + 토큰 sub=새 UUID + profile 생성. (`test_auth_router.py::test_b1_mapping_miss_creates_new_user`)
- [x] 테스트: 기존 sub → 원래 UUID(무회귀, hit 경로 그대로). (`test_b1_mapping_hit_mints_original_uuid_token`)
- [x] 테스트: 신규 생성 로직 단위(fake) — `test_auth_identity.py`.
- [x] 테스트: **실 DB de-dup 안전속성** — sequential(FK/UNIQUE/소문자) + concurrent(asyncio.gather 두 연결 → 단일 user, 중복/고아 0). `test_auth_identity_db.py` (`INVEST_NOTE_TEST_DATABASE_URL` gated, CI migrate-verify 주입). 로컬 실 PG 2 passed.
- [x] `cd api && poetry run pytest -q` 전체 무회귀: 790 passed, 1 skipped (test_me/issuer registry expand gate 포함). 실DB 테스트 +2(미설정 시 skip).
- [x] `docs/decisions.md` 갱신 (2026-06-20 2b-3 항목).

## 운영 cutover runbook (gapless 보장 — 문서로 확정)

> 순서 자체가 gapless의 핵심. 운영 명령은 직접 실행하지 않고 제시만(VPS SSH + docker exec / 마이그레이션·백필은 confirm).

0. (선행, 무영향) BE dormant 코드 운영 배포 + 마이그레이션 0004/0005/0006 적용(dry-run→confirm). Coolify 운영 배포 브랜치 확정.
1. **Supabase 신규가입 동결** — 대시보드 Auth "Allow new signups" off(`GOTRUE_DISABLE_SIGNUP`). 기존 로그인 유지, 신규 신원 생성만 거부.
2. **최종 백필** — `import_auth_identities` → `import_user_profiles`(identity 선행/FK, dry-run→commit, confirm). 동결 후라 완전·확정.
3. **BE 활성화** — `be_token_*` + provider secret + `be_oauth_redirect_base` 등 Coolify env 주입(SSOT). `be_token_audience` 비면 기동 실패(fail-fast) 주의.
4. **신앱 수동 출시** — App Store "Manually release" / Play "Managed publishing". 동결 창 최소화 + [활성화→라이브] 순서 보장.

\* IdP redirect_uri(BE callback) 추가는 3 이전. force-update(구앱 sunset)·Supabase 검증 제거·세션 잔여물 cleanup은 **2c(별도, 신앱 안정 후)**.

## 우려사항 / 리스크

- **활성화 전 백필 미완 시 기존자 중복 생성** — 코드가 아닌 runbook 순서로 가드(활성화는 백필 완료 후). 운영 절차 준수가 전제.
- **race 구현 정확도** — UNIQUE 제약 + ON CONFLICT 또는 advisory lock. 테스트로 단일 user 보장.
- **동결 창 동안 신규가입 차단** — 수동 출시로 분~시간 수준 압축. 모바일 단일 제품이라 영향 미미.
- 범위 밖(2c): force-update, Supabase 검증 제거, supabase-js·세션 잔여물 cleanup.
