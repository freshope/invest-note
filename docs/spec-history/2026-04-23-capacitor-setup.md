# Spec: Capacitor 프로젝트 셋업 + iOS/Android 플랫폼 추가

> 완료: 2026-04-23

## 배경 / 문제

v2.5 로드맵의 **3단계 — Capacitor 모바일 래핑**의 첫 스텝.

- 2단계(FastAPI 백엔드 분리)와 Chunk D(Next.js 정적 export 전환) 완료로 `app/out/` 정적 번들이 준비됨 (`next.config.ts: output: 'export'`).
- Capacitor가 이 정적 번들을 WebView에 직접 로드할 수 있도록 프로젝트를 초기화하고 iOS/Android 네이티브 프로젝트를 생성한다.
- OAuth deep link 처리, Apple Sign-in, 푸시 알림, 생체인증, 아이콘/스플래시 리소스, 스토어 메타데이터 등은 **본 spec 범위 외** — 후속 spec에서 개별 진행.

## 결정 사항

| 항목 | 값 |
|------|-----|
| appId | `com.investnote.app` |
| appName | `투자노트` |
| 네이티브 디렉토리 커밋 | 포함 (Capacitor 공식 권장) |
| 브랜치 | `feature/capacitor-setup` (from `develop`) |
| Capacitor 버전 | 8.3.1 (최신 stable) |
| 설치 위치 | `app/` 워크스페이스 내부 (webDir가 `app/out`을 가리키므로) |
| webDir | `out` |

## 목표 (완료 기준)

1. `pnpm -C app exec cap sync` 가 에러 없이 완료된다.
2. `app/ios/App/App.xcodeproj` 가 존재한다 (Capacitor 8은 SPM 전환으로 `.xcworkspace` 대신 `.xcodeproj`만 생성 — Xcode에서 직접 열기 가능).
3. `app/android/gradlew` 및 Gradle wrapper 파일이 존재한다 (Android Studio에서 폴더 열기 가능).
4. `app/capacitor.config.ts` 에 `appId`, `appName`, `webDir: "out"` 가 설정되어 있다.
5. 네이티브 프로젝트가 git에 커밋되어 있고 빌드 산출물(Pods/, build/, .gradle/ 등)은 `.gitignore` 처리되어 있다.

> 실제 Xcode / Android Studio 열기·Gradle sync 성공 여부는 본 spec 범위 외(파일 존재 확인까지). IDE 빌드 검증은 후속 spec에서 OAuth deep link 테스트와 함께 수행.

## 설계

### 접근 방식

- **설치 위치**: Capacitor는 `app/` 워크스페이스 내부에 설치한다. `webDir`가 `app/out`(Next.js export 결과) 기준 상대 경로 `out` 이어야 하고, `cap` CLI는 `capacitor.config.ts` 기준으로 동작하기 때문.
- **플랫폼 추가 순서**: 정적 번들(`pnpm build`) → `cap add ios` → `cap add android` → `cap sync`. 초기 sync 시 webDir가 비어 있으면 경고가 나므로 `next build`를 먼저 수행.
- **git 처리**: 네이티브 프로젝트는 커밋하되, 빌드 산출물·로컬 캐시·IDE 메타데이터는 ignore.
  - Capacitor가 `app/ios/.gitignore` 와 `app/android/.gitignore` 를 자동 생성하여 빌드 산출물을 이미 커버 — `app/.gitignore` 에 중복 추가하지 않음.
  - iOS ignore 커버: `App/build`, `App/Pods`, `DerivedData`, `xcuserdata`, `App/App/public`, `capacitor-cordova-ios-plugins`, 생성된 config json
  - Android ignore 커버: `.gradle/`, `build/`, `local.properties`, `.idea/` 캐시, `app/src/main/assets/public`, 생성된 config json
- **package.json 스크립트**: `app/package.json` 에 `"cap": "cap"` 추가. 루트 `package.json` 에는 위임 스크립트 추가 없음 (직접 `pnpm -C app exec cap ...`).

### 주요 변경 파일

- `app/package.json` — devDeps 4개 추가(`@capacitor/core`, `@capacitor/cli`, `@capacitor/ios`, `@capacitor/android`), `cap` 스크립트
- `app/capacitor.config.ts` — **신규**. `appId: "com.investnote.app"`, `appName: "투자노트"`, `webDir: "out"`
- `app/ios/.gitignore`, `app/android/.gitignore` — Capacitor 자동 생성 (빌드 산출물 ignore 내장)
- `app/ios/` — **신규** Xcode 프로젝트 (`cap add ios` 생성)
- `app/android/` — **신규** Android Studio 프로젝트 (`cap add android` 생성)
- `docs/decisions.md` — Capacitor 설치 위치/appId 결정 1건 추가
- `docs/backlog.md` — "Capacitor 프로젝트 셋업 + iOS/Android 플랫폼 추가" 체크 처리

