"""전략 계획/실제/준수 평가."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from invest_note_api.domain.analysis.thresholds import SCALPING_MAX_DAYS, SWING_MAX_DAYS
from invest_note_api.domain.trade_types import (
    STRATEGY_LONG_TERM,
    STRATEGY_SCALPING,
    STRATEGY_SWING,
    STRATEGY_UNKNOWN,
    TRADE_TYPE_SELL,
)

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import StrategyType, Trade


StrategyAdherence = Literal["FOLLOWED", "DEVIATED", "UNKNOWN"]

ADHERENCE_FOLLOWED: StrategyAdherence = "FOLLOWED"
ADHERENCE_DEVIATED: StrategyAdherence = "DEVIATED"
ADHERENCE_UNKNOWN: StrategyAdherence = "UNKNOWN"


@dataclass
class StrategyEvaluation:
    planned: "StrategyType | None"
    actual: "StrategyType"
    holding_days: int
    adherence: StrategyAdherence


def infer_actual_strategy(holding_days: int) -> "StrategyType":
    if holding_days <= SCALPING_MAX_DAYS:
        return STRATEGY_SCALPING
    if holding_days <= SWING_MAX_DAYS:
        return STRATEGY_SWING
    return STRATEGY_LONG_TERM


def build_strategy_evaluations(
    trades: list["Trade"],
    holding_days_map: dict[str, int] | None = None,
) -> dict[str, StrategyEvaluation]:
    """저장된 SELL strategy_type/holding_days로 전략 평가를 계산.

    trades와 holding_days_map은 동일 범위(둘 다 period-filtered 또는 둘 다 전체)여야 한다.
    입력 trades 의 범위(period-filtered vs 전체)는 호출자 책임이며, 호출지점마다 의도가 다르다:

    - `compute_summary` 내부 호출: period-filtered trades — 기간별 strat_map/adherence_map
      스냅샷용. 결과 키는 해당 기간의 SELL id 만 포함.
    - `routers/analysis.compute_profile` 호출: 전체 trades — 누적 일관성 평가용
      (`compute_profile` 의 input_rates / behavior 메트릭이 장기 추세를 보기 위함).

    두 호출은 의도가 다르므로 통합하지 않는다 (decisions.md 2026-04-30 참고).
    """
    result: dict[str, StrategyEvaluation] = {}
    for trade in trades:
        if trade.trade_type != TRADE_TYPE_SELL:
            continue

        holding_days = trade.holding_days
        if holding_days is None and holding_days_map is not None:
            holding_days = holding_days_map.get(trade.id)
        if holding_days is None:
            continue

        planned = trade.strategy_type
        actual = infer_actual_strategy(holding_days)
        if not planned or planned == STRATEGY_UNKNOWN:
            adherence: StrategyAdherence = ADHERENCE_UNKNOWN
        else:
            adherence = ADHERENCE_FOLLOWED if planned == actual else ADHERENCE_DEVIATED

        result[trade.id] = StrategyEvaluation(
            planned=planned,
            actual=actual,
            holding_days=holding_days,
            adherence=adherence,
        )

    return result


def evaluate_strategy_for_sell(
    sell: "Trade",
    holding_days: int | None,
) -> StrategyEvaluation | None:
    holding_days_map = {sell.id: holding_days} if holding_days is not None else None
    return build_strategy_evaluations([sell], holding_days_map).get(sell.id)
