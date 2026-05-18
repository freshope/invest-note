# Changelog

이 프로젝트의 주요 변경사항을 기록합니다.
형식은 [Keep a Changelog](https://keepachangelog.com/) 를,
버전 규칙은 [SemVer](https://semver.org/) 를 따릅니다.

마케팅 버전(`X.Y.Z`)과 빌드 번호(monotonic integer)는 분리하여 관리합니다.
변경 명령은 `make bump-{patch|minor|major|build}` (자세한 워크플로는 `make help` 참고).

## [Unreleased]

### Changed

- App Store Connect 수출 규정 자동 응답 설정 (`ITSAppUsesNonExemptEncryption=false`)

## [1.1.7] - 2026-05-15

### Fixed

- 모바일 빌드에 남아있던 옛 Render API URL 제거 (hotfix)
