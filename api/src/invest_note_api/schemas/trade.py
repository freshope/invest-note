"""Trade POST/PATCH Pydantic 스키마.

validators.ts의 TradeCreateSchema / TradeUpdateSchema 포팅.
commaPositive / commaNonNegative → field_validator(mode="before")로 재현.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, field_validator

from ..domain.trade_types import (
    CountryCode,
    EmotionType,
    MarketType,
    ReasoningTag,
    StrategyType,
    TradeResult,
    TradeType,
)
from ..domain.trade_utils import KST_OFFSET


def _comma_positive(v: object) -> float:
    """쉼표 포함 문자열/숫자 → 양수 float."""
    if isinstance(v, str):
        v = float(v.replace(",", "").strip())
    else:
        v = float(v)  # type: ignore[arg-type]
    if v <= 0:
        raise ValueError("양수여야 합니다.")
    return v


def _comma_non_negative(v: object) -> float:
    """쉼표 포함 문자열/숫자 → 0 이상 float."""
    if isinstance(v, str):
        v = float(v.replace(",", "").strip())
    else:
        v = float(v)  # type: ignore[arg-type]
    if v < 0:
        raise ValueError("0 이상이어야 합니다.")
    return v


def _traded_at_transform(raw: object) -> datetime:
    """KST 날짜/시간 문자열 → UTC datetime."""
    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("날짜를 선택해주세요.")
    s = raw.strip()
    # "+09:00" suffix가 없으면 KST로 간주
    if not any(s.endswith(tz) for tz in (KST_OFFSET, "Z", "+00:00")) and "+" not in s[10:] and "Z" not in s:
        s = s + KST_OFFSET
    try:
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except ValueError:
        raise ValueError("traded_at: 올바른 날짜/시간 형식이 아닙니다")


class TradeCreate(BaseModel):
    trade_type: TradeType
    market_type: MarketType = "STOCK"
    account_id: str
    asset_name: str
    ticker_symbol: str
    country_code: CountryCode = "KR"
    exchange: str = ""
    traded_at: datetime
    price: float
    quantity: float
    commission: float = 0.0
    tax: float = 0.0

    @field_validator("account_id", mode="before")
    @classmethod
    def _trim_account_id(cls, v: object) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("account_id가 필요합니다.")
        return v.strip()

    @field_validator("asset_name", mode="before")
    @classmethod
    def _trim_asset_name(cls, v: object) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("종목명을 입력해주세요.")
        if len(v.strip()) > 100:
            raise ValueError("종목명은 100자 이내여야 합니다.")
        return v.strip()

    @field_validator("ticker_symbol", mode="before")
    @classmethod
    def _trim_ticker(cls, v: object) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("종목코드를 입력해주세요.")
        return v.strip()

    @field_validator("exchange", mode="before")
    @classmethod
    def _trim_exchange(cls, v: object) -> str:
        if v is None:
            return ""
        if isinstance(v, str):
            return v.strip()[:50]
        return str(v)[:50]

    @field_validator("traded_at", mode="before")
    @classmethod
    def _parse_traded_at(cls, v: object) -> datetime:
        return _traded_at_transform(v)

    @field_validator("price", "quantity", mode="before")
    @classmethod
    def _positive(cls, v: object) -> float:
        return _comma_positive(v)

    @field_validator("commission", "tax", mode="before")
    @classmethod
    def _non_negative(cls, v: object) -> float:
        return _comma_non_negative(v)


class TradeUpdate(BaseModel):
    market_type: MarketType | None = None
    price: float | None = None
    quantity: float | None = None
    commission: float | None = None
    tax: float | None = None
    strategy_type: StrategyType | None = None
    emotion: EmotionType | None = None
    reasoning_tags: list[ReasoningTag] | None = None
    buy_reason: str | None = None
    sell_reason: str | None = None
    result: TradeResult | None = None
    reflection_note: str | None = None
    improvement_note: str | None = None

    @field_validator("price", "quantity", mode="before")
    @classmethod
    def _positive(cls, v: object) -> float | None:
        if v is None:
            return None
        return _comma_positive(v)

    @field_validator("commission", "tax", mode="before")
    @classmethod
    def _non_negative(cls, v: object) -> float | None:
        if v is None:
            return None
        return _comma_non_negative(v)
