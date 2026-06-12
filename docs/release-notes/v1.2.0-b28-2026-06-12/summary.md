# 출시 노트 요약 — v1.2.0_28

> 작성일: 2026-06-12
> 비교 기준: fe-v1.1.23_28 (2026-06-09, OTA 업데이트 안정화 빌드)
> 대상 빌드: v1.2.0_28 (준비 중 — release/fe-v1.2.0_28 브랜치, bump 커밋 완료)
> 비고: OTA web-only 릴리즈 — 빌드 번호 28 유지(스토어 재심사 불필요), 마케팅 버전만 1.1.23 → 1.2.0

## Git 로그 (fe-v1.1.23_28..HEAD, --no-merges)
| 해시 | 날짜 | 메시지 |
|------|------|--------|
| 0509c91 | 06-12 | feat(stocks): US 종목 한글 별칭 Naver 백필 |
| 719fbb0 | 06-12 | feat(records): 일괄등록 해외 거래 미지원 안내 + 파일명 자동감지 제거 |
| 98662a7 | 06-11 | feat(records): 해외 거래 등록 환율 입력 UX 개선 |
| 2dc9c3b | 06-11 | docs: 완료된 해외주식 v2 백로그 항목 정리 |
| dc777a6 | 06-11 | fix(overseas): 코드리뷰 후속 — 환율 정합·시세 가드·FX 동시조회·정리 |
| 88b75b1 | 06-11 | feat(assets): 일별내역 첫 거래일 전일대비 = 당일 종가 - 구매가 |
| dcbba0c | 06-11 | fix(ui): CountryBadge 줄바꿈/압축 방지 |
| 529aa1b | 06-11 | fix(assets): 자산추이 차트 아래 빈 안내 영역 여백 제거 |
| 8999059 | 06-11 | feat(ui): 중립 안내문구를 Info 아이콘+바텀시트로 이동 |
| 2acade8 | 06-11 | fix(us): 환율 미상(fxMissing)을 시세 미조회와 분리 |
| 441cb9a | 06-11 | fix(us): 해외 종목 표시·환율 정합 + 일별종가 seed 영구실패 가드 |
| 915c53b | 06-11 | feat(assets): 자산추이 해외(US) 보유 원화 환산 통일 |
| 6ea5a77 | 06-11 | fix(seed,trades): cron 일별종가 country 분리 + 환율검증 dedup |
| 449facc | 06-11 | feat(overseas): US 공급처 registry/env 통일 + 환율(FX) 폴백 체인 |
| a0f2c85 | 06-11 | feat(overseas): US 클래스주·우선주 시세 매핑 — Yahoo 심볼 변환 |
| 3c92062 | 06-11 | fix(overseas): 자산추이 환율미상 시 일별 내역 표 가드 |
| 2c151b4 | 06-11 | fix(overseas): 코드리뷰 후속 보완 — 크래시·정합·성능·품질 |
| a232650 | 06-10 | feat(home): 이달 거래건수·환율 표기 한 줄 좌우 배치 |
| d1c65a1 | 06-10 | feat(overseas): 해외주식 잔여 작업 — US 일별종가·시세 폴백·거래수정 통화인지·분석 정밀도 |
| ac191ac | 06-09 | fix(overseas): 코드리뷰 3건 — 종목전환 정렬·FX 음수캐싱·US 환율검증 |
| f65dd6d | 06-09 | feat(overseas): 해외(미국) 주식 지원 — 원화기준 통합표시 + 거래별 체결환율 |

(+ chore: bump version 1건, docs 이동 3건 생략)

## 동기간 spec-history 항목
- 2026-06-11-overseas-stock-phase-a.md — 해외(미국) 주식 지원 1차: 원화 통합 표시 + 거래별 체결환율
- 2026-06-11-asset-history-overseas-krw.md — 자산추이 해외 보유분 원화 환산 통일
- 2026-06-11-info-hint-bottom-sheet.md — 중립 안내문구를 Info 아이콘 + 바텀시트로 이동

## 분류표
| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| NEW | 해외(미국) 주식 지원 — 원화 통합표시 + 거래별 체결환율 | ✓ |
| NEW | US 종목 한글 별칭 검색 | ✓ |
| IMPROVE | 해외 거래 등록 환율 입력 UX | ✓ |
| IMPROVE | 자산추이 해외 보유분 원화 환산 합산 | ✓ |
| IMPROVE | 홈 이달 거래건수·환율 한 줄 배치 | ✓ |
| IMPROVE | 안내문구 Info 아이콘+바텀시트 | ✓ |
| IMPROVE | 일괄등록 해외 거래 미지원 안내 | (해외 지원 맥락에 포함) |
| FIX | 환율 미상 vs 시세 미조회 구분 표시 | ✓ |
| FIX | CountryBadge 줄바꿈 방지 / 자산추이 여백 | ✓ |
| FIX | 일별내역 첫 거래일 전일대비 계산 | (요약에만) |
| INTERNAL | 코드리뷰 후속, cron seed 분리, FX 폴백/캐싱, 테스트, docs | ✗ |

## 검증 결과
- app-store-ko.md: 측정값 아래 보고 참조 / 4000자 한도
- play-store-ko.md: 측정값 아래 보고 참조 / 500자 한도
- 내부 식별자/커밋 해시/PR 번호 없음
- INTERNAL 항목 본문 미혼입
- 대상 버전(1.2.0_28) 폴더명·summary 일치

## 배포 체크리스트 (실행 순서대로)
1. **DB 마이그레이션: 필요** — 신규 `supabase/migrations/029_add_exchange_rate.sql` (trades.exchange_rate 컬럼 추가, NOT NULL DEFAULT 1, 양수 CHECK). **BE 배포 전** 운영 DB 에 선행 적용: `supabase db push --linked`. 신규 BE 코드가 이 컬럼을 전제하므로 순서 역전 시 운영 500.
2. **BE 배포: 필요** — be/ 런타임 다수 변경(해외 시세/FX 폴백, 환율 컬럼 사용). main push 시 Coolify 자동 배포.
3. **MIN_SUPPORTED_VERSION: 변경 불필요** — 현재값 빈 값(OFF) 유지. 변경은 trades 응답에 exchange_rate 필드를 **추가**(additive)하는 방향이라 구버전 앱이 무시해도 깨지지 않음. KR 거래는 exchange_rate=1 로 기존 동작 동일. (breaking 신호 없음.)
4. **모바일 스토어 제출: 불필요** — OTA web-only 변경, 빌드 번호 28 유지. OTA 번들 배포로 전달, 스토어 재심사 불필요.

> 주의: 기존 US 거래(있었다면)는 마이그레이션 백필값 1.0 으로 환율 부정확 → 재등록 필요(데이터 사항, 배포 차단 요소는 아님).

## 다음 빌드를 위한 메모
- 해외주식 v2 백로그(2dc9c3b 에서 정리)는 다음 사이클로 이월.
- 네이티브 변경이 생기는 다음 빌드부터는 빌드 번호(versionCode) 증가 + 스토어 재심사 필요.
