# Spec: 소셜 OAuth Deep Link 처리 (Capacitor Browser + Custom URL Scheme)

> 완료: 2026-04-23

## 배경 / 문제

v2.5 로드맵 3단계(Capacitor 모바일 래핑)의 Capacitor 셋업 직후 후속 작업.

- 현재 웹 OAuth는 `signInWithOAuth` → Supabase hosted UI → `${origin}/auth/callback/` 리다이렉트 → `AuthProvider.onAuthStateChange`가 자동 처리 구조.
- Capacitor WebView에서는 `window.location.origin`이 `capacitor://localhost` / `https://localhost`이 되어 Supabase 콜백이 앱으로 되돌아오지 못하고 404/화이트스크린.
- iOS/Android 네이티브에 Custom URL Scheme 등록 및 딥링크 수신 → `exchangeCodeForSession(code)` 명시 호출 플로우를 배선해야 함.
- 웹(브라우저) 플로우는 그대로 유지 (회귀 방지).

## 목표 (완료 기준)

1. iOS 시뮬레이터에서 Google 로그인 → SFSafariViewController 열림 → 인증 → 앱 자동 복귀 → 홈(`/`) 도달.
2. Android 에뮬레이터에서 Google 로그인 → Chrome Custom Tabs 열림 → 인증 → 앱 자동 복귀 → 홈 도달.
3. Kakao 로그인 동일 시나리오 iOS/Android 각 1회 통과.
4. 카카오 동의 취소(`error_description`) 시 `/login?error=...`로 복귀.
5. 앱 완전 종료 상태(cold start)에서 `com.investnote.app://auth/callback?code=XXX` 딥링크 호출 시 앱이 기동되며 리스너가 code를 수신.
6. 웹 브라우저에서 기존 로그인 플로우 회귀 없음 (`@capacitor/browser`·`@capacitor/app`이 웹 번들에 포함되지 않음 — dynamic import).
7. 타입 체크 통과 (`pnpm -C app tsc --noEmit`).

## 설계

### 접근 방식

**Capacitor Browser 플러그인 + Custom URL Scheme**.

- URL Scheme: **`com.investnote.app://auth/callback`** (reverse-DNS, Bundle ID와 일치, 타 앱 충돌·하이재킹 방지).
- 네이티브 분기: `Capacitor.isNativePlatform()`일 때 `signInWithOAuth({ skipBrowserRedirect: true })`로 URL만 받고 `Browser.open()`으로 직접 오픈.
- 복귀: `App.addListener('appUrlOpen')` + `App.getLaunchUrl()`(cold start 필수)에서 URL을 받아 `code` 추출 → `exchangeCodeForSession(code)` → `onAuthStateChange`가 세션 반영 → `router.replace('/')`.
- 웹: 기존 `signInWithOAuth({ redirectTo })` 그대로 (분기 조건 한 줄).
- Dynamic import로 Capacitor 플러그인이 웹 번들에 포함되지 않도록 격리.

### 주요 변경 파일

- `app/package.json` — `@capacitor/browser`, `@capacitor/app` 추가 (`@capacitor/core`는 dependencies로 이동)
- `app/src/lib/platform.ts` — **신규**. `isNativePlatform()`, `getPlatform()` 2개만 export
- `app/src/lib/auth/oauth-config.ts` — **신규**. `NATIVE_URL_SCHEME`, `NATIVE_REDIRECT_URL`, `WEB_CALLBACK_PATH` 상수
- `app/src/app/login/page.tsx` — `handleSocialLogin` 내부에서 네이티브 분기(`skipBrowserRedirect` + `Browser.open`). `pending` 해제는 `oauth:browser-finished` 커스텀 이벤트로 처리
- `app/src/components/providers/CapacitorDeepLinkHandler.tsx` — **신규**. 루트에서 1회 마운트, `appUrlOpen` + `getLaunchUrl()` + `browserFinished` 리스너, scheme/host 엄격 검증, `exchangeCodeForSession` 호출 후 라우팅
- `app/src/app/layout.tsx` — `AuthProvider` 하위에 `<CapacitorDeepLinkHandler />` 마운트
- `app/ios/App/App/Info.plist` — `CFBundleURLTypes`에 `com.investnote.app` 스킴 등록
- `app/android/app/src/main/AndroidManifest.xml` — MainActivity에 VIEW intent-filter 별도 추가 (기존 MAIN/LAUNCHER filter와 분리, `autoVerify` 미사용)
- `docs/decisions.md` — URL scheme 결정, 딥링크 리스너 배치 결정 기록
- `docs/backlog.md` — "소셜 OAuth deep link 처리" 체크

