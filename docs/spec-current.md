# Supabase Auth 종속성 제거 Phase 1 — 결합 국소화 사양서

작성: 2026-06-19 | 근거: `_workspace/auth-decoupling-research.md` (조사 보고서), `docs/decisions.md`(2026-06-16/17/18 탈-Supabase 맥락)

## 배경 / 목적

탈-Supabase의 마지막 축인 Auth(JWT/OAuth)를 "교체 시 어댑터만 갈아끼우면 되는" 구조로 국소화한다. **Phase 1은 동작 변경 0 + iss 검증 추가가 전부인 리팩토링.** 신규 라이브러리 0. Supabase는 그대로 존속한다(SDK 유지, JWKS 유지). Phase 2(token-broker, BE 토큰 발급)는 이번 범위 밖.

- BE: `jwt.py`를 일반 OIDC verifier로 일반화 + `iss` 핀 고정(보안 하드닝) + admin deleteUser를 IdP 어댑터 뒤로.
- FE: admin의 `lib/auth/` 3계층 패턴(neutral 타입 / SDK 격리 싱글톤 / 함수형 neutral API)을 미러링. SDK import를 `lib/auth/supabase-client.ts` 한 파일로 가둠.

## 범위 (Scope)

**포함:**
- BE: `auth/jwt.py` 일반화, `auth/constants.py`/`config.py` 설정명 추가, `auth/dependency.py` 호출 갱신, deleteUser 어댑터(`auth/identity_provider.py` 신규)·`routers/me.py` 갱신, iss 토글 테스트.
- FE: `lib/auth/types.ts`·`lib/auth/supabase-client.ts`·`lib/auth/index.ts` 신규, SDK 직접 호출 8지점(6파일) neutral 함수로 교체, `lib/supabase/client.ts` 삭제, `AuthProvider.test.tsx` mock 타깃 갱신.
- `docs/decisions.md` 갱신(iss fail-safe 기본값 트레이드오프).

**제외 (명시적):**
- Phase 2 일체(BE OAuth 중개, BE 자체 토큰 발급, refresh 토큰 BE 이관, 딥링크 일회용 code).
- `@supabase/supabase-js` 제거 — Phase 1은 유지.
- 설정 가능한 `oidc_jwks_uri` 오버라이드 — Phase 1은 Supabase 존속이라 speculative. **deferred note만**, 태스크 아님.
- `iss` 검증을 실제로 prod에서 활성화(`oidc_issuer` env 세팅) — 정확한 iss 문자열 검증 후 별도 config 단계. 이번 변경의 기본값은 **skip-when-empty**.

## 가정 (Assumptions)

- `AuthUser{id, email}`로 충분: `useAuth()` 소비자(settings/page, auth/callback, PostHogIdentifyBridge, AuthGuard)는 `user.id`·`user.email`·truthiness만 읽음(grep 확인 완료). supabase `User` 고유 필드 미사용.
- 테스트 JWT(`conftest.make_jwt`)는 현재 `iss` 클레임이 없음 → iss 검증을 기본 활성화하면 전 auth 테스트가 깨진다. 따라서 **`oidc_issuer` 빈 값(기본) → iss 검증 스킵**이 무회귀의 hinge.

---

## ⚠️ 최대 함정 체크리스트 (구현 전 필독)

