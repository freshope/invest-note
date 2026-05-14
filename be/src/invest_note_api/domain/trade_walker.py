from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Literal

from invest_note_api.domain.trade_types import (
    TRADE_TYPE_BUY,
    EmotionType,
    ReasoningTag,
    StrategyType,
    Trade,
)
from invest_note_api.domain.trade_utils import to_kst_ms


EventKind = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class FifoLot:
    """BUY 단위 스냅샷. consumed lot의 메타 출처."""
    qty: float
    time_ms: int
    strategy: StrategyType | None
    reasoning_tags: tuple[ReasoningTag, ...]
    emotion: EmotionType | None
    order: int
    source_trade: Trade


@dataclass(frozen=True)
class ConsumedLot:
    """SELL 시 소비된 lot 분량."""
    qty: float
    lot: FifoLot


@dataclass(frozen=True)
class WalkerState:
    running_qty: float
    running_cost: float

    @property
    def avg_cost(self) -> float:
        return self.running_cost / self.running_qty if self.running_qty > 0 else 0.0


@dataclass(frozen=True)
class TradeEvent:
    kind: EventKind
    trade: Trade
    state_before: WalkerState
    state_after: WalkerState
    matched_qty: float = 0.0
    consumed: tuple[ConsumedLot, ...] = ()
    oversell: bool = False
    no_holding: bool = False


GroupPredicate = Callable[[Trade], bool]
SortFn = Callable[[list[Trade]], list[Trade]]
CostDeduction = Callable[[Trade, WalkerState, float], float]


def recomputed_avg_cost_deduction(
    trade: Trade, state_before: WalkerState, matched_qty: float
) -> float:
    """SELL 시 (running_cost / running_qty) * matched_qty 차감."""
    return state_before.avg_cost * matched_qty


def stored_avg_cost_deduction(
    trade: Trade, state_before: WalkerState, matched_qty: float
) -> float:
    """SELL 시 trade.avg_buy_price(저장값) * matched_qty 차감."""
    return (trade.avg_buy_price or 0.0) * matched_qty


@dataclass
class _QueueEntry:
    lot: FifoLot
    remaining: float


def walk_trades(
    trades: Iterable[Trade],
    *,
    group_filter: GroupPredicate,
    sort_fn: SortFn,
    cost_deduction: CostDeduction = recomputed_avg_cost_deduction,
    track_fifo_lots: bool = True,
) -> Iterator[TradeEvent]:
    """그룹별 FIFO/WAC 누적 walker.

    호출자는 group_filter/sort_fn으로 그룹 단위와 처리 순서를 결정한다.
    BUY/SELL 이벤트마다 처리 전후 running 상태와 (옵션) 소비된 FIFO lot을 노출한다.
    """
    sorted_trades = sort_fn([t for t in trades if group_filter(t)])

    running_qty = 0.0
    running_cost = 0.0
    fifo_queue: deque[_QueueEntry] = deque()
    buy_order = 0

    for trade in sorted_trades:
        state_before = WalkerState(running_qty, running_cost)

        if trade.trade_type == TRADE_TYPE_BUY:
            running_qty += trade.quantity
            running_cost += trade.price * trade.quantity
            if track_fifo_lots:
                lot = FifoLot(
                    qty=trade.quantity,
                    time_ms=to_kst_ms(trade.traded_at),
                    strategy=trade.strategy_type,
                    reasoning_tags=tuple(trade.reasoning_tags or ()),
                    emotion=trade.emotion,
                    order=buy_order,
                    source_trade=trade,
                )
                fifo_queue.append(_QueueEntry(lot=lot, remaining=trade.quantity))
                buy_order += 1
            state_after = WalkerState(running_qty, running_cost)
            yield TradeEvent(
                kind="BUY",
                trade=trade,
                state_before=state_before,
                state_after=state_after,
            )
        else:
            no_holding = state_before.running_qty <= 0
            oversell = trade.quantity > state_before.running_qty
            matched_qty = min(trade.quantity, state_before.running_qty)

            consumed: list[ConsumedLot] = []
            if track_fifo_lots and matched_qty > 0:
                remaining = matched_qty
                while remaining > 0 and fifo_queue:
                    entry = fifo_queue[0]
                    take = min(entry.remaining, remaining)
                    consumed.append(ConsumedLot(qty=take, lot=entry.lot))
                    entry.remaining -= take
                    remaining -= take
                    if entry.remaining <= 0:
                        fifo_queue.popleft()

            deduction = cost_deduction(trade, state_before, matched_qty)
            running_cost = max(0.0, running_cost - deduction)
            running_qty = max(0.0, running_qty - trade.quantity)
            state_after = WalkerState(running_qty, running_cost)

            yield TradeEvent(
                kind="SELL",
                trade=trade,
                state_before=state_before,
                state_after=state_after,
                matched_qty=matched_qty,
                consumed=tuple(consumed),
                oversell=oversell,
                no_holding=no_holding,
            )
