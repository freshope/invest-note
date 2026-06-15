# 출시 노트 요약 — v1.2.2_29

> 작성일: 2026-06-15
> 비교 기준: app-v1.2.1_29 (2026-06-14)
> 대상 빌드: v1.2.2_29 (준비 중 — release/app-v1.2.2_29 브랜치, bump 커밋 완료. OTA web-only, 빌드 번호 29 유지)

## Git 로그 (app-v1.2.1_29..HEAD, --no-merges)
| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 15449a5 | 2026-06-15 | chore: bump version app-v1.2.2_29 |
| b58fe78 | 2026-06-15 | chore(supabase): snippets/ gitignore 추가 |
| b281423 | 2026-06-15 | docs: 하네스 변경 이력 추가 |
| bc1473f | 2026-06-15 | fix(api): 사용자 정의 태그 재추가 시 RLS UPDATE 정책 부재 500 수정 |
| 5f604a4 | 2026-06-15 | fix: 자산추이 해외주식 거래일 날짜를 ET 기준으로 정규화 |
| 774320b | 2026-06-14 | docs(backlog): KIS 일별종가·시세보조 운영 활성화 반영 |
| 722804b | 2026-06-14 | fix(api): KIS 레이트리밋 재실측 후 페이싱 2→18건/초 상향 |
| 82fe79f | 2026-06-14 | fix: 분석탭 국가 그래프 막대 너비를 상위종목과 동일 폭으로 통일 |
| 191f898 | 2026-06-14 | fix(app): 국기 뱃지 폴백을 실패 src 단위로 추적 |
| 7e4ca5d | 2026-06-14 | feat(app): 국내/해외 텍스트 뱃지를 국기 아이콘으로 교체 |
| 73125d2 | 2026-06-14 | docs: spec-current → spec-history 이동 |
| 287126a | 2026-06-14 | docs: feature 완료 후 문서 업데이트 |
| 4812366 | 2026-06-14 | refactor: 사용자 정의 태그 코드리뷰 cleanup |
| a8b6ffa | 2026-06-14 | feat: 분석태그에 사용자 정의 태그 추가 |
| 237c556 | 2026-06-14 | feat(app): 종목 상세에서 바로 매수/매도 등록 |
| 685391c | 2026-06-14 | style(app): 바텀시트 최소 높이 적용 |
| 3c1107c | 2026-06-14 | fix(app): aria-hidden 접근성 경고 제거 |
| 6643e6a | 2026-06-14 | chore(app): 패키지명 app→invest-note-app 일관화 |
| 9795a6a | 2026-06-14 | docs: 백로그 항목 문구 수정 |
| 61893bc | 2026-06-14 | feat(app): 상세 화면 진입 PostHog 익명 수집 추가 |
| 8c1915f | 2026-06-14 | test(api): assets history 라이브 점 테스트 flaky 수정 |

## 동기간 spec-history 항목
- 2026-06-14-custom-analysis-tags.md — 분석 태그에 사용자 정의 태그 추가 (trades.custom_tags 컬럼 + 레지스트리 테이블, BE+FE)

## 분류표
| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| NEW | 종목 상세에서 바로 매수·매도 등록 (237c556) | ✓ |
| NEW | 사용자 정의 분석 태그 추가 (a8b6ffa) | ✓ |
| IMPROVE | 국내·해외 국기 아이콘 배지 (7e4ca5d) | ✓ |
| IMPROVE | 분석탭 국가 그래프 막대 너비 통일 (82fe79f) | ✓ |
| IMPROVE | KIS 페이싱 상향 → 시세/일별 데이터 갱신 속도 (722804b) | ✓ (잠정) |
| FIX | 해외주식 자산추이 거래일 ET 기준 정규화 (5f604a4) | ✓ |
| INTERNAL | 사용자 정의 태그 재추가 500 수정 (bc1473f) — 미출시 신기능 내부 버그 | ✗ |
| INTERNAL | 국기 뱃지 폴백 추적 (191f898) — 신규 국기 기능의 내부 보강 | ✗ |
| INTERNAL | 바텀시트 최소 높이 / 접근성 경고 / 패키지명 / PostHog 수집 / 테스트 / docs / refactor | ✗ |

## 검증 결과
- app-store-ko.md: 측정값 아래 보고 / 4000자 한도
- play-store-ko.md: 측정값 아래 보고 / 500자 한도
- 내부 식별자/커밋 해시/PR 번호 없음 ✓
- INTERNAL 항목 본문 미혼입 ✓
- 버전 v1.2.2_29 폴더명·summary·본문 일치 ✓

## 배포 체크리스트 (출시 노트 외 운영 작업 — 실행 순서대로)
1. **DB 마이그레이션: 필요** — 신규 2개
   - `supabase/migrations/031_add_custom_tags_column.sql`
   - `supabase/migrations/032_custom_tags_registry.sql`
   - **BE 배포(main push) 전에 선행 적용**: `supabase db push --linked` (신규 BE 코드가 새 스키마 전제 — 순서 역전 시 운영 500)
2. **BE 배포: 필요** — api/ 런타임 변경 (custom_tags RLS, 해외주식 ET 날짜 정규화, KIS 페이싱). main push 시 Coolify 자동 배포.
3. **MIN_SUPPORTED_VERSION: 변경 불필요** — 현재값 빈 값(OFF). 이번 변경은 additive(컬럼 추가)·응답 shape 유지로 구버전 앱 하위호환. 인상 신호 없음.
4. **모바일 스토어 제출: 불필요** — OTA web-only 빌드(빌드 번호 29 유지). 스토어 재심사 없이 OTA 번들 배포로 반영.

**실행 순서**: 마이그레이션 적용 → main push(BE 자동 배포) → OTA 번들 배포

## 다음 빌드를 위한 메모
- **PostHog 익명 수집 출시 고지 의무**: 이번 빌드에 종목 상세 화면 진입 익명 수집(61893bc)이 추가됨. PostHog 도입 계약상 출시 고지 의무가 있으므로, 개인정보처리방침/스토어 데이터 수집 고지에 반영되었는지 확인 필요 (스토어 What's New 본문과는 별개).
- KIS 페이싱 상향(2→18건/초)은 신규 제한 기간 종료 후 재실측 결과 반영. 사용자 체감 속도 항목으로 잠정 포함 — 톤 부적합 시 제외 가능.
