from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator


TradeType = Literal["BUY", "SELL"]
MarketType = Literal["STOCK", "CRYPTO", "ETC"]
StrategyType = Literal["SCALPING", "SWING", "LONG_TERM", "UNKNOWN"]
EmotionType = Literal["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"]
ReasoningTag = Literal["TECHNICAL", "FUNDAMENTAL", "NEWS", "FEELING"]
TradeResult = Literal["SUCCESS", "FAIL", "BREAKEVEN"]
CountryCode = Literal["KR", "US", "OTHER"]


class Trade(BaseModel):
    id: str
    user_id: str
    account_id: str

    asset_name: str
    ticker_symbol: str
    market_type: MarketType
    trade_type: TradeType
    price: float
    quantity: float
    total_amount: float
    traded_at: datetime

    strategy_type: StrategyType | None = None
    reasoning_tags: list[ReasoningTag] = []
    buy_reason: str | None = None
    sell_reason: str | None = None

    emotion: EmotionType | None = None

    result: TradeResult | None = None
    reflection_note: str | None = None
    improvement_note: str | None = None

    profit_loss: float | None = None
    avg_buy_price: float | None = None

    country_code: str = "KR"
    exchange: str = ""

    commission: float = 0.0
    tax: float = 0.0

    created_at: datetime
    updated_at: datetime

    @field_validator("id", "user_id", "account_id", mode="before")
    @classmethod
    def _uuid_to_str(cls, v: object) -> str:
        if isinstance(v, UUID):
            return str(v)
        return v  # type: ignore[return-value]

    @field_validator("price", "quantity", "total_amount", "commission", "tax", mode="before")
    @classmethod
    def _decimal_to_float(cls, v: object) -> float:
        if isinstance(v, Decimal):
            return float(v)
        return v  # type: ignore[return-value]

    @field_validator("profit_loss", "avg_buy_price", mode="before")
    @classmethod
    def _decimal_to_float_optional(cls, v: object) -> float | None:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return float(v)
        return v  # type: ignore[return-value]

    model_config = {"from_attributes": True}


class TradeWithAccount(Trade):
    account_name: str | None = None
    account_broker: str | None = None
