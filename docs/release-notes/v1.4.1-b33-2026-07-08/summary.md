# 출시 노트 요약 — v1.4.1_33

> 작성일: 2026-07-08
> 비교 기준: app-v1.4.0_33 (2026-07-03)
> 대상 빌드: v1.4.1_33 (준비 중 — release/app-v1.4.1_33 브랜치, bump 커밋 완료)
> 릴리즈 종류: **OTA web-only (✅ 스토어 재심사 불필요)** · 백엔드 동반 변경 포함 (api 1.3.14 / admin 0.1.11)
> 모드: `store-notes:skip` — summary.md 만 작성 (스토어 노트 없음)

## Git 로그 (app-v1.4.0_33..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| cd04026 | 2026-07-08 | fix(import): 원장 인덱스 락 제거 + ticker 재해소 재커밋 dead-end 해소 |
| 05281ae | 2026-07-07 | fix(import): 파서 parse_number 비유한값(inf/nan/오버플로) 방어 |
| ef52950 | 2026-07-07 | fix(import): mark_batch_committed account_id 를 last-wins 로 복원 (리뷰 회귀 fix) |
| af732eb | 2026-07-07 | fix(import): 일괄등록 커밋 집계·생애주기 마커 정합성 (리뷰 fix) |
| b619ce5 | 2026-07-07 | perf(admin): user_profiles.last_sign_in 인덱스 추가 (대시보드 DAU/WAU/MAU) |
| 9f3ed46 | 2026-07-07 | style(admin): 거래 목록 사용자 컬럼을 종목 다음으로 이동 |
| cde3e2a | 2026-07-07 | feat(admin): user_id UUID 노출을 게시판식 아바타+이름 표시로 통일 |
| 4cdc989 | 2026-07-07 | style(admin): 사용자 목록 보유 계좌수·총 거래수 우측 정렬 |
| 06bde3c | 2026-07-07 | feat(admin): 사용자 목록에 보유 계좌수·총 거래수 컬럼 추가 |
| e6d0f02 | 2026-07-07 | feat(admin): 대시보드 지표 확대 — 오늘/누적·DAU/WAU/MAU·탈퇴·의견/오류신고 카드 |
| ec36d88 | 2026-07-07 | docs(api): .env.example DATABASE_URL 현행화 |
| 07a78db | 2026-07-06 | feat(admin): 거래내역서 원장(import ledger) 조회 추가 |
| f3686a5 | 2026-07-05 | fix(board): 탈퇴 회원 댓글도 '탈퇴한 회원'으로 표시 |
| e0af36c | 2026-07-05 | fix(board): 탈퇴 회원 게시글 작성자를 '탈퇴한 회원'으로 표시 |
| d419470 | 2026-07-05 | feat(app): 자산추이 표시 단위(일/주/월) 선택 추가 |
| e04df24 | 2026-07-04 | test(api): 일괄등록 동시 재커밋 중복 방지 realdb 회귀 테스트 |
| 0df16ea | 2026-07-03 | fix(api): 일괄등록 커밋 동시 재커밋 중복 방어 + R2 업로드 로깅 |
| 7d0897f | 2026-07-03 | refactor(api): 원장 append-only 재설계 + 등록 마커 + 날짜 파일거절 + 리뷰 fix |
| c5c07b4 | 2026-07-03 | test(api): 원장 provenance·cascade 검증 + R2 lifecycle 문서 |
| e664615 | 2026-07-03 | feat(api): 일괄등록 소스를 staging→원장으로 전환 (Stage 2 물질화) |
| 4c66751 | 2026-07-03 | feat(api): Stage 1 캡처 서비스 — 파일→원장 적재 |
| 83f083f | 2026-07-03 | feat(api): 파서 rows[] 원장 캡처 — 모든 행 raw full-dump + dedup_key |
| 7eab934 | 2026-07-03 | feat(api): 0014 거래내역서 원장 마이그레이션 (import_batches / import_ledger_entries) |

(docs 커밋 다수 생략 — 전량 INTERNAL)

## 동기간 spec-history 항목

- `2026-07-03-import-ledger.md` — 거래내역서 원장(ledger) 캡처/물질화 2-스테이지 설계 (BE)
- `2026-07-06-admin-import-ledger.md` — 어드민 거래내역서 원장 조회 화면 (admin)

## 분류표

