# Spec: FE simplify Round 5 — 성능 (렌더링·캐시)

> 완료: 2026-05-03

## 배경 / 문제

`docs/backlog.md` "FE simplify · 성능" 섹션 9 개 항목 중 BE 협조가 필요한 `tradesApi.list()` 페이지네이션(2번)과 invalidation 영향 범위가 다른 캐시 키 통일(5번)을 제외한 **6 개 항목**(1, 3, 4+9, 6+7, 8 — 4+9 와 6+7 은 묶음)을 한 round 로 처리. 모바일 콜드스타트 TTI 단축, 폼 입력 지연 감소, 리스트 카드 리렌더 N→1 절감, 불필요한 네트워크 호출 제거가 목표.

## 목표

- recharts 두 컴포넌트(`AllocationTabs`, `BehaviorRadar`)가 차트 코드 chunk 를 lazy 로드해 초기 번들에서 빠진다.
- `TradeBasicForm` 입력 시 form 전역 리렌더 횟수가 줄어든다 (`watch()` 7 회 → `useWatch` 1 회 일괄 구독).
- `TradeCard`, `HoldingCard` 가 부모 리렌더 시 props 가 동일하면 재렌더되지 않는다 (`React.memo` + 부모 콜백 참조 안정).
- analysis/portfolio/holding 쿼리의 staleTime 이 의도에 맞게 명시되고 (분석 5분, 포트폴리오 요약 2분, holding 10초), 매도 폼 종목 입력마다 매번 fetch 가 발생하지 않는다.
- `groupByDate` 가 정렬 invariant 에 의존하지 않고 자체적으로 traded_at desc 로 정렬한다.

## 설계

### 접근 방식

각 항목을 독립 커밋으로 분리해 회귀 추적이 쉽도록 한다.

1. **recharts dynamic import** — `next/dynamic` 으로 각 차트의 inner 부분(`<PieChart>...`/`<RadarChart>...`)만 별도 child 컴포넌트로 추출해 dynamic import. `ssr: false` (recharts 는 client-only) + 로딩 placeholder 는 기존 차트 영역 높이의 빈 div 로 layout shift 방지. 카드 셸/legend 는 정적 유지(작은 텍스트만).
2. **`TradeBasicForm` `useWatch`** — `const { control } = form` 후 `useWatch({ control, name: ["trade_type", "price", "quantity", "account_id", "asset_name", "ticker_symbol", "country_code"] })` 단일 호출로 통합. `watch()` 와 동일 시맨틱(reactive subscribe) 이므로 동작 회귀 없음. 반환은 배열이라 기존 분해 패턴 유지 가능.
3. **`HoldingCard` + `TradeCard` `React.memo` + 부모 콜백 안정화**
   - 두 카드에 `React.memo(HoldingCard)` / `React.memo(TradeCard)` 적용. props 가 primitive + 안정 ref 인 경우만 memo 효과. 따라서 부모 콜백 안정화 동반 필수.
   - `HoldingsList`: `fetching` 을 `useRef` 로 변경(렌더 트리거 불필요한 가드용 플래그). `handleCardPress` 의 deps 에서 `fetching` 제거 → 콜백 stable. 카드 onPress 도 인라인 클로저 제거.
   - `TradeList`: 인라인 `() => openTrade(...)` 를 `useCallback((trade) => openTrade({trade, accounts, allTrades: trades}), [openTrade, accounts, trades])` 로 추출. 카드에 trade 자체를 받는 시그니처로 변경.
   - `StockDetail`: `onTradePress` 부모로부터 받는 prop. 동일하게 인라인 클로저 제거.
   - **시그니처 변경**: 카드에 `onPress?: (item: ItemType) => void` 시그니처를 두고 카드 내부에서 `onPress?.(item)` 호출. 부모는 stable handler 한 번만 만들어 모든 카드가 공유.
