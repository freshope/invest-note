# 출시 노트 요약 — v1.3.3_31

> 작성일: 2026-06-29
> 비교 기준: app-v1.3.2_31 (2026-06-26, 직전 릴리즈 태그)
> 대상 빌드: v1.3.3_31 (준비 중 — release/app-v1.3.3_31, bump 커밋 완료)
> 릴리즈 형태: **OTA web-only (✅ 스토어 재심사 불필요, 빌드 번호 31 유지)** + api/admin 백엔드 동반 배포
> 스토어 노트: 생략 (store-notes:skip) — 다음 네이티브 제출 시 `since app-v1.2.7_30` 으로 누적 묶어 작성

## Git 로그 (app-v1.3.2_31..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 564c90b | 2026-06-29 | chore: bump version app-v1.3.3_31 |
| 63de937 | 2026-06-28 | feat(stocks): US 한글명 백필 대상을 활성 전 종목 점진 적재로 확대 |
| e545d66 | 2026-06-28 | feat(board): 게시판 읽음/알림 상태 localStorage→DB 이전 |
| 390b900 | 2026-06-28 | feat(stocks): 해외 종목 한글 표시명(name_ko) 적재 + 거래·보유 표시 한글 우선 |
| 8573bcc | 2026-06-28 | feat(board): 내 제보/문의 인앱 알림 — 목록·상세·첨부·어드민 댓글 |
| 2d4f0b9 | 2026-06-28 | fix(import): 일괄등록 staging 메모리→DB 영속화 (preview→commit 유실 해소) |
| b5e90ba | 2026-06-28 | feat(account): 탈퇴 사유 선택 항목 우측 체크 표시 |
| 774b0e3 | 2026-06-28 | feat(account): 탈퇴 사유 선택 필수화 (FE) |
| c6fc4bb | 2026-06-28 | feat(account): 회원 탈퇴 감사 로그 + 어드민 탈퇴 통계 |
| f086484 | 2026-06-27 | feat(auth): cross-provider 동일 이메일 계정 자동연결 (BE OAuth flow) |
| 062077c | 2026-06-27 | feat(import): 토스 해외 거래 ISIN 코드 매칭 (OpenFIGI) |
| 9ba0345 | 2026-06-27 | feat(import): 토스 거래내역서 해외(USD) 거래 임포트 지원 |
| ed97553 | 2026-06-27 | feat(trades): 거래내역서 일괄등록 거래 출처 표식 + 금액 수정 잠금 |

> 위는 사용자 가시·기능 커밋만 발췌. docs/chore/코드리뷰 반영 커밋(95808de, 9e09b6a, 2e5d59b 등)은 INTERNAL 로 생략.

## 동기간 spec-history 항목

- 2026-06-27-toss-overseas-import.md — 토스 해외(USD) 거래 임포트
- 2026-06-27-toss-isin-matching.md — 토스 해외 ISIN→ticker 매칭(OpenFIGI)
- 2026-06-27-trade-origin-badge-lock.md — 거래 출처(MANUAL/IMPORT) 표식 + IMPORT 금액필드 수정 잠금
- 2026-06-28-board-notify.md — 내 제보/문의 인앱 알림(목록·상세·첨부·어드민 댓글)
- 2026-06-28-board-read-state-db.md — 게시판 읽음/알림 상태 localStorage→DB 이전
- 2026-06-28-stock-name-ko.md — 해외 종목 한글 표시명(name_ko)

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| NEW | 토스 거래내역서 해외(USD) 거래 일괄등록 지원 (ISIN→종목 매칭) | ✓ (다음 네이티브 제출 시) |
| NEW | 거래 출처 표식(직접입력/일괄등록) + 일괄등록 거래 금액 수정 잠금 | ✓ |
| NEW | 내 제보/문의 인앱 알림 — 어드민 댓글 답변·첨부 확인 | ✓ |
| IMPROVE | 해외 종목 한글 표시명(name_ko) — 거래·보유 화면 한글 우선 표기 | ✓ |
| IMPROVE | 게시판 읽음/알림 상태 DB 이전 — 기기 바꿔도 읽음 상태 유지 | ✓ |
| IMPROVE | 크로스 프로바이더 동일 이메일 계정 자동연결 (BE OAuth flow) | ✓ |
| IMPROVE | 회원 탈퇴 사유 선택 필수화 + 선택 체크 표시 | ✓ |
| FIX | 일괄등록 staging 영속화 — preview→commit 단계 거래 유실(특히 해외) 해소 | ✓ |
| INTERNAL | US 한글명 백필 대상 확대, 회원 탈퇴 감사 로그/어드민 통계, OpenFIGI ISIN 캐시, 코드리뷰 반영, docs/decisions 갱신 | ✗ |

