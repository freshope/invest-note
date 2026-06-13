"""포트폴리오 응답 스키마 — /api/portfolio/summary."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from invest_note_api.schemas._base import CamelModel


class AccountSnakeResponse(BaseModel):
    # FE Account 인터페이스(snake_case) 호환을 위해 alias_generator 미적용.
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    name: str
    broker: str | None
    cash_balance: float


class PositionResponse(CamelModel):
    key: str
    ticker: str
    country: str
    currency: str
    asset_name: str
    exchange: str
    holding_quantity: float
    avg_buy_price: float            # KRW (primary)
    avg_buy_price_native: float     # native(USD 등) — 달러 보조
    cost_basis: float               # KRW
    cost_basis_native: float        # native
    realized_pnl: float             # KRW
    current_price: float | None     # native 시세
    evaluation: float | None        # KRW
    evaluation_native: float | None  # native
    unrealized_pnl: float | None    # KRW
    last_note_type: str | None
    last_note: str | None
    last_traded_at: str
    account_ids: list[str]


class AccountHoldingResponse(CamelModel):
    key: str
    quantity: float


class AccountSnapshotResponse(CamelModel):
    account: AccountSnakeResponse
    stock_evaluation: float
    cash_balance: float
    total_value: float
    holdings: list[AccountHoldingResponse]


class DashboardTotalsResponse(CamelModel):
    total_evaluation: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    total_cash: float
    total_assets: float
    month_realized_pnl: float
    month_trade_count: int
    missing_quote_tickers: list[str]


class PortfolioSummaryResponse(CamelModel):
    totals: DashboardTotalsResponse
    positions: list[PositionResponse]
    snapshots: list[AccountSnapshotResponse]
    has_accounts: bool
    has_trades: bool