| # | 함정 | 가드 |
|---|---|---|
| T1 | **iss 핀 잘못 설정 시 전체 인증 붕괴.** Supabase 실제 iss는 `{supabase_url}/auth/v1`. | Phase 1 기본값 `oidc_issuer=""` → iss 검증 스킵(fail-safe). prod 활성화는 범위 밖. decisions.md 기록. |
| T2 | `signInWithOAuth` ≠ admin `signInWithGoogle`. admin은 `void` 반환, app 네이티브는 `data.url`을 받아 `Browser.open`에 먹여야 함(login/page.tsx:81-83). | neutral 시그니처가 **OAuth url을 반환**해야 함. url 드롭하면 네이티브 로그인이 조용히 죽음. |
| T3 | `signOut`은 두 호출처 모두 `scope:"local"`. | neutral `signOut()`는 인자 없음, `scope:"local"`을 함수 내부에 박음. |
| T4 | 딥링크 핸들러는 `error` 분기로 `LOGIN_OAUTH_FAILED_PATH` 라우팅(CapacitorDeepLinkHandler.tsx:62,84). | neutral `setSession`/`exchangeCodeForSession`은 **error 시 throw**. 핸들러는 기존 try/catch 유지 → 라우팅 기계적 동일. |
| T5 | AuthProvider `applyUser` id-dedup(불필요 re-render 방지). | `AuthUser{id}`로 dedup 유지. "단순화"로 제거 금지. `loading=false`는 getUser 성공/실패·subscribe 양 경로 모두 유지. |
| T6 | `AuthProvider.test.tsx`가 `@/lib/supabase/client`를 mock. AuthProvider 전환 후 mock 타깃이 `@/lib/auth`로 이동. | 테스트 mock을 neutral API(`getUser`/`subscribe`) 형태로 갱신. 단계 FE-5에 포함. |
| T7 | OAuth 동작 보존: 네이티브/웹 분기, PKCE/implicit dual flow, skipBrowserRedirect, scope:local. | 순수 코드 재배치. 동작 변경 절대 금지. |
| T8 | deleteUser 어댑터화 후 `test_me.py` URL/헤더 단언(:118-120) 무수정 통과 필수. | 어댑터를 기존 `get_http_client`+`get_settings` deps에 그대로 와이어링. secret 미설정→503·http 0회(:91-102)도 유지. |

---

## BE 작업 단위 (api/)

### B1. [BE] `auth/constants.py` + `config.py` — OIDC 설정명 추가
- `constants.py`: `AUTH_ROLE`/`JWT_ALGORITHMS` 유지(하위호환 기본값). 주석을 "Supabase 전용"에서 "OIDC 기본값(현재 Supabase)"로 중립화(선택, 최소 변경).
- `config.py`:
  - `oidc_issuer: str = ""` 추가 — **빈 값이면 iss 검증 스킵**(fail-safe). 실제 값 `{supabase_url}/auth/v1`은 주석으로만 문서화.
  - `oidc_audience: str = AUTH_ROLE` 추가 — `aud` 기본값 하위호환.
  - `jwks_uri` property는 `supabase_url` 파생 그대로 유지(설정 가능 오버라이드 미도입 — 범위 제외).
- verify: `cd api && poetry run pytest tests/test_app_config.py -q`
- 의존: 없음

### B2. [BE] `auth/jwt.py` — 일반 OIDC verifier로 일반화 + iss 핀
- `decode_supabase_jwt` → `decode_oidc_jwt(token, *, jwks_uri, audience, issuer=None)`.
  - `audience`는 호출자(dependency)가 `settings.oidc_audience` 주입.
  - `issuer=None`(또는 빈 문자열) → `jwt.decode`에 `issuer=` 전달 안 함(iss 검증 스킵). 값 있으면 `issuer=issuer` 전달.
  - 기존 `_get_jwks_client` 캐시·claim 추출(`sub`→id, `email`) 동일. `AuthenticatedUser` 그대로.
- `JWT_ALGORITHMS`는 constants에서 계속 import(상수 유지).
- ⚠️ B2 단독으로는 `test_me.py`가 통과 못 함: rename 후 `dependency.py`가 옛 이름을 import → 모듈 로드 실패로 전 테스트 collection 에러. B2의 verify는 "import 클린"까지, `test_me.py` green 은 B3와 합쳐서.
- verify: `cd api && python -c "import invest_note_api.auth.jwt"` (import 클린) — test_me.py green 은 B3에서
- 의존: B1