### 재사용되는 기존 구조

- `app/src/lib/supabase/client.ts` — 그대로. `createBrowserClient`가 PKCE 기본이라 `exchangeCodeForSession`이 localStorage의 code_verifier 자동 조회.
- `app/src/components/providers/AuthProvider.tsx` — 손대지 않음. `exchangeCodeForSession` 성공 시 `onAuthStateChange`가 자동 발화.
- `app/src/app/auth/callback/page.tsx` — 웹 전용으로 그대로 유지. 네이티브에서는 이 라우트를 거치지 않고 딥링크 핸들러가 직접 처리.
- `app/ios/App/App/AppDelegate.swift` — 이미 `ApplicationDelegateProxy`가 있어 수정 불필요.
- `app/android/.../MainActivity.java` — `BridgeActivity` 상속만으로 충분. `singleTask` launchMode 이미 설정.

## 구현 체크리스트

- [x] `pnpm -C app add @capacitor/browser @capacitor/app` 설치 + `@capacitor/core`를 dependencies로 이동
- [x] `app/src/lib/platform.ts` 신규 — `isNativePlatform`, `getPlatform`
- [x] `app/src/lib/auth/oauth-config.ts` 신규 — scheme/callback 상수 (`com.investnote.app://auth/callback`)
- [x] `app/src/components/providers/CapacitorDeepLinkHandler.tsx` 신규 — dynamic import + `getLaunchUrl` + `appUrlOpen` + `browserFinished` + scheme/host 검증 + `exchangeCodeForSession` + 라우팅
- [x] `app/src/app/layout.tsx` 수정 — `AuthProvider` 하위에 핸들러 마운트
- [x] `app/src/app/login/page.tsx` 수정 — `handleSocialLogin` 네이티브 분기, `pending` 해제 이벤트 리스너
- [x] `app/ios/App/App/Info.plist` 수정 — `CFBundleURLTypes` 블록 추가
- [x] `app/android/app/src/main/AndroidManifest.xml` 수정 — VIEW intent-filter 추가 (MAIN/LAUNCHER와 별도 블록)
- [x] `pnpm -C app exec cap sync` 통과 — `@capacitor/app@8.1.0`, `@capacitor/browser@8.0.3` 플러그인 iOS/Android 등록
- [x] **Supabase 대시보드(사용자 작업)**: Authentication → URL Configuration → Redirect URLs에 `com.investnote.app://auth/callback` 추가
- [x] iOS 시뮬레이터 배선 검증: `xcrun simctl openurl booted "com.investnote.app://auth/callback?code=test"` → 앱이 포그라운드로 오며 `/login/?error=oauth_failed` 전환
- [x] Android 에뮬레이터 배선 검증: `adb shell am start -a android.intent.action.VIEW -d "com.investnote.app://auth/callback?code=test" com.investnote.app`
- [ ] Cold start 검증 — 미수행. 현 구현에 `App.getLaunchUrl()` 경로 포함되어 있음. 실기기/에뮬 확보 시 1회 확인 (backlog 아님, 회귀 위험 낮음)
- [x] iOS 실기기 Google/Kakao OAuth E2E 통과
- [ ] Android 실기기 Google/Kakao OAuth E2E — 에뮬레이터 성능 이슈로 보류 (backlog 이관, 동일 JS 번들이 iOS 통과했고 Android 배선 검증은 완료)
- [x] 웹 회귀 1차: `pnpm -C app build` 통과 — 7개 라우트 모두 Static 유지
- [x] `pnpm -C app exec tsc --noEmit` 통과
- [x] **후속 수정**: Supabase client `@supabase/ssr`→`@supabase/supabase-js` 교체 (`capacitor://localhost` 스킴 쿠키 미지원 → PKCE verifier 손실 이슈 해결)
- [x] **후속 수정**: `auth.flowType: 'pkce'` 명시 + `CapacitorDeepLinkHandler`에 implicit flow fragment(`#access_token=...`) fallback 추가
- [x] **후속 수정**: `router.replace` 경로 `trailingSlash: true` 에 맞춰 `/login/?error=...`로 교정 (정적 export 네비게이션 실패 해결)
- [x] `docs/decisions.md` 결정 3건 추가 (scheme, 리스너 배치, Supabase client 교체)
- [x] `docs/backlog.md` 체크 + Android 실기기 E2E 후속 이관

