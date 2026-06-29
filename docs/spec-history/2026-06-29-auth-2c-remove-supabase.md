# 탈-Supabase Auth Phase 2c — 가역 코드 제거 사양서

> 브랜치: `feature/auth-2c-remove-supabase`. **코드 작성·테스트까지만.** 머지·배포·force-update·클라우드 정리 등 운영 명령은 범위 밖(절대 실행 금지).
>
> **방침 변경(2026-06-29, 리더):** #2를 "웹 폐기" → **"개발 편의용 웹 BE flow 복구"**로 전환. supabase-js 물리 제거는 유지하되, 웹도 **BE OAuth flow**로 동작시킨다(어드민 패턴 미러링). BE에 `client=web` 분기 신규(#3).

## 배경 / 목적

탈-Supabase Auth cutover 운영 완료(2026-06-26), force-update bump(`MIN_SUPPORTED_VERSION=1.3.0`) 적용(2026-06-29). 현재는 2c "가역 코드 제거" 단계. backlog ④(2c contract)·⑤(DEFER: isNativePlatform 이중화).

cutover 후 Supabase 잔존 경로: ⓐ BE 검증 default fallback, ⓑ FE 웹 분기(supabase-js). 2c는 ⓐ를 제거하고(#1), ⓑ를 **supabase-js 제거 + 웹 BE flow 전환**으로 대체한다(#2). 웹 BE flow는 어드민(`admin/`)이 이미 구현한 web BE-flow 패턴을 `app/`에 미러링한다.

## 핵심 제약 (불변식)

- **`auth_identities` 매핑 테이블 유지** (기존자 sub→UUID 보존).
- **BE 자체 토큰(ES256) 검증 경로 유지.** 제거 대상은 "Supabase 발급 토큰 검증 fallback" 뿐.
- **웹은 배포 타깃 아님** (Capacitor 단일, [[project_deploy_targets]]). 웹 BE flow는 **개발 편의용** — 운영은 dormant.
- **#1(fallback 제거)과 #3(web client)은 배포 성격이 정반대** → 별개 커밋(상세 아래). #1은 legacy~0 게이트(배포 금지), #3은 무관(개발 편의).

## 제거/유지 경계 (코드 근거)

리더 모호점 "config의 어떤 `SUPABASE_*`가 검증용이고 어떤 게 OAuth 중개용인가"의 답 — **OAuth 중개에 쓰이는 `SUPABASE_*`는 없다.** BE OAuth 브로커는 Google/Kakao/Apple 직결(`google_*`/`kakao_*`/`apple_*`). Supabase 설정의 실제 용도는 둘뿐:

| 심볼 | 용도 | 2c 처리 | 근거 |
|------|------|---------|------|
| `config.oidc_issuer` / `oidc_audience` | Supabase 토큰 **검증** | **제거** | config.py:128~130, 284~289 |
| `config.jwks_uri` property | Supabase JWKS — **검증** fallback URL | **제거**(supabase_issuer_entry 전용 소비) | config.py:249~250 |
| `config.supabase_issuer_entry` property | 검증 default fallback entry | **제거** | config.py:283~289 |
| `decode_oidc_jwt`의 `supabase_entry` default 분기 | iss 미매칭 토큰을 Supabase로 검증 | **제거**(미매칭→401) | jwt.py:59~99 |
| `config.supabase_url` (required) | ⓐ jwks_uri(검증) ⓑ `delete_user`(계정삭제 IdP) ⓒ `be_jwks_uri`(nominal) | **유지** — ⓑⓒ. ⓐ 소비만 제거 | config.py:20, identity_provider.py:25, config.py:255 |
| `config.supabase_secret_key` | `delete_user` admin API 인증(계정삭제 IdP) | **유지** | config.py:31, identity_provider.py:27~28, me.py:44 |
| `auth/identity_provider.py:delete_user` | 탈퇴 시 레거시 Supabase 신원 제거(IdP 관리, **검증 아님**) | **유지** — 클라우드 정리(별도·비가역) 전까지 필요 | me.py:62 |

→ `supabase_url`/`supabase_secret_key`/`delete_user`는 검증이 아니라 **계정삭제 IdP 관리**. 물리 제거는 runbook 2c "비가역 클라우드 정리"(범위 밖). 탈퇴 502는 FE가 정상 종료 처리([[project_account_deletion_audit]]).

## be↔fe shape 계약 (웹 BE flow — 어드민과 동형, 값만 상이)

```
FE web:  GET {API_BASE}/auth/login?provider=&code_challenge=&code_challenge_method=S256&client=web
         → (PKCE verifier 는 localStorage 영속, full-page redirect)
BE:      IdP 중개 후  302 → {be_app_web_redirect_url}?code=<일회용 code>   (토큰 미노출, B4)
FE web:  /auth/callback 페이지가 window.location.search 의 `code` 를 읽어
         → POST {API_BASE}/auth/token  {code, code_verifier}  → {access_token, refresh_token}
```

어드민과 유일 차이: `client` 값 `"admin"`→`"web"`, redirect env `be_admin_redirect_url`→`be_app_web_redirect_url`. param 이름(`client`/`code`/`code_verifier`)·엔드포인트 전부 동일. **계약은 이미 확정**(어드민 구현 직독) — be-engineer는 #3 착수 시 **확정 env 이름(`be_app_web_redirect_url`)만 fe-engineer에 DM**하면 된다.

---

## 작업 단위

### 1. [BE-#1] Supabase 검증 fallback 제거 (⚠️ legacy~0 수렴 전 배포 금지)

> **위험:** 배포 즉시 Supabase 토큰 보유 구앱(현 활성 ~26.2%) **락아웃**. **독립 커밋**으로 격리, 커밋 메시지에 `⚠️ legacy 구앱 비중 ~0 수렴 전 배포 금지` 명시. legacy 게이트는 PostHog 재측정 판정(runbook 2c 로그).

**대상:** `api/src/invest_note_api/auth/{jwt.py, dependency.py, constants.py}`, `config.py`

1. **`decode_oidc_jwt`(jwt.py)**: iss peek → registry(BE issuer) 매칭이면 그 entry 검증, **없으면 `jwt.InvalidTokenError` raise(→401)**. `supabase_entry` default fallback 분기 제거. 레거시 단일-인자 경로(`jwks_uri`/`audience`/`issuer`/`supabase_entry` 파라미터)도 검증용이므로 정리.
2. **`dependency.py`**: `decode_oidc_jwt` 호출에서 `supabase_entry` 인자 제거. `_registry_with_be_key` 유지.
3. **`config.py`**: `oidc_issuer`·`oidc_audience` 필드, `jwks_uri` property, `supabase_issuer_entry` property 제거. `supabase_url`/`supabase_secret_key` **유지**. `oidc_issuer_registry`·`be_jwks_uri`·`be_token_*` 무수정.
4. **⚠️ 불변식 역전(가장 중요):** 현재 안전속성 "registry 비면 Supabase entry 단독=Phase1=dormant-safe"는 **의도적 폐기**. `be_token_signing_key` 미설정 시 registry 빈 → **전원 401**. 로컬 dev `.env.local`에 BE signing key 없으면 dev 인증 전멸. be-engineer는 conftest/fixture가 테스트 토큰을 어떻게 mint하는지 먼저 확인하고 BE-issuer 토큰으로 전환.
5. **orphan 명시 결정:** fallback 제거 후 BE entry는 항상 `verify_key` 보유 → `_verify_with_entry`의 `verify_key is None` 분기·`_get_jwks_client`·`PyJWKClient` import·`jwks_uri` property가 dead가 되는지 확인. **제거 vs 보존을 be-engineer가 명시 결정**(반쯤 죽은 채 방치 금지). `be_jwks_uri`는 `supabase_url` 파생이라 유지되며 향후 클라우드 정리 시 `be_oauth_redirect_base`로 재유도 필요함을 코멘트.
6. **테스트:** Supabase 폴백/Supabase식 토큰 검증 의존 테스트는 BE-issuer 토큰 발급으로 전환. "unknown iss→Supabase"는 **"unknown iss→401"로 교체**. `delete_user`/`supabase_secret_key` 게이트(test_me.py) 무회귀.

- **verify:** `cd api && poetry run pytest tests/test_issuer_registry.py tests/test_auth_router.py tests/test_be_token.py tests/test_me.py -q` (또는 전체 `-q`)
- **의존:** 없음

### 3. [BE-#3] `client=web` 분기 추가 (개발 편의, #1과 별개 커밋)

> **위험 0(운영 dormant):** `be_app_web_redirect_url` 빈 값 → `client=web` 503. 운영 보안 표면 증가 0. **⚠️ #1과 반드시 별개 커밋** — 둘 다 `config.py`를 건드리나 라인 무겹침(#1=제거 oidc_issuer/oidc_audience/jwks_uri/supabase_issuer_entry, #3=추가 be_app_web_redirect_url). **순차 커밋**으로 분리(hunk 수술 불요): #19(#1) 완료 후 #3.

**대상:** `api/src/invest_note_api/{config.py, routers/auth.py}`

1. **`config.py`**: `be_app_web_redirect_url: str = ""` 추가(`be_admin_redirect_url` 인근). default 빈 값 = dormant. 주석에 "개발 편의용 웹 BE flow callback, 운영 빈 값(dormant)" 명시.
2. **`routers/auth.py` `login`**: dormant-503 가드에 web 추가 — `if client == "web" and not settings.be_app_web_redirect_url: raise APIError(ERR_SERVICE_UNAVAILABLE, 503)`(어드민 admin 분기와 **대칭 surgical 추가**, admin 분기를 map으로 리팩토링 금지).
3. **`routers/auth.py` `_handle_callback`**: `client_kind` 분기에 `elif client_kind == "web": target = _redirect_with_code(settings.be_app_web_redirect_url, one_time)` 추가 + 방어적 빈-env 503(admin 분기와 동형).
4. **테스트:** `client=web` + env 설정 시 redirect target = `be_app_web_redirect_url?code=`, env 빈 값 시 login 503. admin 분기 무회귀.
5. **dev env 안내(코드 아님):** 로컬 웹 BE flow 실동작은 BE OAuth dev env 일습(`be_token_signing_key`·provider creds·`be_oauth_redirect_base`·`be_app_web_redirect_url=http://localhost:3000/auth/callback`)이 필요. 이는 **수동 dev 전제**이지 #3의 게이팅 verify 아님.

- **verify:** `cd api && poetry run pytest tests/test_auth_router.py -q` (web 분기 단위 테스트). 라이브 왕복은 dev env 전제(수동).
- **의존:** [BE-#1] (별개 커밋 순차 — addBlockedBy #19)

### 2. [FE-#2] supabase-js 물리 제거 + 웹 BE flow 전환 (다음 스토어 빌드)

> **위험:** 출하 build31 무영향(번들 굳음). 웹은 dev 전용. legacy 게이트 무관.

supabase-js 물리 제거는 유지, 웹은 **폐기 대신 BE flow로 전환**(어드민 미러링). 웹/네이티브 분기 기준은 **platform**(웹=full-page redirect+https callback, 네이티브=Browser.open+딥링크)이지 supabase가 아니다.

**(A) supabase-js 제거**
- `app/package.json` — `@supabase/supabase-js`(`^2.103.0`) 제거.
- `app/src/lib/auth/supabase-client.ts` — **파일 삭제**.
- `app/src/types/database.ts` — `Database` interface 제거(Supabase 클라이언트 전용, 소비처 0 확인). `Account`/`Trade` 등 유지.
- `app/src/components/providers/PostHogIdentifyBridge.tsx`·`settings/DeleteAccountSection.tsx`·`lib/auth/types.ts` — stale Supabase 주석 정리(기능 무변, `delete_user` 유지로 502 동작 동일).

**(B) 웹 토큰 영속 계층 추가 — ⚠️ 핵심 신규(리더 메시지 미명시, 웹 BE flow 동작 필수)**
- `app/src/lib/auth/token-store.ts` — 현재 **네이티브 secure-storage 전용**. 웹 BE flow는 토큰/verifier가 full-page redirect 왕복·리로드를 생존해야 하므로 **platform 분기**: 네이티브 = secure storage(현행 유지, lazy import는 네이티브 분기 안에서만), **웹 = localStorage**(어드민 `admin/src/lib/auth/token-store.ts` 미러링 — `safeGet` graceful, 동일 키 네이밍, async 시그니처 유지).
- **C5 보안 근거(반드시 스펙·코멘트에 명시):** `token-store.ts`는 "평문 localStorage 금지(C5, 금융 앱)"라 명시돼 있다. 웹 localStorage 토큰이 허용되는 근거 — ⓐ 운영 웹은 **dormant**(`be_app_web_redirect_url` 빈 값 → 503), ⓑ 웹은 **배포 타깃 아님**(Capacitor 단일), ⓒ 어드민이 동일 선례(내부 콘솔). **네이티브는 secure storage 불변.** 이 근거를 코멘트로 박아야 리뷰에서 회귀로 오인되지 않는다.

**(C) lib/auth/index.ts — BE flow 단일화 + platform 분기**
- 6함수에서 Supabase `else` 분기 전부 제거. `getSupabaseClient`·`getBeAuthEnabled` import 제거. `isBeAuthFlow()` 제거 → **웹/네이티브 모두 BE flow**.
- `signInWithOAuth`: platform 분기 — 네이티브 = `buildLoginUrl(provider, challenge)` URL 반환(login이 Browser.open), 웹 = `buildLoginUrl(provider, challenge, "web")` 로 `window.location.assign`(full-page, 어드민 `signInWithGoogle` 미러링). **시그니처 권장: `signInWithOAuth(provider)`로 `options` 인자 드롭**(redirectTo/skipBrowserRedirect는 BE flow에서 불필요 — 분기가 내부 platform 판정). 반환 `{ url: string | null }` 유지(네이티브=url, 웹=navigate away). → login.tsx 소폭 수정 동반.
- `getAccessToken`/`getUser`/`signOut`/`subscribe`는 platform-agnostic BE flow(어드민 index.ts와 동일). token-store가 내부 분기하므로 추가 분기 불요. `toAuthUser` dead 정리.
- **⚠️ `exchangeCodeForSession`는 세션 미확립 시 throw로 수정**(어드민 index.ts:229~230 미러링): `persistAndEmit`가 null 반환(decodeClaims null·로그아웃 interleave)이면 **명시적 throw**. 안 그러면 웹 콜백이 "/"로 갔다가 즉시 /login으로 무증상 튕김. 웹 콜백의 `.catch→/login?error`가 이 throw에 의존. (현 네이티브 구현은 throw 안 함 — 정합성 수정 필요, polish 아님.)

**(D) be-client.ts — client param**
- `buildLoginUrl(provider, codeChallenge, client?)` — optional `client` 인자 추가. 웹은 `"web"` 전달, 네이티브는 생략(BE default native). 어드민 be-client `buildLoginUrl`와 형태 일치.

**(E) 웹 콜백 페이지 — 삭제가 아니라 BE flow code 교환용 개조(어드민 콜백 미러링)**
- `app/src/app/auth/callback/page.tsx` — 현재 supabase `detectSessionInUrl` 의존(useAuth만 사용). **개조**: `window.location.search`의 `code` → `exchangeCodeForSession(code)` → 성공 "/" / 실패 `/login?error=oauth`. **⚠️ `exchangedRef` once-guard 필수**(어드민 callback:14~18 미러링) — React strict-mode 이중 effect → 이중 교환 → 2번째 401. async 호출 전 동기 set.
- `app/src/lib/auth/oauth-config.ts:WEB_CALLBACK_PATH` — 웹 BE callback 경로로 유지(삭제 금지). login.tsx redirectTo 드롭으로 FE 미사용화되면 제거 여부는 fe-engineer 판단(콜백 라우트 문서값).
- `CapacitorDeepLinkHandler.tsx` — 네이티브 딥링크 경로(무변 확인됨).

**(F) app-config.ts — FE 플래그 plumbing 제거 (BE 필드는 유지)**
- `getBeAuthEnabled`·`ensureBeAuthFlagLoaded`·`settle`·`beAuthEnabledCache`·`__setBeAuthEnabledForTest` 제거. `fetchAppConfig`는 force-update(minSupportedVersion/storeUrl)용 유지. `AppConfig.beAuthEnabled` 필드 + `settle(config.beAuthEnabled)` 라인 제거.
- `AuthProvider.tsx` — `ensureBeAuthFlagLoaded` 게이트 제거(웹/네이티브 모두 BE flow라 race 소멸), dead `isNativePlatform` import 정리.
- **⚠️ BE `/app-config`의 `beAuthEnabled` 필드는 건드리지 말 것(범위 밖)** — 출하 build31이 `beAuthEnabled:true`를 읽어 동작. FE 소비만 제거.

**테스트(test-architecture 변경 — 과소평가 주의):**
- `app/src/lib/auth/token-store.ts` — **양 분기 테스트 신규**: 웹(localStorage) + 네이티브(`isNativePlatform`=true mock + secure storage mock).
- `app/src/lib/auth/__tests__/index.test.ts` — jsdom default(`isNativePlatform`=false)는 이제 **웹 localStorage 경로**(secure-storage mock 불요). 네이티브-경로 테스트는 `isNativePlatform`=true + secure storage mock. `__setBeAuthEnabledForTest(false)` Supabase 폴백 테스트(line 356~363) **삭제**. exchangeCodeForSession throw-on-no-session 테스트 추가.
- `app/src/lib/api/app-config.test.ts` — 플래그 테스트 제거, force-update 검증만.
- `app/src/app/auth/callback/__tests__/page.test.tsx` — **삭제 아니라 재작성**: BE code-교환 flow 커버(어드민 콜백 테스트 미러링, once-guard 포함).

- **verify:** `pnpm -C app exec tsc --noEmit` + `pnpm -C app test`
- **의존:** [BE-#3] — FE 웹 콜백이 BE web client 계약 소비. 계약은 확정이나 env 이름 확정 후 착수(addBlockedBy #23). #1과는 비블로킹.

### 4. [QA-#1] BE 검증 경로 + web client 분기 정합

- 유효 BE 토큰(ES256, registry 매칭) 검증 **유지** — 200.
- iss 미매칭/Supabase식 토큰 → **401**(default fallback 소멸).
- `be_token_signing_key` 미설정(registry 빈) → 전원 401(불변식 역전), dev `.env.local` BE signing key 확인.
- `delete_user`/`supabase_secret_key` 게이트 무회귀.
- 제거 심볼(`oidc_issuer`/`oidc_audience`/`jwks_uri`/`supabase_issuer_entry`) 잔존 참조 0.
- **web client(#3):** `client=web`+env → redirect `be_app_web_redirect_url?code=`, env 빈 값 → login 503(dormant). admin 분기 무회귀.
- **verify:** `cd api && poetry run pytest -q` 전체 green.
- **의존:** [BE-#1]·[BE-#3] (addBlockedBy #19, #23)

### 5. [QA-#2] FE 웹/네이티브 BE flow 단일 출처 정합 + shape drift 가드

- `grep -rin supabase app/src` 잔여 = 무해 주석만(import/호출 0), `@supabase/supabase-js` package.json·lockfile 부재.
- 6 auth 함수 Supabase 분기 0, 웹/네이티브 모두 BE flow.
- **웹 BE flow 경로 정합:** buildLoginUrl `client=web` shape, 콜백 `code` query 이름, `/auth/token {code, code_verifier}` body가 BE-#3 계약과 일치(drift 0).
- token-store 양 분기(웹 localStorage / 네이티브 secure storage) 동작, C5 근거 코멘트 존재.
- `exchangeCodeForSession` throw-on-no-session + 콜백 once-guard 존재.
- **⚠️ BE `/app-config`의 `beAuthEnabled` 필드 RETAIN 확인**(FE가 BE 응답에서 빼지 않았는지 — 빼면 build31 락아웃).
- `pnpm -C app exec tsc --noEmit` 0 + `pnpm -C app test` green.
- **의존:** [FE-#2] (addBlockedBy #20)

## 완료 조건

- [ ] [BE-#1] verify 통과 + 독립 커밋(⚠️ 배포 금지 경고)
- [ ] [BE-#3] verify 통과 + **별개 커밋**(#1 뒤 순차)
- [ ] [FE-#2] tsc + test 통과
- [ ] [QA-#1]·[QA-#2] 정합 통과
- [ ] `docs/decisions.md` 2c 항목 갱신 — **필수**(트레이드오프 역전: 웹 폐기→복구, localStorage 영속, 운영 dormant, 검증 불변식 역전 기록)
- [ ] spec → `docs/spec-history/2026-06-29-auth-2c-remove-supabase.md` 이동 준비

## 범위 밖 (명시적 제외)

- 운영 배포·머지·force-update·PostHog 재측정.
- runbook 2c "비가역 클라우드 정리": `SUPABASE_*` env 제거·`supabase/` 디렉토리·Supabase 클라우드 정리·PIPA. (`supabase_url`/`secret_key`/`delete_user` 유지가 이 단계 의존.)
- **크로스탭 storage 동기화**(어드민 index.ts:64~83) — 단일 dev 탭, AuthProvider가 리로드마다 storage 재독. YAGNI 제외.
- backlog ⑤ `AuthStrategy` 인터페이스 — platform 분기로 충분, **인터페이스 신설 금지**(과설계).
- `admin/` 어드민 패널 — 이미 BE-auth 전환 완료(2026-06-26, 미러링 원본).