4. **staleTime 명시** (advisor 경고: `refetchOnWindowFocus` 글로벌 변경 금지, per-query 만)
   - `useAnalysisData` (`["analysis", "dashboard", period]`): `staleTime: 5 * 60_000` (5분).
   - `usePortfolioSummary` (`["portfolio", "summary"]`): `staleTime: 2 * 60_000` (2분).
   - `TradeBasicForm` 의 `holding` 쿼리: `staleTime: 10_000` (10초). 폼 안에서 같은 종목/계좌 조합으로 빠르게 재렌더되는 동안은 캐시 활용, 종목/계좌가 바뀌면 queryKey 가 바뀌어 어차피 새 fetch.
   - `accounts` 등 다른 쿼리는 기본 30초 유지.
   - `lib/api-client.ts` 에 `QUERY_*_STALE_TIME_MS` 상수 묶음으로 정의(이미 `QUERY_DEFAULT_STALE_TIME_MS`, `QUERY_STOCK_SEARCH_STALE_TIME_MS` 패턴 존재).
5. **`groupByDate` 정렬 명시** — `lib/trade-utils.ts:groupByDate` 내부에서 `traded_at desc` 정렬 후 그룹화. 호출처는 변경 없음.

### 주요 변경 파일

**1. recharts dynamic import**
- `app/src/components/home/AllocationTabs.tsx` — recharts 차트 부분을 `AllocationPieChart` child 로 추출 후 `dynamic(() => import("./AllocationPieChart"), { ssr: false, loading: ... })`
- `app/src/components/home/AllocationPieChart.tsx` (신규) — 추출된 PieChart/Pie/Cell/ResponsiveContainer 부분만
- `app/src/components/analysis/BehaviorRadar.tsx` — 동일 패턴
- `app/src/components/analysis/BehaviorRadarChart.tsx` (신규) — RadarChart/Radar/PolarGrid/PolarAngleAxis/ResponsiveContainer 부분

**2. TradeBasicForm useWatch**
- `app/src/components/records/TradeBasicForm.tsx` — `watch()` 7회 → `useWatch({ control, name: [...] })` 1회

**3. memo + 콜백 안정화**
- `app/src/components/home/HoldingCard.tsx` — `React.memo` + `onPress: (position) => void` 시그니처
- `app/src/components/home/HoldingsList.tsx` — `fetching` → `useRef`, 카드 onPress 인라인 클로저 제거
- `app/src/components/records/TradeCard.tsx` — `React.memo` + `onPress: (trade) => void` 시그니처
- `app/src/components/records/TradeList.tsx` — `useCallback` 으로 stable handler, 카드 onPress 인라인 클로저 제거
- `app/src/components/stocks/StockDetail.tsx` — 카드 onPress 인라인 클로저 제거 (부모 prop 안정성 가정)

**4. staleTime 명시**
- `app/src/lib/api-client.ts` — `QUERY_ANALYSIS_STALE_TIME_MS`, `QUERY_PORTFOLIO_STALE_TIME_MS`, `QUERY_HOLDING_STALE_TIME_MS` 상수 추가
- `app/src/hooks/useAnalysisData.ts` — `staleTime` 명시
- `app/src/hooks/usePortfolioSummary.ts` — `staleTime` 명시
- `app/src/components/records/TradeBasicForm.tsx` — holding useQuery `staleTime: 0` → `QUERY_HOLDING_STALE_TIME_MS`

**5. groupByDate 정렬**
- `app/src/lib/trade-utils.ts` — `groupByDate` 내부에서 `[...trades].sort((a,b) => +new Date(b.traded_at) - +new Date(a.traded_at))` 후 기존 그룹화 로직 적용

## 구현 체크리스트

