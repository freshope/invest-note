# Supabase Auth 종속성 제거 Phase 2b-1 — OAuth 중개 + BE 토큰 발급 + refresh + 프로필 수집 (BE) 사양서

작성: 2026-06-19 | 근거: `_workspace/auth-phase2-design.md`(advisor 검토 완료 설계 노트, #1~#7 + profile), `docs/spec-history/2026-06-19-auth-decoupling-phase2a.md`(2a expand 토대 — 완료/dormant, **2a finish(Q5/#32) 시 git 의 spec-current 2a 본문에서 생성**), `_workspace/02_be_changes.md`·`_workspace/04_qa_report.md`(2a BE 산출물 + 2b 인수 노트 2건), `_workspace/auth-decoupling-research.md`.

라이브러리(사용자 지정): **Authlib**(IdP OAuth/OIDC code flow 중개 — 2b 신규 도입) + **PyJWT**(2a `be_token.py` 재사용, BE 토큰 ES256 서명/검증).

> **Phase 2a 는 완료·커밋·dormant.** 2a 태스크 #19~#32 는 건드리지 않는다(A1/Q1/Q5 는 운영 토큰·DB 적용 confirm 대기로 open 유지). 이 스펙은 **2b-1(BE) 만 상세 분해**한다. 2b-2(FE 전환)·2c(contract)는 본 문서 말미 "후속" 참조. (직전 spec-current 의 2a 본문은 `docs/spec-history/2026-06-19-auth-decoupling-phase2a.md` 로 보관 — 2a finish 시.)

---

## 배경 / 목적

2a 가 깐 expand 토대(issuer registry 검증 경로 + BE 토큰 mint 헬퍼/JWKS + auth_identities 매핑 인프라) 위에서, **BE 가 실제로 OAuth 를 중개하고 자체 토큰을 발급**한다. 목표(사용자): "API 중심으로 구현하여 추후 IdP 교체에 백엔드 배포만으로 대응" + "Supabase 에서 수집하던 사용자 정보를 그대로 수집".

2b 자체가 거대(OAuth 중개 + refresh + FE 전환 + profile)하므로 **2b-1(BE) / 2b-2(FE)** 로 분할하여 위험을 단계로 격리한다(리더 승인 2026-06-19).

| sub | 범위 | 위험 격리 |
|-----|------|----------|
| **2b-1 (이 스펙, BE)** | OAuth 중개 라우터(Authlib) + (provider,sub)→UUID 해석 + BE access/refresh 발급 + 일회용 code/state/verifier·refresh **DB 영속**(인스턴스 무관) + BE 토큰 활성화(dormant 해제) + profile(user_profiles + 백필 + upsert) + 2a 인수 수정 2건 | 여기서부터 BE 토큰 실발급. **단, expand 유지** — Supabase fallback(2a default) 검증 무회귀가 hard gate(구 앱 무영향). FE 미변경. |
| 2b-2 (개요, FE) | lib/auth swap(BE flow) + refresh-aware getAccessToken(401→refresh→retry) + 딥링크 일회용 code→`/auth/token` + 토큰 store(Capacitor secure storage) + supabase-js 완전제거 **검토** | 신 앱만 BE flow. 구 앱은 expand 동안 Supabase 토큰 유지. |
| 2c (개요) | contract — Supabase 검증 제거 + supabase-js 제거. force-update 로 구 앱 sunset + **양 스토어 승인 후에만**([[project_force_update]]). | 범위 밖. |

---

## 범위 (Scope)

**포함 (2b-1, BE only):**
- **Authlib provider clients**(비균일): Google OIDC discovery / Kakao OAuth2+userinfo(full OIDC 아님) / Apple JWT-client-secret. config 에 provider별 client_id/secret/redirect 추가.
- **OAuth 중개 라우터**: `GET /auth/login?provider=` → IdP authorize 리다이렉트(redirect_uri=BE callback). `GET /auth/callback` → code 교환 + IdP sub 추출 + `(provider, sub)→UUID` 해석(2a `auth_identities`) + BE access/refresh 발급 + 일회용 code 로 딥링크 리다이렉트. `POST /auth/token` → 일회용 code→BE access+refresh 교환. `POST /auth/refresh` → refresh 회전.
- **OAuth transient store(DB short-TTL)**: state·PKCE verifier(callback 검증용) + 일회용 authorization code(딥링크↔/auth/token). **single-use + 만료 + 인스턴스 무관**(리더 함정 — 스케일아웃 lockout 차단).
- **refresh token DB 저장**(0006): 해시 저장(평문 금지) + 회전 + 만료. kis_tokens 의 server-only-secret 패턴(plain pool, RLS 없음, advisory lock) 준용.
- **BE 토큰 활성화**: dormant 해제. `be_token_*` env 채워지면 mint/registry 활성. **be_token_audience fail-fast**(빈 값이면 per-issuer aud 격리 붕괴 → 활성 시 기동 실패, 인수노트#1).
- **2a 인수 수정 #2(be_jwks_uri 호스트)**: 자기검증은 **in-process public key 직접 주입**(self-fetch 제거, P8 self-HTTP 취약성 + 호스트 placeholder 동시 제거). 외부 JWKS 엔드포인트(`/auth/.well-known/jwks.json`, 2a 생성)는 **유지**(미래 외부 검증자용).
- **profile(서브트랙)**: `user_profiles` 테이블(0005, FK→users.id cascade) + Supabase `auth.users` export 백필 스크립트(rollback guard, 작성만) + callback 시 IdP userinfo upsert(**COALESCE — last_sign_in 항상 갱신, email/name/avatar/email_verified 는 null 이면 기존값 유지**).
- 유닛/통합 테스트 + `docs/decisions.md` 갱신.

**제외 (명시적):**
- **2b-2 일체(FE)**: lib/auth 전환, getAccessToken refresh 흡수, 딥링크 핸들러 code→/auth/token, 토큰 store, supabase-js 제거. **2b-1 은 BE only.**
- 2c 일체: Supabase 검증 제거, force-update 가드.
- **DB 마이그레이션·적재·env 키 실제 적용** — 0004(미적용)+0005+0006 작성만, 적용은 사용자 confirm. 백필 스크립트는 작성만, 운영 실행은 confirm.
- Supabase iss 핀 활성화(2a default `oidc_issuer=""` 유지 — A1 실측 별도 단계).

## 가정 (Assumptions)

- **OAuth transient store = DB 테이블 채택**(in-process 아님). 리더 함정 반영: 현재 단일 인스턴스이나 uvicorn `--workers`↑/Coolify replica↑ 시 in-process 는 즉시 lockout. code 는 60s 단명이라 DB 부담 작음. → 0006 에 refresh + transient 함께.
- **redirect_uri = BE callback 고정**(`{BE}/auth/callback`). 딥링크 스킴(`app.pixelwave.investnote://auth/callback`)은 BE→앱 최종 단계에만, IdP redirect_uri 아님.
- BE access token TTL = 1h(2a `mint_be_token` 기본), refresh TTL = 장기(예 30d, decisions 확정). refresh 회전 = 사용 시 신 refresh 발급 + 구 refresh 무효화.
- Apple = Supabase Service ID 재사용(sub 보존, 2a 결정). client secret = 주기 재생성 서명 JWT(Authlib Apple 특정).
- Kakao = full OIDC 아님 → OAuth2 token + `/v2/user/me` userinfo. Kakao `id`(숫자) = 2a 적재 `provider_id` 와 일치해야 매칭(불일치 시 고아화).
- profile 백필 export = 운영자가 2a `auth.identities` 와 **같은 덤프**에 `auth.users` 프로필 컬럼 포함(외부 절차, 1회).

---

## ⚠️ 최대 함정 체크리스트 (구현 전 필독)

| # | 함정 | 가드 |
|---|------|------|
| **B1 (HINGE)** | **identity 매핑 없는 IdP sub 로 BE 토큰 발급 → 기존 데이터 전부 고아화(확실).** callback 이 IdP sub 로 새 UUID mint 하면 trades/accounts 가 원래 UUID 에 묶여 고아. | callback 은 **반드시** `(provider, IdP sub)→auth_identities.user_id` 조회 후 그 UUID 로 `mint_be_token(sub=원래 UUID)`. 매핑 miss = **에러(새 user 생성 금지·email 매칭 금지)**. verify: 매핑된 sub→원래 UUID 토큰, 매핑 없는 sub→401/명시 에러(고아 user row 생성 0). |
| **B2 (HINGE — 리더 추가)** | **transient store in-process → callback(생성)/token(소비)이 다른 워커·replica 면 miss → 로그인 실패.** state/verifier/일회용 code 동일. 현재 단일 인스턴스라 잠복, 스케일아웃 즉시 깨짐. | **DB short-TTL 테이블**(인스턴스 무관). verify: 저장→다른 conn 으로 소비 성공(인스턴스 간 시뮬), 만료/소비 후 재조회 None. in-process 고수 금지. |
| **B3** | **일회용 code replay** → 토큰 재발급(탈취 시 영구 발급). | code = **single-use**(소비 시 즉시 삭제/소진 표시) + short TTL(예 60s). verify: 동일 code 2회 교환 → 2회차 reject. |
| **B4** | **딥링크에 토큰 직접 노출** → URL 로깅/히스토리/스킴 가로채기로 토큰 유출. | 딥링크엔 **일회용 code 만**(access/refresh 직접 미노출). 앱이 `/auth/token` 으로 교환. verify: callback 리다이렉트 URL 에 access_token/refresh_token 문자열 부재. |
| **B5** | **refresh token 평문 DB 저장** → DB 유출 시 전 사용자 영구 토큰. | **해시 저장**(예 sha256) + 회전(사용 시 신규 발급·구 무효) + 만료. verify: DB 에 평문 부재, 회전 후 구 refresh→401, 만료 refresh→401. |
| **B6** | **profile upsert null clobber** — Apple 재로그인 시 이름/email null → 기존 저장값 덮어씀(Apple 은 첫 인증만 제공, 백필이 유일 보존인데 재로그인이 지움). Kakao email optional 동일. | upsert = **COALESCE**: `last_sign_in` 항상 갱신, `email`/`display_name`/`avatar_url`/`email_verified` 는 IdP 가 null/미제공이면 **기존값 유지**. verify: 값 있는 첫 upsert → 이후 null upsert → 기존값 보존 + last_sign_in 만 갱신. |
| **B7** | **be_token_audience 빈 값으로 BE 활성** → BE aud 가 Supabase `authenticated` 로 폴백(`or AUTH_ROLE`) → per-issuer aud 격리가 iss-only 로 격하(인수노트#1). | **fail-fast**: `be_token_enabled`(signing key 있음)인데 `be_token_audience` 빈 값이면 기동/검증 에러. dormant(키 없음)는 무영향. verify: enabled+빈 aud → 명시 에러, enabled+aud 있음 → 정상. |
| **B8 (인수노트#2)** | **be_jwks_uri 호스트 placeholder** — `{supabase_url}/auth/...` 로 빌드 → self-fetch 시 틀린 호스트. 2a A8 string-mock 이 구조적으로 못 잡음(잠복). | 자기검증 = **in-process public key 직접 주입**(self-fetch 안 함). registry 의 BE entry 가 jwks_uri HTTP fetch 대신 in-process key 사용하도록 verifier 조정. **string-mock 금지 — 실제 키 경로 행사 verify**(mint→in-process key 검증 round-trip). 외부 `/auth/.well-known/jwks.json` 은 유지(미래 외부 검증자). |
| **B9 (expand gate)** | **BE 토큰 활성화가 Supabase fallback 을 깨면 구 앱 즉시 lockout** — expand 붕괴. | BE 활성화는 **registry 명시 BE entry 추가만**. Supabase default fallback(2a) 무변경. **`test_me.py` green = hard gate**(BE 활성 Settings 에서도). verify: BE 활성 + Supabase 토큰 → 여전히 200. |
| **B10** | Authlib 비균일 — Kakao userinfo `id` 가 Apple/Google sub 와 다른 의미, callback 이 균일 가정하면 매칭 실패(→ B1 고아화). | provider별 sub 추출 명시: Google=OIDC `sub`, Kakao=`/v2/user/me` `id`(숫자→str, 2a provider_id 와 일치), Apple=id_token `sub`(Service ID 재사용). verify: provider별 sub 추출 유닛. |
| **B11** | OAuth state/CSRF 미검증 → callback 위조. | `/auth/login` 이 state(+IdP PKCE verifier) 발급·저장(B2 store), callback 이 state 일치 검증 후에만 진행. verify: state 불일치 callback → reject. |
| **B12 (HINGE — 리더 결정 2026-06-19: PKCE 완전 차단, 2b-1 실제 구현)** | **악성 앱이 `app.pixelwave.investnote://` 스킴을 가로채 일회용 code 탈취** → `/auth/token` 으로 먼저 교환(토큰 미노출 B4 와 별개 — code 자체가 custom scheme 에서 가로채기 가능). 금융 앱 → 잔여 위험 **수용 안 함**. | **2b-1 에서 app↔BE PKCE 실제 구현(no-op 예약 아님):** `GET /auth/login` 이 `code_challenge`(+`code_challenge_method=S256`) 받아 **transient store(DB)의 code 레코드(B3)에 challenge 묶어 저장** → `POST /auth/token` 이 `code_verifier` 받아 `base64url(SHA256(verifier))` == 저장 challenge 대조. **불일치/누락 = 교환 거부**(code 는 그래도 소진/single-use B3). 가로챈 code 만으론 verifier 없어 교환 불가. ⚠️ 안전: 2b-1 BE 배포 시점엔 BE flow 쓰는 앱 없음(2b-2 FE 미출시) → PKCE 강제 무영향, 신 앱은 처음부터 PKCE 포함 출시. App Links/Universal Links(스킴 hijack 자체 차단)는 도메인 검증 인프라 부담 → **후속 backlog**. verify: 정상 verifier→교환 성공 / verifier 누락→거부 / 잘못된 verifier→거부 / 가로챈 code+오 verifier→거부. |

---

## BE 작업 단위 (api/) — 2b-1 상세 분해

> 의존 순서: 설정/스토어/스키마(토대) → mint 활성화/검증 수정 → 라우터 → profile upsert 합류 → 통합. 각 단위 verify 1개 이상.

### B-1. [BE] `config.py` — Authlib provider 설정 + BE 토큰 fail-fast + refresh/store 설정
- provider별 OAuth 설정: `google_client_id/secret`, `kakao_client_id/secret`(REST API key), `apple_client_id`(Service ID)/`apple_team_id`/`apple_key_id`/`apple_private_key`. `be_oauth_redirect_base`(BE 공개 호스트 — **be_jwks_uri 호스트 버그의 정정 출처**, B8). `be_deeplink_scheme`(기본 `app.pixelwave.investnote://auth/callback`).
- refresh 설정: `be_refresh_token_ttl`(기본 30d), `oauth_code_ttl`(기본 60s), `oauth_state_ttl`(기본 600s).
- **B7 fail-fast**: `be_token_enabled` 인데 `be_token_audience` 빈 값이면 검증 에러(validator). dormant(키 없음) 무영향.
- ⚠️ provider secret 빈 값 허용(미설정 provider 는 `/auth/login` 시 503/명시 에러 — 부분 활성 가능).
- verify: `cd api && poetry run pytest tests/test_app_config.py -q` (fail-fast 케이스 + provider 설정 로드 + redirect_base 추가)
- 의존: 없음

### B-2. [BE] OAuth transient + refresh store 마이그레이션 `0006_auth_token_store` + DB 모듈 (작성만)
- ⚠️ **마이그레이션 번호 배정(확정):** 0004(auth_identities, 미적용) → **0005_user_profiles**(B-7) → **0006_auth_token_store**(refresh + transient). transient/refresh 는 **0006 단일 리비전**에 묶음(둘 다 server-only secret, 동시 적용). down_revision 체인: 0004→0005→0006.
- `0006_auth_token_store`: 두 테이블
  - `auth_refresh_tokens(id uuid PK, user_id uuid FK users(id) cascade, token_hash text not null unique, issued_at, expires_at, revoked_at timestamptz null)`. index(user_id), index(token_hash).
  - `oauth_transient(key text PK, kind text, payload jsonb, expires_at timestamptz, consumed_at timestamptz null)`. (state/verifier=kind 'state', 일회용 code=kind 'code'.) **B12 PKCE: app `code_challenge`(+method)는 payload jsonb 에 담는다** — state 레코드에 보관 후 callback 이 code 레코드 payload 로 이관(별도 컬럼 불요). index(expires_at) for 청소.
  - 소유자 role = [[project_migration_table_owner]] (`invest_note_app` 단일 실행). upgrade/downgrade 양방향.
- 신규 `api/src/invest_note_api/auth/token_store.py`: refresh save(hash)/lookup(hash)/rotate/revoke + transient put(TTL)/consume(single-use, B3)/cleanup. **plain `pool.acquire()`**(server-only secret, RLS 없음 — kis_token_store 패턴). 발급 직렬화 필요 시 advisory xact lock. TTL(`oauth_code_ttl`/`oauth_state_ttl`/`be_refresh_token_ttl`)은 **settings 에서 읽는다**(B-1 의존 이유).
- ⚠️ **빌드 독립성**: token_store 모듈+테스트는 profile(B-7)과 무관 — **standalone 으로 빌드/테스트 가능**. 0005→0006 `down_revision` 문자열만 B-7 에 묶이므로, B-7 미완 시 token_store 본체를 먼저 구현·검증하고 `down_revision` 은 **통합 시 reconcile** 해도 된다(보안 핵심 store 가 profile 대기로 idle 되는 risk 역전 방지).
- ⚠️ **적용 금지** — `alembic upgrade` 사용자 confirm 후([[feedback_no_db_reset_without_confirm.md]]).
- verify: `cd api && poetry run alembic upgrade 0005:0006 --sql`(오프라인 양방향 문법) + `cd api && poetry run pytest tests/test_token_store.py -q`(테스트 PG/sqlite: B2 다른 conn 소비, B3 replay reject, B5 해시·회전·만료, TTL 만료 None)
- 의존: B-1(TTL 설정) + B-7(0005 = 0006 의 down_revision — 번호 체인. 단 위 빌드 독립성 참조: store 본체는 B-7 선행 불요)

### B-3. [BE] `auth/be_token.py` — BE 토큰 활성화 + in-process 자기검증 (B8)
- `mint_be_token` 은 2a 완성(재사용). 활성화 = config 키 채움(B-1)으로 자동(코드 변경 최소).
- **B8 수정**: registry 의 BE entry 가 self-fetch(`be_jwks_uri` HTTP) 대신 **in-process public key 직접 검증**하도록 경로 추가. `build_be_jwks`(public JWK) 를 메모리에서 PyJWT verify 에 직접 주입하는 헬퍼(예: `be_verify_key(settings) -> public key`). registry/jwt.py 가 BE iss 일 때 이 경로 사용.
- ⚠️ **범위 한정**: B-3 은 **mint 활성화 + `be_verify_key`(in-process 검증)만**. refresh **회전 로직은 B-2(token_store) 소유**, `/auth/refresh` 와이어링(mint+rotate)은 **B-6 소유** — B-3 에 회전 헬퍼를 두지 않는다(B-2 와 순환/중복 방지).
- verify: `cd api && poetry run pytest tests/test_be_token.py -q`(기존 round-trip + **in-process verify round-trip**: mint→be_verify_key 로 검증, self-fetch 미사용 + B7 빈 aud fail-fast)
- 의존: B-1

### B-4. [BE] `auth/jwt.py`(또는 dependency) — BE entry in-process 검증 경로 반영
- A4 registry 가 BE iss 매칭 시 jwks_uri HTTP fetch 대신 B-3 의 in-process key 사용(B8). Supabase default fallback 경로 **무변경**(B9). `_verify_with_entry` 가 entry 에 in-process key 있으면 그걸로, 없으면(Supabase) 기존 JWKS fetch.
- verify: `cd api && poetry run pytest tests/test_issuer_registry.py tests/test_me.py -q`(**B9 hard gate**: BE 활성 Settings 에서 BE 토큰 200 + Supabase 토큰 여전히 200, fallback 무회귀)
- 의존: B-3

### B-5. [BE] Authlib provider clients — `auth/oauth_providers.py` 신규
- Authlib `OAuth` registry 또는 provider별 client 래퍼. Google=OIDC discovery, Kakao=OAuth2 + `/v2/user/me`, Apple=client_secret(서명 JWT 생성 헬퍼) + id_token 검증.
- 각 provider: `build_authorize_redirect(state, verifier)`, `fetch_token(code, verifier)`, `extract_identity(token) -> (sub, userinfo)`. **B10**: provider별 sub 추출 의미 명시(Google `sub`/Kakao `id`→str/Apple id_token `sub`). userinfo = {email, name, avatar, email_verified}(B6 upsert 입력, 비균일 — Apple 첫 로그인만 name).
- verify: `cd api && poetry run pytest tests/test_oauth_providers.py -q`(provider별 sub 추출 + userinfo 정규화, IdP 응답은 fixture/mock. Apple client_secret JWT 생성 round-trip)
- 의존: B-1

### B-6. [BE] OAuth 중개 라우터 — `routers/auth.py` 신규
- `GET /auth/login?provider=&code_challenge=&code_challenge_method=S256` → state+IdP verifier 발급·store(B-2, B11) → **app↔BE PKCE: `code_challenge`(method S256) 를 transient store 에 보관**(B12, callback 에서 발급할 code 레코드와 잇기 위해 state 와 함께 저장) → provider authorize 리다이렉트(redirect_uri={be_oauth_redirect_base}/auth/callback). ⚠️ `code_challenge` 누락 = 거부(2b-1 부터 PKCE 강제 — 배포 시점 BE flow 앱 없어 무영향, B12).
- `GET /auth/callback?code&state` → state 검증(B11) → `fetch_token`+`extract_identity`(B-5) → **`(provider, sub)→auth_identities.user_id` 해석(B1)** → 매핑 miss = 명시 에러(새 user 금지) → `mint_be_token(원래 UUID)` access + refresh(token_store 저장, B5) → **일회용 code 발급·store(B3) + 해당 state 의 `code_challenge` 를 code 레코드에 묶어 저장**(B12) → 딥링크 `{scheme}?code=<일회용>` 리다이렉트(**토큰 직접 미노출**, B4) → **profile upsert 호출(B-7, B6 COALESCE)**.
- `POST /auth/token` {code, **code_verifier(필수)**} → transient consume(single-use, B3) → **PKCE 검증(B12): `base64url(SHA256(code_verifier))` == 저장 `code_challenge` 대조, 불일치/누락 = 거부**(code 는 소진) → 저장된 access+refresh 반환. 가로챈 code 만으론 verifier 없어 교환 불가.
- `POST /auth/refresh` {refresh_token} → hash 조회·만료·revoke 확인(B5) → 회전(신 refresh 발급·구 revoke) + 신 access(mint) 반환.
- ⚠️ 라우터 mount 순서: health(JWKS) 다음, auth 보호 라우터(/me, /v1)보다 **앞**(이 라우터들은 무인증 — 로그인 진입점). `/auth/login`·`/auth/callback`·`/auth/token`·`/auth/refresh` 무인증.
- verify: `cd api && poetry run pytest tests/test_auth_router.py -q`(B1 매핑 miss 에러·매핑 hit→원래 UUID 토큰, B3 code replay reject, B4 리다이렉트에 토큰 부재, B5 refresh 회전·구 refresh 401, B11 state 불일치 reject, **B12 정상 verifier→성공·누락/오 verifier→거부·가로챈 code+오 verifier→거부**. IdP 는 B-5 mock)
- 의존: B-2, B-4, B-5, B-7

### B-7. [BE] profile — `0005_user_profiles` 마이그레이션 + upsert 모듈 + 백필 스크립트 (작성만)
- `0005_user_profiles`(down_revision=0004): `user_profiles(user_id uuid PK FK users(id) cascade, email text, display_name text, avatar_url text, email_verified bool, providers text[], created_at timestamptz, last_sign_in timestamptz)`. **named 컬럼만**(raw_meta 통째 복사 금지, PIPA). 소유자 role 규칙. 양방향.
- `api/src/invest_note_api/services/user_profile.py`: `upsert_profile(conn, user_id, *, email, display_name, avatar_url, email_verified, provider, last_sign_in)` — **COALESCE(B6)**: last_sign_in 항상 갱신, 나머지는 `COALESCE(EXCLUDED.col, user_profiles.col)`. providers 는 배열 union(append distinct).
- `api/scripts/import_user_profiles.py`: 운영자 `auth.users` export(2a identities 와 동일 덤프) → user_profiles 적재. **rollback guard**(A3 패턴): 단일 트랜잭션 + ① 적재 user_id ⊆ users.id(고아 FK 금지) ② 적재 행수 = export 행수(silent drop 금지) ③ user_id 유니크. dry-run 기본. **작성만, 적용 confirm**([[feedback_no_prod_command_execution.md]]).
- ⚠️ 0005 적용 금지(confirm). 백필 실행 금지(confirm).
- verify: `cd api && poetry run alembic upgrade 0004:0005 --sql` + `cd api && poetry run pytest tests/test_user_profile.py -q`(**B6 COALESCE: 값 upsert→null upsert→기존값 보존+last_sign_in 갱신**, providers union) + `tests/test_import_user_profiles.py`(rollback guard 3케이스)
- 의존: 없음(0005 는 0004 위 — 번호 체인. 0006 의 down_revision 이라 B-2 가 참조)

### B-8. [BE] 통합 테스트 — full OAuth flow + expand 무회귀
- end-to-end(IdP mock): login→callback(매핑 해석+발급+code)→token(교환)→refresh(회전). provider 3종.
- **B9 expand hard gate**: BE 활성 Settings 에서 Supabase 토큰 여전히 200(`test_me` 무회귀) + BE 토큰 200.
- B1 고아화 방지(매핑 miss→에러, user row 생성 0), B3 replay, B4 토큰 미노출, B5 회전, B6 profile null 보존, B11 state.
- verify: `cd api && poetry run pytest tests/test_auth_router.py tests/test_issuer_registry.py tests/test_me.py tests/test_be_token.py tests/test_token_store.py tests/test_user_profile.py -q` + 전체 `cd api && poetry run pytest -q`(무회귀)
- 의존: B-3, B-4, B-6, B-7

---

## QA 작업 단위 (단위별 분리 — addBlockedBy 로 즉시 unblock)

### Q-1. [QA] config — provider 설정 + be_token aud fail-fast (B7)
- B-1: provider 설정 로드, `be_oauth_redirect_base`/deeplink/TTL 추가. **B7: enabled+빈 aud→에러, enabled+aud→정상, dormant 무영향.**
- 의존: B-1

### Q-2. [QA] transient/refresh store — 인스턴스 안전·single-use·해시 (B2/B3/B5)
- B-2: **B2 다른 conn 소비 성공(인스턴스 간 시뮬), in-process 아님 확인.** B3 code replay reject. B5 refresh 해시 저장(평문 부재)·회전(구 무효)·만료. TTL 만료 None. 0006 양방향 SQL.
- 의존: B-2

### Q-3. [QA] BE 토큰 in-process 자기검증 + expand 무회귀 (B8/B9)
- B-3/B-4: **B8 in-process key 검증(self-fetch 미사용, string-mock 아닌 실제 키 경로).** be_jwks_uri 호스트 placeholder 가 자기검증 경로에서 더는 load-bearing 아님 확인. 외부 JWKS 엔드포인트 유지(미래용).
- **B9 hard gate: BE 활성 Settings + Supabase 토큰 200(fallback 무회귀) + BE 토큰 200.**
- 의존: B-4

### Q-4. [QA] OAuth 라우터 — 데이터 고아화 방지·딥링크·CSRF·PKCE (B1/B4/B10/B11/B12)
- B-6/B-5: **B1 매핑 hit→원래 UUID sub 토큰, 매핑 miss→명시 에러(새 user row 생성 0건, email 매칭 코드 부재).** B4 딥링크 리다이렉트에 access/refresh 문자열 부재(code 만). B10 provider별 sub 추출 정확(Kakao id↔2a provider_id). B11 state 불일치 reject. 무인증 라우터 mount.
- **B12 PKCE(실제 검증, no-op 아님): `/auth/login` code_challenge 누락→거부, `/auth/token` 정상 verifier→교환 성공·verifier 누락→거부·잘못된 verifier→거부·가로챈 code+오 verifier→거부.** SHA256(verifier)==challenge 대조 코드 존재.
- 의존: B-5, B-6

### Q-5. [QA] profile — COALESCE null 보존·백필 guard·PIPA (B6)
- B-7: **B6 재로그인 null clobber 방지(값→null upsert→기존 보존, last_sign_in 만 갱신).** providers union. 백필 rollback guard 3케이스. **named 컬럼만(raw_meta 통째 저장 부재, PIPA).** 0005 양방향. "작성만·confirm" 명시.
- 의존: B-7

### Q-6. [QA] 2b-1 최종 통합 게이트
- B-8: full flow green. `cd api && poetry run pytest -q` 전체 green(**expand-safe 무회귀 = lockout canary**).
- decisions.md 갱신 확인(D-1). **DB 마이그레이션(0004+0005+0006)·백필·env 키 미적용 상태 명시**(사용자 confirm 대기).
- grep 불변식: email 매칭 없음(B1), HS256 없음, 딥링크 토큰 직접 노출 없음(B4), refresh 평문 저장 없음(B5).
- spec → spec-history 이동 준비.
- 의존: Q-1, Q-2, Q-3, Q-4, Q-5, D-1

---

## 정합성 / 문서

### D-1. [DOC] `docs/decisions.md` — Phase 2b-1 결정 기록
- OAuth 중개 flow(redirect_uri=BE, 딥링크 일회용 code, 토큰 미노출).
- **app↔BE PKCE 강제(B12, 2b-1 실제 구현)** — 일회용 code 가로채기 차단(custom scheme hijack). `/auth/login` code_challenge(S256) → `/auth/token` code_verifier 대조. 트레이드오프: 잔여 위험 수용 거부(금융 앱) vs FE 복잡도↑. 2b-1 배포 시점 BE flow 앱 없어 강제 무영향, 신 앱은 PKCE 포함 출시. App Links/Universal Links(더 강함)는 도메인 검증 부담 → 후속 backlog.
- **transient store DB(not in-process)** — 트레이드오프: 단순성↓ vs 스케일아웃 안전(B2 lockout 차단).
- refresh 해시 저장·회전·만료(B5). BE 토큰 활성화 + **be_token_audience fail-fast**(B7).
- **be_jwks_uri 자기검증 in-process key 직접 주입**(B8, self-fetch 폐기) — 외부 JWKS 엔드포인트는 유지.
- profile: 별도 user_profiles 테이블(named 컬럼·PIPA), COALESCE upsert(B6), export 백필(2c 전 필수·비가역 마감).
- Authlib 비균일(Google OIDC/Kakao OAuth2+userinfo/Apple JWT-client-secret) + provider별 sub 의미(B10).
- verify: 파일 내용 확인
- 의존: B-1, B-6 (결정 확정 후)

---

## 의존 그래프 (2b-1 요약)

```
B-1(config) ─┬→ B-3(be_token 활성·in-proc) → B-4(jwt registry) ─┐
             ├→ B-5(providers) ─────────────────────────────────┤
             └→ B-2(store/0006) ──┐                              ├→ B-6(라우터) → B-8(통합)
B-7(profile/0005) ────────────────┴──────────────────────────────┘
QA: Q1←B1  Q2←B2  Q3←B4  Q4←B5,B6  Q5←B7  D1←B1,B6  Q6←Q1..Q5,D1
마이그레이션 체인: 0004(미적용) → 0005_user_profiles → 0006_auth_token_store
```
- 마이그레이션 적용은 0004+0005+0006 **한 배치**(사용자 confirm). 적용 순서 = 번호순.
- BE only. FE 변경 없음(2b-2).

## 완료 조건 (2b-1)

- [ ] B-1 provider 설정 + redirect_base + TTL + **be_token_audience fail-fast**(B7)
- [ ] B-2 0006(refresh+transient) 작성 + token_store(DB·single-use·해시·회전·만료, **인스턴스 무관** B2) — 적용 confirm 대기
- [ ] B-3/B-4 BE 토큰 활성화 + **in-process 자기검증**(B8, self-fetch 폐기) + **expand 무회귀**(B9 test_me 200)
- [ ] B-5 Authlib provider 3종(비균일) + provider별 sub 추출(B10)
- [ ] B-6 OAuth 중개 라우터 4개(login/callback/token/refresh) — **B1 매핑 해석(고아화 방지)·B3 replay·B4 토큰 미노출·B11 state**
- [ ] B-7 user_profiles(0005) + **COALESCE upsert**(B6) + 백필 guard — 적용·실행 confirm 대기
- [ ] B-8 full flow green + `poetry run pytest -q` 전체 무회귀(expand-safe)
- [ ] grep 불변식: email 매칭 없음 / HS256 없음 / 딥링크 토큰 직접 노출 없음 / refresh 평문 저장 없음
- [ ] `docs/decisions.md` 갱신(D-1)
- [ ] **DB 마이그레이션(0004+0005+0006)·백필·env 키 미적용 상태 명시** + 사용자 confirm 대기
- [ ] spec → `spec-history/2026-06-19-auth-decoupling-phase2b1.md` 이동 준비

---

## 외부 작업 (코드 아님 — 운영자 수행, 선행/배포 절차)

| 작업 | 시점 | 비고 |
|------|------|------|
| Supabase `auth.users` 프로필 컬럼 export(2a `auth.identities` 와 **같은 덤프**) | B-7 백필 선행 | ⚠️ **2c 전 비가역 마감** — Apple 첫인증만·Kakao optional → export 가 유일 보존. |
| IdP 콘솔 redirect_uri 에 **BE callback 추가**(expand 동안 Supabase callback 과 둘 다) | 2b-1 라우터 활성 전 | Google/Kakao/Apple 각각. `{be_oauth_redirect_base}/auth/callback`. |
| BE 로 OAuth client secret 이전(현재 Supabase 보유) + Apple client secret(서명 JWT용 key/team/key_id) | 2b-1 활성 전 | Apple Service ID 재사용(sub 보존). 운영 Coolify env(SSOT, [[project_env_production_drift]]). |
| BE 토큰 서명 키(ES256) + `be_token_issuer`/`be_token_audience` env 주입 | BE 활성 전 | aud 빈 값이면 기동 실패(B7 fail-fast). |
| 마이그레이션 적용(`alembic upgrade` 0004+0005+0006) | 라우터·백필 전 | **사용자 confirm 필수.** 순서=번호순. |
| identity 적재(2a A3) + profile 백필(B-7) 실행 | 마이그레이션 후 | **사용자 confirm 필수.** dry-run 선행. identity 가 profile 보다 선행(FK·매핑). |
| ⚠️ 스케일아웃(uvicorn workers↑/replica↑) | 운영 | transient DB 채택으로 **안전**(B2 해소). in-process 였다면 lockout. |

## PIPA 후속 (backlog 등록 — spec-finish 시)
profile PII 저장 확대 → 개인정보처리방침·Play Data Safety·App Store 라벨 갱신(기존 PostHog 고지 backlog 연동, [[project_posthog_analytics]]).

---

## 후속 sub-phase 개요 (2b-2 / 2c — 별도 스펙)

### 2b-2 — FE 전환 + refresh 흡수 (개요, 2b-1 머지 후 상세)
- `lib/auth/index.ts` 의 signInWithOAuth/getAccessToken/setSession/exchangeCodeForSession 을 BE flow 로 교체: 인앱 브라우저→`{BE}/auth/login`, 딥링크 일회용 code→`{BE}/auth/token`. `CapacitorDeepLinkHandler.tsx` 가 code→/auth/token 교환(현 setSession/exchangeCodeForSession 대체). `login/page.tsx` 의 signInWithOAuth url 획득 경로 조정.
- **getAccessToken refresh 책임**: 순수 getter 아니게 — 만료/401→`/auth/refresh`→retry 흡수(api-client.ts:82 콜사이트 무변경).
- ⚠️ **숨은 비용**: supabase-js 제거 시 세션 persistence + subscribe/onAuthStateChange 상실 → FE 자체 **토큰 store(Capacitor secure storage)** 신설(getAccessToken 읽기·refresh 쓰기). supabase-js 격리 3파일(supabase-client/types/index)이 교체 대상. **완전 제거는 "검토(assess)"** — expand 동안 신 앱은 BE flow 만이라 가능성 높으나 2b 확정 산출물 아님.
- 함정: 딥링크 code 교환 실패 라우팅(기존 LOGIN_OAUTH_FAILED 재사용), 토큰 store 보안, refresh 경쟁(동시 401 다발→single-flight).

### 2c — contract (개요)
- registry 에서 Supabase issuer 제거(BE 단독). supabase-js 완전 제거. **force-update 로 구 앱 sunset + 양 스토어 승인 후에만**([[project_force_update]]). 양 스토어 라이브 바이너리 확인이 gate.
