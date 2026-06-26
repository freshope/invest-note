# 출시 노트 요약 — v1.3.2_31

> 작성일: 2026-06-26
> 비교 기준: app-v1.3.1_31 (2026-06-23, 직전 OTA 빌드)
> 대상 빌드: v1.3.2_31 (준비 중 — release/app-v1.3.2_31, OTA web-only)
> 모드: store-notes:skip (OTA web-only → 스토어 노트 미생성, summary 만)
> 마지막 네이티브 제출 태그: app-v1.3.0_31 (스토어 노트는 다음 네이티브 제출 시 `since app-v1.3.0_31`)

## Git 로그 (app-v1.3.1_31..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| ae9db50 | 2026-06-26 | feat(app): 활성화 퍼널 계측 이벤트 추가 |
| b98227a | 2026-06-26 | fix(app): zod 단일 버전 강제(pnpm override)로 zodResolver 타입 에러 해소 |
| ec08ffd | 2026-06-26 | feat(auth): 어드민 패널 BE 토큰-브로커 인증 전환 + /auth/logout revoke |
| 6e69450 | 2026-06-26 | feat(admin): 대시보드 사용자 추이 차트에 일별 신규 가입자 추가 |
| 8c5e293 | 2026-06-26 | fix: 가입자 그래프 차트에 빈 날짜 표시 (generate_series로 연속 시계열) |
| 8f7b77c | 2026-06-26 | feat(admin): 게시판 작성자 회원을 ID 대신 아바타+이름으로 표시 |
| 5babd10 | 2026-06-26 | fix: 설정 게시판 폼 재진입 시 입력값 잔존 수정 |
| 7dfec5d | 2026-06-25 | feat(settings): 설정 화면 리스트 메뉴 재구성 + 사용자 게시판(공지/의견/오류신고) |
| 31123a3 | 2026-06-25 | feat(import): 거래내역서 일괄등록에 신한투자증권·미래에셋증권 파서 추가 |
| 60fce50 | 2026-06-23 | feat(admin): 게시판 단일 메뉴 → board_type별 개별 메뉴 + 성격별 UI |
| 2ad7b6c | 2026-06-23 | feat(admin): 사용자 목록에 user_profiles 프로필 정보 표시 |
| 7a809a8 | 2026-06-23 | feat(admin): 대시보드에 거래내역서 제출 등록 건수 카드 추가 |

(5ced6e7 `chore: bump version` 은 릴리즈 메커닉 — 제외. docs 이동 커밋 4건 생략)

## 동기간 spec-history 항목

- `2026-06-25-broker-import-shinhan-mirae.md` — 거래내역서 일괄등록에 신한투자증권·미래에셋증권 파서 추가 (국내 전용)
- `2026-06-26-settings-restructure-board-endpoints.md` — 설정 화면 리스트 메뉴 재구성 + 사용자 게시판(공지/의견/오류신고) BE 엔드포인트
- `2026-06-26-admin-board-author-display.md` — 어드민 게시판 작성자 아바타+이름 표시
- `2026-06-26-admin-user-growth-chart.md` — 어드민 대시보드 사용자 추이 차트 일별 신규 가입자
- `2026-06-26-admin-be-auth.md` — 어드민 패널 Supabase → BE 토큰-브로커 인증 교체 (코드 머지, 실배포 게이트 이월)

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| NEW | 설정 화면 메뉴 재구성 + 사용자 게시판(공지/의견/오류신고) | ✓ (다음 네이티브 제출 시) |
| NEW | 거래내역서 일괄등록 신한투자증권·미래에셋증권 파서 추가 | ✓ (다음 네이티브 제출 시) |
| FIX | 설정 게시판 폼 재진입 시 입력값 잔존 수정 | ✓ (다음 네이티브 제출 시) |
| INTERNAL | 활성화 퍼널 계측 이벤트 추가 (PostHog analytics, 사용자 비가시) | ✗ |
| INTERNAL | 어드민 패널 BE 토큰-브로커 인증 전환 + /auth/logout revoke (admin/, dormant) | ✗ (앱 사용자 비가시) |
| INTERNAL | 어드민 대시보드 차트(일별 신규 가입자·빈 날짜)·게시판 메뉴 재구성·작성자 표시·사용자 프로필·제출 카드 | ✗ |
| INTERNAL | zod 단일 버전 강제(pnpm override) — 빌드/타입 에러 해소 | ✗ |