- [x] **1번** recharts: `AllocationTabs` 차트 부분 별도 컴포넌트로 분리 + `next/dynamic({ ssr: false })` 로 import
- [x] **1번** recharts: `BehaviorRadar` 차트 부분 별도 컴포넌트로 분리 + `next/dynamic({ ssr: false })` 로 import
- [x] **2번** `TradeBasicForm` 의 `watch()` 7회 → `useWatch` 1회 일괄 구독
- [x] **3번** staleTime 상수 추가 (`lib/constants/query.ts`)
- [x] **3번** `useAnalysisData` staleTime 명시 (5분)
- [x] **3번** `usePortfolioSummary` staleTime 명시 (2분)
- [x] **3번** `TradeBasicForm` holding 쿼리 staleTime 0 → 10초
- [x] **4번** `HoldingCard` `React.memo` 적용 + `onPress: (position) => void` 시그니처 변경
- [x] **4번** `HoldingsList`: `fetching` → `useRef`, 카드 onPress 인라인 클로저 제거
- [x] **4번** `TradeCard` `React.memo` 적용 + `onPress: (trade) => void` 시그니처 변경
- [x] **4번** `TradeList`: `useCallback` 으로 stable handler, 카드 onPress 인라인 클로저 제거
- [x] **4번** `StockDetail`: 카드 onPress 인라인 클로저 제거 (부모 prop 안정성 가정)
- [x] **5번** `groupByDate` 내부에 traded_at desc 정렬 추가
- [x] 타입 체크 통과 (`pnpm tsc`) — exit 0
- [x] 빌드 통과 (`pnpm build`) — recharts PieChart/RadarChart 가 각각 별도 chunk 로 분리 (`PieChart` 49KB, `RadarChart` 29KB)

## 검증

- **타입 체크**: `pnpm -C app exec tsc --noEmit`
- **빌드**: `pnpm -C app build` — `.next/static/chunks/` 에서 recharts 가 별도 chunk 로 빠졌는지 확인
- **수동 확인** (개발 서버 `pnpm -C app dev` 후):
  - 홈 대시보드: 포트폴리오 구성 탭 진입 시 차트가 잠깐 늦게 나타나는지(=chunk lazy load 동작)
  - 분석 탭: 행동 프로필 레이더 차트 동일
  - 거래 등록 폼: 가격/수량 빠르게 입력해도 끊김 없는지
  - 매도 폼: 같은 종목 재선택 시 holding 쿼리 네트워크 요청이 10초 내 재발생 안 하는지(devtools)
  - 보유 리스트: 카드 클릭 후 패널 열기 / 다른 카드 클릭 시 정상 동작
  - 거래 리스트: 카드 클릭 → 상세 패널 열기 / 계좌 필터 변경 정상 동작
  - 거래 리스트 그룹 헤더: 날짜가 최신부터 desc 정렬

## 우려사항 / 리스크

- **memo 패턴**: `onPress: (item) => void` 로 시그니처를 바꾸면 모든 호출처를 동시에 수정해야 함. grep 으로 카드 사용처를 빠짐없이 찾아 일괄 변경.
- **recharts dynamic + ResponsiveContainer**: dynamic import 직후 `<ResponsiveContainer>` 가 width=0 으로 잠깐 나타날 수 있음 → loading placeholder 의 높이를 차트와 동일하게 두면 layout shift 없음.
- **`useWatch` 시맨틱**: 같은 form 인스턴스에서 `watch()` 와 `useWatch` 는 reactive 결과는 동일하나 미세한 timing 차이 가능. 변경 후 폼 동작(가격 변경 시 자동계산, 종목 선택 시 holding 조회 enabled 토글) 수동 검증 필수.
- **groupByDate 정렬**: 백엔드가 이미 desc 로 정렬해 보내지만 invariant 명시. 호출처는 변경 없음 → 회귀 영향 없음.
- **staleTime 5분/2분**: refetchOnWindowFocus 는 default true 유지(advisor 경고). 백그라운드 → 포그라운드 복귀 시 자동 refetch 는 살아있어 stale 데이터 노출 시간이 사실상 짧음.
