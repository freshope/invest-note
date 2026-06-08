# Spec: 메인(홈)에 계좌 필터 추가

> 완료: 2026-05-23

## 배경 / 문제

기록 페이지에는 이미 `AccountFilter` 칩 UI 와 전역 `AccountFilterProvider` 가 있어 계좌별로 거래를 볼 수 있다. 그러나 메인(`HomeDashboard`)은 항상 **전체 계좌 합산**만 보여줘 사용자가 특정 계좌의 평가액·손익·보유 종목만 따로 확인할 수 없다. 계좌별로 메인을 좁혀 보고 싶다는 요구가 누적되어, 기존 필터 패턴을 메인까지 확장한다.

## 목표

- 메인 페이지에 계좌 필터 칩(records 와 동일한 UI)이 표시된다.
- 칩에서 특정 계좌를 선택하면 메인의 **모든 집계**가 그 계좌 기준으로 좁혀진다.
  - 상단 KPI(`DashboardBody`: 총평가액·미실현·실현·현금·총자산·월거래)
  - 자산배분 차트(`AllocationTabs`: 주식/현금 비율, 계좌별 스냅샷)
  - 보유 종목 리스트(`HoldingsList`)
- "전체" 칩을 선택하면 기존(현재) 합산 동작 그대로 유지된다.
- 필터 상태는 기존 `AccountFilterProvider` 를 그대로 공유 → 기록 탭과 메인이 같은 선택을 본다(탭 전환해도 유지).
- 계좌가 1개뿐이면 필터 칩 자체를 숨긴다 (records 와 동일 규칙).
- `pnpm tsc --noEmit` / `cd be && poetry run pytest -q` 통과.

## 설계

### 접근 방식

**BE 에서 필터링한다.** FE 클라 사이드 필터링은 불가능 — `Position` 데이터에 `account_ids: list[str]` 만 있고 **계좌별 holding_quantity/cost_basis 가 분리돼 있지 않아** 한 종목을 여러 계좌에서 보유 중일 때 정확히 잘라낼 수 없다. 따라서:

1. **BE `/portfolio/summary` 에 옵션 쿼리 파라미터 `account_id` 추가.**
   - 미지정: 기존 동작 유지(전체 합산).
   - 지정: trades 와 accounts 를 그 계좌로 좁힌 뒤 `build_positions` / `build_account_snapshots` / `build_totals` / `build_pnl_map` 호출. 핵심 도메인 로직은 그대로 재사용.
2. **FE `usePortfolioSummary(accountId)` 로 옵션 인자 추가** 후 queryKey 에 포함해 캐시 분리.
3. **`HomeDashboard` 가 `useEffectiveAccountId(accounts)` 를 읽어 훅에 주입**하고, `accounts.length >= 2` 일 때 `AccountFilter` 칩 렌더.
   - accounts 목록은 `accountsApi.list` (`queryKey: queryKeys.accounts`) 로 별도 조회 — settings 페이지가 이미 같은 패턴 사용. summary 응답에서 추출하지 않는다(필터링된 응답은 snapshots 가 1개로 줄어 칩을 그릴 수 없음).

### 빈 상태 처리

- 글로벌 거래 0건: 기존 `EmptyState variant="no-trades"` 그대로.
- 특정 계좌 선택했는데 그 계좌에는 거래 0건: BE 응답의 `has_trades` 가 false 로 내려와 동일한 `EmptyState variant="no-trades"` 가 렌더됨 → 그대로 사용 (별도 카피 분기 없음).

### 무효화 영향 (회귀 가드)

- trades mutation 후 `invalidateQueries({ queryKey: queryKeys.portfolio })` 가 모든 accountId 별 summary 캐시를 prefix 매칭으로 무효화 → 기존 mutation 코드 수정 불필요.
- Capacitor resume 시 `refetchOnWindowFocus: true` 글로벌 default 가 살아 있으므로 stale 노출 시간은 staleTime 2 분으로 한정 (decisions.md 2026-05-03).

### 주요 변경 파일

**BE**
- `be/src/invest_note_api/routers/portfolio.py` — `get_portfolio_summary` 에 `account_id: str | None = Query(default=None, alias="accountId")` 추가, trades/accounts 필터링 로직 삽입.
- `be/tests/test_portfolio_summary.py` (있다면 갱신, 없으면 추가) — `accountId` 지정/미지정 두 케이스 회귀 테스트.