## 검증 결과

- app-store-ko.md: 해당 없음 (store-notes:skip)
- play-store-ko.md: 해당 없음 (store-notes:skip)
- 대상 버전 v1.3.3_31 — 폴더명·summary.md 메타데이터 일치 ✓
- 모바일 버전 3곳 동기화: `[app] in sync: 1.3.3 build 31` ✓ (빌드 31 유지 = OTA web-only)
- 백엔드 버전: api 1.3.9 / admin 0.1.9 (독립 SemVer, 모바일과 별개)

## 배포 체크리스트 (출시 노트 외 운영 작업)

- **DB 마이그레이션: 필요** — 신규 Alembic 마이그레이션 6개(이 델타에서 추가, 운영 미적용):
  - `0007_trade_origin` · `0008_isin_ticker_map` · `0009_account_deletions` · `0010_import_staging` · `0011_stocks_name_ko` · `0012_board_reads` (현재 로컬 head)
  - ⚠️ **BE 배포(main push)보다 먼저** 운영 DB 에 적용. 신규 BE 코드가 새 스키마(trades.origin/custom_tags, import_staging, stocks.name_ko, board_post_reads/user_notice_state, isin_cache, account_deletions)를 전제하므로 순서가 뒤바뀌면 운영 500.
  - 적용: Alembic (supabase 아님) — `cd api && poetry run alembic upgrade head` 를 **운영 DB DSN** 으로 실행. 운영 PG 는 호스트 포트 미publish → 컨테이너 IP SSH 터널 + `DATABASE_URL` override 필요 ([project_prod_db_access] / [project_alembic_migrations] 참고). 적용 전 `alembic heads` 실측으로 현재 운영 head 확인할 것.
- **BE 배포: 필요** — api/src 다수 변경(auth/board/trades/import/stocks/portfolio 라우터·repo·도메인). main push 시 Coolify 자동 배포. **마이그레이션 적용 후** 나가야 함.
- **admin 배포: 필요** — admin/src 변경(withdrawals·board 댓글·탈퇴 추이 차트). GHA→registry→Coolify 경로.
- **MIN_SUPPORTED_VERSION: 변경 불필요** — 현재값 빈 값(OFF). 이번 BE 변경은 모두 additive(신규 필드/엔드포인트, name_ko COALESCE 오버레이, 출처 표식 등) → 구버전 스토어 앱과 하위호환. breaking 신호 없음.
- **모바일 스토어 제출: 불필요** — OTA web-only(`✅ 재심사 불필요`), 빌드 번호 31 유지. OTA 번들 배포로 반영. 누적 변경은 다음 네이티브 제출 때 스토어 노트로 묶임.
- **실행 순서**: ① 마이그레이션(운영 DB, alembic upgrade head) → ② main push(=BE 자동 배포) + admin 배포 → ③ OTA 번들 배포(app) → (스토어 제출 없음)

## 다음 빌드를 위한 메모

- 다음 **네이티브 제출** 시 `release-notes` 를 `since app-v1.2.7_30`(마지막 네이티브 빌드 _30) 으로 돌려 1.3.0~1.3.3 OTA-only 누적 변경을 한 번에 스토어 노트로 작성한다. (1.3.0/1.3.1/1.3.2/1.3.3 모두 빌드 _31 = OTA, 스토어 미제출 상태)
- 미해결: OAuth 자동연결의 카카오 verified 값/중복 병합/인덱스 ([project_oauth_account_link]) — BE-flow-only라 네이티브 실기기 검증 필요.
- 마이그레이션 0007~0012 운영 적용은 이번이 첫 일괄 반영 — `alembic heads` 실측 후 진행 (prefix 숫자 ≠ 실제 head 주의).
- stash 보류된 docs/auth-cutover-runbook.md 변경은 릴리즈와 무관 — 릴리즈 finish 후 develop 에서 별도 복원/커밋.
