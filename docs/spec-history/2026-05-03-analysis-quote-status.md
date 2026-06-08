# Spec: 분석 dashboard 시세 누락 신호 (missing_quote_tickers)

## 배경 / 문제

`/api/portfolio/summary` 는 시세 fetch 통째 실패(또는 부분 실패) 시 `DashboardTotalsResponse.missing_quote_tickers` 로 누락 종목을 응답에 명시하고, 홈 대시보드 (`DashboardSummary.tsx:61-64`) 가 "시세 미조회: X, Y, Z 외 N개 — 평가금액 제외됨" 배지로 사용자에게 즉시 알린다.

반면 `/api/analysis/dashboard` (`routers/analysis.py:99-105`) 는 동일하게 `fetch_quotes_by_keys` 실패 시 `positions = positions0` 로 cost_basis 폴백하면서도, 응답 스키마(`AnalysisDashboardResponse`)에 시세 누락 신호가 없다. 결과:

- `compute_concentration(positions, all_trades)` 가 cost_basis 기반 평가로 계산됨에도 분석 페이지(`AnalysisDashboard.tsx`) 는 정상값처럼 보여줌
- 사용자는 분산/집중도 수치가 stale/불완전한지 인지 불가

이 spec 은 portfolio summary 와 동일한 패턴을 분석 dashboard 에 추가해 두 엔드포인트 응답의 일관성을 확보하고, 분석 페이지 상단에도 동일한 배지를 노출한다.

## 목표

- `AnalysisDashboardResponse` top-level 에 `missing_quote_tickers: list[str]` 필드 추가
- `routers/analysis.py` 에서 `[p.asset_name for p in positions if p.current_price is None]` 로 채움 (portfolio.py 의 `build_totals` 와 동일 표현)
- FE `AnalysisDashboardData` 에 `missingQuoteTickers: string[]` 추가
- `DashboardSummary.tsx` 의 배지 코드를 공통 컴포넌트(`MissingQuoteBadge`)로 추출, 분석 페이지 상단에서도 재사용
- `pnpm tsc`, `pnpm test`, `cd api && poetry run ruff check`, `poetry run pytest -q` 통과

## 설계

### 위치 결정 — top-level vs BehaviorResponse

`portfolio_response.py` 가 `DashboardTotalsResponse.missing_quote_tickers` 인 것에 맞춰, `AnalysisDashboardResponse` 도 **top-level** 에 둔다 (분석엔 `totals` 같은 단일 집합 객체가 없음). `BehaviorResponse` 또는 `ConcentrationResponse` 안에 두는 안은 분산 섹션과 강결합되어 페이지 상단 배지 사용이 어색해지므로 기각.

### BE 변경

**`api/src/invest_note_api/schemas/analysis_response.py`**
- `AnalysisDashboardResponse` 에 `missing_quote_tickers: list[str]` 필드 추가

**`api/src/invest_note_api/routers/analysis.py`**
- `merge_quotes` 적용 후의 `positions` 에서 `missing = [p.asset_name for p in positions if p.current_price is None]` 계산
- `model_validate` 호출 시 `"missing_quote_tickers": missing` 추가

### FE 변경

**`app/src/lib/api-client.ts`**
- `AnalysisDashboardData` 인터페이스에 `missingQuoteTickers: string[]` 추가

**`app/src/components/shared/MissingQuoteBadge.tsx` (신규)**
- props: `{ tickers: string[] }`
- 빈 배열이면 `null` 반환
- 기존 `DashboardSummary.tsx:61-66` 의 inline 마크업을 그대로 옮김 ("시세 미조회: X, Y, Z 외 N개 — 평가금액 제외됨")

**`app/src/components/home/DashboardSummary.tsx`**
- inline 배지를 `<MissingQuoteBadge tickers={missingQuoteTickers} />` 호출로 교체

**`app/src/components/analysis/AnalysisDashboard.tsx`**
- `useAnalysisData` 가 반환하는 `missingQuoteTickers` 를 페이지 상단 (PageHeader 아래, SummaryCards 위) 에 `<MissingQuoteBadge>` 로 표시
- `useAnalysisData` 훅에서 `dashboard.missingQuoteTickers` 를 노출하도록 보강 필요

**`app/src/hooks/useAnalysisData.ts`**
- 반환 객체에 `missingQuoteTickers` 추가

### 비범위

- `quote_status` enum (ok/partial/failed) 도입 — A 옵션(최소 침습) 채택. 부분 실패 vs 전체 실패 구분은 `missing_quote_tickers.length` 와 `positions.length` 비교로 충분.
- `concentration` 계산을 시세 누락 시 skip 하거나 다른 메트릭으로 대체 — 현재 cost_basis 폴백 동작 유지
- portfolio summary 의 배지 메시지 변경 — 기존 텍스트 그대로 유지

## 구현 체크리스트

- [x] BE: `AnalysisDashboardResponse.missing_quote_tickers` 필드 추가
- [x] BE: `routers/analysis.py` 에서 missing 계산 + 응답 포함
- [x] BE 테스트: `tests/test_analysis.py` 11건 모두 통과 (응답 단언이 새 필드 무시 — 기존 동작 영향 없음)
- [x] FE: `AnalysisDashboardData.missingQuoteTickers` 타입 추가
- [x] FE: `MissingQuoteBadge` 컴포넌트 신규
- [x] FE: `DashboardSummary.tsx` 가 새 컴포넌트 사용
- [x] FE: `useAnalysisData` 훅이 `missingQuoteTickers` 노출
- [x] FE: `AnalysisDashboard.tsx` 페이지 상단에 배지 표시
- [x] `pnpm tsc` ✅, `pnpm test` ✅ (124 passed)
- [x] `poetry run ruff check` ✅, `poetry run pytest -q` ✅ (251 passed)

## 검증

1. **타입 정합성**: BE 응답에 새 필드 추가됐을 때 FE 타입에서도 인지하는지 `pnpm tsc` 로 확인
2. **단위 테스트 통과**: 기존 BE/FE 테스트가 새 필드 추가로 깨지지 않는지
3. **수동 검증** (가능 시):
   - 시세 fetch 정상: 분석 페이지 상단에 배지 미표시
   - 시세 fetch 통째 실패 (e.g., 외부 API 응답 차단): 배지에 모든 종목 표시
   - 시세 부분 실패 (특정 종목만): 해당 종목명만 표시

## 우려사항 / 리스크

- **`MissingQuoteBadge` 위치**: `components/shared/` 에 두지만, portfolio 와 analysis 두 페이지에서 사용. 향후 다른 페이지 추가 시 그대로 재사용.
- **응답 스키마 변경 호환성**: BE가 새 필드 추가되어도 기존 클라이언트가 무시 가능 (Pydantic optional 처리 필요 없음 — required field 로 두되 빈 배열 default 보장). 서비스 중인 모바일앱이 있다면 강제 업데이트 전까지 미인지 (→ 단지 배지가 안 보일 뿐, breaking change 아님).
- **`useAnalysisData` 시그니처 확장**: 기존 호출처가 destructuring 으로 받고 있으면 안전 (추가만, 제거 없음).
