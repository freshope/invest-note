# Spec: Apple ID 로그인 추가

> 완료: 2026-05-19

## 배경 / 문제

현재 로그인 화면은 Google과 Kakao만 지원한다 (`fe/src/app/login/page.tsx`). iOS 앱이 Google/Kakao를 제공하는 상태에서 App Store Review Guideline 4.8(다른 third-party 로그인 제공 시 Apple Sign In 동등 제공 의무)을 충족하려면 Apple ID 로그인을 추가해야 한다.

Supabase 측은 이미 Apple OAuth provider를 지원하고 `supabase/config.toml`에 `[auth.external.apple]` 섹션이 비활성 상태로 준비되어 있다. 기존 Google/Kakao가 Supabase OAuth + PKCE + InAppBrowser(`@capacitor/browser`) deep-link 패턴으로 일관되게 구현되어 있어 동일 패턴을 그대로 따른다.

## 목표

- 웹/iOS/Android 모두에서 로그인 화면에 "Apple로 계속하기" 버튼이 노출된다.
- Apple 버튼 클릭 시 Supabase OAuth web flow가 시작되고, 콜백 후 세션이 정상 생성된다 (기존 Google/Kakao와 동일 흐름).
- Supabase 로컬 설정(`supabase/config.toml`)에서 Apple provider가 활성화되고, 자격증명은 env 변수로 주입된다.
- 타입 체크 통과 (`pnpm -C fe exec tsc --noEmit`).

> 사전 요건(사양 범위 외, 사용자가 별도 진행):
> - Apple Developer 계정에서 App ID(Sign in with Apple capability) + Services ID 생성
> - Sign in with Apple Key(.p8) 발급
> - Supabase Apple OAuth secret JWT 생성 후 `SUPABASE_AUTH_EXTERNAL_APPLE_CLIENT_ID` / `SUPABASE_AUTH_EXTERNAL_APPLE_SECRET` 주입

## 설계

### 접근 방식

기존 `handleSocialLogin(provider)` 함수의 union 타입을 `"google" | "kakao" | "apple"`로 확장하고, 동일한 `supabase.auth.signInWithOAuth({ provider, options: { redirectTo, skipBrowserRedirect: native } })` 호출 경로를 재사용한다. 별도 콜백 핸들러는 필요 없다 — `CapacitorDeepLinkHandler.tsx`와 `/auth/callback/page.tsx`가 provider에 의존하지 않는 PKCE/implicit 분기 처리만 하기 때문이다.

Supabase 측은 `config.toml`의 `[auth.external.apple]` 블록을 `enabled = true`로 바꾸고 env 변수만 연결한다. Apple은 nonce 검증이 필요하지만 `signInWithOAuth`가 내부에서 처리한다 (`skip_nonce_check`는 기본값 false 유지).

UI는 Apple HIG 권장 디자인을 따른다: 검정 배경, 흰 사과 로고, 흰 텍스트. 한국어 라벨은 "Apple로 계속하기" / 진행 중 "처리 중...".

### 주요 변경 파일

- `fe/src/app/login/page.tsx` — `pending` state union에 `"apple"` 추가, `handleSocialLogin` 인자 타입 확장, `AppleIcon` 컴포넌트 추가, Apple 버튼 렌더링.
- `supabase/config.toml` — `[auth.external.apple]` 섹션을 `enabled = true`, `client_id = "env(SUPABASE_AUTH_EXTERNAL_APPLE_CLIENT_ID)"`, `redirect_uri = "http://127.0.0.1:64321/auth/v1/callback"`로 수정. secret 라인은 이미 env 참조로 되어 있음.
- `supabase/.env.example` — Apple 자격증명 env 키(`SUPABASE_AUTH_EXTERNAL_APPLE_CLIENT_ID`, `SUPABASE_AUTH_EXTERNAL_APPLE_SECRET`) 빈 값으로 추가.

> 변경 불필요(재사용): `CapacitorDeepLinkHandler.tsx`, `/auth/callback/page.tsx`, `oauth-config.ts`, `fe/ios/App/App/Info.plist`(URL scheme 이미 등록), 백엔드(JWKS 검증 기반).

## 구현 체크리스트

- [x] `supabase/config.toml`의 `[auth.external.apple]` 활성화 (`enabled`, `client_id`, `redirect_uri` 수정).
- [x] `supabase/.env.example`에 Apple env 키 2개 추가.
- [x] `fe/src/app/login/page.tsx`에 `AppleIcon` 컴포넌트 + Apple 버튼 추가 + `pending`/`handleSocialLogin` 타입 확장.
- [x] `pnpm -C fe exec tsc --noEmit` 통과.

## 우려사항 / 리스크

- Apple은 첫 로그인에만 이메일 제공한다 ("Hide My Email" 시 relay 주소). 현재 기능 범위에 영향 없음.
- Apple OAuth redirect URI가 Apple Developer 콘솔의 Services ID Return URLs와 일치해야 함 — 사용자 사전 설정에서 처리.
- App Store 심사 시 Apple 버튼 시각 규격(HIG 가이드)에 부합해야 함. 본 사양은 흔히 받아들여지는 디자인을 따르되, 심사 피드백 시 후속 수정 가능.
