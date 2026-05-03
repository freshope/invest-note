# Spec: 단일 버전 관리

## 배경

앱/웹/API 버전이 `app/package.json`, `api/pyproject.toml`, Android Gradle, iOS Xcode 설정에 흩어져 있어 릴리스 때 값이 어긋날 수 있다.

## 목표

- 루트 `version.json`을 제품 버전의 단일 소스로 둔다.
- 웹/앱/API/native 설정 파일을 한 명령으로 동기화한다.
- CI나 릴리스 전 검증에서 버전 불일치를 감지할 수 있는 check 명령을 제공한다.

## 설계

- `version`: 사용자에게 보이는 SemVer 문자열.
- `build`: iOS/Android 스토어 제출용 증가 정수.
- Android `versionName`/iOS `MARKETING_VERSION`은 `version`을 따른다.
- Android `versionCode`/iOS `CURRENT_PROJECT_VERSION`은 `build`를 따른다.

## 구현 항목

- [x] `version.json` 추가
- [x] 버전 동기화/검증/증가 스크립트 추가
- [x] 루트 `package.json` 명령 추가
- [x] 현재 흩어진 버전 값을 단일 소스에 맞춰 동기화
- [x] 검증 명령 실행

## 검증

- `pnpm version:check` 통과
- `node --check scripts/version.mjs` 통과
