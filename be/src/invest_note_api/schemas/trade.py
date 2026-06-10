"""Trade POST/PATCH Pydantic 스키마.

validators.ts의 TradeCreateSchema / TradeUpdateSchema 포팅.
commaPositive / commaNonNegative → field_validator(mode="before")로 재현.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator, model_validator

from ..domain.trade_types import (
    CURRENCY_KRW,
    CountryCode,
    EmotionType,
    MAX_NAME_LEN,
    MarketType,
    ReasoningTag,
    StrategyType,
    TradeResult,
    TradeType,
    currency_for_country,
)
from ..domain.trade_utils import KST_OFFSET
from ..utils.numbers import strip_comma_number

TRADE_FREE_TEXT_MAX_LEN = 5000

# 해외(비-KRW) 거래에 거래 시점 환율이 누락(1.0)됐을 때의 에러 메시지.
# TradeCreate(model_validator)와 PATCH 라우터 가드가 공유 — 계약상 동일 문구 유지.
FOREIGN_EXCHANGE_RATE_REQUIRED_MSG = "해외 거래는 거래 시점 환율(exchange_rate)이 필요합니다."

# 원화(KRW: KR/OTHER) 거래에 1.0 이 아닌 환율을 지정했을 때의 에러 메시지.
# krw_normalized_trade 가 rate != 1.0 이면 무조건 ×rate 해 원가·손익을 부풀리므로 거부한다.
# TradeCreate(model_validator)와 PATCH 라우터 가드가 공유 — 계약상 동일 문구 유지.
KRW_EXCHANGE_RATE_FORBIDDEN_MSG = "원화 거래에는 환율을 지정할 수 없습니다."


def _comma_positive(v: object) -> float:
    """쉼표 포함 문자열/숫자 → 양수 float."""
    f = float(strip_comma_number(v))  # type: ignore[arg-type]
    if f <= 0:
        raise ValueError("양수여야 합니다.")
    return f


def _comma_non_negative(v: object) -> float:
    """쉼표 포함 문자열/숫자 → 0 이상 float."""
    f = float(strip_comma_number(v))  # type: ignore[arg-type]
    if f < 0:
        raise ValueError("0 이상이어야 합니다.")
    return f


def _traded_at_transform(raw: object) -> datetime:
    """KST 날짜/시간 문자열 → UTC datetime."""
    if isinstance(raw, datetime):
        traded_at = raw.astimezone(timezone.utc)
    elif not isinstance(raw, str) or not raw.strip():
        raise ValueError("날짜를 선택해주세요.")
    else:
        s = raw.strip()
        # "+09:00" suffix가 없으면 KST로 간주
        if not any(s.endswith(tz) for tz in (KST_OFFSET, "Z", "+00:00")) and "+" not in s[10:] and "Z" not in s:
            s = s + KST_OFFSET
        try:
            traded_at = datetime.fromisoformat(s).astimezone(timezone.utc)
        except ValueError:
            raise ValueError("traded_at: 올바른 날짜/시간 형식이 아닙니다")
    if traded_at > datetime.now(timezone.utc):
        raise ValueError("미래 날짜의 거래는 등록할 수 없습니다.")
    return traded_at


class TradeCreate(BaseModel):
    trade_type: TradeType
    market_type: MarketType = "STOCK"
    account_id: str
    asset_name: str
    ticker_symbol: str
    country_code: CountryCode = "KR"
    exchange: str = ""
    exchange_rate: float = 1.0
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
        stripped = v.strip()
        if ":" in stripped:
            raise ValueError("종목코드에 ':'를 포함할 수 없습니다.")
        return stripped

    @field_validator("exchange", mode="before")
    @classmethod
    def _trim_exchange(cls, v: object) -> str:
        if v is None:
            return ""
        if isinstance(v, str):
            return v.strip()[:MAX_NAME_LEN]
        return str(v)[:MAX_NAME_LEN]

    @field_validator("traded_at", mode="before")
    @classmethod
    def _parse_traded_at(cls, v: object) -> datetime:
        return _traded_at_transform(v)

    @field_validator("price", "quantity", "exchange_rate", mode="before")
    @classmethod
    def _positive(cls, v: object) -> float:
        return _comma_positive(v)

    @field_validator("commission", "tax", mode="before")
    @classmethod
    def _non_negative(cls, v: object) -> float:
        return _comma_non_negative(v)

    @model_validator(mode="after")
    def _foreign_requires_exchange_rate(self) -> "TradeCreate":
        # 비-KRW(해외) 거래는 거래 시점 환율이 필수. 기본값/누락(1.0)이면 native 금액을
        # KRW 로 간주해 원가·손익이 조용히 어긋나므로 거부한다.
        # 반대로 KRW(KR/OTHER) 거래에 1.0 이 아닌 환율을 지정하면 krw_normalized_trade 가
        # ×rate 로 원가·손익을 부풀리므로 미러 가드로 거부한다(역방향 가드).
        if currency_for_country(self.country_code) == CURRENCY_KRW:
            if self.exchange_rate != 1.0:
                raise ValueError(KRW_EXCHANGE_RATE_FORBIDDEN_MSG)
        elif self.exchange_rate == 1.0:
            raise ValueError(FOREIGN_EXCHANGE_RATE_REQUIRED_MSG)
        return self


class TradeUpdate(BaseModel):
    market_type: MarketType | None = None
    price: float | None = None
    quantity: float | None = None
    exchange_rate: float | None = None
    commission: float | None = None
    tax: float | None = None
    strategy_type: StrategyType | None = None
    emotion: EmotionType | None = None
    reasoning_tags: list[ReasoningTag] | None = None
    buy_reason: str | None = None
    sell_reason: str | None = None
    result: TradeResult | None = None

    @field_validator("buy_reason", "sell_reason")
    @classmethod
    def _free_text_max_len(cls, v: str | None) -> str | None:
        if v is not None and len(v) > TRADE_FREE_TEXT_MAX_LEN:
            raise ValueError(f"자유 텍스트는 {TRADE_FREE_TEXT_MAX_LEN}자 이내여야 합니다.")
        return v

    @field_validator("price", "quantity", "exchange_rate", mode="before")
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


class TradeBulkDeleteRequest(BaseModel):
    """기록 탭 다중 선택 일괄 삭제 요청 — 1~200건 제한."""

    ids: list[str] = Field(..., min_length=1, max_length=200)
