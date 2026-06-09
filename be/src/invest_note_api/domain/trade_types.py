from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable, Literal
from uuid import UUID

from pydantic import BaseModel, field_validator


TradeType = Literal["BUY", "SELL"]
MarketType = Literal["STOCK", "CRYPTO", "ETC"]
StrategyType = Literal["SCALPING", "SWING", "LONG_TERM", "UNKNOWN"]
EmotionType = Literal["CONFIDENT", "ANXIOUS", "FOMO", "IMPULSIVE", "CALM"]
ReasoningTag = Literal["TECHNICAL", "FUNDAMENTAL", "NEWS", "FEELING"]
TradeResult = Literal["SUCCESS", "FAIL", "BREAKEVEN"]
CountryCode = Literal["KR", "US", "OTHER"]
UntaggedLiteral = Literal["UNTAGGED"]
EmotionBucket = EmotionType | UntaggedLiteral
ReasoningTagBucket = ReasoningTag | UntaggedLiteral

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
# 분석 집계에서 emotion/reasoning_tags 미입력 SELL을 묶기 위한 표시 전용 키.
# 사용자가 직접 선택할 수 없는 값이므로 폼 옵션 배열에는 포함하지 않는다.
EMOTION_UNTAGGED: UntaggedLiteral = "UNTAGGED"
TAG_UNTAGGED: UntaggedLiteral = "UNTAGGED"
RESULT_SUCCESS: TradeResult = "SUCCESS"
RESULT_FAIL: TradeResult = "FAIL"
RESULT_BREAKEVEN: TradeResult = "BREAKEVEN"
DEFAULT_COUNTRY: CountryCode = "KR"
COUNTRY_US: CountryCode = "US"

Currency = Literal["KRW", "USD"]
CURRENCY_KRW: Currency = "KRW"
CURRENCY_USD: Currency = "USD"

MAX_CODE_LEN = 20
MAX_NAME_LEN = 50


def trade_identifier(trade: "Trade") -> str:
    """ticker_symbol 우선, 없으면 asset_name. lot/포지션 그룹핑의 1차 키."""
    return trade.ticker_symbol or trade.asset_name


def trade_country(trade: "Trade") -> str:
    """country_code fallback to DEFAULT_COUNTRY (KR). 빈 문자열도 KR로 정규화."""
    return trade.country_code or DEFAULT_COUNTRY


def currency_for_country(country: str) -> Currency:
    """country_code → 거래 통화. US=USD, 그 외(KR/OTHER)=KRW."""
    return CURRENCY_USD if country == COUNTRY_US else CURRENCY_KRW


def to_krw(value: float, currency: str, usdkrw: float | None) -> float | None:
    """native 통화 금액을 KRW 로 환산. KRW 는 그대로, USD 는 ×usdkrw.

    환산 불가(USD 인데 환율 None, 또는 미지원 통화)면 None — 호출측이 missing 으로 처리해
    조용한 통화 혼재 합산을 막는다(KR 은 항상 환산 성공이라 영향 없음).
    """
    if currency == CURRENCY_KRW:
        return value
    if currency == CURRENCY_USD:
        return value * usdkrw if usdkrw is not None else None
    return None


def krw_normalized_trade(trade: "Trade") -> "Trade":
    """거래의 native 금액(price/commission/tax)을 거래 시점 환율로 KRW 로 정규화한 사본.

    계산 엔진(walker/realized_pnl)이 KRW 단일 통화로 동작하게 하는 전처리. 수량·시각·정렬
    키는 불변이라 FIFO·정렬 불변식에 영향 없다. `exchange_rate=1.0` 으로 두어 이중 적용 방지.
    KR(rate=1.0)은 그대로 반환(불필요한 copy 회피).
    """
    rate = trade.exchange_rate or 1.0
    if rate == 1.0:
        return trade
    return trade.model_copy(
        update={
            "price": trade.price * rate,
            "commission": trade.commission * rate,
            "tax": trade.tax * rate,
            "exchange_rate": 1.0,
        }
    )


def _decimal_to_number(v: object, conv: Callable[[Decimal], float | int]) -> object:
    if isinstance(v, Decimal):
        return conv(v)
    return v


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

    profit_loss: float | None = None
    avg_buy_price: float | None = None
    holding_days: int | None = None

    country_code: str = DEFAULT_COUNTRY
    exchange: str = ""
    # 거래 시점 환율(native→KRW). KR=1.0. KRW 금액 = native × exchange_rate.
    exchange_rate: float = 1.0

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

    @field_validator(
        "price", "quantity", "total_amount", "commission", "tax", "exchange_rate", mode="before"
    )
    @classmethod
    def _decimal_to_float(cls, v: object) -> float:
        return _decimal_to_number(v, float)  # type: ignore[return-value]

    @field_validator("profit_loss", "avg_buy_price", mode="before")
    @classmethod
    def _decimal_to_float_optional(cls, v: object) -> float | None:
        return _decimal_to_number(v, float)  # type: ignore[return-value]

    @field_validator("holding_days", mode="before")
    @classmethod
    def _decimal_to_int_optional(cls, v: object) -> int | None:
        return _decimal_to_number(v, int)  # type: ignore[return-value]

    model_config = {"from_attributes": True}


class TradeWithAccount(Trade):
    account_name: str | None = None
    account_broker: str | None = None
