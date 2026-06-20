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
- 운영 cutover 순서(shell 사전출시→동결→백필→활성화→서버 플래그 flip)가 문서로 확정돼 gapless가 보장된다.

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
> **B안(심사-cutover 디커플):** secure-storage 네이티브 플러그인을 포함한 shell 바이너리를 **먼저 일반 출시**해 두고(BE flow는 서버 플래그로 OFF=Supabase 유지), 실제 cutover는 **서버 플래그 flip**으로 수행한다. flip이 즉시·통제 가능하므로 동결 창이 심사 타이밍에 묶이지 않는다.

**사전 단계 (심사 필요, cutover와 분리):**
- **A. shell 바이너리 출시** — secure-storage 플러그인 포함 + BE-flow JS는 present하되 **서버 플래그 OFF**(런타임 Supabase flow 유지 → 무동작·무영향). 일반 출시(타이밍 압박 없음). 기기에 점진 보급.
  - 신규 네이티브 델타는 secure-storage 플러그인 **하나뿐**(딥링크 scheme `app.pixelwave.investnote://auth`는 기존 바이너리에 이미 등록·BE flow 재사용). 그 외 auth 로직은 전부 JS.

**cutover (전부 서버·플래그 — 심사 무관):**
0. (선행, 무영향) BE dormant 코드 운영 배포 + 마이그레이션 0004/0005/0006 적용(dry-run→confirm). Coolify 운영 배포 브랜치 확정.
1. **Supabase 신규가입 동결** — 대시보드 Auth "Allow new signups" off(`GOTRUE_DISABLE_SIGNUP`). 기존 로그인 유지, 신규 신원 생성만 거부.
2. **최종 백필** — `import_auth_identities` → `import_user_profiles`(identity 선행/FK, dry-run→commit, confirm). 동결 후라 완전·확정.
3. **BE 활성화** — `be_token_*` + provider secret + `be_oauth_redirect_base` 등 Coolify env 주입(SSOT). `be_token_audience` 비면 기동 실패(fail-fast) 주의.
4. **서버 플래그 flip ON** — shell 바이너리(플러그인 보유) 기기가 BE flow로 즉시·원자적 전환. **이 시점이 gapless 임계점**(클라이언트가 BE callback을 처음 때리는 = 신규 생성 시작). flip은 **반드시 (2) 백필 완료 후**(hard precondition). 이상 시 즉시 flip OFF로 롤백.

\* IdP redirect_uri(BE callback) 추가는 3 이전. force-update(구앱 sunset)·Supabase 검증 제거·세션 잔여물 cleanup은 **2c(별도, 신앱 안정 후)**.
\* 구 바이너리(플러그인·플래그 코드 없음)는 flip의 영향을 받지 않고 Supabase flow 유지 → 동결 후 신규가입 불가. 이 모집단은 **force-update(2c)**로 신 바이너리 전환 유도(별도 문제).

## 우려사항 / 리스크

- **플래그 flip 전 백필 미완 시 기존자 중복 생성** — 코드가 아닌 runbook 순서로 가드(flip은 백필 완료 후). 운영 절차 준수가 전제.
- **race 구현 정확도** — UNIQUE 제약 + ON CONFLICT 또는 advisory lock. 테스트로 단일 user 보장.
- **동결 창 동안 신규가입 차단** — 서버 플래그 flip이 즉시·원자적이라 동결 창을 분 단위로 압축(심사 타이밍 무관). 모바일 단일 제품이라 영향 미미.
- 범위 밖(2c): force-update, Supabase 검증 제거, supabase-js·세션 잔여물 cleanup.

---

# Phase 2b-4: BE flow 서버 플래그

작성: 2026-06-20 | spec-planner | 설계: 리더 확정(B안 cutover flip 메커니즘) | 2b-3과 한 묶음 출시

## 배경 / 목표

위 cutover runbook의 4단계 **"서버 플래그 flip ON"** 이 의존하는 실제 메커니즘을 구현한다.
현재(2b-2) 네이티브는 `isNativePlatform()` 만으로 **무조건 BE flow** 를 탄다 → 서버에서 끌 방법이 없다.

B안(심사-cutover 디커플)은 secure-storage 플러그인을 포함한 shell 바이너리를 **BE flow OFF 로 먼저 일반 출시**해 두고,
실제 cutover 는 **서버 플래그 flip(OFF→ON)** 으로 수행한다. 따라서:

