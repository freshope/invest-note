# Spec: 라우터 응답을 Pydantic response_model로 통일

## 배경 / 문제

`routers/portfolio.py`, `routers/analysis.py`, `routers/trades.py`에서 도메인 dataclass를 수동 snake_case→camelCase dict로 변환하는 헬퍼와 인라인 dict 빌더가 누적됨 (`_pos_dict`/`_snap_dict`/`_totals_dict`/`_breakdown_dict` + 인라인 dict ~80줄). 필드 추가 시마다 매핑을 손으로 동기화해야 하고 OpenAPI 스키마가 비어 있다. Pydantic v2 `response_model` + `alias_generator`로 자동화하여 ~100줄 감축하고 OpenAPI 문서를 자동 보강한다. (백로그 출처: `docs/backlog.md` "수동 snake→camel dict 빌더를 Pydantic response_model로 대체")

## 목표

- `/api/portfolio/summary`, `/api/analysis/{summary,behavior,suggestions}`, `/api/trades/{id}/summary` 응답이 **현재와 동일한 wire format**(camelCase + PnL 약어 대문자 `L` 유지 + account 중첩 snake_case 유지)으로 직렬화된다
- 라우터 파일에서 수동 dict 빌더가 제거되고 `response_model`이 명시된다
- 기존 테스트 + 추가 검증이 모두 통과한다
- 프론트엔드 변경 없음 (`app/src/lib/portfolio.ts`, `app/src/types/database.ts` 등 그대로)

## 설계

### 핵심 결정

1. **`to_camel_pnl` 커스텀 generator** — `pydantic.alias_generators.to_camel`은 `unrealized_pnl` → `unrealizedPnl`(소문자 l)로 변환하지만 프론트는 `unrealizedPnL`(대문자 L). 1줄 wrapper `to_camel(s).replace("Pnl", "PnL")`로 처리. 응답 surface 필드명에 `_pnl` 접미사 외에 `pnl` 토큰 없음 — false-positive 안전.

2. **중첩 Account snake_case 유지** — `AccountSnakeResponse`는 `CamelModel`을 **상속하지 않고** 별도 `BaseModel` + `model_config=ConfigDict(from_attributes=True)`. Pydantic v2는 nested model의 자체 config를 우선하므로 outer가 camelCase여도 inner는 snake_case로 직렬화됨.

3. **`/suggestions`, `/{trade_id}/summary`에 `response_model_exclude_none=True`** — 현재 wire가 `metric`/`linkSection`/`strategyEvaluation` null 시 키 자체를 누락시키는 동작 보존. portfolio summary 등 `current_price: null` 유지가 필요한 라우트에는 적용하지 않음.

4. **`trades.py`의 `_trade_dict`/`_trade_with_account_dict`는 유지** — Trade 도메인은 이미 snake_case Pydantic 모델이고 프론트도 snake_case로 받으므로 보일러플레이트 제거 ROI가 낮음. `_breakdown_dict`만 제거.

### 응답 스키마 위치

기존 `api/src/invest_note_api/schemas/`(평탄) 컨벤션 유지. 신규 4파일:
- `schemas/_base.py` — `CamelModel`, `to_camel_pnl`
- `schemas/portfolio_response.py`
- `schemas/analysis_response.py`
- `schemas/trade_response.py`

### 주요 변경 파일

