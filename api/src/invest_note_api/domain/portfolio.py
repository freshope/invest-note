from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from invest_note_api.domain.trade_types import DEFAULT_COUNTRY, TRADE_TYPE_BUY, TRADE_TYPE_SELL
from invest_note_api.domain.trade_utils import to_kst
from invest_note_api.domain.realized_pnl import build_pnl_map

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import Trade

NOTE_TYPE_REASON = "근거"
NOTE_TYPE_REFLECTION = "회고"


@dataclass
class Account:
    id: str
    user_id: str
    name: str
    broker: str | None
    cash_balance: float
    created_at: datetime
    updated_at: datetime


QuoteEntry = dict  # {"price": float, "currency": str, "as_of": str}
QuoteMap = dict[str, QuoteEntry | None]  # key: "TICKER:COUNTRY"


@dataclass
class Position:
    key: str            # "TICKER:COUNTRY"
    ticker: str
    country: str
    asset_name: str
    exchange: str
    holding_quantity: float
    avg_buy_price: float
    cost_basis: float
    realized_pnl: float
    current_price: float | None
    evaluation: float | None
    unrealized_pnl: float | None
    last_note_type: str | None   # "근거" | "회고" | None
    last_note: str | None
    last_traded_at: str
    account_ids: list[str] = field(default_factory=list)


@dataclass
class AccountSnapshot:
    account: Account
    stock_evaluation: float
    cash_balance: float
    total_value: float


@dataclass
class DashboardTotals:
    total_evaluation: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    total_cash: float
    total_assets: float
    month_realized_pnl: float
    month_trade_count: int
    missing_quote_tickers: list[str]


def build_positions(trades: list["Trade"]) -> list[Position]:
    """계좌별 lot 추적 → 종목별 포지션 집계."""
    lot_map: dict[str, dict] = {}

    sorted_trades = sorted(trades, key=lambda t: t.traded_at)

    for trade in sorted_trades:
        ticker = trade.ticker_symbol or trade.asset_name
        country = trade.country_code or DEFAULT_COUNTRY
        lot_key = f"{ticker}:{country}:{trade.account_id}"

        if lot_key not in lot_map:
            lot_map[lot_key] = {
                "ticker": ticker,
                "country": country,
                "asset_name": trade.asset_name,
                "account_id": trade.account_id,
                "exchange": trade.exchange,
                "running_qty": 0.0,
                "running_cost": 0.0,
                "realized_pnl": 0.0,
                "last_traded_at": trade.traded_at.isoformat(),
                "last_note_type": None,
                "last_note": None,
            }

        lot = lot_map[lot_key]
        lot["last_traded_at"] = trade.traded_at.isoformat()
        if trade.exchange:
            lot["exchange"] = trade.exchange

        if trade.trade_type == TRADE_TYPE_BUY:
            lot["running_qty"] += trade.quantity
            lot["running_cost"] += trade.price * trade.quantity
            reason = (trade.buy_reason or "").strip()
            if reason:
                lot["last_note_type"] = NOTE_TYPE_REASON
                lot["last_note"] = reason
        else:
            avg_cost = trade.avg_buy_price or 0.0
            matched_qty = min(trade.quantity, lot["running_qty"])
            lot["realized_pnl"] += trade.profit_loss or 0.0
            lot["running_cost"] = max(0.0, lot["running_cost"] - avg_cost * matched_qty)
            lot["running_qty"] = max(0.0, lot["running_qty"] - trade.quantity)
            note = (trade.sell_reason or "").strip()
            if note:
                lot["last_note_type"] = NOTE_TYPE_REFLECTION
                lot["last_note"] = note

    # lot → position 집계 (보유수량 > 0인 lot만)
    pos_map: dict[str, dict] = {}

    for lot in lot_map.values():
        if lot["running_qty"] <= 0:
            continue
        display_key = f"{lot['ticker']}:{lot['country']}"
        if display_key not in pos_map:
            pos_map[display_key] = {
                "ticker": lot["ticker"],
                "country": lot["country"],
                "asset_name": lot["asset_name"],
                "exchange": lot["exchange"],
                "running_qty": 0.0,
                "running_cost": 0.0,
                "realized_pnl": 0.0,
                "last_traded_at": lot["last_traded_at"],
                "account_ids": set(),
                "last_note_type": None,
                "last_note": None,
            }
        pos = pos_map[display_key]
        pos["running_qty"] += lot["running_qty"]
        pos["running_cost"] += lot["running_cost"]
        pos["realized_pnl"] += lot["realized_pnl"]
        if lot["last_traded_at"] > pos["last_traded_at"]:
            pos["last_traded_at"] = lot["last_traded_at"]
        if lot["exchange"]:
            pos["exchange"] = lot["exchange"]
        pos["account_ids"].add(lot["account_id"])
        if lot["last_note_type"]:
            pos["last_note_type"] = lot["last_note_type"]
            pos["last_note"] = lot["last_note"]

    positions: list[Position] = []
    for key, pos in pos_map.items():
        holding_qty = pos["running_qty"]
        avg_buy_price = pos["running_cost"] / holding_qty if holding_qty > 0 else 0.0
        positions.append(Position(
            key=key,
            ticker=pos["ticker"],
            country=pos["country"],
            asset_name=pos["asset_name"],
            exchange=pos["exchange"],
            holding_quantity=holding_qty,
            avg_buy_price=avg_buy_price,
            cost_basis=pos["running_cost"],
            realized_pnl=pos["realized_pnl"],
            current_price=None,
            evaluation=None,
            unrealized_pnl=None,
            last_note_type=pos["last_note_type"],
            last_note=pos["last_note"],
            last_traded_at=pos["last_traded_at"],
            account_ids=list(pos["account_ids"]),
        ))

    return positions


