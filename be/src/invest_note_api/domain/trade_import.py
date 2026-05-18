"""거래 import 공통 로직: 시그니처 dedup, 버킷팅, 머지 patch."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING

from invest_note_api.domain.trade_utils import to_kst

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import Trade


@dataclass(frozen=True)
class TradeSignature:
    """중복 판단 키 (commit 경로). traded_at은 날짜 단위만 비교한다."""

    account_id: str
    trade_date: date          # date only (no time)
    identifier: str           # ticker 또는 asset_name (ticker 우선)
    trade_type: str           # "BUY" | "SELL"
    quantity: Decimal
    price: Decimal            # 소수점 2자리로 정규화


@dataclass(frozen=True)
class PreviewSignature:
    """import preview 경로 dedup 키. account_id 가 아직 결정되지 않은 단계에서 사용.

    commit 시점에는 정확한 account_id 기반의 `TradeSignature` 로 dedup 이 재실행되므로
    preview 의 dup_count 는 참고용 카운트.
    """

    trade_date: date
    identifier: str
    trade_type: str
    quantity: Decimal
    price: Decimal


def _normalise_price(price: float | Decimal) -> Decimal:
    return Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _signature_fields(
    *,
    trade_date: date,
    ticker: str | None,
    asset_name: str,
    trade_type: str,
    quantity: float | Decimal,
    price: float | Decimal,
) -> dict:
    return {
        "trade_date": trade_date,
        "identifier": ticker if ticker else asset_name,
        "trade_type": trade_type,
        "quantity": Decimal(str(quantity)),
        "price": _normalise_price(price),
    }


def _trade_signature_kwargs(trade: "Trade") -> dict:
    # KST 기준 date — import 측 `pt.traded_at_kst` 와 동일한 시간대로 비교해야
    # KST 새벽(00~08시)에 수동 등록된 거래도 거래내역서 일자와 매칭된다.
    return {
        "trade_date": to_kst(trade.traded_at).date(),
        "ticker": trade.ticker_symbol,
        "asset_name": trade.asset_name,
        "trade_type": trade.trade_type,
        "quantity": trade.quantity,
        "price": trade.price,
    }


def make_signature(
    account_id: str,
    trade_date: date,
    ticker: str | None,
    asset_name: str,
    trade_type: str,
    quantity: float | Decimal,
    price: float | Decimal,
) -> TradeSignature:
    return TradeSignature(
        account_id=account_id,
        **_signature_fields(
            trade_date=trade_date,
            ticker=ticker,
            asset_name=asset_name,
            trade_type=trade_type,
            quantity=quantity,
            price=price,
        ),
    )


def make_preview_signature(
    trade_date: date,
    ticker: str | None,
    asset_name: str,
    trade_type: str,
    quantity: float | Decimal,
    price: float | Decimal,
) -> PreviewSignature:
    return PreviewSignature(
        **_signature_fields(
            trade_date=trade_date,
            ticker=ticker,
            asset_name=asset_name,
            trade_type=trade_type,
            quantity=quantity,
            price=price,
        ),
    )


def trade_to_signature(trade: "Trade", account_id: str) -> TradeSignature:
    """저장된 Trade row → commit 경로 시그니처."""
    return make_signature(account_id=account_id, **_trade_signature_kwargs(trade))


def trade_to_preview_signature(trade: "Trade") -> PreviewSignature:
    """저장된 Trade row → preview 경로 시그니처 (account_id 무관)."""
    return make_preview_signature(**_trade_signature_kwargs(trade))


def parse_kst_date(s: str) -> date | None:
    """KST ISO 문자열의 앞 10자(YYYY-MM-DD)를 date 로 파싱. 실패 시 None."""
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _money_decimal(v: float | Decimal | int) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_merge_patch(existing: "Trade", row: dict) -> dict:
    """기존 Trade 와 staging row 를 비교해 머지로 update 할 필드만 반환한다.

    비교 대상은 거래내역서 출처 필드 중 시그니처에 포함되지 않는 것들:
    - commission, tax: 소수점 2자리 quantize 후 비교 (부동소수 정밀도 회피)
    - traded_at: row 에 `traded_at_utc` (datetime) 가 있을 때만 비교. 없으면 보존.

    Returns:
        변경된 필드만 담은 dict. 완전히 동일하면 빈 dict.
    """
    patch: dict = {}

    if _money_decimal(row["commission"]) != _money_decimal(existing.commission):
        patch["commission"] = float(_money_decimal(row["commission"]))

    if _money_decimal(row["tax"]) != _money_decimal(existing.tax):
        patch["tax"] = float(_money_decimal(row["tax"]))

    row_traded_at: datetime | None = row.get("traded_at_utc")
    if row_traded_at is not None and row_traded_at != existing.traded_at:
        patch["traded_at"] = row_traded_at

    return patch


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
