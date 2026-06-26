# 어드민 패널 인증 — Supabase → BE 토큰-브로커 교체 사양서

> 탈-Supabase Auth 2c(Supabase 물리 제거) **선행작업**. 어드민 패널(`admin/`)을 BE OAuth flow 로
> 교체한다. 이걸 하지 않으면 2c 에서 Supabase 제거 시 `/admin/*` 가 전부 401 된다.

## 배경 / 목적

- 탈-Supabase Auth cutover 운영 완료(BE 토큰-브로커 라이브: JWKS `be-prod-2026-06`, `/auth/*`
  ES256, refresh DB, `ADMIN_EMAILS` allowlist 운영 동작). 네이티브 앱은 BE flow 전환됨.
- 남은 Supabase 의존 중 하나가 **어드민 패널**(`admin/` standalone Node SPA — `app/` 과 별개 FE).
  현재 supabase-js `signInWithOAuth` → `getSession().access_token` → `/admin/*` Bearer.
- 어드민을 BE flow 로 교체. 어드민은 `app/` 의 네이티브 BE flow(`app/src/lib/auth/`)를 **웹용으로
  미러링**한다.

## 범위 (Scope)

- **포함:**
  - BE: `/auth/login` 에 web/native 구분자(`client`) 추가, `/auth/callback` 에 web 리다이렉트 분기
    (어드민 origin 으로 일회용 code 부착), redirect 대상 env(`be_admin_redirect_url`) 신설.
  - FE(admin): `lib/auth/` 격리 모듈을 BE flow 로 재작성(pkce / be-client / token-store(localStorage)
    / index 재작성, supabase-client 삭제), login·callback 페이지 수정, supabase env/의존 제거.
- **제외:**
  - Supabase 물리 제거(2c 별건). Supabase 클라우드/구성 변경 없음.
  - `app/`(네이티브) 변경 — 무관, 무회귀(BE `/auth/login` 의 `client` 는 default native).
  - 신규 마이그레이션(token_store / auth_identities 재사용 — **불필요**).
  - httpOnly cookie / CSRF 토큰 강화(현 Supabase 도 localStorage — 회귀 없음, 내부 allowlist 콘솔).
  - 어드민 BE-flow 점진 토글 플래그(단일 web 배포라 hard-swap — `app/` 의 `be_auth_enabled`
    게이트 불필요).

## 핵심 제약 / 함정 (load-bearing)

1. **IdP redirect_uri 는 고정·등록값**(`{be_oauth_redirect_base}/auth/callback`) → 별도 web callback
   endpoint 신설 불가. 어드민 web redirect 는 IdP **다음**의 BE→client 2차 hop이므로
   **Google/Kakao 에 새 redirect URI 등록이 불필요**(IdP 작업 0).
2. **web/native 구분 = `client` 쿼리 파라미터(정확 문자열)** 를 `/auth/login` 에서 받아 state transient
   에 저장 → `_handle_callback` 이 분기. `client="admin"` ↔ env `be_admin_redirect_url` 짝. default
   는 native(딥링크) — 기존 앱 무회귀.
3. **open redirect 차단:** 클라이언트는 redirect **URL 을 보내지 않는다**. 고정 식별자(`client=admin`)
   만 보내고 BE 가 env 의 고정 URL 로 매핑. 단일 env 가 곧 allowlist(URL 리스트로 일반화 금지, YAGNI).
4. **`be_admin_redirect_url` 빈 값 → login 시점 fail-fast**(Google 왕복·state 소모 **전**). dormant
   503 패턴(`be_token_enabled` 와 동일 사상).
5. **PKCE enforce-always(S256):** 어드민 web flow 도 verifier 생성 → S256 challenge → `/auth/login`,
   `/auth/token` 에서 verifier 제출. BE `pkce.py` 와 일치. **verifier 는 full-page 리다이렉트 왕복을
   생존해야 하므로 메모리 불가 → localStorage(또는 sessionStorage) 보관**, 교환 후 삭제.
6. **refresh single-flight 는 web 에서도 필수**(native 전용 아님). refresh rotation(B5)이라 만료 직후
   동시 `/admin/*` 호출(AuthProvider `/admin/me` 프로브 + 대시보드 react-query 병렬)이 같은 refresh
   token 으로 동시 회전하면 첫 호출만 성공·나머지 401 → 강제 logout. app `index.ts` 의 single-flight
   machinery 를 떼지 말 것.
