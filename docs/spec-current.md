> 완료: 2026-04-25

# Spec: 모바일앱 세로모드 고정 (가로모드 차단)

## 배경 / 문제

invest-note 모바일앱(Capacitor 8 + Next.js 16 하이브리드)이 현재 iOS/Android 모두에서 가로모드를 허용하고 있다. 종목 입력·차트·표 등 모든 화면이 세로 기준으로 설계되어 있어 가로 회전 시 레이아웃이 어색하게 늘어진다. 가로 사용을 지원할 계획이 없으므로 네이티브 매니페스트 수준에서 세로 전용으로 고정한다.

## 목표

- iPhone에서 앱이 항상 세로(Portrait) 모드로만 표시된다.
- iPad에서 앱이 세로(Portrait) 모드로만 표시된다.
- Android에서 앱이 세로 모드로만 표시되며, 디바이스를 회전해도 가로로 전환되지 않는다.

## 설계

### 접근 방식

런타임 락(`@capacitor/screen-orientation` 등) 추가 없이 네이티브 두 파일만 수정해 OS가 회전을 시도조차 하지 않도록 한다. Capacitor에는 전역 orientation 설정 키가 없으므로 iOS `Info.plist` 와 Android `AndroidManifest.xml` 을 직접 편집하는 것이 정석.

- **iOS**: `UISupportedInterfaceOrientations` 배열을 Portrait 단일 값으로 축소 (iPhone/iPad 동일 정책).
- **Android**: `MainActivity`에 `android:screenOrientation="portrait"` 추가. 기존 `android:configChanges`는 유지(회전 자체가 차단되어 영향 없음).

### 주요 변경 파일

- `app/ios/App/App/Info.plist` — `UISupportedInterfaceOrientations` (iPhone) 및 `UISupportedInterfaceOrientations~ipad` 에서 Landscape* 제거, Portrait만 남김.
- `app/android/app/src/main/AndroidManifest.xml` — `<activity android:name=".MainActivity" ...>` 에 `android:screenOrientation="portrait"` 속성 추가.

## 구현 체크리스트

- [x] iOS `Info.plist` `UISupportedInterfaceOrientations` 에서 `UIInterfaceOrientationLandscapeLeft`/`UIInterfaceOrientationLandscapeRight` 제거 (Portrait만 남김)
- [x] iOS `Info.plist` `UISupportedInterfaceOrientations~ipad` 에서 `Landscape*` 및 `PortraitUpsideDown` 제거 (Portrait만 남김)
- [x] Android `AndroidManifest.xml` MainActivity에 `android:screenOrientation="portrait"` 속성 추가
- [x] (검증) Android 에뮬레이터/실기기에서 디바이스를 회전해도 세로가 유지되는지 확인
- [x] (검증) iOS 시뮬레이터에서 디바이스를 회전해도 세로가 유지되는지 확인

## 우려사항 / 리스크

- 추후 `@capacitor/screen-orientation` 플러그인을 도입해 런타임에 락을 풀 경우 본 spec과 정책이 어긋날 수 있음 — 도입 시 재검토.
- 현재 변경된 채로 남아 있는 `app/android/app/build.gradle`(릴리스 서명 설정) 및 `app/package.json`은 본 작업과 무관 — 동일 커밋에 섞지 않도록 주의.

## 검증 방법

```bash
# iOS
cd app && pnpm build:mobile && npx cap sync ios && npx cap open ios
# Xcode 시뮬레이터에서 ⌘← / ⌘→ 로 회전 시 세로 유지 확인

# Android
cd app && pnpm build:mobile && npx cap sync android && npx cap open android
# 에뮬레이터에서 회전 단축키(⌃⌘←/→)로 회전 시 세로 유지 확인
```