### 재사용되는 기존 설정

- `app/next.config.ts`: `output: 'export'`, `trailingSlash: true`, `images.unoptimized: true` — 이미 Capacitor 호환 설정. 추가 변경 없음.
- `app/out/`: Next.js export 산출물 디렉토리 — Capacitor `webDir`가 가리키는 대상.

## 구현 체크리스트

- [x] Capacitor 의존성 설치 (Capacitor 8.3.1 — core/cli/ios/android)
- [x] `app/capacitor.config.ts` 생성 (appId/appName/webDir)
- [x] `app/package.json` 에 `"cap": "cap"` 스크립트 추가
- [x] `pnpm build` — `app/out/` 정적 export 생성 (7개 라우트 Static)
- [x] `pnpm -C app exec cap add ios` → `app/ios/` 생성 (CocoaPods 1.16.2 Homebrew 설치 포함)
- [x] `pnpm -C app exec cap add android` → `app/android/` 생성
- [x] `pnpm -C app exec cap sync` → 에러 없이 완료 (`Sync finished in 0.5s`)
- [x] gitignore 검증 — Capacitor 자동 생성 `app/ios/.gitignore` / `app/android/.gitignore` 가 빌드 산출물 커버 (Pods/build/DerivedData/.gradle/assets/public 등)
- [x] `docs/decisions.md` 에 Capacitor 셋업 결정 + CocoaPods 설치 기록 2건 추가
- [x] `docs/backlog.md` 의 "Capacitor 프로젝트 셋업 + iOS/Android 플랫폼 추가" 체크
- [x] 타입 체크 통과 (`pnpm tsc --noEmit`)

## 검증 방법

1. **CLI 동작**: `pnpm -C app exec cap --version` → `8.3.1`.
2. **sync 성공**: `pnpm -C app exec cap sync` 가 `✔ Copying web assets from out to ios/App/App/public` / `android/app/src/main/assets/public` 류 메시지 출력 후 `Sync finished in 0.5s` 완료.
3. **iOS 프로젝트 파일 존재**: `test -d app/ios/App/App.xcodeproj` — Capacitor 8 SPM 기본 템플릿은 `.xcworkspace` 없음, `.xcodeproj` 직접 사용.
4. **Android 프로젝트 파일 존재**: `test -x app/android/gradlew` — Gradle wrapper가 실행권한 포함하여 존재.
5. **타입 체크**: `pnpm tsc --noEmit` 성공 — `capacitor.config.ts` 타입 에러 없음.

실제 시뮬레이터/디바이스 빌드·실행, Xcode/Android Studio 열기·Gradle sync 성공 검증은 **본 spec 범위 외** — 후속 spec에서 OAuth deep link 처리와 함께 수행.

## 우려사항 / 리스크

- **CocoaPods 설치 필요**: `cap add ios` 가 내부적으로 `pod install`을 호출. 개발 머신에 CocoaPods 미설치 시 실패 → `brew install cocoapods`로 선설치. macOS 한정.
- **Android Studio / JDK 17**: 본 spec은 프로젝트 생성까지만. 실제 빌드·실행은 후속 작업이므로 JDK/SDK 버전 이슈는 이번 scope 밖이지만, 후속 spec 착수 전 로컬 환경 확인 필요.
- **appId 고정성**: `com.investnote.app` 확정 후 변경 시 App Store/Play Console 재등록 필요. 스토어 등록 전까지는 변경 가능.
- **Capacitor 8 플러그인 호환성**: 향후 도입할 플러그인(`@capacitor/browser`, `@capacitor-community/apple-sign-in` 등)이 Capacitor 8과 호환 확인 필요 — 후속 spec에서 플러그인별 재검토.
- **API CORS**: 런타임 시 Capacitor WebView origin 은 iOS `capacitor://localhost`, Android `https://localhost`. FastAPI(`api/`)의 CORS 허용 설정 필요 — 후속 spec에서 처리 (본 spec은 build + sync까지, 실행 테스트 포함 안 함).
- **정적 export `trailingSlash: true`**: Capacitor WebView 라우팅 시 말미 슬래시 처리가 원인이 되는 404 가능성 — 실제 WebView 실행 시 확인. 이번 scope에서는 서류상 호환으로 간주.
