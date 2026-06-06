from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from invest_note_api.domain.trade_types import (
    TRADE_TYPE_SELL,
    trade_country,
    trade_identifier,
)
from invest_note_api.domain.realized_pnl import sort_for_calc
from invest_note_api.domain.trade_utils import position_key, to_kst
from invest_note_api.domain.trade_walker import (
    stored_avg_cost_deduction,
    walk_trades,
)

if TYPE_CHECKING:
    from invest_note_api.domain.trade_types import Trade

NOTE_TYPE_REASON = "근거"
NOTE_TYPE_SELL = "매도이유"


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


@dataclass(frozen=True)
class Lot:
    ticker: str
    country: str
    asset_name: str
    account_id: str
    exchange: str
    running_qty: float
    running_cost: float
    realized_pnl: float
    last_traded_at: str
    last_note_type: str | None
    last_note: str | None


LotMap = dict[str, Lot]  # lot_key → Lot (account_id 별 종목 잔량/원가 등)


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


@dataclass(frozen=True)
class AccountHolding:
    key: str        # "TICKER:COUNTRY" — position.key 와 동일 규칙
    quantity: float


@dataclass
class AccountSnapshot:
    account: Account
    stock_evaluation: float
    cash_balance: float
    total_value: float
    holdings: list[AccountHolding] = field(default_factory=list)


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


def _lot_key_of(trade: "Trade") -> str:
    return f"{position_key(trade_identifier(trade), trade_country(trade))}:{trade.account_id}"


def _build_lot_map(trades: list["Trade"]) -> LotMap:
    """trades → lot_map: 계좌별 종목 lot 의 walker 누산.

    각 lot 그룹마다 walker 를 돌려 terminal 누산값과 BUY/SELL 메타(마지막 note,
    실현손익 합계) 를 frozen `Lot` 으로 등록한다.
    """
    trades_by_lot: dict[str, list["Trade"]] = defaultdict(list)
    for trade in trades:
        trades_by_lot[_lot_key_of(trade)].append(trade)

    lot_map: LotMap = {}
    for lot_key, lot_trades in trades_by_lot.items():
        first = lot_trades[0]
        # walk 루프 동안 가변 누산 — 종료 시점에 frozen Lot 인스턴스로 등록
        exchange = ""
        running_qty = 0.0
        running_cost = 0.0
        realized_pnl = 0.0
        last_traded_at = first.traded_at.isoformat()
        last_note_type: str | None = None
        last_note: str | None = None

        for ev in walk_trades(
            lot_trades,
            group_filter=lambda _t: True,
            sort_fn=sort_for_calc,
            cost_deduction=stored_avg_cost_deduction,
            track_fifo_lots=False,
        ):
            last_traded_at = ev.trade.traded_at.isoformat()
            if ev.trade.exchange:
                exchange = ev.trade.exchange
            if ev.kind == "BUY":
                reason = (ev.trade.buy_reason or "").strip()
                if reason:
                    last_note_type = NOTE_TYPE_REASON
                    last_note = reason
            else:
                realized_pnl += ev.trade.profit_loss or 0.0
                note = (ev.trade.sell_reason or "").strip()
                if note:
                    last_note_type = NOTE_TYPE_SELL
                    last_note = note
            running_qty = ev.state_after.running_qty
            running_cost = ev.state_after.running_cost

        lot_map[lot_key] = Lot(
            ticker=trade_identifier(first),
            country=trade_country(first),
            asset_name=first.asset_name,
            account_id=str(first.account_id),
            exchange=exchange,
            running_qty=running_qty,
            running_cost=running_cost,
            realized_pnl=realized_pnl,
            last_traded_at=last_traded_at,
            last_note_type=last_note_type,
            last_note=last_note,
        )
    return lot_map