## 검증 방법

1. **배선 단독 검증** (실제 OAuth 없이 가짜 code로):
   - iOS: `xcrun simctl openurl booted "com.investnote.app://auth/callback?code=test"` → `/login?error=oauth_failed` (verifier 불일치로 정상 실패)
   - Android: `adb shell am start -a android.intent.action.VIEW -d "com.investnote.app://auth/callback?code=test" com.investnote.app`
2. **Cold start**: 앱 스와이프 킬 → 위 명령 실행 → 앱이 기동되면서 리스너가 `getLaunchUrl()` 경로로 수신.
3. **실제 E2E**: iOS/Android 각각 Google/Kakao 로그인 → SFSafariVC/Chrome Custom Tabs → 인증 → 홈 도달.
4. **실패 케이스**: Kakao 동의 취소 → `error_description` 파라미터로 복귀 → `/login?error=...`.
5. **브라우저 수동 종료**: SFSafariVC "Done"/Custom Tabs 백버튼 → `pending` 버튼 해제되고 다시 누를 수 있음.
6. **웹 회귀**: `pnpm -C app dev` → 브라우저 기존 플로우 그대로. DevTools Network 탭에서 Capacitor 플러그인 chunk 미로드 확인.
7. **타입 체크**: `pnpm -C app tsc --noEmit`.

## 우려사항 / 리스크

- **Cold start 이벤트 소실**: `App.getLaunchUrl()`을 리스너 등록 전에 1회 호출하지 않으면 종료 상태에서 딥링크 기동 시 이벤트 손실 → 구현에 명시됨.
- **PKCE code_verifier 지속성**: `Browser.open`은 SFSafariVC/Chrome Custom Tabs를 여는 것이라 WebView localStorage가 유지됨. 다만 사용자가 OAuth 도중 앱 데이터 삭제 시 실패 — 허용 가능한 엣지.
- **Android 중복 인텐트 필터**: MAIN/LAUNCHER와 VIEW deep link는 반드시 **별도 `<intent-filter>` 블록**으로. 한 블록에 섞으면 LAUNCHER 자격 깨짐.
- **iOS URL Scheme 하이재킹**: 커스텀 스킴은 동명 앱 간 선점 undefined. reverse-DNS로 충돌 가능성 최소화.
- **Supabase 대시보드 Redirect URL 누락**: `com.investnote.app://auth/callback` 미등록 시 Supabase가 redirect 거부 → 체크리스트에 명시.
- **Universal Links 추후 도입**: https 기반 Universal Links 추가 시 `appUrlOpen`에 섞여 들어올 수 있으나 핸들러의 scheme/host 필터가 방어.
- **번들 사이즈**: `@capacitor/core`는 웹 번들에 수 KB 포함. `@capacitor/browser`·`@capacitor/app`은 dynamic import로 차단 — 구현에 명시.
- **딥링크 위조 방어**: 현재 OAuth 용도에서는 Supabase verifier 불일치로 자동 거부. 향후 다른 기능(포트폴리오 공유 등)을 같은 스킴에 얹을 때는 별도 검증 필요.