### B3. [BE] `auth/dependency.py` — neutral verifier 호출로 갱신
- `decode_supabase_jwt(token, settings.jwks_uri)` → `decode_oidc_jwt(token, jwks_uri=settings.jwks_uri, audience=settings.oidc_audience, issuer=settings.oidc_issuer or None)`.
- import 갱신(`decode_oidc_jwt`). except 절(InvalidTokenError 등) 동일. **`decode_supabase_jwt` 심볼 잔존 금지**(전부 교체).
- verify: `cd api && poetry run pytest tests/test_me.py -q`
- 의존: B2

### B4. [BE] `auth/identity_provider.py` 신규 + `routers/me.py` 갱신 — deleteUser 어댑터화
- 신규 `auth/identity_provider.py`: `IdentityProvider` 인터페이스(또는 함수) — `async delete_user(user_id, *, http_client, settings) -> None`. 내부에 기존 GoTrue 호출(`{supabase_url}/auth/v1/admin/users/{id}` + apikey/Bearer, 200/204 외 502, HTTPError 502) 이동.
- `routers/me.py`: deleteUser 인라인 httpx 블록을 어댑터 호출로 대체. **`supabase_secret_key` 미설정→503은 라우터에 유지**(http 0회 보장, T8). 어댑터는 기존 `get_http_client`/`get_settings` deps를 그대로 받음.
- verify: `cd api && poetry run pytest tests/test_me.py -q` (test_me.py **무수정** 통과 — URL/헤더/503/502 단언 그대로)
- 의존: 없음 (B1~B3과 독립, 병렬 가능)

### B5. [BE] iss 검증 토글 테스트 추가
- `tests/conftest.make_jwt`에 `iss: str | None = None` 파라미터 추가(기본 None → iss 클레임 미포함, 기존 호출 무영향).
- `tests/test_me.py`(또는 신규 `test_auth_jwt.py`)에 케이스 추가:
  - `oidc_issuer` 빈 값 → iss 없는 토큰도 200(기존 동작 보존).
  - `oidc_issuer` 설정 + 일치 iss 토큰 → 200.
  - `oidc_issuer` 설정 + 불일치 iss 토큰 → 401.
  - ⚠️ `auth_client` 픽스처는 `oidc_issuer=""` 기본. iss-설정 케이스는 `Settings(oidc_issuer=...)`로 별도 app 빌드 필요(`_make_delete_client` 패턴 참고) + `make_jwt(iss=...)`.
- verify: `cd api && poetry run pytest tests/test_me.py tests/test_app_config.py -q`
- 의존: B2, B3

### B6. [QA-BE] BE 무회귀 + 격리 검증
- `cd api && poetry run pytest -q` 전체 무회귀.
- grep 불변식: `decode_supabase_jwt` 심볼이 api/src·api/tests 어디에도 없음. `dependency.py`가 `decode_oidc_jwt` 호출. me.py가 어댑터 경유(인라인 admin URL 직접 호출 잔존 없음).
- iss 토글 3케이스(스킵/일치/불일치) 통과 확인.
- 의존: B3, B4, B5

---

## FE 작업 단위 (app/)

### F1. [FE] `lib/auth/types.ts` 신규 — neutral 타입
- admin `types.ts` 미러: `export interface AuthUser { id: string; email: string | null }`, `export type AuthChangeCallback = (user: AuthUser | null) => void`.
- supabase `User` 타입 절대 노출 금지(격리 경계 주석).
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 없음

### F2. [FE] `lib/auth/supabase-client.ts` 신규 — SDK 격리 싱글톤
- 기존 `lib/supabase/client.ts` **verbatim 이전**(auth 옵션 변경 0): `createClient as createSupabaseClient`, `getSupabaseClient()` 싱글톤, `flowType:"pkce"`만 명시(detectSessionInUrl/autoRefreshToken/persistSession/localStorage는 SDK 기본값 의존 — 건드리면 웹 PKCE 콜백 동작 drift), 주석(capacitor 쿠키 미저장 제약) 그대로.
- **이 파일이 `@supabase/supabase-js`를 import하는 유일한 파일.**
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: 없음

