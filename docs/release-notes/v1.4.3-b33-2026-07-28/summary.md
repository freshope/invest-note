# 출시 노트 요약 — v1.4.3_33
> 작성일: 2026-07-28
> 비교 기준: app-v1.4.2_33 (2026-07-20)
> 대상 빌드: app-v1.4.3_33 (준비 중 — OTA web-only, store-notes:skip)
> 동반 백엔드: api-v1.3.16 (같은 릴리즈 브랜치에서 함께 태깅)

## Git 로그 (app-v1.4.2_33..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 0732bfa | 2026-07-28 | chore: bump version app-v1.4.3_33 |
| db58066 | 2026-07-28 | docs: spec-current → spec-history/2026-07-22-board-notifications.md 이동 |
| 55fdbdd | 2026-07-28 | docs: feature 완료 후 문서 업데이트 |
| 612cbb5 | 2026-07-22 | feat(notifications): 게시판 처리 알림 → 푸시 전환 + 알림 이력 페이지 |
| 4acc605 | 2026-07-20 | fix(api): trades.py 미사용 date 임포트 제거 (ruff F401) |

## 동기간 spec-history 항목

- `2026-07-22-board-notifications.md` — 게시판 처리 통지(답변·상태변경·공지)를 인앱 배지+폴링에서 푸시 알림으로 전환하고, 알림 이력 페이지를 신설.

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| NEW | 게시판 답변/상태변경/공지 푸시 알림 + 알림 이력 페이지 (612cbb5) | ✓ (다음 네이티브 제출 시 스토어 노트에 반영) |
| INTERNAL | `trades.py` 미사용 import 제거 (4acc605, ruff 린트) | ✗ |
| INTERNAL | spec 문서 정리·이동 (55fdbdd, db58066) | ✗ |
| INTERNAL | 버전 bump 커밋 (0732bfa) | ✗ |

## 검증 결과

- app-store-ko.md: 해당 없음 (store-notes:skip)
- play-store-ko.md: 해당 없음 (store-notes:skip)
- 대상 버전(app-v1.4.3_33 / api-v1.3.16)이 폴더명·본 문서에 일관 반영됨

## 배포 체크리스트 (출시 노트 외 운영 작업)

1. **DB 마이그레이션**: 필요 — 신규 2개
   - `api/alembic/versions/0019_notifications.py`
   - `api/alembic/versions/0020_device_tokens.py`
   - BE 배포 전 운영 DB에 선행 적용 필요 (Alembic, `project_alembic_migrations` 참고 — supabase db push 아님)
2. **BE 배포**: 필요 — `api/src/invest_note_api/` 하위 라우터(`notifications.py`, `board.py`, `me.py`, `admin_board.py`), 서비스(`push_sender.py`), repo(`notifications_repo.py`, `device_tokens_repo.py`) 신규/변경. main push 시 Coolify 자동 배포.
3. **MIN_SUPPORTED_VERSION**: 현재 `1.3.0` — 변경 불필요. 이번 변경은 신규 테이블·신규 엔드포인트 추가(알림/디바이스 토큰)로 기존 API 응답 shape을 깨지 않음 — 구버전 앱과 하위호환.
4. **모바일 스토어 제출**: 불필요 — OTA web-only(`app` 변경은 JS/TS만, 네이티브 코드 변경 없음), 번들 배포로 반영. 빌드 번호(33) 유지.

**실행 순서**: 마이그레이션(0019, 0020) 적용 → BE 배포(main push) → OTA 번들 배포.

## 다음 빌드를 위한 메모

- 이번 v1.4.3_33은 OTA web-only라 스토어 노트를 작성하지 않음. 다음 네이티브 제출 시 `release-notes since app-v1.4.0_33`(마지막 네이티브 태그, build 32→33) 로 돌려 이번 건(게시판 푸시 알림 + 알림 이력 페이지) 및 v1.4.1/v1.4.2의 OTA 누적 변경을 함께 포함한 스토어 노트를 작성할 것.
- 푸시 알림은 게이트(Phase 2) 기능 — 실제 발송 활성화 여부는 배포 후 운영 설정 확인 필요.
