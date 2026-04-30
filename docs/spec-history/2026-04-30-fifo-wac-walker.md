# Spec: FIFO/WAC walker 통합

> 완료: 2026-04-30

## 배경 / 문제

`api/src/invest_note_api/domain/`의 세 함수가 같은 그룹별 FIFO/WAC 회계를 각자 재구현하고 있다:

- `realized_pnl.py:121` `compute_group_pnl` — SELL별 PnL/holding_days/strategy/emotion 계산 (FIFO lot 메타 추적)
- `realized_pnl.py:193` `validate_mutation` — INSERT/UPDATE/DELETE 가상 적용 후 oversell 검증 (메타 불필요)
- `portfolio.py:78` `build_positions` — 계좌별 lot 누적 후 종목별 포지션 집계 (저장된 `avg_buy_price`/`profit_loss` 사용)

세 함수 모두 `running_qty`/`running_cost` 누적, BUY 등록, SELL 시 lot 매칭/소진 패턴이 동일하다. 회계 규칙이 바뀌면 세 곳을 모두 수정해야 하고, 불일치 시 분석 탭과 거래 기록 합계가 어긋난다.

## 목표

- 공통 walker(generator) 모듈 신설 후, 위 세 함수가 모두 walker 위에 재구현되어 회계 규칙 변경이 한 곳에서 수렴한다.
- 외부 호출자(`routers/`, `db_ops/pnl_sync.py`)의 시그니처는 변경되지 않는다.
- 기존 테스트(`test_realized_pnl.py`, `test_portfolio_logic.py`, `test_holdings.py`, `test_portfolio.py`)가 그대로 통과한다.
- walker 자체에 대한 단위 테스트가 새로 추가되어 회계 동작이 핀으로 박힌다.

## 설계

### 접근 방식

**Generator 기반 walker.** 호출자가 BUY/SELL 이벤트를 for 루프로 소비하면서 결과를 자유롭게 누적한다. 콜백 기반보다 early-exit(`validate_mutation`의 oversell)가 자연스럽고 호출자 책임이 명확하다.

**정책 주입.** 두 가지 핵심 차이를 인터페이스로 흡수:

1. `cost_deduction` 정책 — SELL 시 `running_cost` 차감 방식
   - `recomputed_avg_cost_deduction` (재계산): `state_before.avg_cost * matched_qty` — `compute_group_pnl`/`validate_mutation`
   - `stored_avg_cost_deduction` (저장값): `(trade.avg_buy_price or 0.0) * matched_qty` — `build_positions`
2. `track_fifo_lots: bool` — FIFO lot 메타 추적 여부 (`validate_mutation`/`build_positions`는 False로 메모리·복사 비용 절감)

**그룹 필터·정렬 주입.** `group_filter: Callable[[Trade], bool]`, `sort_fn: Callable[[list[Trade]], list[Trade]]`를 인자로 받아 `_is_same_group`/`_is_flexible_match`, `sort_for_calc`/`sorted(traded_at)` 등을 그대로 사용 가능. 향후 holdings.py 함수 흡수 시 호출만 추가.

### Walker 인터페이스

```python
# api/src/invest_note_api/domain/trade_walker.py

@dataclass(frozen=True)
class FifoLot:
    qty: float
    time_ms: int
    strategy: StrategyType | None
    reasoning_tags: tuple[ReasoningTag, ...]
    emotion: EmotionType | None
    order: int
    source_trade: Trade

@dataclass(frozen=True)
class ConsumedLot:
    qty: float
    lot: FifoLot

@dataclass(frozen=True)
class WalkerState:
    running_qty: float
    running_cost: float
    @property
    def avg_cost(self) -> float:
        return self.running_cost / self.running_qty if self.running_qty > 0 else 0.0

@dataclass
class TradeEvent:
    kind: Literal["BUY", "SELL"]
    trade: Trade
    state_before: WalkerState
    state_after: WalkerState
    matched_qty: float = 0.0          # SELL 전용
    consumed: tuple[ConsumedLot, ...] = ()
    oversell: bool = False             # sell_qty > state_before.running_qty
    no_holding: bool = False           # state_before.running_qty <= 0

def walk_trades(
    trades: Iterable[Trade],
    *,
    group_filter: Callable[[Trade], bool],
    sort_fn: Callable[[list[Trade]], list[Trade]],
    cost_deduction: Callable[[Trade, WalkerState, float], float] = recomputed_avg_cost_deduction,
    track_fifo_lots: bool = True,
) -> Iterator[TradeEvent]: ...
```

### 세 함수 재구현 스케치

