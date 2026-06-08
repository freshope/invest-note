# Spec: `compute_summary` 인자 시그니처 정리

> 완료: 2026-04-30

## 배경 / 문제

`compute_summary(trades, pnl_map, holding_days_map)`은 `routers/analysis.py:90`에서 호출되는데, `trades`는 period-필터링된 거래이고 `pnl_map`/`holding_days_map`은 `all_trades`(전체 거래) 기준으로 빌드되어 있다. 함수 내부 lookup이 SELL id 기준으로만 일어나므로 결과는 정확하지만, 시그니처가 "전체 vs 필터링" 데이터 혼용을 암시해 후속 수정 시 오해를 부를 수 있다. 같은 call path 위 `compute_profile`/`build_strategy_evaluations`도 동일한 명명 불일치를 갖고 있어 함께 정리한다.

`build_pnl_map`/`compute_holding_days_map`은 SELL의 저장 컬럼(`profit_loss`/`holding_days`)을 그대로 읽어 ID→값 맵을 만들 뿐이므로(BUY 카운터파티에 의존하지 않음), period-필터링된 `trades`로 빌드해도 SELL id별 값은 동일하다.

## 목표

- `compute_summary`/`compute_profile`/`get_analysis_dashboard`의 입력이 모두 동일한 period 범위(`trades`)에서 일관되게 빌드된다.
- 함수 시그니처/파라미터명이 실제 입력 범위를 정확히 표현한다.
- 중복된 방어 필터(`sell_ids` 재필터, `period_sell_ids` 가드)를 제거하고 docstring으로 contract를 1회 명시한다.
- 기존 단위/라우터 통합 테스트가 모두 통과한다.

## 설계

### 접근 방식

`pnl_map`/`holding_days_map`을 period-필터링된 `trades`에서 직접 빌드하고, contract와 코드를 한 방향으로 통일한다(part-only 정리는 거짓 주석을 남기게 되므로 풀 정리).

- 라우터에서 맵 빌드 소스를 `trades`로 교체
- 두 헬퍼/소비자(compute_summary, compute_profile, holding_period_dist 루프)는 입력이 이미 period 범위라 가정 → 내부 재필터 제거
- `build_strategy_evaluations` 파라미터명 `all_trades` → `trades` (실제 호출은 모두 period-filtered)
- 각 함수에 한 줄 docstring로 "trades 및 maps 모두 동일 period 범위" 명시

`concentration`/`positions`는 포트폴리오 현재 시점 계산이므로 `all_trades`를 그대로 유지한다.

### 주요 변경 파일

- `api/src/invest_note_api/routers/analysis.py:78-79` — `build_pnl_map(trades)`, `compute_holding_days_map(trades)`로 변경
- `api/src/invest_note_api/routers/analysis.py:96-102` — `holding_period_dist` 루프의 `period_sell_ids` 가드 제거 후 단순화
- `api/src/invest_note_api/domain/analysis/aggregate.py:80-84` — `compute_summary` docstring 추가
- `api/src/invest_note_api/domain/analysis/profile.py:43-53` — `compute_profile` docstring 갱신 + 재필터 제거
- `api/src/invest_note_api/domain/analysis/strategy_adherence.py:39-45` — `all_trades` → `trades` rename

### 재사용할 기존 함수

- `build_pnl_map` (`api/src/invest_note_api/domain/realized_pnl.py:214`)
- `compute_holding_days_map` (`api/src/invest_note_api/domain/analysis/holding_period.py:12`)

## 구현 체크리스트

- [x] `routers/analysis.py:78-79` — `pnl_map`/`holding_days_map`을 `trades`(period-filtered) 기준으로 빌드
- [x] `routers/analysis.py:96-102` — `holding_period_dist` 루프에서 `period_sell_ids` 가드 제거
- [x] `domain/analysis/aggregate.py` — `compute_summary` docstring 1줄 추가
- [x] `domain/analysis/profile.py` — `compute_profile` docstring 갱신 + `sell_ids` 재필터 및 관련 주석 제거
- [x] `domain/analysis/strategy_adherence.py` — `all_trades` → `trades` rename (파라미터 + 루프 변수)
- [x] `cd api && poetry run pytest tests/test_analysis_logic.py tests/test_analysis.py -q` 통과 (50 passed)
- [x] `cd api && poetry run pytest -q` 전체 통과 (247 passed)
- [x] `docs/backlog.md` — 해당 항목 제거

## 검증

1. **단위 테스트**: `cd api && poetry run pytest tests/test_analysis_logic.py -q`
2. **라우터 통합 테스트**: `cd api && poetry run pytest tests/test_analysis.py -q`
3. **전체 회귀**: `cd api && poetry run pytest -q`

## 우려사항 / 리스크

- caller가 router 한 곳뿐이라 내부 가드 제거는 안전 (docstring이 contract).
- `build_strategy_evaluations` rename: 호출 2곳 모두 위치 인자 → keyword 호환성 깨짐 없음.
- SELL 저장 컬럼만 읽는 헬퍼 특성상 결과값은 변하지 않음. 라우터 통합 테스트가 가드.
