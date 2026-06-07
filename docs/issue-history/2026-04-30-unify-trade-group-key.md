# Spec: `_is_flexible_match` ↔ `_is_same_group` 통합

> 완료: 2026-04-30

## 배경 / 문제

`docs/backlog.md` 의 백엔드 단순화 항목. 두 매칭 함수가 같은 의도(같은 종목·계좌·국가의 trade 그룹화)이지만 시그니처와 정책이 미묘하게 다르다.

| 함수 | 위치 | 입력 | 매칭 로직 |
|---|---|---|---|
| `_is_flexible_match` | `holdings.py:41-53` | 개별 5개 인자 | `trade_id == target_ticker OR trade.asset_name == target_asset` |
| `_is_same_group` | `realized_pnl.py:50-57` | `(trade, TradeGroupKey)` | `trade_id == (key.ticker or key.asset_name)` |

키 타입도 둘로 갈라져 있다: `LotKey`(holdings) vs `TradeGroupKey`(realized_pnl).

`Trade.ticker_symbol` 은 invariant 상 항상 채워져야 하므로 `_is_flexible_match` 의 OR 분기와 `portfolio.py:61` SQL 의 `OR asset_name = $5` 는 dead branch.

## 목표

- `LotKey` 제거, `TradeGroupKey` 단일 키 타입으로 통일
- `_is_flexible_match` 제거, `is_same_group` 단일 매칭 함수로 통일 (strict 정책)
- `portfolio.py:61` SQL 의 잉여 OR 분기 제거
- 기존 테스트 통과, 동작 회귀 없음

## 설계

### 접근 방식

1. `TradeGroupKey` + 매칭 함수는 `realized_pnl.py` 에 그대로 유지. `holdings.py` 가 import. (의존 방향: holdings → realized_pnl, 순환 없음)
2. `_is_same_group` → `is_same_group` rename (외부 import 대상이므로 module-private 표기 부적절)
3. `compute_holding_summary` 시그니처: 4개 개별 인자 → `key: TradeGroupKey` 단일 인자
4. `compute_lot_quantity`, `find_latest_buy_strategy`: `LotKey` → `TradeGroupKey` 만 교체
5. `compute_flexible_holding_days`: 시그니처 유지, 내부에서 `trade_to_group_key(sell)` + `is_same_group` 사용

### 주요 변경 파일

- `api/src/invest_note_api/domain/realized_pnl.py` — `is_same_group` rename
- `api/src/invest_note_api/domain/holdings.py` — `LotKey`/`_is_flexible_match` 삭제, 4개 함수 갱신
- `api/src/invest_note_api/routers/portfolio.py` — `/holding` SQL 정리, 호출부 갱신
- `api/src/invest_note_api/routers/trades.py` — `compute_holding_summary` 호출부 갱신
- `api/tests/test_holdings.py` — `LotKey` → `TradeGroupKey`, 호출부 갱신
- `docs/backlog.md` — 완료 항목 제거

### 재사용

- `realized_pnl.trade_to_group_key(trade) -> TradeGroupKey`
- `trade_types.trade_identifier`, `trade_types.trade_country`

## 구현 체크리스트

- [x] `realized_pnl.py`: `_is_same_group` → `is_same_group` rename + 호출 2곳 갱신
- [x] `holdings.py`: `LotKey`/`_is_flexible_match` 제거, import 정리
- [x] `holdings.py`: `compute_lot_quantity(trades, key: TradeGroupKey)` 갱신
- [x] `holdings.py`: `find_latest_buy_strategy(trades, key: TradeGroupKey)` 갱신
- [x] `holdings.py`: `compute_holding_summary(trades, key: TradeGroupKey)` 시그니처 통합
- [x] `holdings.py`: `compute_flexible_holding_days` 내부 매칭 갱신
- [x] `routers/portfolio.py`: SQL `OR asset_name = $5` 제거, 호출부 갱신
- [x] `routers/trades.py`: `compute_holding_summary` 호출부 갱신
- [x] `tests/test_holdings.py`: 시그니처 변경 반영
- [x] `docs/backlog.md`: 라인 19 항목 제거
- [x] `cd api && poetry run pytest -q` 통과

## 우려사항 / 리스크

- `/holding` SQL 변경 — `ticker_symbol` 항상 존재 invariant 신뢰. 불안 시 `SELECT count(*) FROM trades WHERE ticker_symbol = '' OR ticker_symbol IS NULL` 로 사전 검증 가능
- `routers/trades.py:106` 의 인라인 OR 는 사용자가 ticker 박스에 종목명을 입력하는 검색 UX 분기. 본 통합 범위 외
