# Supabase Auth 종속성 제거 Phase 2b-2 — FE 전환(BE flow) + refresh 흡수 (FE) 사양서

작성: 2026-06-19 | 근거: `_workspace/auth-phase2-design.md`(#5 FE 전환), `_workspace/02_be_changes.md`(**2b-1 BE 계약 — 필수**), `docs/spec-history/2026-06-19-auth-decoupling-phase1.md`(FE `lib/auth/` 3계층, 전환 대상), 2b-1 상세 본문은 git commit `9fa5181`(직전 spec-current 의 2b-1 — 본 갱신으로 overwrite, 아직 spec-history 로 rename 전).

> **Phase 2a·2b-1(BE) 는 완료·커밋·dormant.** 태스크 #19~#49 는 건드리지 않는다(A1/Q1/Q5·마이그레이션·env 적용은 confirm 대기로 open 유지). 이 스펙은 **2b-2(FE 전환) 만** 상세 분해한다. 2c(contract)는 말미 "후속" 참조. ⚠️ **2b-1 본문 보관 미완**: 직전 spec-current(2b-1)는 git `9fa5181` 에만 남았고 `spec-history/2026-06-19-auth-decoupling-phase2b1.md` 로 아직 rename 안 됨(spec-finish 워크플로 소유). 리더가 2b-1 finish 시 git 본문으로 history 파일 생성 필요(working tree 유실 방지).

---

## 배경 / 목적

2b-1 이 BE 에 OAuth 중개·BE 토큰 발급·refresh·profile 인프라를 깔았다(dormant — env 미주입). 이제 **신 앱(FE)이 Supabase SDK 대신 BE OAuth flow 를 쓰도록 전환**한다. 목표(사용자): "API 중심 — IdP 교체를 백엔드 배포만으로". supabase-js 가 자동 처리하던 세션 영속·토큰 갱신·상태 구독을 FE 가 떠안는다.

**flow(2b-1 계약, 네이티브):** 앱이 PKCE `code_verifier` 생성 → `code_challenge(S256)` → 인앱 브라우저로 `{BE}/auth/login?provider=&code_challenge=&code_challenge_method=S256` → BE 가 IdP 중개 → 딥링크 `{scheme}?code=<일회용>` → 앱이 `{BE}/auth/token` 에 `{code, code_verifier}` 제출 → `{access_token, refresh_token}` 수신 → secure storage 저장. 이후 401/만료 시 `{BE}/auth/refresh` 로 회전.

---

## ⚠️ 먼저 정정 — B12 spec drift (enforce-always)

직전 spec-current(2b-1) line69 부근 및 design 노트의 "code_verifier 예약/미사용" 텍스트는 **stale**. 2b-1 실제 구현은 **PKCE enforce-always**(02_be_changes line 150/160/195):
- `GET /auth/login` 의 `code_challenge`(S256) **필수** — 누락 시 거부.
- `POST /auth/token` 의 `code_verifier` **필수** — 누락/불일치 시 거부(code 는 소진).

→ 2b-2 FE 는 **반드시** code_verifier 생성→challenge 전달→딥링크 code 수신→verifier 제출을 구현한다. stale 텍스트대로 challenge/verifier 없이 구현하면 **전 로그인 거부**. (이 정정은 D-1 decisions 및 2b-1 spec-history 보관본에도 반영.)

---

## 범위 (Scope)

**포함 (2b-2, FE only — `app/`):**
- **lib/auth swap (네이티브 분기만)**: Phase 1 의 supabase-js 기반 7함수(`signInWithOAuth`/`getAccessToken`/`getUser`/`signOut`/`subscribe`/`setSession`/`exchangeCodeForSession`)를 **BE flow** 로 교체. 네이티브는 BE store/token, **웹은 expand 동안 Supabase 유지**(아래 결정 참조).
- **PKCE 앱 측**: `code_verifier`(crypto random) 생성 → `code_challenge = base64url(SHA256(verifier))` → `/auth/login` 전달 → 딥링크 code 수신 → `/auth/token` 에 verifier 제출. **2b-1 enforce-always 와 짝.**
- **토큰 store (Capacitor secure storage)**: supabase-js 자동 persistence/onAuthStateChange 상실 대체. access/refresh 보관, PKCE verifier 임시 보관(cold-start 생존).
- **refresh 흡수**: `getAccessToken` 이 순수 getter 가 아니게 됨 — exp 디코드 후 만료 임박이면 `/auth/refresh` 로 회전→retry. **모듈 레벨 single-flight**(병렬 폭주 차단). 실패 시 토큰 clear + logout emit(무한루프 차단).
- **getUser / subscribe 자체 구현**: getUser = access token claim 로컬 디코드. subscribe = 자체 listener registry(토큰 set/clear 시 emit).
- **딥링크 핸들러**: BE flow code→`/auth/token` 교환(네이티브). 웹 분기는 Supabase 유지.
- **secure storage 플러그인 추가**(Capacitor 8 peer 호환) + decisions 기록.
- `docs/decisions.md` 갱신.

**제외 (명시적):**
- **supabase-js 완전 제거 = "assess" 결론만, 실제 제거는 2c.** 웹 분기가 expand 동안 Supabase 를 계속 쓰므로 2b-2 에서 물리적 제거 불가(아래 결정). `supabase-client.ts` 격리경계 존속.
- **웹 BE flow 전환**: BE 가 web origin 으로 code 를 돌려줄 수 없음(callback = custom scheme 전용). 웹은 Supabase 유지.
- 2c 일체: Supabase 검증 제거, force-update 가드, 양 스토어 sunset.
- BE env·마이그레이션·백필 적용(2b-1 confirm 대기 — FE 코드와 무관).
- App Links/Universal Links(스킴 hijack 자체 차단) — 도메인 검증 부담, 후속 backlog.

## 가정 / 결정 (Assumptions & Decisions)

- **D-A (웹/네이티브 분기 — ✅ 리더 confirm 2026-06-19):** FE 는 Capacitor 네이티브 단일 배포([[invest-note]] deploy-targets, 웹 일반사용자 배포 없음·dev 서버뿐). 2b-1 BE flow 는 네이티브 전용(callback=custom scheme). → **2b-2 = 네이티브만 BE flow, 웹은 expand 동안 Supabase 유지**(lib/auth 함수를 `isNativePlatform()` 으로 이중화). **supabase-js 완전 제거는 "웹 잔존이라 제거 불가" 로 확정 이연 → 2c/웹 폐기**(F-10 assess 결론 못박음).
- **D-B (secure storage 플러그인):** access/refresh/verifier 평문 localStorage 금지(금융 앱). 네이티브 secure storage 플러그인 신규 추가 — Capacitor 8 peer 호환 필수(8.x 최신이라 lag 플러그인 다수, 호환이 tightest constraint). 후보 평가 후 1개 선정(F-1). ⚠️ **신규 네이티브 플러그인 = OTA 불가, 스토어 빌드 필수**([[invest-note]] OTA/deploy).
- **D-C (getAccessToken refresh 전략):** **proactive** — access JWT exp 디코드 후 60s skew 내 만료면 refresh. + **모듈 single-flight promise**(스타트업에 AuthProvider+대시보드 다발 호출 → N개 refresh 폭주 차단, hard req). access 가 self-contained JWT(서버 조기폐기 없음)라 반응형 401-retry 불요 → **api-client.ts:82 콜사이트 무변경**(apiFetch 무수정).
- **D-D (getUser 디코드):** access token payload 를 base64url 로컬 디코드(`sub`→id, `email`). **검증 라이브러리 미도입**(BE 가 서명 검증, 앱은 claim 읽기만). 만료 시 getAccessToken 경유로 refresh 후 디코드.
- **D-E (PKCE verifier 영속):** 딥링크 cold-start(`App.getLaunchUrl`, CapacitorDeepLinkHandler line 90-95) 생존 위해 verifier 를 메모리 아닌 secure storage 임시 보관 → 교환 성공/실패 후 삭제.
- **D-F (BE base URL):** `/auth/login·token·refresh` 는 `/v1` 아래가 아니라 **bare**(02_be_changes line 120, health 다음 mount). api-client 의 `NEXT_PUBLIC_API_BASE_URL`(`API_BASE`) 공유. lib/auth 가 BE 호스트 의존 추가.
- **D-G (dormant 503 우아 처리):** env 미주입 BE → `/auth/*` 503. FE 는 크래시 금지, 기존 `LOGIN_OAUTH_FAILED_PATH` 라우팅.

---

## ⚠️ 최대 함정 체크리스트 (구현 전 필독)

| # | 함정 | 가드 |
|---|------|------|
| **C1 (HINGE)** | **PKCE 누락/불일치 → 전 로그인 거부.** 2b-1 은 enforce-always(challenge/verifier 필수, S256 외 method 400). stale spec 텍스트대로 생략하면 `/auth/token` 이 모두 거부. ⚠️ **BE 에 plain 폴백 없음** — S256 만 허용. | `/auth/login` 에 `code_challenge`+`code_challenge_method=S256` **필수** 전달, `/auth/token` 에 `code_verifier` 제출. challenge = `base64url(SHA256(verifier))`, verifier = 고엔트로피 crypto random(43~128 char unreserved). ⚠️ **`crypto.subtle.digest` 디바이스 검증 필수**: jsdom/node 테스트는 항상 crypto.subtle 가 있어 green 이나 Capacitor WebView(특히 custom scheme origin)에서 부재 시 전 네이티브 로그인 사망. plain 폴백 불가(BE 거부). verify: 생성한 verifier↔challenge round-trip(SHA256) + **iOS·Android 디바이스 WebView 실측 1회**(jsdom 통과 ≠ 디바이스 보증). 참고: 현 supabase-js PKCE 가 네이티브에서 S256 으로 성공 중이면 동일 WebView 라 안전 신호. |
| **C2 (HINGE)** | **PKCE verifier cold-start 소실** → 앱이 OAuth 중 죽으면(브라우저 전환·OOM) 딥링크 복귀 시 verifier 없어 교환 영구 불가. 메모리 only 면 발생. | verifier 를 **secure storage 영속**(D-E). login 시 저장, 딥링크 교환 직전 읽기, 교환 성공/실패 후 삭제. verify: store 에 저장→읽기→삭제 경로 + 콜드스타트(`getLaunchUrl`) 경로가 verifier 읽음. |
| **C3 (HINGE)** | **refresh single-flight 부재 → 폭주.** 스타트업에 AuthProvider.getUser + 대시보드 다발 fetch 가 동시에 만료 access 로 getAccessToken 호출 → N개 동시 `/auth/refresh` → refresh 회전이라 첫 1개만 유효·나머지 "이미 회전" 401 → 로그아웃 폭사. | getAccessToken refresh = **모듈 단일 in-flight promise** 공유(동시 호출은 같은 promise await). verify: 동시 getAccessToken N회 호출 시 `/auth/refresh` fetch 1회만, 모두 같은 신 토큰 수신. |
| **C4** | **refresh 무한루프.** refresh 실패→재시도→또 refresh. | refresh 실패(401/네트워크) = 토큰 clear + logout emit(subscribe→AuthProvider user=null) + getAccessToken null 반환. **재호출은 토큰 부재라 즉시 null**(refresh 미시도). verify: 실패 refresh 후 getAccessToken null·refresh 재미발생, AuthProvider user=null. |
| **C5** | **refresh 토큰 평문 저장** → 단말 탈취 시 영구 토큰. | secure storage(D-B, Keychain/Keystore) — localStorage 금지. verify: localStorage 에 토큰 부재(grep + 런타임), store 인터페이스가 secure plugin 경유. |
| **C6** | **딥링크에 토큰 직접 처리 잔존(B4 위반).** 2b-1 딥링크엔 code 만 옴(access/refresh 미노출). 기존 핸들러의 implicit fragment(access_token/refresh_token) 분기를 BE 네이티브 경로에 남기면 죽은 코드 + 혼동. | 네이티브 BE 경로 = **code→/auth/token 단일**. fragment/`setSession` 분기는 네이티브에서 제거(웹 Supabase 경로엔 잔존). verify: 네이티브 핸들러에 access_token fragment 파싱 부재, code 경로만. |
| **C7** | **dormant BE(503) 크래시.** env 미주입 BE 면 `/auth/login`·`/token` 503. | fetch 비-2xx → throw → login/딥링크 기존 catch → `LOGIN_OAUTH_FAILED_PATH`. verify: 503 mock 시 크래시 없이 FAILED 라우팅. |
| **C8** | **웹 회귀.** 네이티브 전환이 웹 Supabase 경로를 깨면 dev/웹 콜백 붕괴. | lib/auth 7함수 = `isNativePlatform()` 분기, 웹 가지는 **기존 supabase-client 호출 무변경**. verify: 웹 분기에서 기존 supabase 호출 보존(코드 리뷰) + AuthProvider.test 무회귀. |
| **C9** | **getUser exp 미반영.** 디코드만 하면 만료 토큰으로도 user 반환 → 인증 실패와 UI 불일치. | getUser = getAccessToken(refresh-aware) 경유로 유효 토큰 확보 후 디코드. 토큰 없으면 null. verify: 만료 토큰→refresh 성공 시 user, refresh 실패 시 null. |
| **C10** | **base64url 디코드 오류.** JWT payload 는 base64url(+padding 제거). 표준 atob 직접 쓰면 `-`/`_`·padding 으로 깨짐(특히 한글 email). | base64url→base64 치환(`-`→`+`,`_`→`/`)+padding 보정 후 디코드, UTF-8 안전. verify: 한글 포함 claim 디코드 round-trip. |
| **C11** | **signOut 네이티브 = revoke 엔드포인트 없음.** 2b-1 계약에 logout 없음. | 네이티브 signOut = **로컬 store clear + logout emit**(서버 미호출). 웹은 기존 `signOut({scope:"local"})` 유지(parity). verify: 네이티브 signOut 후 store 비움·user null, 서버 호출 부재. |

---

## FE 작업 단위 (app/) — 2b-2 상세 분해

> 의존 순서: foundation(plugin/store/pkce/fetch) → lib/auth swap(7함수+딥링크+login) → AuthProvider+test+콜사이트+assess. 각 단위 verify 1개 이상.

### ── 2b-2a foundation ──

### F-1. [FE] secure storage 플러그인 추가 + 평가
- npm 에서 Capacitor **8.x peer 호환** secure storage 플러그인 후보 평가(예: `@capacitor-community/secure-storage` 류 — 실제 8 호환 패키지 npm 으로 확인, 추측 금지). iOS Keychain + Android Keystore 백킹 확인. 1개 선정 후 `pnpm -C app add`.
- `app/package.json` 에 의존 추가. 네이티브 sync(`npx cap sync`)는 빌드 단계 — 코드 외 절차로 명시.
- ⚠️ **신규 네이티브 플러그인 = OTA 불가·스토어 빌드 필수**(D-B).
- verify: `pnpm -C app exec tsc --noEmit`(타입 해석) + 선정 근거(8 호환·Keychain/Keystore)를 summary 에 기록.
- 의존: 없음

### F-2. [FE] `lib/auth/token-store.ts` 신규 — secure 토큰 store
- F-1 플러그인 래핑. API: `saveTokens({access, refresh})`, `getAccessTokenRaw()`, `getRefreshToken()`, `clearTokens()`, `saveVerifier(v)`/`getVerifier()`/`clearVerifier()`(C2). 모두 async(네이티브 secure storage async).
- **네이티브 전용** — 웹 분기는 이 모듈 미사용(Supabase 가 자체 persistence). 웹에서 호출 시 no-op 또는 미진입(isNativePlatform 게이트는 lib/auth/index 가 담당).
- verify: `pnpm -C app exec tsc --noEmit` + `pnpm -C app test src/lib/auth/__tests__/token-store.test.ts`(save→get→clear round-trip, verifier 별도 키, 플러그인 mock)
- 의존: F-1

### F-3. [FE] `lib/auth/pkce.ts` 신규 — PKCE S256 (C1)
- `generateVerifier(): string`(고엔트로피 crypto random, 43~128 char, unreserved `[A-Za-z0-9-._~]`). `challengeFromVerifier(verifier): Promise<string>`(`base64url(SHA256(verifier))`, WebCrypto `crypto.subtle.digest`). base64url 인코딩 헬퍼 공유.
- ⚠️ **C1 디바이스 함정**: `crypto.subtle.digest` 는 jsdom 에 항상 있어 unit test 가 부재를 못 잡음. BE plain 폴백 없음(S256 거부) → WebView 부재 시 전 로그인 사망.
- verify: `pnpm -C app exec tsc --noEmit` + `pnpm -C app test src/lib/auth/__tests__/pkce.test.ts`(verifier 형식·길이, challenge round-trip: 알려진 verifier→기대 challenge, S256 정확성) + **iOS·Android 디바이스 WebView 에서 `crypto.subtle.digest` 실측 1회**(QA carry-forward, jsdom green ≠ 디바이스 보증)
- 의존: 없음

### F-4. [FE] `lib/auth/be-client.ts` 신규 — BE auth fetch + JWT 디코드
- BE base URL = `NEXT_PUBLIC_API_BASE_URL`(D-F, api-client 와 동일 env). bare 경로(`/auth/login`·`/auth/token`·`/auth/refresh`).
- `buildLoginUrl(provider, codeChallenge): string` → `{BASE}/auth/login?provider=&code_challenge=&code_challenge_method=S256`(인앱 브라우저용 URL, C1).
- `exchangeToken(code, verifier): Promise<{access, refresh}>` → `POST {BASE}/auth/token` `{code, code_verifier}`. 비-2xx throw(C7).
- `refreshToken(refresh): Promise<{access, refresh}>` → `POST {BASE}/auth/refresh` `{refresh_token}`. 비-2xx throw.
- `decodeClaims(accessToken): { id: string; email: string | null } | null` → base64url payload 디코드(C10), `sub`/`email` 추출, exp 만료 판정 헬퍼(`isExpiringSoon(token, skewSec)` C3/C9). **검증 안 함**(D-D).
- verify: `pnpm -C app exec tsc --noEmit` + `pnpm -C app test src/lib/auth/__tests__/be-client.test.ts`(URL 빌드 정확, 한글 email claim 디코드 round-trip C10, exp skew 판정, fetch mock 으로 token/refresh shape·503 throw C7)
- 의존: F-3(challenge 입력은 호출부에서 주입 — be-client 자체는 pkce 직접 의존 최소)

### ── 2b-2b lib/auth swap ──

### F-5. [FE] `lib/auth/index.ts` — 7함수 네이티브 BE flow 분기 (HINGE)
- 각 함수에 `isNativePlatform()` 분기 추가(C8). **웹 가지는 기존 supabase-client 호출 그대로**(무변경), 네이티브 가지만 BE flow.
- **signInWithOAuth(provider, options)**: 네이티브 = `generateVerifier`→`saveVerifier`(C2)→`challengeFromVerifier`→`buildLoginUrl(provider, challenge)`→`{ url }` 반환(login page 가 Browser.open). redirectTo/skipBrowserRedirect 옵션은 네이티브 BE flow 에선 불필요(BE 가 deeplink 고정) — 시그니처는 호환 유지하되 네이티브 분기는 url 만 사용.
- **exchangeCodeForSession(code)**: 네이티브 = `getVerifier`→`exchangeToken(code, verifier)`→`saveTokens`→`clearVerifier`→emit(subscribe). 실패 throw(C2/C7, 딥링크 핸들러 라우팅). 웹 = 기존 supabase `exchangeCodeForSession`.
- **getAccessToken()**: 네이티브 = `getAccessTokenRaw`→exp 검사(C3)→만료임박이면 **single-flight refresh**(`refreshToken`→`saveTokens`→emit)→유효 토큰 반환. refresh 실패 = `clearTokens`+logout emit(C4)+null. 웹 = 기존 supabase getSession.
- **getUser()**: 네이티브 = `getAccessToken`(refresh-aware C9)→`decodeClaims`→AuthUser. 없으면 null. 웹 = 기존.
- **subscribe(cb)**: 네이티브 = **자체 listener registry**(set/clear emit), 해제 함수 반환. 웹 = 기존 onAuthStateChange.
- **signOut()**: 네이티브 = `clearTokens`+logout emit(C11, 서버 미호출). 웹 = 기존 `signOut({scope:"local"})`.
- **setSession(a, r)**: 네이티브 BE flow 에선 미사용(implicit fragment 없음, C6). 웹 가지만 유지하거나, 네이티브는 throw/no-op(딥링크 핸들러에서 호출 안 하도록 F-6 와 짝). → F-6 가 네이티브에서 setSession 미호출하도록 정리하면 네이티브 setSession 분기 불요.
- ⚠️ single-flight promise 는 **모듈 스코프 변수**(C3). emit 은 subscribe registry 와 공유.
- verify: `pnpm -C app exec tsc --noEmit` + `pnpm -C app test src/lib/auth/__tests__/index.test.ts`(네이티브 mock: signIn=verifier 저장+url, exchange=token 저장+emit, **getAccessToken single-flight(동시 N호출→refresh 1회 C3)**, refresh 실패→clear+null+emit(C4), getUser 디코드, signOut clear+emit. 웹 mock: 기존 supabase 호출 보존 C8)
- 의존: F-2, F-3, F-4

### F-6. [FE] `CapacitorDeepLinkHandler.tsx` — code→/auth/token 단일 경로 (C6)
- 네이티브 딥링크 = **code→`exchangeCodeForSession(code)`(F-5 네이티브 = /auth/token 교환) 단일**. 기존 implicit fragment(access_token/refresh_token)→`setSession` 분기 **제거**(BE flow 엔 토큰 직접 미노출, B4). `error_description` 분기·`getLaunchUrl` 콜드스타트(C2 verifier 읽음)·browserFinished 이벤트 유지.
- 성공→`router.replace("/")`, 실패(throw)→`LOGIN_OAUTH_FAILED_PATH_WITH_SLASH`(기존 catch, C7). 기계적 동일.
- ⚠️ 이 핸들러는 `isNativePlatform()` 가드로 이미 네이티브 전용 → 분기 단순. 웹 콜백은 별도 페이지(auth/callback/page.tsx, 무변경).
- verify: `pnpm -C app exec tsc --noEmit`(+ 기존 핸들러 테스트 있으면 무회귀 — 없으면 코드 리뷰로 fragment 분기 제거·code 경로 확인)
- 의존: F-5

### F-7. [FE] `login/page.tsx` — BE flow signInWithOAuth (최소 변경)
- `handleSocialLogin`: 네이티브 분기는 F-5 가 흡수 — login page 는 기존대로 `signInWithOAuth(provider, {redirectTo, skipBrowserRedirect})`→`{url}`→`Browser.open({url})`. **시그니처 유지라 변경 최소**(redirectTo 는 네이티브 분기에서 무시되나 웹 호환 위해 호출부 유지). 에러/pending/browserFinished 동일.
- ⚠️ 변경이 거의 없을 수 있음 — F-5 시그니처 호환이면 login page 무변경 가능. 그 경우 이 단위는 "무변경 확인"으로 닫음.
- verify: `pnpm -C app exec tsc --noEmit` + 동작 시나리오(네이티브: 버튼→Browser.open(BE login url) / 웹: 기존 supabase redirect)
- 의존: F-5

### ── 2b-2c AuthProvider + 콜사이트 + assess ──

### F-8. [FE] `AuthProvider.tsx` + 테스트 — neutral 유지 + logout emit 수신
- AuthProvider 는 이미 `getUser`/`subscribe` neutral 소비(Phase 1) → **표면 무변경**. 단 네이티브 logout emit(C4/C11, subscribe→`applyUser(null)`)이 user=null 로 전파되는지 확인. id-dedup·loading 양경로 유지.
- `__tests__/AuthProvider.test.tsx`: mock 타깃은 이미 `@/lib/auth`(neutral). 네이티브 logout emit→user null 케이스 추가(또는 기존 subscribe null 케이스로 커버 확인). 7케이스 시맨틱 유지.
- verify: `pnpm -C app exec tsc --noEmit` + `pnpm -C app test src/components/providers/__tests__/AuthProvider.test.tsx`
- 의존: F-5

### F-9. [FE] signOut 콜사이트 확인 — `UserInfoSection.tsx` / `DeleteAccountSection.tsx`
- 둘 다 이미 neutral `signOut()` 호출(Phase 1) → **무변경 예상**. F-5 가 네이티브 signOut 을 store clear+emit 로 바꿨으므로 콜사이트는 동일 시그니처. queryClient.clear/router.replace 후속 동일.
- verify: `pnpm -C app exec tsc --noEmit`(+ 코드 리뷰: signOut 시그니처 무변경 확인)
- 의존: F-5

### F-10. [FE] supabase-js 제거 가능성 평가 (assess only — 제거 아님)
- **결론 선기록:** 웹 분기가 expand 동안 supabase-client 를 계속 사용 → **2b-2 에서 supabase-js 제거 불가, 2c**. `supabase-client.ts` 격리경계 존속(웹 전용).
- grep 으로 supabase-js import 가 `supabase-client.ts` 1파일 유지(네이티브 swap 후에도 웹 분기가 이를 호출) 확인. 제거 시 깨질 웹 경로 목록화 → summary/decisions 에 "2c 제거 대상" 기록.
- verify: grep 결과(supabase-js 1파일·웹 분기 호출처 enumerate) + decisions 항목
- 의존: F-5, F-8, F-9

---

## QA 작업 단위 (단위별 분리 — addBlockedBy 로 즉시 unblock)

### Q-2b2-1. [QA] foundation — store/pkce/be-client (C1/C2/C5/C10)
- F-2: 토큰 store round-trip + verifier 별도 키(C2) + **secure storage 경유(localStorage 평문 부재 C5)**.
- F-3: PKCE challenge = base64url(SHA256(verifier)) 정확(C1, 알려진 벡터), verifier 형식.
- F-4: 한글 email claim base64url 디코드 round-trip(C10), exp skew 판정, token/refresh fetch shape, 503 throw(C7).
- 의존: F-2, F-3, F-4

### Q-2b2-2. [QA] lib/auth swap — refresh single-flight·무한루프·웹 무회귀 (C3/C4/C8/C9)
- F-5: **C3 동시 getAccessToken N회→`/auth/refresh` fetch 1회(single-flight).** C4 refresh 실패→clear+null+logout emit·재시도 안 함. C9 getUser refresh-aware(만료→refresh→디코드, 실패→null). **C8 웹 분기 기존 supabase 호출 보존**(코드 리뷰 + 웹 mock 테스트).
- 의존: F-5

### Q-2b2-3. [QA] 딥링크·로그인·signOut — code 단일·토큰 미처리·revoke 없음 (C6/C7/C11)
- F-6: **C6 네이티브 딥링크 implicit fragment 분기 제거(access_token 파싱 부재), code→/auth/token 단일.** C7 503/실패→FAILED 라우팅 크래시 없음. cold-start verifier 읽음(C2).
- F-7: login 네이티브=Browser.open(BE login url, challenge 포함 C1)·웹=기존. F-9: signOut 네이티브=store clear+emit, 서버 미호출(C11).
- 의존: F-6, F-7, F-9

### Q-2b2-4. [QA] AuthProvider + 전체 무회귀 게이트
- F-8: logout emit→user null 전파, AuthProvider.test green. F-10: supabase-js assess 결론(1파일·2c) 확인.
- `pnpm -C app exec tsc --noEmit` + `pnpm -C app test` **전체 무회귀**.
- grep 불변식: **localStorage 토큰 평문 부재(C5)**, 네이티브 딥링크 access_token fragment 파싱 부재(C6), supabase-js import = supabase-client.ts 1파일(F-10).
- spec → spec-history 이동 준비.
- 의존: Q-2b2-1, Q-2b2-2, Q-2b2-3, D-2b2

---

## 정합성 / 문서

### D-2b2. [DOC] `docs/decisions.md` — Phase 2b-2 결정 기록
- **B12 enforce-always 정정**(이전 "예약" 텍스트 stale → PKCE 강제, 앱이 verifier 생성·challenge 전달).
- **웹/네이티브 분기**(D-A): 네이티브만 BE flow, 웹 expand 동안 Supabase, supabase-js 제거=2c. 트레이드오프: lib/auth 이중화 복잡도↑ vs 점진 expand 안전.
- secure storage 플러그인 선정(D-B, Keychain/Keystore·Capacitor8 호환) + OTA 불가·스토어 빌드 필수.
- getAccessToken proactive refresh + **single-flight**(C3) + 실패 logout(C4), api-client 콜사이트 무변경(D-C).
- getUser JWT 로컬 디코드(검증 미도입, BE 검증, D-D), subscribe 자체 emitter.
- PKCE verifier 영속(cold-start 생존, D-E). 딥링크 implicit fragment 분기 제거(C6).
- verify: 파일 내용 확인
- 의존: F-1(플러그인 확정), F-5

---

## 의존 그래프 (2b-2 요약)

```
F-1(plugin) → F-2(store) ─┐
F-3(pkce) ────────────────┤
F-4(be-client) ───────────┴→ F-5(lib/auth swap) ─┬→ F-6(딥링크) ─┐
                                                  ├→ F-7(login)  │
                                                  ├→ F-8(AuthProvider) ┤
                                                  ├→ F-9(signOut 콜사이트)┤
                                                  └→ F-10(assess) ─────┤
QA: Q1←F2,F3,F4  Q2←F5  Q3←F6,F7,F9  D-2b2←F1,F5  Q4←Q1,Q2,Q3,D-2b2
```
- FE only. BE 변경 없음(2b-1 계약 소비). 웹 분기 무회귀가 hard gate(C8).
- 1요청=1파일 — F-2~F-10 은 파일 단위 분리.

## 완료 조건 (2b-2)

- [ ] B12 enforce-always 정정 반영(spec/decisions, C1)
- [ ] F-1 secure storage 플러그인(Capacitor8 호환·Keychain/Keystore) 추가 + OTA 불가 명시
- [ ] F-2 토큰 store(secure, verifier 영속 C2/C5) + F-3 PKCE S256(C1) + F-4 BE fetch/디코드(C10)
- [ ] F-5 lib/auth 7함수 네이티브 BE flow 분기 — **single-flight refresh(C3)·실패 logout(C4)·웹 무회귀(C8)**
- [ ] F-6 딥링크 code→/auth/token 단일(implicit fragment 제거 C6)·503 우아(C7)·cold-start verifier(C2)
- [ ] F-7 login BE flow / F-8 AuthProvider logout emit / F-9 signOut store clear(C11)
- [ ] F-10 supabase-js 제거 = **2c assess 결론**(2b-2 제거 아님)
- [ ] `pnpm -C app exec tsc --noEmit` + `pnpm -C app test` 전체 무회귀
- [ ] grep 불변식: localStorage 토큰 평문 부재(C5) / 네이티브 access_token fragment 파싱 부재(C6) / supabase-js 1파일(F-10)
- [ ] `docs/decisions.md` 갱신(D-2b2)
- [ ] spec → `spec-history/2026-06-19-auth-decoupling-phase2b2.md` 이동 준비

---

## 외부 작업 (코드 아님 — 운영자/빌드 절차)

| 작업 | 시점 | 비고 |
|------|------|------|
| 2b 전체 활성화 = BE env 주입(provider secret·Apple .p8·ES256 키·`be_token_audience`·`redirect_base`) + IdP 콘솔 redirect_uri(BE callback) + 마이그레이션(0004+0005+0006) 적용 | FE 출시 전 | 2b-1 confirm 대기 항목. BE dormant 면 FE OAuth 503(C7 우아 처리). |
| secure storage 신규 플러그인 → `npx cap sync` + 네이티브 빌드 | F-1 후 | **OTA 불가·스토어 빌드 필수**(D-B). |
| FE 출시 = Capacitor 빌드/스토어 제출 | 2b-2 머지 후 | force-update 는 2c. 신 앱은 BE flow, 구 앱은 Supabase(expand). |

## PIPA 후속 (2b-1 이월)
profile PII 저장 확대 → 개인정보처리방침·Play Data Safety·App Store 라벨 갱신([[project_posthog_analytics]] 연동). spec-finish 시 backlog 등록.

---

## 후속 sub-phase 개요 (2c — 별도 스펙)

### 2c — contract (개요)
- lib/auth 웹 분기 BE flow 전환(또는 웹 자체 폐기 확정) + **supabase-js 완전 제거**(F-10 assess 결론 이행) + registry 에서 Supabase issuer 제거(BE 단독).
- **force-update 로 구 앱 sunset + 양 스토어 승인 후에만**([[project_force_update]]). 양 스토어 라이브 바이너리 확인이 gate.
