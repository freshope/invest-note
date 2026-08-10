# 출시 노트 요약 — v1.5.1_34

> 작성일: 2026-08-10
> 비교 기준: app-v1.5.0_34 (2026-07-29)
> 대상 빌드: v1.5.1_34 (준비 중 — release/app-v1.5.1_34 브랜치, bump 커밋 완료)
> 동반 백엔드: api-v1.3.19 (현재 라이브 api-v1.3.18)
> 배포 방식: **OTA web-only** — 빌드 번호 34 유지, 스토어 재심사 불필요 (`store-notes:skip`)

## Git 로그 (app-v1.5.0_34..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 0c57801 | 2026-08-10 | chore: bump version app-v1.5.1_34 |
| 9b9d84a | 2026-08-10 | feat(app): 의견·거래내역서 제보에서 상태 칩 숨김 |
| 9997cb0 | 2026-08-10 | fix(api): 게시판 상태 변경 시 알림 발송 제거 |
| ecc1451 | 2026-08-05 | docs(app): SystemBars 비활성화 사유 주석을 현재 구현에 맞게 갱신 |
| e7d3c71 | 2026-08-05 | chore(ci): node 22 로 툴체인 정렬 |

## 동기간 spec-history 항목

- 없음 (직전 태그 이후 `docs/spec-history/` 신규 항목 없음. 최신 항목은 직전 빌드에 포함된 `2026-07-29-push-firebase-unify.md`)

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| FIX | 게시판 문의·제보에서 상태 변경과 관리자 답변이 함께 일어날 때 알림이 두 번 오던 문제 수정 (`9997cb0`) | ✓ (다음 네이티브 제출 노트에 누적) |
| IMPROVE | 의견·거래내역서 제보 화면에서 처리 상태 칩("검토중/완료/반려") 숨김 — 오류 신고만 상태 표시 (`9b9d84a`) | ✓ (다음 네이티브 제출 노트에 누적) |
| INTERNAL | capacitor.config.ts SystemBars 주석 갱신 (`ecc1451`) — 설정값 무변경 | ✗ |
| INTERNAL | CI node 20 → 22 정렬 + `.nvmrc` 추가 (`e7d3c71`) | ✗ |
| INTERNAL | 버전 bump (`0c57801`) | ✗ |

> 이번 릴리즈는 OTA web-only 라 스토어 노트를 만들지 않는다. 위 FIX/IMPROVE 2건은 **다음 네이티브 제출 때** `release-notes` 를 `since app-v1.5.0_34`(= 마지막 네이티브 태그) 로 다시 돌려 누적 스토어 노트로 묶는다.

## 검증 결과

- app-store-ko.md: 해당 없음 (store-notes:skip)
- play-store-ko.md: 해당 없음 (store-notes:skip)
- 버전 3곳 일치: `make version-check` → `[app] in sync: 1.5.1 build 34` ✓
- 빌드 번호 유지 확인: 직전 34 → 이번 34 (OTA web-only 규칙대로 `bump-build` 생략) ✓
- 백엔드 버전 독립 갱신: api 1.3.18 → 1.3.19 ✓
- 테스트: api `pytest tests/test_admin_board.py tests/test_push.py -q` 39 passed / app `vitest run` 315 passed ✓

## 배포 체크리스트 (출시 노트 외 운영 작업)

- **DB 마이그레이션: 불필요** — `api/alembic/` 변경 없음 (repo head `0018_drop_import_staging` 유지)
- **BE 배포: 필요** — `api/src/invest_note_api/routers/admin_board.py` 런타임 변경 + `pyproject.toml` 버전. main push 시 Coolify 자동 배포
- **MIN_SUPPORTED_VERSION: 변경 불필요** — 커밋된 값 `1.3.0` 유지. API 응답 shape·엔드포인트 변경이 없고, 알림 미발송은 구버전 앱과 하위호환 (⚠️ 운영 실제 값의 SSOT 는 Coolify env — git `.env.production` 과 다를 수 있음)
- **모바일 스토어 제출: 불필요** — OTA 번들 배포로 반영, 빌드 번호 34 유지. 누적 변경은 다음 네이티브 제출 때 스토어 노트로 묶여 나감
- **실행 순서**: BE 배포(main push) → OTA 번들 배포

> 순서 근거: FE 상태 칩 숨김은 OTA 번들이 나가야 반영되고, 중복 알림 제거는 BE 배포로만 반영된다. BE 가 먼저 나가도 구버전 앱은 상태변경 알림을 안 받게 될 뿐이라 깨지지 않는다.

## 다음 빌드를 위한 메모

- **스토어 노트 누적**: 다음 네이티브 제출 시 `release-notes ... since app-v1.5.0_34` 로 호출해 v1.5.1 의 FIX/IMPROVE 2건을 함께 묶을 것
- **release-scope 오탐 주의**: `app/capacitor.config.ts` 는 주석만 바뀌어도 "네이티브 변경 → 📱 재심사 필요" 로 잡힌다 (판정이 파일 경로 기준). 이번 릴리즈는 diff 를 확인해 web-only 로 처리했다
- **`OTA_REQUIRED_NATIVE=1.1.23`** (루트 `.env`) — 현재 스토어 라이브 바이너리 버전과 맞는지 번들 발행 전 확인
- 거래내역서 제보를 `resolved` 로 바꿀 때 **댓글 없이 상태만 변경하면 사용자에게 알림이 가지 않는다**. "해결 시 항상 댓글" 운영 관행이 전제 — 어긋나면 별도 통지 경로 검토 필요