7. **callback 페이지 double-exchange 가드:** 일회용 code 는 single-use(B3). React strict-mode(dev)
   effect 이중 invoke·재렌더로 두 번 교환하면 두 번째 401 → 로그인 실패. app deeplink handler 의
   `handledUrls` dedup 과 동일하게 **once-guard(ref)** 필요.
8. **ADMIN_EMAILS 게이트 그대로:** BE 토큰에 email 클레임 있음 → `require_admin` allowlist 통과.
   어드민 유저는 백필됨(auth_identities sub=원래 UUID). 비허용 이메일 401 유지(변경 없음).
9. **격리 경계 이득:** `admin/src/lib/api.ts`·`AuthProvider.tsx` 는 **무변경**(provider-neutral
   인터페이스 `getAccessToken`/`getUser`/`subscribe`/`signOut`/`AdminUser` 유지). login·callback
   페이지와 `lib/auth/` 내부만 변경 → blast radius 작음.

## 계약 핀 (shape-drift 가드)

- `/auth/login` 쿼리: `provider`, `code_challenge`, `code_challenge_method=S256`, **`client=admin`**(신규).
- BE→어드민 redirect: `{be_admin_redirect_url}?code=<일회용>`(기존 query 있으면 `&`, B4 — code 만).
- `POST /auth/token` body: `{ code, code_verifier }` → resp `{ access_token, refresh_token, token_type }`.
- `POST /auth/refresh` body: `{ refresh_token }` → 동일 resp shape.
- access JWT claims: `sub`(원래 UUID), `email`, `exp` — FE 로컬 디코드(검증 안 함, BE 가 서명 검증).

## 작업 단위

### 1. [BE] `api/src/invest_note_api/config.py` — `be_admin_redirect_url` env 추가
- `be_admin_redirect_url: str = ""` 필드 추가(딥링크 scheme 인근, 주석으로 dormant-503 의미 명시).
- 선택: `be_token_audience` 처럼 강제하지 않음 — 빈 값은 **login 라우터에서** fail-fast(아래 2).
- verify: `cd api && poetry run pytest tests/test_auth_router.py -q` (2 와 함께)
- 의존: 없음

### 2. [BE] `api/src/invest_note_api/routers/auth.py` — `client` 분기 + web redirect
- `login()` 시그니처에 `client: str = "native"` 추가. `client == "admin"` 인데
  `settings.be_admin_redirect_url` 가 빈 값이면 503(`ERR_SERVICE_UNAVAILABLE`) — **fail-fast**(state
  저장·IdP 리다이렉트 전). state transient payload 에 `"client": client` 저장.
- `_handle_callback()`: state 에서 `client` 꺼내 분기.
  - `client == "admin"` → `_web_redirect_with_code(settings.be_admin_redirect_url, one_time)` 로 302.
  - 그 외(default native) → 기존 `_deeplink_with_code(settings.be_deeplink_scheme, one_time)`.
- `_web_redirect_with_code(base, code)` 헬퍼 추가(`_deeplink_with_code` 와 동형 — query 안전 부착).
  미지원 `client` 값은 native 로 폴백하지 말고 **명시적으로 admin/native 만 허용**(알 수 없는 값 →
  native default 유지로 무회귀, 단 web redirect 는 `client=="admin"` && env 존재일 때만).
- ⚠️ state consume 가 `client` 를 주므로 web redirect 결정은 state 검증 **후**. state 무효 등
  pre-resolution 에러는 기존대로 APIError(JSON) — native 와 대칭(어드민 callback 페이지가 code 부재로
  에러 처리).
- verify: `cd api && poetry run pytest tests/test_auth_router.py tests/test_auth_flow_integration.py -q`
- 의존: 1

### 3. [QA-BE] BE flow shape·보안 검증 (integration-qa)
- `/auth/login?client=admin&...` → 302 IdP, state 에 client 저장됨.
- `be_admin_redirect_url` 빈 값 + `client=admin` → 503(fail-fast, IdP 리다이렉트 안 함).
- callback(admin client) → `{be_admin_redirect_url}?code=...` 로 302(딥링크 아님).
- callback(client 미지정/native) → 기존 딥링크 302(무회귀).
- PKCE: `client=admin` 도 challenge 필수·S256 외 400. `/auth/token` 에서 verifier 대조(B12).
- open redirect: 클라가 임의 URL 못 주입(고정 식별자만) 확인.
- verify: `cd api && poetry run pytest tests/test_auth_router.py -q` (신규 케이스 추가)
- 의존: 2

