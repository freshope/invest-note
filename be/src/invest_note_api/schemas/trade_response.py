"""거래 응답 스키마 — /api/trades/{id}/summary."""
from __future__ import annotations

from invest_note_api.schemas._base import CamelModel


class SellBreakdownResponse(CamelModel):
    sell_price: float
    quantity: float
    avg_cost_price: float
    sell_amount: float
    cost_basis: float
    commission: float
    tax: float
    pnl: float


class StrategyEvaluationResponse(CamelModel):
    planned: str | None
    actual: str
    holding_days: int
    adherence: str


class TradeSummaryResponse(CamelModel):
    pnl: float
    result: str | None = None
    holding_days: int | None = None
    strategy_evaluation: StrategyEvaluationResponse | None = None
    breakdown: SellBreakdownResponse
    # FIFO 매칭에서 가장 최근 소비된 BUY의 buy_reason — SELL row에는 저장되지 않으므로 조회 시점 계산.
    buy_reason: str | None = None
