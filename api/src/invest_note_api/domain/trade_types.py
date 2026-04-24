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

# 명명 상수 — 비교/기본값에 문자열 리터럴 직접 사용 방지
TRADE_TYPE_BUY: TradeType = "BUY"
TRADE_TYPE_SELL: TradeType = "SELL"
MARKET_TYPE_STOCK: MarketType = "STOCK"
MARKET_TYPE_CRYPTO: MarketType = "CRYPTO"
MARKET_TYPE_ETC: MarketType = "ETC"
STRATEGY_SCALPING: StrategyType = "SCALPING"
STRATEGY_SWING: StrategyType = "SWING"
STRATEGY_LONG_TERM: StrategyType = "LONG_TERM"
STRATEGY_UNKNOWN: StrategyType = "UNKNOWN"
EMOTION_FOMO: EmotionType = "FOMO"
EMOTION_IMPULSIVE: EmotionType = "IMPULSIVE"
EMOTION_ANXIOUS: EmotionType = "ANXIOUS"
EMOTION_CONFIDENT: EmotionType = "CONFIDENT"
EMOTION_CALM: EmotionType = "CALM"
TAG_FEELING: ReasoningTag = "FEELING"
RESULT_SUCCESS: TradeResult = "SUCCESS"
RESULT_FAIL: TradeResult = "FAIL"
RESULT_BREAKEVEN: TradeResult = "BREAKEVEN"
DEFAULT_COUNTRY: CountryCode = "KR"
COUNTRY_US: CountryCode = "US"


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

    country_code: str = DEFAULT_COUNTRY
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