### 4. [FE] `admin/src/lib/auth/pkce.ts` (신규) — S256 PKCE
- `app/src/lib/auth/pkce.ts` 미러링: `generateVerifier()`, `challengeFromVerifier()`,
  `isWebCryptoAvailable()`. (web 은 https secure context 라 WebCrypto 항상 존재하지만 명시적 가드
  유지 — silent 실패 대신 throw.)
- verify: `pnpm -C admin exec tsc --noEmit`
- 의존: 없음

### 5. [FE] `admin/src/lib/auth/be-client.ts` (신규) — BE OAuth fetch + JWT 디코드
- `app/src/lib/auth/be-client.ts` 미러링:
  - `buildLoginUrl(provider, codeChallenge)` — 쿼리에 **`client=admin`** 포함(계약 핀).
  - `exchangeToken(code, verifier)` → `POST /auth/token`.
  - `refreshToken(refresh)` → `POST /auth/refresh`.
  - `decodeClaims(accessToken)`, `isExpiringSoon(accessToken, skewSec)`.
  - `API_BASE` = `NEXT_PUBLIC_API_BASE_URL`(trailing slash 제거) — `api.ts` 와 동일 env.
- verify: `pnpm -C admin exec tsc --noEmit`
- 의존: 없음

### 6. [FE] `admin/src/lib/auth/token-store.ts` (신규) — localStorage 토큰 저장
- access/refresh/verifier 를 localStorage 에 저장(native secure-storage 대체).
  키: `auth.access_token` / `auth.refresh_token` / `auth.pkce_verifier`(app 과 동일 네이밍).
- `saveTokens`, `getAccessTokenRaw`, `getRefreshToken`, `clearTokens`, `saveVerifier`, `getVerifier`,
  `clearVerifier`. (sync localStorage 를 Promise 로 감싸 app 시그니처와 동형 유지 — index 미러링 용이.)
- ⚠️ verifier 는 full-page 리다이렉트 왕복 생존 필수(메모리 불가).
- verify: `pnpm -C admin exec tsc --noEmit`
- 의존: 없음

