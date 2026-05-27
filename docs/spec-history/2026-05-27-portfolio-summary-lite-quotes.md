# Spec: 시세 조회를 요청 경로에서 분리 (포트폴리오 요약 가속)

> 완료: 2026-05-27

## 배경 / 문제

`/portfolio/summary`(홈 대시보드의 단일 데이터 소스)는 요청 처리 중 네이버/야후 시세를
**동기로 가져온 뒤**(개별 2초, 전체 5초 deadline) 평가금액·평가손익·총계를 계산해 응답한다.
시세 fetch가 응답의 임계 경로에 묶여 있어, 외부 API가 느리거나 캐시 미스일 때 홈 진입이 통째로 지연된다.

**목표 = "API 응답 속도 개선"** (외부 호출을 BE에서 제거하는 것 자체가 목표 아님). 따라서 **옵션 B**:
시세 조회를 요약 응답의 임계 경로에서 떼어내고, FE가 이미 존재하는 `/stocks/quote`(BE)를 **별도·병렬**로
호출해 평가 값을 클라이언트에서 덮어쓴다. 두 엔드포인트 모두 BE라 CORS/CapacitorHttp 신규 표면이 없고,
FE에 trade walker 부활이 불필요해 `sort_for_calc` 패리티 리스크가 없다.
(옵션 A=FE가 네이버 직접 호출 은 부담이 커서 제외.)

## 목표 (완료 기준)

1. 신규 FE에서 홈 진입 시 `/portfolio/summary`가 **외부 시세 fetch 없이** 즉시 응답 (보유종목·원가·실현손익·현금 즉시 표시).
2. FE가 `/stocks/quote`를 병렬 호출해 현재가·평가금액·평가손익·총자산·계좌별 총액을 **도착하는 대로 덮어쓴다**.
3. **기 출시 앱(구버전)은 동작 그대로** 유지 (요약이 여전히 시세 포함 응답 — `withQuotes` 기본 true).
4. pull-to-refresh 시 시세가 BE 캐시를 우회해 최신값으로 갱신.
5. BE/FE 타입체크·테스트 통과.

## 설계

### 접근 방식 (옵션 B)

- BE `/summary`에 opt-in 파라미터 `withQuotes`(기본 true=하위호환). 신규 FE는 `false` 전송 → 시세 fetch skip.
- 시세 의존 값은 FE가 `/stocks/quote` 별도 호출 후 overlay. 시세 비의존 값(수량/원가/실현손익/현금)은 BE 값 그대로.
- 계좌별 탭 `totalValue` overlay 위해 BE가 계좌별 종목 수량(`holdings`)을 additive 필드로 제공 → FE walker 부활 회피.

### Step 0 — 병목 측정 (사용자 결정: 생략)

BE에 이미 45s TTLCache+single-flight 존재 → 정상 트래픽은 대부분 캐시 히트. "느린 원인=시세 fetch"가 미측정.
**사용자 결정(2026-05-27): 측정 생략·바로 구현.** 진행하되, 배포 후 체감 개선이 없으면 그때 원인 재조사
(DB·콜드부트·네트워크 RTT 가능성). 임시 계측 로그는 넣지 않음.

### 주요 변경 파일

- `be/src/invest_note_api/routers/portfolio.py` — `withQuotes` 파라미터(default True) + 조건부 시세 skip
- `be/src/invest_note_api/schemas/portfolio_response.py` — `AccountHoldingResponse` 신규 + `AccountSnapshotResponse.holdings` additive
- `be/src/invest_note_api/domain/portfolio.py` — `build_account_snapshots`가 holdings(key/qty) 동봉
- `be/tests/test_portfolio*.py` — `withQuotes` false/true + holdings 회귀 테스트
- `fe/src/lib/api-client.ts` — `portfolioApi.summary(withQuotes)` 파라미터, `stocksApi.quote`에 `refresh` 추가 (quote 함수는 api-client.ts:359에 이미 존재)
- `fe/src/hooks/useQuotes.ts` (신규) — `/stocks/quote` 쿼리, `enabled: keys.length>0`, staleTime 45s
- `fe/src/hooks/usePortfolioSummary.ts` — lite(`withQuotes=false`) 호출
- `fe/src/lib/query-keys.ts` — `quotes(keys)` 키 추가
- `fe/src/lib/portfolio.ts` — `applyQuotesToTotals`, `applyQuotesToSnapshots` overlay 함수 신규 (기존 `mergeQuotes` 재사용; `buildTotals`/`buildAccountSnapshots`는 재사용 금지)
- `fe/src/lib/portfolio.test.ts` (신규) — overlay 함수 vitest 단위 테스트
- `fe/src/components/home/HomeDashboard.tsx` — summary+quotes 두 쿼리 결합 + overlay + pull-to-refresh 양쪽 갱신

## 구현 체크리스트

- [x] Step 0 측정 게이트 — 사용자 결정으로 생략(효과 없으면 사후 재조사)
- [x] BE: `withQuotes` 파라미터 + 조건부 skip (default true=하위호환)
- [x] BE: `AccountHoldingResponse` + `AccountSnapshotResponse.holdings` additive + `build_account_snapshots` 확장
- [x] BE: pytest 회귀 (전체 317 passed)
- [x] FE: `portfolioApi.summary(withQuotes)` + `stocksApi.quote(refresh)` 파라미터
- [x] FE: `useQuotes` 훅 + `queryKeys.quotes`
- [x] FE: `applyQuotesToTotals` / `applyQuotesToSnapshots` + vitest 단위 테스트 (155 passed; 테스트는 레포 컨벤션상 `__tests__/portfolio.test.ts`)
- [x] FE: HomeDashboard 두 쿼리 결합 + pull-to-refresh(quote refresh=1) 갱신
- [x] FE: 타입체크 통과 (`pnpm -C fe exec tsc --noEmit`)
- [x] 정합성 QA: BE 풀응답 vs (BE lite + FE overlay) 값 일치 (positions/totals/계좌별 totalValue)
- [x] 버전 skew 가드(사후 발견·수정): 구 BE 응답에 `holdings` 부재 시 `applyQuotesToSnapshots` TypeError → 홈 크래시. `snapshot.holdings ?? []` 가드 + 회귀 테스트 추가. **배포 순서 BE→FE 필수.**

## 우려사항 / 리스크

- **(최우선) 병목 미확정**: Step 0 측정 게이트 없이 진행하면 옮기고도 안 빨라질 수 있음.
- **시세 캐시 분산**: 이제 `/stocks/quote`가 BE 캐시(45s, single-flight) 공유 담당 → 외부 호출량 증가 없음.
- **값 정합성(shape drift)**: overlay는 시세 의존 필드만 건드리고 나머지는 BE 값 사용 + 순수함수 단위 테스트로 가드.
- **계좌별 탭 totalValue**: `holdings` additive 필드 의존 → BE 먼저 배포 후 FE 배포(앱+Coolify 동시 릴리즈면 무관).
- **dead code**: `fe/src/lib/quotes.ts`(네이버 직접, SSR 유물)는 본 작업과 무관 — 제거는 범위 외(언급만).
- **분석 대시보드 `/analysis/dashboard`**: 동일 패턴이나 concentration cost_basis fallback 차이로 표면적 다름 → 별도 spec.

## 스코프

- 이번 작업: 홈 `/portfolio/summary` 경로만. 분석 대시보드는 후속 별도 spec.
