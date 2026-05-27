# 출시 노트 요약 — v1.1.14_19

> 작성일: 2026-05-27
> 비교 기준: v1.1.13_18 (2026-05-26)
> 대상 빌드: v1.1.14_19 (준비 중 — 버전 4곳 bump 완료, commit/tag 전. 작업 트리의 변경은 버전 bump 뿐)

## Git 로그 (v1.1.13_18..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 6521e11 | 2026-05-26 | chore(fe): 다크 모드 스플래시 이미지 갱신 |
| eee4743 | 2026-05-26 | docs: v1.1.12 출시 노트를 버전 디렉터리로 이동 |
| 9f2f484 | 2026-05-26 | fix(fe): pull-to-refresh 시 fetchQuery staleTime:0 으로 캐시 우회 강제 |
| 96350c2 | 2026-05-26 | perf(api): trades 그룹 인덱스 + bulk_delete N+1 제거 + 시세 fetch latency cap |
| 0793780 | 2026-05-26 | docs: spec-current → spec-history/account-filter-loading-ux.md 이동 |
| 4590aef | 2026-05-26 | feat(fe): 계좌 필터 전환 시 본문 스켈레톤 + 헤더 숫자 count-up |
| 6fe029e | 2026-05-26 | docs: 백로그 정리 — 완료/불필요 항목 제거 |
| d1070a9 | 2026-05-26 | chore(fe): 앱 아이콘 및 스플래시 이미지 에셋 갱신 |
| 1e88934 | 2026-05-26 | docs: spec-current → spec-history/force-update.md 이동 |
| c1c99c8 | 2026-05-26 | docs: feature 완료 후 문서 업데이트 |
| cf55775 | 2026-05-26 | feat: 앱 강제 업데이트 메커니즘 추가 |

## 동기간 spec-history 항목

- 2026-05-26-account-filter-loading-ux.md — 계좌 필터 전환 시 본문 스켈레톤 + 헤더 숫자 count-up (keepPreviousData 로 이전 값을 count-up 시작값으로 재활용)
- 2026-05-26-force-update.md — 강제 업데이트 메커니즘 (BE `MIN_SUPPORTED_VERSION` + `GET /app-config`, 네이티브 전체화면 오버레이). 이번 빌드는 향후 강제의 baseline 으로 동작 — 이 빌드 사용자에겐 가시 변화 없음

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| IMPROVE | 계좌 필터 전환 시 본문 스켈레톤 + 헤더 자산 숫자 count-up 애니메이션 (4590aef) | ✓ |
| IMPROVE | 속도 개선 — trades 그룹 인덱스, bulk_delete N+1 제거, 시세 fetch latency cap (96350c2) | ✓ |
| IMPROVE | 새 앱 아이콘 + 다크 모드 스플래시 에셋 갱신 (d1070a9, 6521e11) — cosmetic, 잠정 포함 | ✓ (잠정) |
| FIX | 당겨서 새로고침 시 캐시를 우회해 최신 데이터를 확실히 반영 (9f2f484) | ✓ |
| INTERNAL | 강제 업데이트 메커니즘 (cf55775) — 이번 빌드는 baseline, 사용자 가시 변화 없음 | ✗ (요약에만) |
| INTERNAL | docs/백로그 정리 5건 (eee4743, 0793780, 6fe029e, 1e88934, c1c99c8) | ✗ |

## 검증 결과

- app-store-ko.md: 286자 / 4000자 한도 ✓ (LC_ALL=en_US.UTF-8 wc -m 기준)
- play-store-ko.md: 184자 / 500자 한도 ✓
- 내부 식별자/커밋 해시/PR 번호 노출 없음 ✓
- INTERNAL 항목(강제 업데이트·docs) 본문 미포함 ✓
- 대상 버전(1.1.14 / 19)이 폴더명·summary 에 일치. 스토어 본문엔 버전 표기 없음(이전 노트 컨벤션 동일) ✓

## 다음 빌드를 위한 메모

- **강제 업데이트 활성화**: 이번 빌드(1.1.14_19)가 강제 업데이트 체크 로직의 baseline. 실제로 사용자에게 보이게 하려면 향후 양 스토어 승인 후 BE `MIN_SUPPORTED_VERSION` 을 인상해야 함. 그 시점 릴리즈 노트에 "이전 버전 사용자 업데이트 안내" 류 문구가 적합 (lockout 방지 위해 신중히).
- 앱 아이콘/다크 스플래시는 cosmetic 으로 잠정 포함 — 사용자가 제외 원하면 in-place 제거.
