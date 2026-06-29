from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from invest_note_api.domain.trade_types import (
    TRADE_TYPE_SELL,
    currency_for_country,
    krw_normalized_trade,
    to_krw,
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
    name_ko: str | None
    account_id: str
    exchange: str
    running_qty: float
    running_cost: float         # KRW (거래 시점 환율 고정, primary)
    running_cost_native: float  # native 통화(USD 등) — 달러 보조 표시용
    realized_pnl: float         # KRW
    last_traded_at: str
    last_note_type: str | None
    last_note: str | None


LotMap = dict[str, Lot]  # lot_key → Lot (account_id 별 종목 잔량/원가 등)


@dataclass
class Position:
    key: str            # "TICKER:COUNTRY"
    ticker: str
    country: str
    currency: str       # 거래 통화(KRW|USD) — 달러 보조 표시 분기용
    asset_name: str
    exchange: str
    holding_quantity: float
    avg_buy_price: float          # KRW (거래 시점 환율 고정, primary)
    avg_buy_price_native: float   # native(USD 등) — 달러 보조
    cost_basis: float             # KRW (primary)
    cost_basis_native: float      # native
    realized_pnl: float           # KRW
    current_price: float | None   # native(USD 등) — 시세 그대로
    evaluation: float | None      # KRW (= current_price × qty × 현재환율, primary)
    evaluation_native: float | None  # native(= current_price × qty)
    unrealized_pnl: float | None  # KRW (= evaluation - cost_basis)
    last_note_type: str | None   # "근거" | "회고" | None
    last_note: str | None
    last_traded_at: str
    account_ids: list[str] = field(default_factory=list)
    # 표시용 한글명(US). asset_name(계산 키)과 별개, 표시 전용.
    # ⚠️ trades 로더가 stocks.name_ko 를 실어줄 때만 채워진다(list_trades_with_account 의 LEFT JOIN).
    # JOIN 없는 list_trades(SELECT *)로 들어온 거래로 만든 Position 은 항상 None(분석 탭 경로 — 의도).
    name_ko: str | None = None


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
        running_cost = 0.0          # KRW (정규화 walk)
        running_cost_native = 0.0   # native (원본 price walk)
        realized_pnl = 0.0
        last_traded_at = first.traded_at.isoformat()
        last_note_type: str | None = None
        last_note: str | None = None

        # 동일 정렬 순서의 두 walk 를 병렬로 진행: 정규화(KRW) + 원본(native).
        # 원가/평단은 KRW(primary)를, native(USD)는 달러 보조 표시용으로 함께 추적한다.
        # stored_avg_cost_deduction 은 SELL 의 avg_buy_price(KRW 저장값)를 쓰므로 정규화 walk 와
        # 일관(둘 다 KRW). native walk 는 avg_buy_price 가 native 가 아니라 KRW 라 부정확할 수
        # 있어 recomputed(running) 차감을 써서 native 원가를 일관 산출한다.
        krw_walk = walk_trades(
            [krw_normalized_trade(t) for t in lot_trades],
            group_filter=lambda _t: True,
            sort_fn=sort_for_calc,
            cost_deduction=stored_avg_cost_deduction,
            track_fifo_lots=False,
        )
        native_walk = walk_trades(
            lot_trades,
            group_filter=lambda _t: True,
            sort_fn=sort_for_calc,
            track_fifo_lots=False,
        )
        for ev, ev_native in zip(krw_walk, native_walk):
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
            running_cost_native = ev_native.state_after.running_cost

        lot_map[lot_key] = Lot(
            ticker=trade_identifier(first),
            country=trade_country(first),
            asset_name=first.asset_name,
            name_ko=first.name_ko,
            account_id=str(first.account_id),
            exchange=exchange,
            running_qty=running_qty,
            running_cost=running_cost,
            running_cost_native=running_cost_native,
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
                "name_ko": lot.name_ko,
                "exchange": lot.exchange,
                "running_qty": 0.0,
                "running_cost": 0.0,
                "running_cost_native": 0.0,
                "realized_pnl": 0.0,
                "last_traded_at": lot.last_traded_at,
                "account_ids": set(),
                "last_note_type": None,
                "last_note": None,
            }
        pos = pos_map[display_key]
        pos["running_qty"] += lot.running_qty
        pos["running_cost"] += lot.running_cost
        pos["running_cost_native"] += lot.running_cost_native
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
        avg_buy_price_native = (
            pos["running_cost_native"] / holding_qty if holding_qty > 0 else 0.0
        )
        positions.append(Position(
            key=key,
            ticker=pos["ticker"],
            country=pos["country"],
            currency=currency_for_country(pos["country"]),
            asset_name=pos["asset_name"],
            name_ko=pos["name_ko"],
            exchange=pos["exchange"],
            holding_quantity=holding_qty,
            avg_buy_price=avg_buy_price,
            avg_buy_price_native=avg_buy_price_native,
            cost_basis=pos["running_cost"],
            cost_basis_native=pos["running_cost_native"],
            realized_pnl=pos["realized_pnl"],
            current_price=None,
            evaluation=None,
            evaluation_native=None,
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

    자산 추이 차트(`/assets/history`)는 단일 country 로 스코프되어 단일 통화이므로 native
    통화 합산을 그대로 쓴다(차트 series 와 같은 단위 유지 — KRW 환산하면 단위 불일치).
    보유가 없으면 None.
    """
    positions, _ = build_positions(trades)
    # 자산 추이 차트는 단일 country(통화)이므로 native cost_basis 합산(차트 series 와 같은 단위).
    invested = sum(p.cost_basis_native for p in positions if p.holding_quantity > 0)
    return invested if invested > 0 else None


def merge_quotes(
    positions: list[Position], quotes: QuoteMap, usdkrw: float | None = None
) -> list[Position]:
    """시세를 포지션에 overlay. current_price 는 native(시세 그대로). 평가액은 현재 환율로
    KRW(primary)와 native 를 함께 산출. 원가는 KRW 고정(거래 시점 환율)이므로 환산 불필요.

    해외인데 현재 환율(usdkrw)을 못 받으면 evaluation(KRW)=None(미실현 미상) — 원가 KRW 는 유지.
    """
    result = []
    for pos in positions:
        quote = quotes.get(pos.key)
        if not quote:
            result.append(pos)
            continue
        price = quote["price"]
        evaluation_native = price * pos.holding_quantity
        evaluation_krw = to_krw(evaluation_native, pos.currency, usdkrw)
        unrealized = (
            evaluation_krw - pos.cost_basis if evaluation_krw is not None else None
        )
        result.append(replace(
            pos,
            current_price=price,
            evaluation=evaluation_krw,
            evaluation_native=evaluation_native,
            unrealized_pnl=unrealized,
        ))
    return result


def build_account_snapshots(
    accounts: list[Account],
    lot_map: LotMap,
    quotes: QuoteMap,
    usdkrw: float | None = None,
) -> list[AccountSnapshot]:
    """`build_positions` 가 반환한 lot_map 을 재사용해 계좌별 stock_evaluation 집계(KRW).

    trades 풀스캔 없이 lot 의 running_qty 와 quote.price 만으로 평가액을 계산하고,
    통화별 평가액을 `usdkrw` 로 KRW 환산해 합산한다(현금은 KRW 가정). 환산 불가 lot 은 제외.
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
                krw = to_krw(
                    quote["price"] * lot.running_qty,
                    currency_for_country(lot.country),
                    usdkrw,
                )
                if krw is not None:
                    stock_evaluation += krw

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
    """포트폴리오 totals 집계(KRW 단일값).

    evaluation/unrealized 는 merge_quotes 가 이미 KRW(현재 환율 환산)로 채웠고, 원가·실현손익은
    거래 시점 환율로 KRW 고정이라 추가 환산이 필요 없다. evaluation 이 None 인 포지션(시세 없음
    또는 해외인데 현재 환율 미수신)은 합산에서 빠지고 `missing_quote_tickers` 로 노출된다.

    `pnl_map` 은 호출자가 `build_pnl_map(trades)`(저장 profit_loss=KRW)로 빌드해 주입한다.
    """
    total_evaluation = sum(p.evaluation or 0.0 for p in positions)
    total_unrealized_pnl = sum(p.unrealized_pnl or 0.0 for p in positions)
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

    # evaluation 이 None = 시세 없음 또는 해외인데 현재 환율 미수신 → KRW 평가액 미상.
    missing_quote_tickers = [p.asset_name for p in positions if p.evaluation is None]

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