def merge_quotes(positions: list[Position], quotes: QuoteMap) -> list[Position]:
    result = []
    for pos in positions:
        quote = quotes.get(pos.key)
        if not quote:
            result.append(pos)
            continue
        evaluation = quote["price"] * pos.holding_quantity
        result.append(Position(
            **{
                **pos.__dict__,
                "current_price": quote["price"],
                "evaluation": evaluation,
                "unrealized_pnl": evaluation - pos.cost_basis,
            }
        ))
    return result


def build_account_snapshots(
    accounts: list[Account],
    trades: list["Trade"],
    quotes: QuoteMap,
) -> list[AccountSnapshot]:
    by_account: dict[str, list["Trade"]] = {}
    for t in trades:
        by_account.setdefault(t.account_id, []).append(t)

    snapshots = []
    for account in accounts:
        account_trades = by_account.get(str(account.id), [])
        pos_map: dict[str, dict] = {}

        for trade in account_trades:
            ticker = trade.ticker_symbol or trade.asset_name
            key = f"{ticker}:{trade.country_code or DEFAULT_COUNTRY}"
            if key not in pos_map:
                pos_map[key] = {"qty": 0.0, "cost_basis": 0.0}
            p = pos_map[key]
            if trade.trade_type == TRADE_TYPE_BUY:
                p["qty"] += trade.quantity
                p["cost_basis"] += trade.price * trade.quantity
            else:
                p["qty"] -= trade.quantity

        stock_evaluation = 0.0
        for key, p in pos_map.items():
            if p["qty"] <= 0:
                continue
            quote = quotes.get(key)
            if quote:
                stock_evaluation += quote["price"] * p["qty"]

        snapshots.append(AccountSnapshot(
            account=account,
            stock_evaluation=stock_evaluation,
            cash_balance=account.cash_balance,
            total_value=stock_evaluation + account.cash_balance,
        ))

    return snapshots


def build_totals(
    positions: list[Position],
    accounts: list[Account],
    trades: list["Trade"],
) -> DashboardTotals:
    total_evaluation = sum(p.evaluation or 0 for p in positions)
    total_unrealized_pnl = sum(p.unrealized_pnl or 0 for p in positions)
    total_cash = sum(a.cash_balance for a in accounts)

    now = to_kst(datetime.now(timezone.utc))
    this_year = now.year
    this_month = now.month

    pnl_map = build_pnl_map(trades)

    total_realized_pnl = 0.0
    month_realized_pnl = 0.0
    month_trade_count = 0

    for trade in trades:
        if trade.trade_type == TRADE_TYPE_SELL:
            total_realized_pnl += pnl_map.get(trade.id, 0.0)
        kst = to_kst(trade.traded_at)
        if kst.year == this_year and kst.month == this_month:
            month_trade_count += 1
            if trade.trade_type == TRADE_TYPE_SELL:
                month_realized_pnl += pnl_map.get(trade.id, 0.0)

    missing_quote_tickers = [p.asset_name for p in positions if p.current_price is None]

    return DashboardTotals(
        total_evaluation=total_evaluation,
        total_unrealized_pnl=total_unrealized_pnl,
        total_realized_pnl=total_realized_pnl,
        total_cash=total_cash,
        total_assets=total_evaluation + total_cash,
        month_realized_pnl=month_realized_pnl,
        month_trade_count=month_trade_count,
        missing_quote_tickers=missing_quote_tickers,
    )