### 7. [FE] `admin/src/lib/auth/index.ts` (재작성) — provider-neutral BE flow
- `app/src/lib/auth/index.ts` 의 BE-flow 경로 미러링(단, isNativePlatform/flag 게이트 **없음** —
  어드민은 항상 BE flow):
  - `signInWithGoogle(redirectTo?)`: WebCrypto 가드 → verifier 생성·저장 → S256 challenge →
    `window.location.assign(buildLoginUrl("google", challenge))`(full-page 리다이렉트). 반환 없음.
  - `getAccessToken()`: 캐시(F#1) → cold-start storage 적재 → 만료 임박 시 **single-flight refresh**
    (제약 #6). epoch 가드(로그아웃 후 부활 차단).
  - `getUser()`: getAccessToken 으로 refresh-aware 확보 후 claims 반환(캐시 재사용).
  - `signOut()`: epoch++ → clearCache → clearTokens → emit(null).
  - `subscribe(cb)`: 자체 listener registry(supabase onAuthStateChange 대체).
  - `exchangeCodeForSession(code)`: getVerifier → exchangeToken → persistAndEmit → 성공 시에만
    clearVerifier(실패 시 보존 — BE peek-before-consume 라 재교환 가능).
  - `__resetForTest()`(선택): 모듈 스코프 상태 리셋.
- `AdminUser`/`AuthChangeCallback` 타입(`types.ts`) **무변경** 재사용. supabase-client import 제거.
- verify: `pnpm -C admin exec tsc --noEmit`
- 의존: 4, 5, 6

### 8. [FE] `admin/src/lib/auth/supabase-client.ts` 삭제 + supabase 의존/env 제거
- `supabase-client.ts` 삭제.
- `admin/package.json` 에서 `@supabase/supabase-js` 제거 후 `pnpm -C admin install`.
- `admin/.env.example`·`.env.production`·`.env.development.local` 에서 `NEXT_PUBLIC_SUPABASE_*` 제거.
- ⚠️ supabase-js 잔존 import 0 확인(`lib/auth/` 외엔 원래 없음 — 격리 경계).
- verify: `pnpm -C admin exec tsc --noEmit` + `grep -rn "supabase" admin/src` == 0
- 의존: 7

### 9. [FE] `admin/src/app/login/page.tsx` + `admin/src/app/auth/callback/page.tsx` 수정
- `login/page.tsx`: `handleLogin` 의 `redirectTo` 구성 제거(또는 무시) — `signInWithGoogle()` 가
  내부에서 BE login URL 로 리다이렉트. 성공 시 페이지 이탈(기존 try/catch 유지). UI 무변경.
- `auth/callback/page.tsx`: **실질 재작성** — Supabase 자동 교환에 의존하던 것을, URL `?code=` 를
  직접 읽어 `exchangeCodeForSession(code)` 호출 후 성공 시 `/`·실패 시 `/login/?error=oauth`.
  ⚠️ **once-guard(ref)** 로 double-exchange 차단(제약 #7). code 부재 시 즉시 에러.
- verify: `pnpm -C admin exec tsc --noEmit` + 수동 시나리오(로컬 dev: 어드민 3001 ↔ api 3108)
- 의존: 7

### 10. [QA-FE] 어드민 lib/auth + 페이지 정합 검증 (integration-qa)
- `pnpm -C admin exec tsc --noEmit` 통과.
- `grep -rn "supabase" admin/src` == 0(격리 제거 확인).
- 동시 `/admin/*` 호출 시 refresh 1회만 회전(제약 #6) — 수동/단위.
- callback 페이지 once-guard 로 code 1회만 교환(제약 #7).
- 의존: 8, 9

### 11. [QA] end-to-end shape 정합 (integration-qa)
- FE `buildLoginUrl` 의 `client=admin` ↔ BE `/auth/login` param 합의.
- FE `exchangeToken` body `{code, code_verifier}` ↔ BE `TokenRequest` 일치.
- token/refresh resp shape ↔ FE `BeTokens` 매핑 일치.
- `/admin/me` 프로브가 BE 토큰으로 200(허용 이메일)·403(비허용) — AuthProvider isAdmin 판정 무회귀.
- 로컬 dev 전체 시나리오: 로그인 → callback 교환 → 대시보드 진입 → 새로고침 세션 유지 → 로그아웃.
- 의존: 3, 10

### 12. [DOC] `docs/decisions.md` 갱신
- 결정 기록: ① web/native 구분 = `client` state 플래그(별도 endpoint 불가 이유: IdP redirect_uri 고정),
  ② 어드민 redirect = 고정 식별자→env URL 매핑(open redirect 차단, 단일 env=allowlist),
  ③ 브라우저 토큰 저장 = localStorage(현 Supabase 동작과 동일·회귀 없음, httpOnly cookie 미채택 사유),
  ④ 어드민 BE-flow 점진 플래그 미도입(단일 web 배포 hard-swap).
- 의존: 11

## 배포 순서 (prod-breaking — hard-swap)

1. **BE env 주입(어드민 배포 전):** Coolify api 서비스에 `be_admin_redirect_url` =
   어드민 운영 콜백 URL(예: `https://<admin-domain>/auth/callback/`). **값은 사용자 확인 필요**(열린 질문).
2. **CORS 확인:** 어드민 운영 origin 이 `cors_origins`(Coolify env)에 포함됐는지 확인 — `/auth/token`·
   `/auth/refresh` fetch 가 CORS 통과해야 함. (`/admin/*` 가 이미 prod 동작 → 포함됐을 공산 크나
   **가정 말고 확인**.)
3. signing key 는 cutover 로 이미 live(추가 작업 없음).
4. 위 1~2 확인 후 어드민 SPA 배포.

## 완료 조건

- [ ] 작업 1~9 모든 verify 통과(`poetry run pytest` / `pnpm -C admin exec tsc --noEmit`)
- [ ] QA 3·10·11 통과(BE shape·보안 / FE 정합 / e2e)
- [ ] `grep -rn "supabase" admin/src` == 0
- [ ] `docs/decisions.md` 갱신(작업 12)
- [ ] 배포 순서 노트 사용자 전달(BE env + CORS 선행)
- [ ] spec → `docs/spec-history/2026-06-26-admin-be-auth.md` 이동 준비

## 가정 (Assumptions)

- 어드민 운영 도메인은 repo 에 없음(API base 만 존재, Coolify env 가 SSOT) → `be_admin_redirect_url`
  값은 사용자 확인 대상(열린 질문). env 파라미터로 구조만 잡고 값은 비워둠.
- 어드민에 test runner/auth 테스트 인프라 부재 → FE verify 는 `tsc --noEmit` + 수동 시나리오 + BE
  pytest 로 한다(vitest 신규 도입 안 함 — YAGNI). 도입 필요 시 사용자 확인.
- 어드민은 Google OAuth 만 사용(현행 동일) — Kakao/Apple 버튼 없음.