- `api/src/invest_note_api/schemas/_base.py` — 신규
- `api/src/invest_note_api/schemas/portfolio_response.py` — 신규: `PositionResponse`, `AccountSnakeResponse`, `AccountSnapshotResponse`, `DashboardTotalsResponse`, `PortfolioSummaryResponse`
- `api/src/invest_note_api/schemas/analysis_response.py` — 신규: 4개 Stats(`StrategyStatsResponse`/`EmotionStatsResponse`/`TagStatsResponse`/`StrategyAdherenceStatsResponse`), `AnalysisSummaryResponse`, `BehaviorProfileResponse`, `ProfileInputRatesResponse`, `ConcentrationResponse`, `BehaviorResponse`, `SuggestionResponse`, `SuggestionsResponse`
- `api/src/invest_note_api/schemas/trade_response.py` — 신규: `SellBreakdownResponse`, `StrategyEvaluationResponse`, `TradeSummaryResponse`
- `api/src/invest_note_api/routers/portfolio.py` — `_pos_dict`/`_snap_dict`/`_totals_dict` 제거, `/summary`에 `response_model=PortfolioSummaryResponse`
- `api/src/invest_note_api/routers/analysis.py` — 3개 인라인 dict 제거, 각 라우트에 `response_model` 추가, `/suggestions`에 `response_model_exclude_none=True`
- `api/src/invest_note_api/routers/trades.py` — `_breakdown_dict` 제거, `/{trade_id}/summary`에 `response_model=TradeSummaryResponse, response_model_exclude_none=True`
- `api/tests/test_portfolio.py` — PnL 키 (`realizedPnL`/`unrealizedPnL`/`totalRealizedPnL` 등) + snapshot account snake_case 검증 추가
- `api/tests/test_analysis.py` — `sumPnL` 키 존재 검증 추가

## 구현 체크리스트

- [ ] `schemas/_base.py` — `CamelModel`, `to_camel_pnl` 정의
- [ ] `schemas/portfolio_response.py` — Position/AccountSnake/AccountSnapshot/DashboardTotals/PortfolioSummary 응답 모델
- [ ] `routers/portfolio.py` — `_pos_dict`/`_snap_dict`/`_totals_dict` 제거, `/summary`에 `response_model` 적용
- [ ] `schemas/analysis_response.py` — Stats×4 / Summary / Behavior / Suggestions 응답 모델
- [ ] `routers/analysis.py` — 3개 라우트 `response_model` 적용 (`/suggestions`은 `exclude_none`)
- [ ] `schemas/trade_response.py` — Breakdown/StrategyEvaluation/TradeSummary 응답 모델
- [ ] `routers/trades.py` — `_breakdown_dict` 제거, `/{trade_id}/summary`에 `response_model` + `exclude_none`
- [ ] `tests/test_portfolio.py` — PnL 키 및 snake_case account 검증 추가
- [ ] `tests/test_analysis.py` — `sumPnL` 키 검증 추가
- [ ] 백엔드 테스트 통과 (`cd api && poetry run pytest -q`)
- [ ] 프론트엔드 타입 체크 (`pnpm tsc`) — 변경 없지만 회귀 미발생 확인

## 검증 방법

- `cd api && poetry run pytest -q` — 모든 테스트 통과
- `/api/portfolio/summary` 응답에서 다음 키 존재 확인:
  - camelCase: `assetName`, `holdingQuantity`, `avgBuyPrice`, `costBasis`, `currentPrice`, `lastTradedAt`, `accountIds`
  - PnL 약어 대문자 L: `realizedPnL`, `unrealizedPnL`, `totalRealizedPnL`, `totalUnrealizedPnL`, `monthRealizedPnL`
  - 중첩 snake_case: `snapshots[0].account.user_id`, `snapshots[0].account.cash_balance`
- `/api/analysis/summary` 응답에서 `byStrategy[0].sumPnL`, `byEmotion[0].sumPnL` 등 PnL 키 확인
- `/api/analysis/suggestions` 응답에서 metric이 null인 경우 키 자체가 누락되는지 확인
- `pnpm tsc` 통과 (프론트 타입 무변경 회귀 확인)

## 우려사항 / 리스크

- **`to_camel_pnl`의 `Pnl→PnL` 치환 충돌** — 응답 모델 필드명 grep 결과 `_pnl` 접미사 외 `pnl` 토큰 없음, 안전. 새 필드 추가 시 같은 가정 유지 필요
- **Pydantic nested model의 alias_generator 비상속** — `AccountSnakeResponse`가 `BaseModel`을 직접 상속(CamelModel 아님)한다는 점이 핵심. 잘못 상속하면 `user_id`→`userId`로 깨져 프론트 회귀. 테스트로 강제
- **`response_model_exclude_none` 라우트 한정 적용** — portfolio summary의 `current_price`/`unrealized_pnl` null 유지 vs `/suggestions`의 metric 키 누락. 라우트별 적용 범위 명확히 구분