- **플래그 OFF 면 네이티브도 Supabase flow 로 폴백**해야 한다(= 현재 라이브 동작).
- 플래그 ON 으로 flip 하면 플러그인 보유 기기가 즉시·원자적으로 BE flow 로 전환된다.
- flip = Coolify env 변경(force-update·다른 운영 토글과 동일 운영 모델, 신규 마이그레이션 없음).

**핵심 무회귀 게이트:** 플래그 default OFF → 이 변경 배포 즉시 동작 변화 0(현재 라이브와 100% 동일)이어야 한다.

## 설계 (확정 — 재설계 금지)

### BE — app-config 재사용 (단일 passthrough)
강제 업데이트 플래그를 이미 나르는 무인증 public 엔드포인트 `GET /app-config` 에 필드 하나 추가.
신규 엔드포인트·마이그레이션 없음.

- `config.py`: `be_auth_enabled: bool = False` (env, dormant 안전 default). `min_supported_version` 등과 같은 패턴.
- `schemas/app_config.py`: `AppConfigResponse` 에 `be_auth_enabled: bool` 추가. `CamelModel` → wire 키 `beAuthEnabled`.
- `routers/app_config.py`: `get_app_config` 에서 `settings.be_auth_enabled` passthrough.

### FE — 공유 캐시 + 단일 predicate seam

**★핵심 함정:** 플래그는 app-config **async fetch** 로 오는데, auth 분기 결정(login 버튼/딥링크/refresh/cold-start)은
여러 시점에 **동기적으로** 일어난다(`lib/auth/index.ts` 6함수 전부 `isNativePlatform()` 동기 분기).
→ 분기 시점에 플래그 값이 **동기 가용**해야 하고, **미수신/fetch 실패/타임아웃/필드 부재 시 반드시 fail-safe=OFF**
(=Supabase flow=현재 라이브 동작)로 폴백.

해법(모듈 싱글톤 캐시):
- `app/src/lib/api/app-config.ts`: `AppConfig` 타입에 `beAuthEnabled: boolean` 추가.
  같은 모듈에 **sync getter/setter** 노출 — 모듈 스코프 `let beAuthEnabledCache = false;` + `setBeAuthEnabled(v)` + `getBeAuthEnabled(): boolean`(default **false**, 미설정 시 false 반환).
  `fetchAppConfig()` 가 성공 시 `setBeAuthEnabled(config.beAuthEnabled ?? false)` 로 캐시를 채운다(필드 부재→`?? false`로 OFF).
- `app/src/components/providers/ForceUpdateGate.tsx`: 이미 startup 에 `fetchAppConfig()` 를 호출하므로 **그 호출이 캐시를 채우는 유일 seam**.
  단, 현재 `ForceUpdateGate` 는 `isNativePlatform()` 일 때만 fetch 한다 — 이는 BE flow 가 네이티브 전용이라 정합(웹은 어차피 Supabase 무조건).
  fetch 성공 시 `setBeAuthEnabled` 호출 추가(fetchAppConfig 내부에서 set 하면 ForceUpdateGate 무수정 가능 — **이 방식 우선**).
- `app/src/lib/auth/index.ts`: 내부 predicate **단일 seam** 도입 —
  `function isBeAuthFlow(): boolean { return isNativePlatform() && getBeAuthEnabled(); }`.
  현재 `isNativePlatform()` 게이트를 쓰는 **6함수**(`signInWithOAuth`/`getAccessToken`/`getUser`/`signOut`/`subscribe`/`exchangeCodeForSession`)가
  `isNativePlatform()` → `isBeAuthFlow()` 로 교체. `&& beAuthEnabled` 를 6곳에 흩뿌리지 말 것.

### 게이트가 **불필요**한 지점 (코드 확인 — 과게이팅 금지)
- `app/src/components/providers/CapacitorDeepLinkHandler.tsx:16` — `isNativePlatform()` 게이트는
  "네이티브에서만 딥링크 처리" 의미. code 추출 후 `exchangeCodeForSession` 에 위임할 뿐 BE/Supabase 분기를 자체적으로 안 한다
  (양 flow 모두 PKCE code 콜백). 분기는 `exchangeCodeForSession`(6함수 중 하나)이 담당 → **플래그 불필요**.
