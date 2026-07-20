# 출시 노트 요약 — v1.4.2_33

> 작성일: 2026-07-20
> 비교 기준: app-v1.4.1_33 (2026-07-08)
> 대상 빌드: v1.4.2_33 (준비 중 — release/app-v1.4.2_33 브랜치, bump 커밋 완료)
> 릴리즈 종류: **OTA web-only (✅ 스토어 재심사 불필요)** · 백엔드 동반 변경 포함 (api 1.3.15 / admin 0.1.12)
> 모드: `store-notes:skip` — summary.md 만 작성 (스토어 노트 없음)

## Git 로그 (app-v1.4.1_33..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 861635d | 2026-07-16 | feat(import): 암호 걸린 거래내역서 파일 안내·검증 추가 |
| 3354917 | 2026-07-16 | fix(board): 제출 폼 연타 시 중복 등록 방지 (동기 ref 락) |
| ca21ea5 | 2026-07-16 | refactor(import): preview·commit 판단을 공유 plan 으로 통합 + 이미 등록됨 표시 |
| de1c0dd | 2026-07-16 | feat(import): 한국투자증권 거래내역서 파서 추가 |
| 993a104 | 2026-07-10 | feat(admin): 대시보드에 일괄등록 원장 카드 추가 |
| 1a400b6 | 2026-07-08 | chore(api): import_staging 테이블 drop + dead 코드 정리 |

(docs(backlog) 커밋 2건 생략 — 전량 INTERNAL)

## 동기간 spec-history 항목

- 없음 — 이번 빌드 변경(한국투자증권 파서·암호화 안내·공유 plan 리팩토링)은 별도 spec-history 파일 없이 진행됨. (직전 `2026-07-06-admin-import-ledger.md` 는 v1.4.1 에 반영 완료)

## 분류표

| 라벨 | 항목 | 대상 | 출시 노트 반영 |
|------|------|------|--------------|
| NEW | 한국투자증권 거래내역서 일괄등록 지원 (HTML 위장 xls 파서) | app+api | 해당 없음 (OTA, 스토어 노트 없음) — 다음 네이티브 제출 시 반영 |
| NEW | 암호 걸린 거래내역서 파일 감지·안내·검증 | app+api | 사용자 가시 (파일 업로드) |
| IMPROVE | 일괄등록 미리보기 '이미 등록됨' 표시 | app+api | 사용자 가시 (일괄등록) |
| FIX | 제출 폼 연타 시 중복 등록 방지 (오류신고·의견 제출 포함) | app+api | 사용자 가시 (게시판/제보) |
| NEW | 어드민 대시보드 일괄등록 원장 카드 | admin | 어드민 전용 |
| INTERNAL | preview·commit 판단을 공유 plan(trade_import_plan)으로 통합 + trades 라우터 리팩토링 | api | ✗ |
| INTERNAL | import_staging 테이블 drop(0018) + import_staging_repo dead 코드 정리 | api | ✗ |
| INTERNAL | 파서/암호화/plan/http 테스트 추가, docs(backlog) 현행화 | api | ✗ |

## 검증 결과

- app-store-ko.md / play-store-ko.md: **해당 없음 (store-notes:skip)**
- 버전 일치: package.json / iOS / Android 마케팅 1.4.2, build 33 (유지) — `make version-check` 통과
- api 1.3.15 / admin 0.1.12 bump 확인
- 폴더명·summary.md 대상 버전 = v1.4.2_33 일치

## 배포 체크리스트 (실행 순서대로)

1. **DB 마이그레이션: 필요 (단, 순서 주의)** — Alembic 신규 1개.
   - `0018_drop_import_staging.py` — import_staging 테이블 **DROP** (원장 전환으로 dead 화된 테이블 정리)
   - ⚠️ **DROP 마이그레이션이라 순서가 additive 와 반대다.** import_staging 는 v1.4.1 원장 전환 시점에 이미 런타임에서 미사용(dead)이 되었고, 이번 신규 BE 는 `import_staging_repo` 자체를 제거했다. 따라서 **BE 배포(신규 코드가 테이블 참조 완전 제거) → 그 다음 0018 적용** 순서를 권장 (테이블을 참조할 코드가 라이브에 없을 때 DROP). 위험도 낮음(라이브 1.4.1 도 미참조)이나 보수적으로 후행.
   - 적용 명령: `cd api && poetry run alembic upgrade head` (운영 DATABASE_URL 대상 — 운영 PG 는 호스트 포트 미publish라 SSH 터널/컨테이너 IP 경유 필요. 컨테이너는 배포 시 자동 upgrade 안 됨 → 수동 실행)
   - 참고: prod head=0017, repo head=0018 (0018 미적용 배포대기) — [[project_alembic_migrations]]
2. **BE 배포: 필요** — api/src 런타임 변경(routers/trades 대폭 리팩토링, broker_import/koreainvest_xls 파서 추가, services/broker_capture 암호화 검증, domain/trade_import_plan 신규, db_ops). main push 시 Coolify 자동 배포.
   - 어드민 SPA(admin/) 는 별도 GHA→registry→Coolify 파이프라인으로 배포됨.
3. **MIN_SUPPORTED_VERSION: 변경 불필요** — 현재값 `1.3.0` 유지. import preview/commit 은 내부 공유 plan 으로 통합됐으나 엔드포인트·필수 응답 필드 제거 없이 하위호환 유지 전제. 스토어 설치본은 build 33(마케팅 ≥1.4.0)이라 1.3.0 게이트 위. → **단, 일괄등록 preview/commit wire shape 하위호환은 배포 전 재확인 권장** (BE 가 앱보다 먼저 라이브, OTA 도달 전 구 web 이 신 BE 호출하는 창 존재).
4. **모바일 스토어 제출: 불필요** — app 변경은 OTA web-only. OTA 번들 배포로 반영, 빌드 번호 33 유지. 누적 변경은 다음 네이티브 제출 시 스토어 노트로 묶여 나감.

**실행 순서**: main push(BE 자동 배포) → 0018 마이그레이션(운영 DB, DROP 후행) → admin SPA 배포 → OTA 번들 배포

## 다음 빌드를 위한 메모

- **다음 네이티브 제출 시**: `release-notes` 를 `since app-v1.3.8_32`(마지막 네이티브 빌드) 로 돌려 build 32 이후 누적 OTA 변경(1.3.x~1.4.2)을 한꺼번에 묶어 스토어 노트 작성. 특히 **한국투자증권 파서 지원**은 사용자 가시 NEW 로 스토어 노트 대상.
- 키움 암호화 거래내역서는 보류 상태 — [[project_broker_import_parsers]]. 이번 암호화 안내는 "암호 걸린 파일 감지→안내" 까지.
- 일괄등록 preview·commit 이 공유 plan(trade_import_plan)으로 통합됨 — preview 카운트=commit 대상 모델링 정합성은 [[project_import_preview_commit_parity]] 불변식 유지 확인 대상.