### F3. [FE] `lib/auth/index.ts` 신규 — 함수형 neutral API
- import `getSupabaseClient`, neutral 타입. `toAuthUser(user) -> AuthUser | null` 단일 매핑.
- export 함수(시그니처 **고정**):
  - `signInWithOAuth(provider: "google"|"kakao"|"apple", options: { redirectTo: string; skipBrowserRedirect: boolean }): Promise<{ url: string | null }>` — ⚠️T2 url 반환. SDK 호출 후 `error` throw, `{ url: data?.url ?? null }` 반환.
  - `getAccessToken(): Promise<string | null>` — getSession→access_token, catch null.
  - `getUser(): Promise<AuthUser | null>` — getSession→toAuthUser, catch null.
  - `signOut(): Promise<void>` — `signOut({ scope: "local" })` 내부 고정(T3).
  - `subscribe(callback: AuthChangeCallback): () => void` — onAuthStateChange→toAuthUser 콜백, unsubscribe 반환.
  - `setSession(accessToken: string, refreshToken: string): Promise<void>` — error 시 **throw**(T4).
  - `exchangeCodeForSession(code: string): Promise<void>` — error 시 **throw**(T4).
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: F1, F2

### F4. [FE] `api-client.ts` — getSession→getAccessToken
- `getBearerHeader`(:87-96)에서 `getSupabase().auth.getSession()` → `getAccessToken()`. 지연 싱글톤 `_supabase`/`getSupabase`/`createClient` import 제거(neutral 함수가 격리 담당). 동작(토큰 없으면 `{}`, catch `{}`) 동일.
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: F3

### F5. [FE] `AuthProvider.tsx` + 테스트 — neutral getUser/subscribe
- `import type { User }`·`createClient` 제거 → `import { getUser, subscribe, type AuthUser } from "@/lib/auth"`.
- `User` → `AuthUser`. 초기 로드 `getSession().then` → `getUser().then((u)=>{applyUser(u); setLoading(false);})`(+catch 동일); `onAuthStateChange` → `subscribe((u)=>{applyUser(u); setLoading(false);})`(unsubscribe 반환 활용). ⚠️ `subscribe(applyUser)` 단축형 금지 — 원본은 콜백에서 `setLoading(false)`도 호출함(T5). `applyUser` id-dedup 유지.
- `__tests__/AuthProvider.test.tsx`: `vi.mock("@/lib/supabase/client")` → `vi.mock("@/lib/auth")`로 변경, mock을 `getUser`(Promise)·`subscribe`(콜백 등록+unsubscribe) 형태로 재구성. 7개 케이스 시맨틱 유지(T6).
- verify: `pnpm -C app exec tsc --noEmit` + `pnpm -C app test src/components/providers/__tests__/AuthProvider.test.tsx`
- 의존: F3

### F6. [FE] `login/page.tsx` — signInWithOAuth neutral
- `createClient` import 제거 → `import { signInWithOAuth } from "@/lib/auth"`.
- `handleSocialLogin`(:62-90): `supabase.auth.signInWithOAuth({provider, options:{redirectTo, skipBrowserRedirect:native}})` → `const { url } = await signInWithOAuth(provider, { redirectTo, skipBrowserRedirect: native })`. 이후 `if (native && url) { Browser.open({ url, ... }) }`(T2). 나머지 분기·에러·pending 동일.
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: F3

### F7. [FE] `CapacitorDeepLinkHandler.tsx` — setSession/exchangeCodeForSession neutral
- `createClient` import 제거 → `import { setSession, exchangeCodeForSession } from "@/lib/auth"`.
- implicit 분기(:58): `supabase.auth.setSession({access_token, refresh_token})` → `await setSession(accessToken, refreshToken)`(throw 시 기존 catch→FAILED_PATH, T4). PKCE 분기(:83): `supabase.auth.exchangeCodeForSession(code)` → `await exchangeCodeForSession(code)`. `error` 객체 구조분해 대신 try/catch 라우팅으로 정합(기계적).
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: F3

