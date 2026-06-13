# 출시 노트 요약 — v1.2.1_29
> 작성일: 2026-06-14
> 비교 기준: fe-v1.2.0_28 (2026-06-12)
> 대상 빌드: v1.2.1_29 (준비 중 — release/app-v1.2.1_29 브랜치 bump 완료)

## Git 로그 (fe-v1.2.0_28..HEAD, --no-merges)
| 해시 | 날짜 | 메시지 |
|------|------|--------|
| f523038 | 2026-06-14 | chore: bump version app-v1.2.1_29 |
| 4d7051c | 2026-06-14 | chore: .gitignore 하네스 산출물 패턴 통합 |
| 6cb55ba | 2026-06-14 | fix(api,app): 코드리뷰 발견 버그 3건 (Naver 백필 오염·메타 오매칭·import prefix) |
| 081d627 | 2026-06-12 | docs: spec-current → spec-history 이동 |
| b4ce717 | 2026-06-12 | feat(app): US 종목 S&P500 편입 뱃지 + /stocks/meta us_index 노출 |
| da836ee | 2026-06-12 | docs: PostHog 도입 후 문서 업데이트 |
| 82c3b11 | 2026-06-12 | feat(app): PostHog 제품 분석 도입 (FE 전용) |
| 527ceca | 2026-06-12 | feat(api): US S&P500 시드 적재 + 유동성-상위 별칭 백필 확대 |
| 6f290fe | 2026-06-12 | perf(api): US 별칭 백필 naver_checked_at 게이팅 |
| 0bd89d0 | 2026-06-12 | docs(api): be→api rename 후 잔존 참조 갱신 |
| b960686 | 2026-06-12 | fix(api): healthz OpenAPI 중복 operation ID 경고 해결 |
| 1bee4e1 | 2026-06-12 | refactor(api): 앱 라우트 /v1/* 정식화, 기존 경로 하위호환 alias |
| 85bdc1b | 2026-06-12 | refactor: 디렉토리 rename be→api, fe→app |
| 19c0cba | 2026-06-12 | feat(settings): 설정 화면 버전 OTA 번들 버전 우선 표시 |
| 82f9afc | 2026-06-12 | docs(ota): .env.example OTA_REQUIRED_NATIVE 문서화 |
| 83e8600 | 2026-06-12 | docs: CHANGELOG be-v1.2.1 |
| c3a79c2 | 2026-06-12 | chore: bump version be-v1.2.1 |
| faea0bb | 2026-06-12 | fix(ota): required_native default 를 .env 단일 출처로 |
| dcbf6f2 | 2026-06-12 | fix(be): 테스트 lint 오류 수정 |

## 동기간 spec-history 항목
- 2026-06-12-us-sp500-badge.md — US 종목 S&P500 편입(us_index) 시드 + /stocks/meta 노출 + FE 배지

## 분류표
| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| NEW | 미국 주식 S&P500 편입 배지 (상세·목록) | ✓ |
| IMPROVE | S&P500 편입 ~500종목 한글 별칭 검색 확대 | ✓ |
| IMPROVE | 설정 화면 버전을 실제 적용 번들 버전 기준 표시 | ✓ |
| FIX | 동일 ticker 국가 충돌 시 메타 오매칭 차단 | ✓ |
| FIX | Naver 일시 실패가 한글 별칭을 영구 차단하던 백필 오염 수정 | ✓ |
| FIX | 거래내역 파일 import preview /v1 prefix 누락 → 404 수정 | ✓ |
| INTERNAL | PostHog 제품 분석 도입 (FE 전용·키 없으면 no-op) | ✗ (개인정보 고지는 별도) |
| INTERNAL | be→api/fe→app rename, /v1 정식화 alias, healthz, OTA 문서, 테스트, docs, bump | ✗ |

## 검증 결과
- app-store-ko.md: 459자 / 4000자 한도 ✓
- play-store-ko.md: 270자 / 500자 한도 ✓
- 내부 식별자/커밋 해시/PR 번호 없음 ✓
- INTERNAL 항목 본문 미혼입 ✓
- 대상 버전(1.2.1 / 29) 폴더명·summary·양쪽 노트 일치 ✓

## 배포 체크리스트 (출시 노트 외 운영 작업)
- DB 마이그레이션: **필요** — 신규 `supabase/migrations/030_stocks_us_index.sql` 1개. BE 배포 전 `supabase db push --linked` 선행 (us_index 컬럼/시드 전제).
- BE 배포: **필요** — api/src 런타임·시드·pyproject 변경 다수 (S&P500 시드, 별칭 백필, /v1 정식화, 메타/Naver 버그 수정). main push 시 Coolify 자동 배포.
- MIN_SUPPORTED_VERSION: 현재값 빈 값(OFF) — **변경 불필요**. /v1 정식화에 기존 경로 하위호환 alias 유지, us_index 는 옵셔널 응답 필드라 구버전 앱 호환 유지.
- 모바일 스토어 제출: **필요** — app/ 네이티브 변경(빌드 29) 포함, App Store/Play 재제출 + 심사.
- **실행 순서**: 마이그레이션(`supabase db push --linked`) → main push(BE 자동 배포) → 스토어 제출

## 다음 빌드를 위한 메모
- PostHog 분석 도입: 출시 전 개인정보처리방침에 분석 수집 고지 반영 여부 확인 (메모리 project_posthog_analytics 계약). What's New 본문에는 미포함.
- OTA: 이번 빌드는 네이티브 변경 포함이라 빌드 29 로 올려 스토어 제출. 이후 web-only 변경은 OTA 번들로 전달 가능.
