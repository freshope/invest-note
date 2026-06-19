# Changelog

이 프로젝트의 주요 변경사항을 기록합니다.
형식은 [Keep a Changelog](https://keepachangelog.com/) 를,
버전 규칙은 [SemVer](https://semver.org/) 를 따릅니다.

마케팅 버전(`X.Y.Z`)과 빌드 번호(monotonic integer)는 분리하여 관리합니다.
변경 명령은 `make bump-{patch|minor|major|build}` (자세한 워크플로는 `make help` 참고).

## [Unreleased]

### Changed

- App Store Connect 수출 규정 자동 응답 설정 (`ITSAppUsesNonExemptEncryption=false`)

## [1.3.4] - 2026-06-19

탈-Supabase Auth Phase 1 + 멀티 게시판 어드민 구조 (`app-v1.2.6_29` OTA web-only + `api-v1.3.4` + `admin-v0.1.6`). 사용자 가시 변경 없음.

### Changed

- 탈-Supabase Auth Phase 1 — 결합 국소화(동작 변경 없는 리팩토링). BE `jwt.py` 일반 OIDC verifier 어댑터화(`decode_oidc_jwt`) + `IdentityProvider`(GoTrue deleteUser) 격리, FE `lib/auth/` 3계층으로 `@supabase/supabase-js` 단일 파일 격리. `iss` 핀 검증 토글 추가(기본 비활성 = 검증 스킵, prod 활성화는 범위 밖). 하위호환 — 토큰 형식 불변

### Added

- 멀티 게시판 어드민 구조(공지/의견/오류신고/거래내역서) — `board_posts` + `board_type` + `metadata jsonb`, 어드민 전용(`require_admin`). ⚠️ **DB 마이그레이션 `0003_board_tables` 필요 — main push 전 운영 DB 선행 적용**

### Fixed

- `OIDC_AUDIENCE` 빈 값(present-but-empty)으로 인한 전체 인증 401 방지 — `decode_oidc_jwt` 가 audience/issuer 를 자체 정규화

## [1.3.3] - 2026-06-18

어드민 대시보드 누적 사용자수 차트 (`api-v1.3.3` + `admin-v0.1.5`).

### Added

- `GET /admin/user-growth` — 일별 누적 가입자 시계열(`{date, cumulative}`, KST 버킷, `require_admin` 게이트). 하위호환 — 엔드포인트 추가만
- 어드민 대시보드: 통계 카드 아래에 누적 사용자수 라인 차트 추가 (recharts 도입, 로딩/에러/빈 상태 처리)

## [1.3.2] - 2026-06-18

어드민 패널 접근 제어 강화 (`api-v1.3.2` + `admin-v0.1.4`).

### Added

- `GET /admin/me` — Supabase JWT + `ADMIN_EMAILS` allowlist(`require_admin`) 게이트의 경량 프로브. 어드민 패널 FE 라우트 가드가 셸 진입 전 admin 여부를 판정하는 용도(DB 미접근, 하위호환 — 엔드포인트 추가만)

### Fixed

- 어드민 패널: allowlist 밖 계정이 셸에 진입(데이터 호출만 403)하던 문제 수정 — FE 가 `/admin/me` 프로브로 비-admin 을 진입 단계에서 차단("접근 권한 없음" 화면). ⚠️ FE 가 BE 보다 먼저 배포되면 admin 전원 잠김 → **BE 먼저 배포 후 FE** 순서 준수 필요

## [1.3.0] - 2026-06-17

백엔드 보안 릴리즈 (사용자 가시 변경 없음 — DB RLS 메커니즘 전환).

### Changed

- DB Row Level Security 를 Supabase 고유 객체 비의존 표준 PostgreSQL 로 전환 — RLS 정책을 `current_user_id()`(`app.current_user_id` GUC) 단일로 정리(`auth.uid()`/`auth.users` 분기·FK 제거), accounts/trades/custom_tags 에 FORCE ROW LEVEL SECURITY 를 적용해 `app_authenticated` SET ROLE 없이 owner 접속+GUC 만으로 본인 행 격리
- ⚠️ 마이그레이션 `035_force_rls.sql` 은 BE 배포 전에 prod 선적용 필요 (FORCE 미적용 상태로 새 BE 가 뜨면 owner 가 RLS 우회)

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