def _lot_to_positions(lot_map: LotMap) -> list[Position]:
    """lot_map → positions: 보유수량 > 0 lot 을 종목별(`TICKER:COUNTRY`) 로 집계."""
    pos_map: dict[str, dict] = {}
    for lot in lot_map.values():
        if lot.running_qty <= 0:
            continue
        display_key = position_key(lot.ticker, lot.country)
        if display_key not in pos_map:
            pos_map[display_key] = {
                "ticker": lot.ticker,
                "country": lot.country,
                "asset_name": lot.asset_name,
                "exchange": lot.exchange,
                "running_qty": 0.0,
                "running_cost": 0.0,
                "realized_pnl": 0.0,
                "last_traded_at": lot.last_traded_at,
                "account_ids": set(),
                "last_note_type": None,
                "last_note": None,
            }
        pos = pos_map[display_key]
        pos["running_qty"] += lot.running_qty
        pos["running_cost"] += lot.running_cost
        pos["realized_pnl"] += lot.realized_pnl
        if lot.last_traded_at > pos["last_traded_at"]:
            pos["last_traded_at"] = lot.last_traded_at
        if lot.exchange:
            pos["exchange"] = lot.exchange
        pos["account_ids"].add(lot.account_id)
        if lot.last_note_type:
            pos["last_note_type"] = lot.last_note_type
            pos["last_note"] = lot.last_note

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


def build_positions(trades: list["Trade"]) -> tuple[list[Position], LotMap]:
    """계좌별 lot 추적 → 종목별 포지션 집계.

    Returns:
        (positions, lot_map): 보유 수량 > 0인 포지션 리스트와 lot_key → Lot.
        `lot_map` 은 `build_account_snapshots` 등 후속 단계에서 재사용된다.
    """
    lot_map = _build_lot_map(trades)
    positions = _lot_to_positions(lot_map)
    return positions, lot_map


def holding_invested_amount(trades: list["Trade"]) -> float | None:
    """현재 보유분 매수 원금(cost_basis 합) — 자산 차트 손익 가이드 라인 기준값.

    대시보드 평가손익과 동일한 walker 기반 cost_basis 를 사용한다. 보유가 없으면 None.
    """
    positions, _ = build_positions(trades)
    invested = sum(p.cost_basis for p in positions if p.holding_quantity > 0)
    return invested if invested > 0 else None


def merge_quotes(positions: list[Position], quotes: QuoteMap) -> list[Position]:
    result = []
    for pos in positions:
        quote = quotes.get(pos.key)
        if not quote:
            result.append(pos)
            continue
        evaluation = quote["price"] * pos.holding_quantity
        result.append(replace(
            pos,
            current_price=quote["price"],
            evaluation=evaluation,
            unrealized_pnl=evaluation - pos.cost_basis,
        ))
    return result


def build_account_snapshots(
    accounts: list[Account],
    lot_map: LotMap,
    quotes: QuoteMap,
) -> list[AccountSnapshot]:
    """`build_positions` 가 반환한 lot_map 을 재사용해 계좌별 stock_evaluation 집계.

    trades 풀스캔 없이 lot 의 running_qty 와 quote.price 만으로 평가액을 계산한다.
    """
    by_account: dict[str, list[Lot]] = defaultdict(list)
    for lot in lot_map.values():
        by_account[str(lot.account_id)].append(lot)

    snapshots = []
    for account in accounts:
        account_lots = by_account.get(str(account.id), [])
        stock_evaluation = 0.0
        holdings: list[AccountHolding] = []
        for lot in account_lots:
            if lot.running_qty <= 0:
                continue
            quote_key = position_key(lot.ticker, lot.country)
            holdings.append(AccountHolding(key=quote_key, quantity=lot.running_qty))
            quote = quotes.get(quote_key)
            if quote:
                stock_evaluation += quote["price"] * lot.running_qty

        snapshots.append(AccountSnapshot(
            account=account,
            stock_evaluation=stock_evaluation,
            cash_balance=account.cash_balance,
            total_value=stock_evaluation + account.cash_balance,
            holdings=holdings,
        ))

    return snapshots


def build_totals(
    positions: list[Position],
    accounts: list[Account],
    trades: list["Trade"],
    pnl_map: dict[str, float],
) -> DashboardTotals:
    """포트폴리오 totals 집계.

    `pnl_map` 은 호출자가 `build_pnl_map(trades)` 로 미리 빌드해 주입한다.
    내부에서 다시 빌드하지 않으므로 summary 핫패스에서 trades 풀스캔이 1회 줄어든다.
    """
    total_evaluation = sum(p.evaluation or 0 for p in positions)
    total_unrealized_pnl = sum(p.unrealized_pnl or 0 for p in positions)
    total_cash = sum(a.cash_balance for a in accounts)

    now = to_kst(datetime.now(timezone.utc))
    this_year = now.year
    this_month = now.month

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
