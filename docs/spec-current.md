# Spec: 분석 API 단일 엔드포인트 통합

## 배경 / 문제

분석 탭 진입 시 `/api/analysis/summary`, `/behavior`, `/suggestions` 3개 엔드포인트가 동시에 호출되어 동일한 `list_trades` SQL이 3회 실행된다. 더 큰 비용은 Python 단의 중복: `/suggestions`가 `evaluate_rules({summary, profile, concentration})`을 부르기 위해 내부에서 `compute_summary`, `compute_profile`, `compute_concentration`을 다시 계산한다. 결과적으로 SQL 3배 + 핵심 집계 2배 부하. 백로그(`docs/backlog.md:9`).

## 목표

- `GET /api/analysis/dashboard?period=<...>` 단일 엔드포인트가 `{ period, summary, behavior, suggestions }`를 반환한다.
- 한 요청 처리에서 `list_trades`, `build_positions`, `compute_concentration`, `compute_summary`, `compute_profile`, `compute_holding_days_map`, `evaluate_rules`, `fetch_quotes_by_keys`가 각 1회만 호출된다.
- 기존 3개 엔드포인트(`/summary`, `/behavior`, `/suggestions`)는 동일 PR에서 제거된다 (FE 외 consumer 없음 — grep 확인됨).
- 프론트 `useAnalysisData` 외부 반환 shape(`summary`, `behavior`, `suggestionsData`, `loading`, `isError`, `refetch`)는 그대로 유지되어 `AnalysisDashboard.tsx`는 무수정.
- 분석 탭 진입 시 네트워크 요청 1건, `list_trades` SQL 1회 호출이 테스트로 보장된다.

## 설계

### 접근 방식

옵션 A — 단일 통합 엔드포인트 추가 + 기존 3개 제거 + 프론트 hook 단일 `useQuery`로 교체. 캐싱(옵션 B)이나 SQL 가드(옵션 C, 별도 백로그 항목)는 본 작업 범위 외.

응답은 기존 모델을 nest: `AnalysisDashboardResponse = { period, summary: AnalysisSummaryResponse, behavior: BehaviorResponse, suggestions: SuggestionsResponse }`. 평탄화 안 함 — FE hook 반환 shape를 동일하게 보존하기 쉽고, BE 응답 모델 분해 영향이 0.

통합 로딩 단일 상태 채택: `useAnalysisData`가 이미 3쿼리 모두 pending일 때 loading=true이므로 단일 쿼리 전환 시 UX 동일. quotes 외부 호출의 콜드 패스 지연도 기존 `/behavior`와 동일하게 발생하며 실패 시 cost_basis fallback 그대로.

### 주요 변경 파일

- `api/src/invest_note_api/schemas/analysis_response.py` — `AnalysisDashboardResponse` 모델 추가 (`CamelModel` 상속, snake→camel 자동 변환 활용)
- `api/src/invest_note_api/routers/analysis.py` — 핸들러 3개 삭제, `get_analysis_dashboard` 1개로 교체, `_get_trades_context` 인라인
- `api/tests/test_analysis.py` — 단일 `TestAnalysisDashboard` 클래스로 마이그레이션, `list_trades` 1회 호출 검증 테스트 추가
- `app/src/lib/api-client.ts` — `ROUTES.analysis.dashboard`, `analysisApi.dashboard`, `AnalysisDashboardData` 타입
- `app/src/lib/query-keys.ts` — `analysisDashboard(period)` 단일 키
- `app/src/hooks/useAnalysisData.ts` — `useQueries(3)` → `useQuery(1)`, 외부 반환 shape 유지

재사용 (신규 도메인 로직 0):
- `compute_summary` / `compute_profile` / `compute_concentration` / `evaluate_rules`
- `compute_holding_days_map` / `build_pnl_map` / `build_positions` / `merge_quotes`
- `parse_period` / `filter_by_period` / `DEFAULT_PERIOD`
- `fetch_quotes_by_keys` / `list_trades`
- 라우터 내부 헬퍼 `_holding_bucket`, `_size_bucket` 및 버킷 상수
- `AnalysisSummaryResponse` / `BehaviorResponse` / `SuggestionsResponse` (nested)
- FE `AnalysisSummary` / `BehaviorData` / `SuggestionsData` 인터페이스

## 구현 체크리스트

- [x] BE: `schemas/analysis_response.py`에 `AnalysisDashboardResponse` 추가
- [x] BE: `routers/analysis.py` — 3 핸들러 제거, `get_analysis_dashboard` 추가 (`response_model_exclude_none=True`, `_get_trades_context` 인라인)
- [x] BE 테스트: `tests/test_analysis.py` — 기존 3개 클래스 → `TestAnalysisDashboard` 통합 (응답 키 nested 경로로 변경), `list_trades` 1회 호출 검증 케이스 추가
- [x] BE 테스트 통과: `cd api && poetry run pytest tests/ -q` (247 passed)
- [x] FE: `lib/api-client.ts` — `ROUTES.analysis` 단순화, `AnalysisDashboardData` 타입, `analysisApi.dashboard(period)` 메서드
- [x] FE: `lib/query-keys.ts` — `analysisDashboard(period)` 단일 키
- [x] FE: `hooks/useAnalysisData.ts` — `useQueries` → `useQuery` 교체, 반환 shape 유지
- [x] FE 타입 체크 통과: `pnpm tsc --noEmit`
- [x] FE 테스트 통과: `pnpm -C app test` (96 passed)
- [ ] dev 서버에서 `/analysis` 페이지 진입 → DevTools Network 탭에서 `/api/analysis/dashboard` 1건만 호출 확인, SummaryCards / BehaviorRadar / SuggestionList / Drilldown 정상 렌더

## 우려사항 / 리스크

- **breaking change**: `/api/analysis/{summary,behavior,suggestions}` 3개 동시 제거. 외부 consumer는 grep으로 없음을 확인했지만 모바일앱 등 정적 export 캐시를 가진 클라이언트가 있으면 일시적 404. 같은 PR에서 BE/FE 동시 배포 필요.
- **`response_model_exclude_none=True` 부작용**: nested `summary`/`behavior` 모델에 향후 누가 Optional 필드를 추가하면 응답에서 누락될 수 있음. 현재 두 모델에 Optional 필드 없음 확인. 추가 시 명시적 default 값으로 채우는 패턴을 따른다.
- **nested `period` 중복**: top-level과 `summary.period`/`behavior.period`/`suggestions.period`가 동일 값. 라우터에서 `period_val` 한 변수로 주입하여 일관성 보장.
- **`.limit(1000)` 가드**: 별도 백로그 항목(`docs/backlog.md:10`). 본 작업 범위 외.
