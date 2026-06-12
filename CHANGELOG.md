# Changelog

이 프로젝트의 주요 변경사항을 기록합니다.
형식은 [Keep a Changelog](https://keepachangelog.com/) 를,
버전 규칙은 [SemVer](https://semver.org/) 를 따릅니다.

마케팅 버전(`X.Y.Z`)과 빌드 번호(monotonic integer)는 분리하여 관리합니다.
변경 명령은 `make bump-{patch|minor|major|build}` (자세한 워크플로는 `make help` 참고).

## [Unreleased]

### Changed

- App Store Connect 수출 규정 자동 응답 설정 (`ITSAppUsesNonExemptEncryption=false`)

## [1.2.1] - 2026-06-12

백엔드 패치 릴리즈 (사용자 가시 변경 없음 — 테스트·내부 도구 정리).

### Changed

- OTA 발행 스크립트(`scripts/publish-ota.mjs`) `required_native` 기본값을 레포 마케팅 버전 → `.env OTA_REQUIRED_NATIVE` 단일 출처로 전환 (스토어 라이브 바이너리 버전 추적, 미설정 시 중단)

### Fixed

- BE 테스트 lint 오류 정리 (미사용 변수·import 제거)

## [1.1.21] - 2026-06-08

백엔드 인프라 릴리즈 (사용자 가시 변경 없음 — 모바일 스토어 제출 생략).

### Added

- KIS Open API 연동 인프라 — 공통 클라이언트, 시세/일별 종가/종목마스터 provider 등록 (env 토글 뒤 대기, prod 미활성)
- KIS 토큰 DB 영속화 (`kis_tokens` 테이블 + advisory lock 발급 직렬화)
- 외부 데이터 공급자 env 토글 구조

### Changed

- Makefile 을 devtools 멀티 프로젝트 구성(PROJECTS)으로 전환
- CI 를 BE/FE 경로 필터 워크플로로 분리

## [1.1.7] - 2026-05-15

### Fixed

- 모바일 빌드에 남아있던 옛 Render API URL 제거 (hotfix)