> 스토어 노트는 이번 빌드에서 생성하지 않음 — OTA web-only 라 스토어 제출이 없다. 위 NEW/FIX 는 **다음 네이티브 제출** 때 `since app-v1.3.0_31` 로 묶어 스토어 노트를 작성한다 (v1.3.1 의 거래내역서 제보·analytics fix 와 함께).

## 검증 결과

- app-store-ko.md: 해당 없음 (store-notes:skip)
- play-store-ko.md: 해당 없음 (store-notes:skip)
- 버전 일치: app 3곳 in sync 1.3.2 build 31 (version-check 통과) · api 1.3.8 · admin 0.1.8
- 식별자 노출: summary 내부 문서이므로 해당 없음

## 배포 체크리스트 (실행 순서대로)

1. **DB 마이그레이션: 불필요** — `app-v1.3.1_31..HEAD` 에 `api/alembic/versions/` 변경 0건. 사용자 게시판(공지/의견/오류신고)은 기존 `board_posts`+`board_type` 재사용([project_board_structure]), 어드민 BE-auth 는 `token_store`/`auth_identities` 재사용(spec 명시 — 신규 마이그레이션 불필요).
2. **BE 배포: 필요** — `api/src/` 변경(auth 라우터 `client` 분기+`/auth/logout`, board 라우터/repo, broker_import 신한·미래에셋 파서, admin_repo, schemas, config `be_admin_redirect_url` 신설). main push 시 Coolify 자동 배포. **구앱 하위호환 OK** — `/auth/login` 의 `client` 기본값 native 라 앱 딥링크 flow 무회귀(spec 제외항목), `/auth/logout`·broker 파서는 additive.
   - ⚠️ **어드민 BE-auth 실활성화는 이 배포에 포함 안 됨 — 별도 게이트**(backlog "어드민 BE-auth 배포"). `be_admin_redirect_url`+BE auth env 미주입이면 `/auth/login?client=admin` 은 dormant-503, 코드만 라이브. **단, `admin/` FE 는 BE flow 로 hard-swap(supabase-client 삭제)** 됐으므로 — 어드민 패널(admin v0.1.8)을 운영에 재배포하려면 BE auth env(`be_admin_redirect_url` 포함)가 운영에 살아있어야 로그인 가능. 어드민 재배포는 GHA→registry→Coolify 별도 경로 — main push 와 독립.
   - cutover 불변식 주의([project_auth_cutover_exec_method]): BE auth env 주입은 app cutover 백필 완료가 전제. 어드민 활성화를 위해 env 를 넣을 때 app `/auth/callback` 동시 활성화 영향을 함께 확인.
3. **MIN_SUPPORTED_VERSION: 변경 불필요** — 현재값 빈 값(OFF). app 응답 shape 무변경, 구앱 깨짐 신호 없음(auth `client` 분기·broker 파서·게시판 모두 additive).
4. **모바일 스토어 제출: 불필요** — OTA web-only(`✅ 재심사 불필요`). OTA 번들 배포로 반영, 빌드 번호 31 유지. 누적 NEW/FIX 는 다음 네이티브 제출 시 스토어 노트로 묶임.

**실행 순서**: (마이그레이션 없음) → BE 배포(main push, auth env 는 어드민 게이트 별도) → OTA 번들 배포. 어드민 패널 재배포는 BE auth env 활성화 후 별도 진행.

## 다음 빌드를 위한 메모

- **다음 네이티브 제출 시** `release-notes ... since app-v1.3.0_31` 로 돌려 누적 OTA 변경을 묶어 스토어 노트 작성: (v1.3.1) 거래내역서 제보·analytics native_version fix + (v1.3.2) 설정 메뉴 재구성·사용자 게시판·신한/미래에셋 파서·게시판 폼 fix.
- **어드민 BE-auth 배포 게이트**: 코드는 머지됐으나 실 OAuth e2e + 운영 env 주입은 backlog "어드민 BE-auth 배포" 로 이월. admin v0.1.8 을 운영 반영하기 전, BE auth env(`be_admin_redirect_url`+서명/IdP)를 Coolify 에 주입하고 app cutover 불변식과 충돌 없는지 확인 필요.
- broker 파서(신한·미래에셋)는 국내 전용. KB·해외는 Phase C 보류([project_broker_import_parsers]).
