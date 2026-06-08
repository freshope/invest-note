# 출시 노트 요약 — v1.1.17_22

> 작성일: 2026-06-05
> 비교 기준: v1.1.16_21 (2026-06-03)
> 대상 빌드: v1.1.17_22 (준비 중 — 태그 전, release/v1.1.17_22 브랜치)

## Git 로그 (v1.1.16_21..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 7716d75 | 2026-06-05 | chore: bump version to 1.1.17 (build 22) |
| 9ce4b54 | 2026-06-05 | fix: code-review 발견 5건 수정 — 자산 추이 정합성·캐시 무효화 |
| 2d1ecae | 2026-06-05 | docs: spec-current → issue-history/2026-06-05-stock-meta-badges.md 이동 |
| 9c593cf | 2026-06-05 | docs: feature 완료 후 문서 업데이트 |
| 0b0c859 | 2026-06-05 | feat: 종목 메타 뱃지 (마켓/시총순위/국민연금) + 바텀시트 안내 |
| 9924a87 | 2026-06-05 | docs: backlog 에 미사용 admin 라우터/ADMIN_TOKEN 인프라 제거 항목 추가 |
| 11f45af | 2026-06-05 | fix(be): nps_seed CLI 에 reconcile 선행 추가 |
| bf137ec | 2026-06-04 | docs: spec-current → issue-history/2026-06-04-daily-price-backfill-sync-state.md 이동 |
| 8c22dd6 | 2026-06-04 | docs: feature 완료 후 문서 업데이트 |
| 0b1a4b9 | 2026-06-04 | feat(be): 자산 추이 backfill 빈-범위 재질의 차단 + 종목 병렬화 |
| e7941d2 | 2026-06-04 | docs: spec-current → issue-history/2026-06-04-stock-switch-bottom-sheet.md 이동 |
| 1ed5f76 | 2026-06-04 | feat(fe): 종목 헤더 바텀시트로 보유 종목 전환 |
| 8ce7748 | 2026-06-04 | docs: spec-current → issue-history/2026-06-04-asset-history-page.md 이동 |
| 8c5171b | 2026-06-04 | style(fe): Select 콘텐츠 max-w 클래스를 Tailwind v4 canonical 문법으로 변경 |
| a770da3 | 2026-06-04 | docs: 자산 추이 페이지 완료 처리 + 종가 자동적재 후속 등록 |
| 172e6dc | 2026-06-04 | feat: 내 자산 추이 페이지 추가 (계좌별/종목별 일별 자산) |
| 96269e9 | 2026-06-04 | docs: 자산 변화 페이지 백로그 항목 추가 |
| f94ceba | 2026-06-04 | docs(be): data.go.kr 게이트웨이 안정성 재진단 기록 + 진단 스크립트 |
| 0dafa8e | 2026-06-04 | feat(be): /admin/seed/nps 적재 전 reconcile 선행 실행 |

## 동기간 issue-history 항목

- 2026-06-04-asset-history-page.md — 내 자산 추이 페이지 (계좌별/종목별 일별 자산, 차트 3개월 창 + 스와이프 팬 최대 2년, 종가 신규 테이블 + data.go.kr 백필)
- 2026-06-04-stock-switch-bottom-sheet.md — 종목 헤더 종목명 클릭 시 바텀시트로 보유 종목 전환
- 2026-06-04-daily-price-backfill-sync-state.md — 자산 추이 backfill 빈-범위 재질의 차단 + 종목 병렬화 (12초 → 단축, 성능)
- 2026-06-05-stock-meta-badges.md — 종목 메타 뱃지 (마켓/시총순위/국민연금 보유) + Popover 설명

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| NEW | 내 자산 추이 페이지 (172e6dc; 성능 0b1a4b9·정합성 9ce4b54 fold) | ✓ |
| NEW | 종목 전환 바텀시트 (1ed5f76) | ✓ |
| NEW | 종목 메타 뱃지 (0b0c859) | ✓ |
| INTERNAL | nps seed reconcile 선행 (0dafa8e, 11f45af — admin/CLI 전용) | ✗ |
| INTERNAL | Select max-w Tailwind v4 canonical 문법 (8c5171b — 동작 동일) | ✗ |
| INTERNAL | docs 6건, 버전 bump, data.go.kr 진단 스크립트 | ✗ |

비고: 9ce4b54(code-review 수정 5건)와 0b1a4b9(backfill 성능)는 이번 빌드에서 처음 출시되는 자산 추이 기능의 일부이므로 별도 FIX/IMPROVE 가 아닌 NEW 항목에 흡수.

## 검증 결과

- app-store-ko.md: 329자 / 4000자 한도 ✓
- play-store-ko.md: 236자 / 500자 한도 ✓ (LC_ALL=en_US.UTF-8 wc -m)
- 내부 식별자/커밋 해시/PR 번호 없음 ✓
- INTERNAL 항목 본문 미포함 ✓ (성능·정합성 수정은 자산 추이 NEW 한 줄에 흡수)
- 버전 일치: 폴더명 v1.1.17-b22 = 파일 4곳(1.1.17/22) = 브랜치 release/v1.1.17_22 ✓

## 배포 체크리스트 (출시 노트 외 운영 작업 — 6.5 단계)

- DB 마이그레이션: **필요** — 신규 SQL 2개 (`026_daily_close_prices.sql`, `027_daily_price_sync_state.sql`). **BE 배포 전 `supabase db push --linked` 선행** (자산 추이 엔드포인트가 신규 테이블 전제).
- BE 배포: **필요** — `be/src/` 런타임 변경 (assets 라우터 신설, stocks 라우터 메타 필드, daily_price_seed/nps_seed 서비스 등).
- MIN_SUPPORTED_VERSION: 현재값 `빈 값 (OFF)` — 변경 검토 **불필요로 보임** (신규 엔드포인트/응답 필드 모두 additive, 구버전 클라이언트 비파괴). 최종 판단은 사용자 몫.
- FE 스토어 제출: **필요** — fe/ 변경 다수 (신규 페이지·컴포넌트·훅).
- **실행 순서**: 마이그레이션(`supabase db push --linked`) → BE 배포 → 스토어 제출

## 다음 빌드를 위한 메모

- backlog: 미사용 admin 라우터/ADMIN_TOKEN 인프라 제거 항목 등록됨 (9924a87)
- 종가 자동적재(스케줄러) 후속 작업 backlog 등록됨 (a770da3) — 현재는 페이지 진입 시 동기 백필
- data.go.kr 게이트웨이 간헐 404 는 쿼터/타임아웃 이슈로 재진단 완료 (f94ceba) — 버그 아님
