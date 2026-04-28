"""거래 import 공통 로직: 시그니처 dedup, 버킷팅."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class TradeSignature:
    """중복 판단 키. traded_at은 날짜 단위만 비교한다."""

    account_id: str
    trade_date: date          # date only (no time)
    identifier: str           # ticker 또는 asset_name (ticker 우선)
    trade_type: str           # "BUY" | "SELL"
    quantity: Decimal
    price: Decimal            # 소수점 2자리로 정규화


def _normalise_price(price: float | Decimal) -> Decimal:
    return Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def make_signature(
    account_id: str,
    trade_date: date,
    ticker: str | None,
    asset_name: str,
    trade_type: str,
    quantity: float | Decimal,
    price: float | Decimal,
) -> TradeSignature:
    identifier = ticker if ticker else asset_name
    return TradeSignature(
        account_id=account_id,
        trade_date=trade_date,
        identifier=identifier,
        trade_type=trade_type,
        quantity=Decimal(str(quantity)),
        price=_normalise_price(price),
    )


@dataclass
class ImportError:
    row_no: int
    reason: str
    raw: dict = field(default_factory=dict)


@dataclass
class ImportSummary:
    new_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0
    usd_skip_count: int = 0
    errors: list[ImportError] = field(default_factory=list)