**`compute_group_pnl`**: walker 이벤트의 `consumed`로 `holding_days`/`strategy`/`reasoning_tags`/`emotion` 계산. 기존 헬퍼 `_strategy_from_consumed`/`_meta_from_consumed_latest`는 ConsumedLot 시퀀스를 받도록 어댑팅 (또는 시그니처 변경).

**`validate_mutation`**: `_apply_virtual` 헬퍼 추출(insert/update/delete) → `track_fifo_lots=False`로 walker 호출 → SELL 이벤트의 `no_holding`/`oversell` 플래그로 검증·early return.

**`build_positions`**: `trades_by_lot_key` 사전 분리 (성능 위해 O(T) 단일 패스 유지) → 각 lot_key별로 `cost_deduction=stored_avg_cost_deduction`, `track_fifo_lots=False`로 walker 호출 → 마지막 `state_after`에서 `running_qty`/`running_cost` 추출, SELL 이벤트에서 `trade.profit_loss` 누적·`sell_reason` 기록 → 기존 display_key 집계 로직 유지.

### 주요 변경 파일

- `api/src/invest_note_api/domain/trade_walker.py` — 신규. 데이터클래스, 정책 함수, `walk_trades` generator
- `api/src/invest_note_api/domain/realized_pnl.py` — `compute_group_pnl`, `validate_mutation` 내부 walker 사용으로 교체. 헬퍼는 ConsumedLot 어댑팅
- `api/src/invest_note_api/domain/portfolio.py` — `build_positions` 내부 walker 사용으로 교체
- `api/tests/test_trade_walker.py` — 신규. walker 단위 테스트

## 구현 체크리스트

- [x] `domain/trade_walker.py` 신규 작성 — `FifoLot`/`ConsumedLot`/`WalkerState`/`TradeEvent`, `recomputed_avg_cost_deduction`/`stored_avg_cost_deduction`, `walk_trades` generator
- [x] `tests/test_trade_walker.py` 신규 — BUY 누적 / FIFO 소진 순서 / oversell·no_holding 플래그 / `track_fifo_lots=False` / `recomputed` vs `stored` 차감 / group_filter / sort_fn 주입 / 부동소수점 clamp
- [x] `realized_pnl.py::compute_group_pnl` 재구현 — walker 사용. `_strategy_from_consumed`·`_meta_from_consumed_latest`는 ConsumedLot 받도록 어댑팅
- [x] `realized_pnl.py::validate_mutation` 재구현 — `_apply_virtual` 헬퍼 추출 + walker 호출 + early return
- [x] `portfolio.py::build_positions` 재구현 — `trades_by_lot_key` 사전 분리 + walker 호출 + display_key 집계 보존
- [x] 기존 테스트 회귀 — `cd api && poetry run pytest tests/test_realized_pnl.py tests/test_portfolio_logic.py tests/test_holdings.py tests/test_portfolio.py -q` 그린
- [x] 전체 테스트 회귀 — `cd api && poetry run pytest -q` 그린 (249 passed)

## 우려사항 / 리스크

- **부동소수점 drift**: walker의 `state_before.avg_cost * matched_qty`가 기존 `running_cost / running_qty * matched_qty`와 정확히 같은 식·순서로 평가되어야 함. `WalkerState.avg_cost` property가 동일 식 사용 → OK. `max(0.0, ...)` clamp 위치도 동일 유지.
- **lot 메타 mutation 누설**: 기존 코드는 fifo_lots dict의 `slot["qty"]`를 직접 mutate. walker는 내부 큐는 mutable dict로 유지하되 외부 노출은 frozen `FifoLot`/`ConsumedLot`. 호출자가 mutate 못 함을 보장.
- **`build_positions` 성능**: lot_key가 N개면 walker를 N번 돌면서 매번 trades 전체를 필터링하면 O(N*T). `trades_by_lot_key` 사전 분리로 단일 패스 O(T) 유지.
- **별도 백로그 항목과의 분리**: `compute_total_holding`+`compute_wac` 병합, `_is_flexible_match`↔`_is_same_group` 통합은 이번 PR 범위 밖. walker 인터페이스는 향후 두 항목 흡수 가능하도록 group_filter/sort_fn 주입형으로 설계.

## 검증

1. `cd api && poetry run pytest -q` 전체 그린
2. 핵심 시나리오 수동 골든 비교 (선택):
   - 다중 BUY/부분 SELL FIFO 시나리오로 `compute_group_pnl` 결과 dict가 walker 적용 전후 동일
   - `build_positions` 다중 계좌 통합 케이스 결과 list가 walker 적용 전후 동일