- `app/src/app/login/page.tsx:66` — `native` 분기는 `redirectTo` 선택 + `Browser.open(url)` 뿐.
  url 의 내용만 BE/Supabase 로 다르고(그 분기는 `signInWithOAuth` 내부), page 의 분기 의미는 "네이티브=인앱 브라우저 open" 으로 양 flow 공통.
  OFF 시 `signInWithOAuth` 가 supabase url 을 반환하면 그대로 인앱 브라우저로 열려 2b-2 이전 라이브 동작과 동일 → **플래그 불필요**.
- 웹: `isBeAuthFlow()` 가 `isNativePlatform()===false` 에서 항상 false → 웹은 플래그 값과 무관하게 무조건 Supabase(무회귀).

### 세션 내 불변 (cross-flow 불일치 차단)
플래그는 **startup 1회 fetch 후 세션 내 불변**으로 취급한다. mid-flow 에 값이 바뀌면
`signInWithOAuth` 는 Supabase 경로로(verifier 저장 안 함) 갔는데 `exchangeCodeForSession` 은 BE 로 가는
cross-flow 불일치로 로그인이 깨진다. sync getter 가 항상 같은 값을 반환하면(캐시는 fetch 성공 시 1회 set) 자연히 보장.

## 구현 체크리스트

**BE (단일 태스크):**
- [ ] `config.py` `be_auth_enabled: bool = False` 추가
- [ ] `schemas/app_config.py` `AppConfigResponse.be_auth_enabled: bool` 추가
- [ ] `routers/app_config.py` passthrough
- [ ] `tests/test_app_config.py`: ① 응답에 `beAuthEnabled` 포함 ② default False ③ env 토글 시 True ④ 기존 케이스 무회귀

**FE:**
- [ ] `lib/api/app-config.ts`: `AppConfig.beAuthEnabled` + 모듈 캐시(`getBeAuthEnabled`/`setBeAuthEnabled`, default false) + `fetchAppConfig` 성공 시 `setBeAuthEnabled(config.beAuthEnabled ?? false)`
- [ ] `lib/auth/index.ts`: `isBeAuthFlow()` 단일 seam + 6함수 게이트 교체
- [ ] 테스트: OFF→Supabase 분기 / ON→BE 분기 / fetch 실패 시 캐시 OFF 유지 / 필드 부재 시 OFF / 웹 무회귀

**DOC:**
- [ ] `docs/decisions.md` 2b-4 플래그 결정 기록

## 검증 기준

- BE: `cd api && poetry run pytest tests/test_app_config.py -q` + 전체 `poetry run pytest -q` 무회귀
- FE: `pnpm -C app exec tsc --noEmit` + `pnpm -C app test` 전체 무회귀
- BE↔FE shape 정합: 응답 `beAuthEnabled`(camel) ↔ `AppConfig.beAuthEnabled`
- 무회귀 canary: default OFF 면 네이티브가 Supabase flow(현재 라이브)와 동일. 웹은 플래그 무관 항상 Supabase.

## 리스크 / carry-forward

- **startup config-resolve 전 짧은 창:** config fetch 완료 전 네이티브 auth 분기가 일어나면 OFF 폴백(Supabase flow).
  cutover 맥락에선 무해 — expand 중 기존자 Supabase 로그인은 여전히 동작하고, 신규는 config 로드 후 재시도(앱 재진입/버튼 재탭)로 ON 경로 진입.
  코드로 해결할 문제가 아니라 fail-safe 의 의도된 동작.
- **wire 경계 런타임 미검증:** `fetchAppConfig` 가 `res.json() as AppConfig`(런타임 스키마 검증 없음).
  구 BE(필드 미제공)와 신 FE 조합 시 `beAuthEnabled` undefined → `?? false` 로 OFF. QA-FE 가 "필드 부재→OFF" 케이스로 가드.
- **디바이스 실측 carry-forward 유지(2b-2):** secure storage·WebCrypto S256 는 jsdom/node 에 항상 존재해 unit test 가 디바이스 부재를 못 잡음.
  flip ON 전 iOS·Android 실측 1회 여전히 필수(이 변경이 추가하는 것 없음, 기존 carry-forward 유지).
- **flip 절차:** flip 은 Coolify env `BE_AUTH_ENABLED=true`. runbook 4단계의 hard precondition(백필 완료 후) 준수 — 이 spec 은 메커니즘만 제공, 절차 가드는 runbook 소관.