### F8. [FE] `UserInfoSection.tsx` + `DeleteAccountSection.tsx` — signOut neutral
- 양 파일 `createClient` import 제거 → `import { signOut } from "@/lib/auth"`.
- `supabase.auth.signOut({ scope: "local" })` → `signOut()`(scope 내부 고정, T3). try/catch·후속 정리(queryClient.clear/router.replace) 동일.
- verify: `pnpm -C app exec tsc --noEmit`
- 의존: F3

### F9. [FE] `lib/supabase/client.ts` 삭제
- F2가 흡수했으므로 삭제. 잔존 import가 없는지 확인 후 제거.
- verify: `pnpm -C app exec tsc --noEmit` (잔존 import 있으면 컴파일 실패로 검출)
- 의존: F4, F5, F6, F7, F8

### F10. [QA-FE] FE 무회귀 + 격리 검증
- `pnpm -C app exec tsc --noEmit` + `pnpm -C app test` 무회귀.
- grep 불변식: `@supabase/supabase-js`는 `lib/auth/supabase-client.ts` **한 파일에서만** import. `@/lib/supabase/client` import 0건. `lib/supabase/client.ts` 파일 부재.
- 동작 보존 수동 확인(코드 리뷰): T2(url 반환)·T3(scope local)·T4(throw→FAILED_PATH)·T5(dedup/loading)·T7(네이티브/웹·dual flow·skipBrowserRedirect).
- 의존: F9

---

## 정합성 / 문서

### D1. [DOC] `docs/decisions.md` — iss fail-safe 기본값 기록
- 결정: Phase 1 `oidc_issuer=""` 기본 → iss 검증 스킵. 트레이드오프(보안 하드닝 vs 점진 배포 안전). 실제 iss=`{supabase_url}/auth/v1`, prod 활성화는 검증 후 별도 config 단계.
- 어댑터화(jwt.py 일반화, IdentityProvider, FE lib/auth 3계층)도 1줄 요약.
- verify: 파일 내용 확인
- 의존: B2, B6 (기본값 결정 확정 후)

### Z1. [QA] 최종 통합 게이트
- BE 전체(`poetry run pytest -q`) + FE 전체(`tsc --noEmit` + `pnpm -C app test`) 동시 그린.
- BE-FE shape 협상 의존 없음(FE 어댑터 표면은 내부 완결, BE는 토큰 검증만). 단 양측 무회귀가 핵심.
- spec → `spec-history/2026-06-19-auth-decoupling-phase1.md` 이동 준비.
- 의존: B6, F10, D1

---

## 의존 그래프 (요약)

```
BE:  B1 → B2 → B3 ─┐
                   ├→ B6(QA-BE) ─┐
     B1 → B2 → B5 ─┤             │
     B4 ───────────┘             │
FE:  F1,F2 → F3 → F4,F5,F6,F7,F8 → F9 → F10(QA-FE) ┤
     B2,B6 → D1 ───────────────────────────────────┤
                                                    └→ Z1(최종 게이트)
```
- BE/FE 자연 병렬(공유 shape 없음).
- BE 내부: B4(deleteUser)는 B1~B3과 독립 → 병렬.
- FE 내부: F3 완료 후 F4~F8 병렬 가능, 전부 끝나고 F9(삭제).

## 완료 조건

- [ ] 모든 단위 verify 통과 (B1~B6, F1~F10)
- [ ] BE 전체 `poetry run pytest -q` 무회귀 + iss 토글 3케이스 통과
- [ ] FE 전체 `tsc --noEmit` + `pnpm -C app test` 무회귀
- [ ] grep 불변식: BE `decode_supabase_jwt` 0건 / FE `@supabase/supabase-js` 1파일·`@/lib/supabase/client` 0건
- [ ] `docs/decisions.md` 갱신 (D1)
- [ ] 동작 변경 0 확인 (T2~T5, T7)
- [ ] spec → spec-history 이동 준비 (Z1)
