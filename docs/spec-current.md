# Spec: 번들ID를 `app.pixelwave.investnote`로 변경

> 완료: 2026-05-14

## 배경 / 문제

현재 앱 번들ID는 `com.investnote.app` (역도메인이 미보유 도메인 기반). 운영/스토어 등록을 위해 보유 도메인 기반의 `app.pixelwave.investnote`로 통일한다. Capacitor 설정, iOS Xcode 프로젝트, Android Gradle/Manifest/Java 패키지, OAuth 딥링크 스킴까지 모두 갱신해야 한다.

## 목표

- 모든 native 빌드 설정과 앱 내 상수가 `app.pixelwave.investnote`를 사용한다.
- `pnpm -C fe build && (cd fe && npx cap sync)` 가 에러 없이 통과한다.
- OAuth 딥링크 스킴이 `app.pixelwave.investnote://auth/callback` 으로 통일된다 (Android Manifest, iOS Info.plist, `oauth-config.ts` 일치).
- Android 시뮬레이터/iOS 시뮬레이터 빌드가 성공한다(가능한 환경에서).

## 설계

### 접근 방식

- 단순 문자열 치환 + Android Java 패키지 디렉토리 이동.
- Capacitor sync 결과물(`fe/ios/App/App/capacitor.config.json`, `fe/android/app/src/main/assets/capacitor.config.json`)은 직접 수정하지 않고 마지막에 `npx cap sync` 로 갱신한다.
- 빌드 결과물 캐시(`fe/ios/App/App/public/`, `fe/android/app/src/main/assets/public/`)는 다음 빌드 시 재생성되므로 그대로 둔다.

### 주요 변경 파일

**Capacitor 설정**
- `fe/capacitor.config.ts` (L4) — `appId: "com.investnote.app"` → `"app.pixelwave.investnote"`

**iOS**
- `fe/ios/App/App.xcodeproj/project.pbxproj` (L309, L331) — `PRODUCT_BUNDLE_IDENTIFIER = com.investnote.app;` (Debug/Release 2곳) → `app.pixelwave.investnote`
- `fe/ios/App/App/Info.plist` (L51) — `CFBundleURLName`: `com.investnote.app.oauth` → `app.pixelwave.investnote.oauth`
- `fe/ios/App/App/Info.plist` (L56) — `CFBundleURLSchemes` 항목: `com.investnote.app` → `app.pixelwave.investnote`

**Android**
- `fe/android/app/build.gradle` (L11) — `namespace = "com.investnote.app"` → `"app.pixelwave.investnote"`
- `fe/android/app/build.gradle` (L14) — `applicationId "com.investnote.app"` → `"app.pixelwave.investnote"`
- `fe/android/app/src/main/AndroidManifest.xml` (L27) — `<data android:scheme="com.investnote.app" ...>` → `app.pixelwave.investnote`
- `fe/android/app/src/main/res/values/strings.xml` (L5, L6) — `package_name`, `custom_url_scheme` 값 변경
- `fe/android/app/src/main/java/com/investnote/app/MainActivity.java`
  - 파일 이동: `fe/android/app/src/main/java/app/pixelwave/investnote/MainActivity.java`
  - 1행 `package com.investnote.app;` → `package app.pixelwave.investnote;`
  - 기존 빈 디렉토리 `fe/android/app/src/main/java/com/investnote/app/`, `com/investnote/`, `com/` 정리

**앱 소스**
- `fe/src/lib/auth/oauth-config.ts` (L1) — `NATIVE_URL_SCHEME = "com.investnote.app"` → `"app.pixelwave.investnote"`

**문서**
- `docs/decisions.md` — 번들ID 변경 결정 1줄 추가 (이유: pixelwave.app 도메인 기반 통일)
- `docs/spec-history/2026-04-23-*.md` 등 과거 문서는 히스토리이므로 수정하지 않음

**Capacitor sync로 자동 갱신 (직접 수정 X)**
- `fe/ios/App/App/capacitor.config.json`
- `fe/android/app/src/main/assets/capacitor.config.json`

## 구현 체크리스트

- [x] `fe/capacitor.config.ts` appId 변경
- [x] `fe/src/lib/auth/oauth-config.ts` `NATIVE_URL_SCHEME` 변경
- [x] iOS: `project.pbxproj` 2곳, `Info.plist` 2곳 변경
- [x] Android: `build.gradle` namespace/applicationId 변경
- [x] Android: `AndroidManifest.xml` scheme 변경
- [x] Android: `strings.xml` package_name / custom_url_scheme 변경
- [x] Android: `MainActivity.java` 디렉토리 이동 + package 선언 변경, 빈 디렉토리 정리
- [x] `pnpm -C fe exec tsc --noEmit` 통과
- [x] `pnpm -C fe build` 통과
- [x] `(cd fe && npx cap sync)` 실행 → sync된 두 json 파일에 신규 appId 반영 확인
- [x] 잔존 검색: 결과가 sync 자동 갱신 항목과 히스토리 문서(`docs/spec-history/`, `docs/decisions.md` 과거 항목)에만 남음을 확인
- [x] `docs/decisions.md` 변경 결정 1줄 추가

## 우려사항 / 리스크

- **OAuth 외부 서비스**: Supabase 대시보드 Authentication → URL Configuration → Redirect URLs에 `app.pixelwave.investnote://auth/callback` 추가 필요 (사용자 수동 작업). 기존 `com.investnote.app://auth/callback`은 점진 제거 가능.
- **스토어 등록 상태**: 현재 App Store / Play Console 미등록 가정. 등록된 상태라면 번들ID 변경 = 신규 앱 등록이 되므로 사용자 확인 필요.
- **Android 패키지 디렉토리 이동**: Java 패키지 선언과 실제 디렉토리 경로가 일치해야 빌드 성공. 기존 `com/investnote/app/` 경로는 완전히 비워야 한다.
- **빌드 캐시**: iOS DerivedData / Android `.gradle` 캐시에 옛 번들ID가 남아 있으면 클린 빌드 필요할 수 있음.

## 검증 (Verification)

1. `pnpm -C fe exec tsc --noEmit` — 타입 체크.
2. `pnpm -C fe build` — Next.js 정적 빌드 성공.
3. `(cd fe && npx cap sync)` — Capacitor가 native로 설정 동기화 성공. 두 sync된 json 파일에 신규 appId 반영 확인.
4. 잔존 grep 검색 (위 체크리스트 참고).
5. (선택) iOS 시뮬레이터 빌드 / Android 에뮬레이터 빌드. OAuth 딥링크 검증은 Supabase Redirect URL 등록 후 별도 수행.
