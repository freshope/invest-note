# 출시 노트 요약 — v1.3.1_31

> 작성일: 2026-06-23
> 비교 기준: app-v1.3.0_31 (2026-06-20, 마지막 네이티브 제출)
> 대상 빌드: v1.3.1_31 (준비 중 — release/app-v1.3.1_31, OTA web-only)
> 모드: store-notes:skip (OTA web-only → 스토어 노트 미생성, summary 만)

## Git 로그 (app-v1.3.0_31..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| cacc419 | 2026-06-22 | fix(analytics): native_version 누락 수정 — 부팅 경합 봉합 + 이벤트 버퍼링 |
| 9e26c48 | 2026-06-22 | docs: spec-current → spec-history/2026-06-22-broker-statement-submission.md 이동 |
| 5790e2b | 2026-06-22 | fix(broker-statement): 코드리뷰 지적 8건 반영 |
| 975545c | 2026-06-22 | feat(broker-statement): 거래내역서 제보 기능 (R2 업로드 + 어드민 게시판) |
| 9d6146e | 2026-06-21 | docs(auth): cutover runbook + Supabase export SQL + .env.example BE 블록 |

(452b549 `chore: bump version` 은 릴리즈 메커닉 — 제외)

## 동기간 spec-history 항목

- `2026-06-22-broker-statement-submission.md` — 거래내역서 제보(샘플 수집): R2 presigned PUT 직접 업로드 + 어드민 게시판 게시·첨부 다운로드

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| NEW | 거래내역서 제보 기능 (설정 + 거래 가져오기 dual-entry, R2 업로드) | ✓ (다음 네이티브 제출 시) |
| FIX | analytics native_version 누락 수정 (부팅 경합 봉합 + 이벤트 버퍼링) | ✓ (다음 네이티브 제출 시) |
| INTERNAL | 어드민 게시판 첨부 다운로드 버튼 (admin-v0.1.7) | ✗ (앱 사용자 비가시) |
| INTERNAL | auth cutover runbook · export SQL · .env.example BE 블록 (docs/dormant) | ✗ |
| INTERNAL | BE board 라우터 · R2 스토리지 · poetry.lock | ✗ |

> 스토어 노트는 이번 빌드에서 생성하지 않음 — OTA web-only 라 스토어 제출이 없다. 위 NEW/FIX 는 **다음 네이티브 제출** 때 `since app-v1.3.0_31` 로 묶어 스토어 노트를 작성한다.

## 검증 결과

- app-store-ko.md: 해당 없음 (store-notes:skip)
- play-store-ko.md: 해당 없음 (store-notes:skip)
- 버전 일치: app 3곳 in sync 1.3.1 build 31 (version-check 통과) · api 1.3.7 · admin 0.1.7
- 식별자 노출: summary 내부 문서이므로 해당 없음

## 배포 체크리스트 (실행 순서대로)

1. **DB 마이그레이션: 불필요** — `app-v1.3.0_31..HEAD` 에 `api/alembic/` 변경 0건. broker-statement 가 쓰는 board 테이블(0003)·auth(0004~0006)은 이미 운영 적용됨.
2. **BE 배포: 필요** — `api/src/`(board 라우터·R2 스토리지·config R2 블록)·`pyproject.toml`·`poetry.lock` 변경. main push 시 Coolify 자동 배포. **구앱 하위호환 OK** (additive 신규 엔드포인트, 기존 응답 shape 무변경).
   - ⚠️ **cutover 전 — BE auth env 절대 주입 금지**: `BE_TOKEN_SIGNING_KEY`·`GOOGLE_*/KAKAO_*/APPLE_*` 를 넣으면 `/auth/callback` 이 살아나 백필 전 `auth_identities` 오염(runbook 불변식 #2). `BE_AUTH_ENABLED=false` 유지.
   - broker-statement 활성화에 필요한 건 **R2 env 4종만** (`R2_ENDPOINT_URL`·`R2_BUCKET`·`R2_ACCESS_KEY_ID`·`R2_SECRET_ACCESS_KEY`). auth env 와 무관 — 미설정 시 presign/submit 503(dormant).
3. **MIN_SUPPORTED_VERSION: 변경 불필요** — 현재값 빈 값(OFF). broker-statement 는 additive 신규 엔드포인트라 구앱 깨짐 신호 없음.
4. **모바일 스토어 제출: 불필요** — OTA web-only(`✅ 재심사 불필요`). OTA 번들 배포로 반영, 빌드 번호 31 유지. 누적 NEW/FIX 는 다음 네이티브 제출 시 스토어 노트로 묶임.

**실행 순서**: (마이그레이션 없음) → BE 배포(R2 env 주입, auth env 제외) → OTA 번들 배포.

## 다음 빌드를 위한 메모

- **R2 env 주입 확인 필수**: broker-statement 가 동작하려면 운영 Coolify 에 R2 자격증명 4종이 있어야 한다. 없으면 제보 패널이 503. (R2 CORS·env Ops 는 [project_broker_statement_submission] 참고)
- **cutover 대기 중**: 이 릴리즈는 auth Phase 2 cutover 와 직교. auth env 주입·`BE_AUTH_ENABLED` flip 은 별도 runbook(`docs/auth-cutover-runbook.md`) 절차로, 보급률 충족 후 진행.
- 다음 네이티브 제출 시 `release-notes ... since app-v1.3.0_31` 로 돌려 broker-statement 제보 + analytics fix 를 스토어 노트로 작성.