| 라벨 | 항목 | 대상 | 출시 노트 반영 |
|------|------|------|--------------|
| NEW | 자산추이 표시 단위(일/주/월) 선택 | app | 해당 없음 (OTA, 스토어 노트 없음) |
| NEW | 거래내역서 원장(import ledger) — 파서 전체 행 캡처 + 2-스테이지 물질화 | api | (내부 재설계, 사용자 동선 동일) |
| IMPROVE | 탈퇴 회원 게시글/댓글 작성자 '탈퇴한 회원' 표시 | api→app | 사용자 가시 (게시판) |
| NEW | 어드민 대시보드 지표 확대 (오늘/누적·DAU/WAU/MAU·탈퇴·의견/오류) | admin | 어드민 전용 |
| NEW | 어드민 사용자 목록 보유 계좌수·총 거래수 컬럼 | admin | 어드민 전용 |
| NEW | 어드민 거래내역서 원장 조회 | admin | 어드민 전용 |
| IMPROVE | 어드민 user_id UUID → 아바타+이름 표시, 컬럼 정렬/순서 | admin | 어드민 전용 |
| IMPROVE | last_sign_in 인덱스 (대시보드 성능) | api | 내부 |
| FIX | 일괄등록 커밋 동시 재커밋 중복 방어·집계·생애주기 마커 정합성 | api | 사용자 가시 (일괄등록 안정성) |
| FIX | 파서 parse_number 비유한값(inf/nan/오버플로) 방어 | api | 사용자 가시 (일괄등록 안정성) |
| INTERNAL | 원장 provenance/cascade·재커밋 realdb 회귀 테스트, R2 lifecycle, docs 현행화 | api | ✗ |

## 검증 결과

- app-store-ko.md / play-store-ko.md: **해당 없음 (store-notes:skip)**
- 버전 일치: package.json / iOS / Android 마케팅 1.4.1, build 33 (유지) — `make version-check` 통과
- api 1.3.14 / admin 0.1.11 bump 확인
- 폴더명·summary.md 대상 버전 = v1.4.1_33 일치

## 배포 체크리스트 (실행 순서대로)

1. **DB 마이그레이션: 필요** — Alembic 신규 4개, BE 배포보다 **먼저** 운영 DB 에 적용
   - `0014_import_ledger.py` (import_batches / import_ledger_entries 신규 테이블)
   - `0015_trades_ledger_uniq.py` (trades↔원장 유니크 제약)
   - `0016_board_comment_withdrawn.py`
   - `0017_user_profiles_last_sign_in_idx.py` (대시보드 인덱스)
   - 적용 명령: `cd api && poetry run alembic upgrade head` (운영 DATABASE_URL 대상 — 운영 PG 는 호스트 포트 미publish라 SSH 터널/컨테이너 IP 경유 필요)
2. **BE 배포: 필요** — api/src 런타임 변경(routers/trades·admin·me, db_ops, broker_import, services/broker_capture, storage/r2). main push 시 Coolify 자동 배포.
   - 어드민 SPA(admin/) 는 별도 GHA→registry→Coolify 파이프라인으로 배포됨.
3. **MIN_SUPPORTED_VERSION: 변경 불필요** — 현재값 `1.3.0` 유지. 이번 변경은 원장 내부 물질화·admin·FE 표시로 additive, 엔드포인트/필수 응답 필드 제거 없음 → 구버전 앱 하위호환 유지.
4. **모바일 스토어 제출: 불필요** — app 변경은 OTA web-only. OTA 번들 배포로 반영, 빌드 번호 33 유지. 누적 변경은 다음 네이티브 제출 시 스토어 노트로 묶여 나감.

**실행 순서**: 마이그레이션(운영 DB) → main push(BE 자동 배포) → admin SPA 배포 → OTA 번들 배포

## 다음 빌드를 위한 메모

- **다음 네이티브 제출 시**: `release-notes` 를 `since app-v1.3.8_32`(마지막 네이티브 빌드) 로 돌려 build 32 이후 누적 OTA 변경(1.3.x~1.4.x)을 한꺼번에 묶어 스토어 노트 작성.
- 자산추이 5년/all 범위는 BE 2년 캡 때문에 확장 필요 (미착수) — [[project_asset_history_unit]].
- 거래내역서 원장 후속 과제는 docs/backlog.md 참조.