**FE**
- `fe/src/lib/api-client.ts` — `portfolioApi.summary` 시그니처를 `(accountId?: string | null) => ...` 로 변경, accountId 가 truthy 일 때 `?accountId=...` 쿼리스트링 부착.
- `fe/src/lib/query-keys.ts` — `portfolioSummary` 를 함수형으로 변환: `portfolioSummary: (accountId: string | null) => ["portfolio", "summary", accountId] as const`. (`portfolio` prefix 는 그대로 유지)
- `fe/src/hooks/usePortfolioSummary.ts` — `accountId: string | null` 인자 받기, queryKey 에 반영.
- `fe/src/components/home/HomeDashboard.tsx`
  - `accountsApi.list` 로 accounts 목록 조회.
  - `useEffectiveAccountId(accounts)` 로 정규화된 id 얻어 `usePortfolioSummary` 에 주입.
  - `accounts.length >= 2` 일 때 `<AccountFilter accounts={accounts} value={effectiveAccountId} onChange={setSelectedAccountId} />` 를 `PageHeader` 와 본문 사이에 렌더 (records 와 동일 sticky 패턴).
  - 빈 상태 분기(`hasAccounts`, `hasTrades`) 는 그대로.

### 영향 없는 영역(가드)

- 기록 페이지 `TradeList` 의 클라 사이드 trades 필터링 패턴은 그대로 유지(현 동작 변경 없음).
- `StockDetail` / `DetailPanelProvider` 의 `useEffectiveAccountId` 사용처 변경 없음.

## 구현 체크리스트

- [x] BE: `portfolio.py` 에 `accountId` 쿼리 파라미터 + `list_trades_with_account(account_id=...)` SQL push + accounts 필터링 로직
- [x] BE: pytest 회귀 테스트 (`accountId` 미지정 / 지정 / 존재하지 않는 id 3 케이스)
- [x] FE: `query-keys.ts` 의 `portfolioSummary` 를 `(accountId) => [...]` 함수형으로 변환
- [x] FE: invalidate 호출처 4곳을 `queryKeys.portfolio` prefix 로 전환 (모든 accountId 캐시 무효화)
- [x] FE: `api-client.ts` `portfolioApi.summary(accountId?)` 시그니처/쿼리스트링 변경
- [x] FE: `usePortfolioSummary(accountId)` 훅 + `keepPreviousData` 적용 (칩 전환 시 깜박임 차단)
- [x] FE: `HomeDashboard` accounts 쿼리 + AccountFilter 칩 + records 와 동일한 sticky 컨테이너 패턴
- [x] decisions.md: 2026-05-23 결정 기록 (2026-05-03 "클라 메모리 필터링" 범위 명시 + invalidate scope 확대 트레이드오프)
- [x] 타입 체크: `pnpm -C fe exec tsc --noEmit` 통과
- [x] BE 테스트: `test_portfolio.py` / `test_trades.py` / `test_holdings.py` 64건 통과 (전체 suite 의 시간 의존 `test_analysis_logic.py::test_1m_excludes_old` 2건은 본 작업과 무관한 사전 결함 — hardcoded `2026-04-22` 가 오늘 기준 1m 윈도우 밖)
- [ ] **수동 검증 (사용자)**: 계좌 2개 이상 환경에서 칩 전환 시 KPI/차트/홀딩이 즉시 갱신, "전체" 복귀 시 기존 합산 일치, 거래 추가/수정/삭제 후 모든 accountId 캐시 무효화 확인

## 우려사항 / 리스크

- **queryKey breaking**: `queryKeys.portfolioSummary` 를 상수에서 함수로 바꾸므로 참조처 전부 갱신해야 한다. `git grep portfolioSummary` 로 빠짐없이 처리.
- **Capacitor 회귀**: 탭 전환/resume 시 필터 상태와 캐시 키 매칭이 어긋날 가능성 — `useEffectiveAccountId` 가 stale id 를 null 로 강등하므로 회귀는 차단되지만, 수동 테스트로 한 번 확인 필요.
- **존재하지 않는 account_id 가 BE 로 들어가는 케이스**: `useEffectiveAccountId` 가 클라에서 정규화하므로 정상 사용에선 발생 X. 그래도 BE 는 user 의 계좌가 아닐 경우 빈 결과를 안전하게 반환하도록 처리.
