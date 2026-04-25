"""portfolio 라우터 — holding + summary."""
from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Query

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import acquire_for_user, get_pool
from invest_note_api.domain.holdings import compute_total_holding, compute_wac
from invest_note_api.domain.portfolio import (
    Account,
    build_account_snapshots,
    build_positions,
    build_totals,
    merge_quotes,
)
from invest_note_api.domain.trade_types import Trade, TradeWithAccount
from invest_note_api.errors import APIError
from invest_note_api.external.quotes import fetch_quotes_by_keys

router = APIRouter(prefix="/api/portfolio")


def _account_from_row(row) -> Account:
    d = dict(row)
    for field in ("id", "user_id"):
        if field in d and d[field] is not None:
            d[field] = str(d[field])
    if "cash_balance" in d and d["cash_balance"] is not None:
        d["cash_balance"] = float(d["cash_balance"])
    return Account(**d)


@router.get("/holding")
async def get_holding(
    account_id: str = Query(alias="accountId"),
    asset_name: str = Query(alias="assetName"),
    ticker: str | None = Query(default=None),
    country: str = Query(default="KR"),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    if not account_id or not asset_name:
        raise APIError("accountId, assetName은 필수입니다.", 400)

    async with acquire_for_user(pool, user.id) as conn:
        rows = await conn.fetch(
            """
            SELECT trade_type, quantity, price, ticker_symbol, asset_name,
                   country_code, account_id, traded_at,
                   id, user_id, market_type, total_amount,
                   strategy_type, reasoning_tags, buy_reason, sell_reason,
                   emotion, result, reflection_note, improvement_note,
                   profit_loss, avg_buy_price, exchange, commission, tax,
                   created_at, updated_at
            FROM trades
            WHERE user_id = $1
            ORDER BY traded_at ASC
            """,
            user.id,
        )

    trades = [Trade(**dict(r)) for r in rows]

    quantity = compute_total_holding(
        trades,
        ticker=ticker,
        asset_name=asset_name,
        country=country,
        account_id=account_id,
    )
    avg_buy_price = compute_wac(
        trades,
        ticker=ticker,
        asset_name=asset_name,
        country=country,
        account_id=account_id,
    )

    return {"quantity": quantity, "avgBuyPrice": avg_buy_price}


@router.get("/summary")
async def get_portfolio_summary(
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    async with acquire_for_user(pool, user.id) as conn:
        trade_rows = await conn.fetch(
            """
            SELECT t.*,
                   a.name  AS account_name,
                   a.broker AS account_broker
            FROM trades t
            LEFT JOIN accounts a ON a.id = t.account_id
            WHERE t.user_id = $1
            ORDER BY t.traded_at DESC
            """,
            user.id,
        )
        account_rows = await conn.fetch(
            "SELECT * FROM accounts ORDER BY created_at ASC"
        )

    trades = [TradeWithAccount(**dict(r)) for r in trade_rows]
    accounts = [_account_from_row(r) for r in account_rows]

    positions0 = build_positions(trades)

    quotes = {}
    try:
        quotes = await fetch_quotes_by_keys([p.key for p in positions0])
    except Exception:
        pass

    positions = merge_quotes(positions0, quotes)
    snapshots = build_account_snapshots(accounts, trades, quotes)
    totals = build_totals(positions, accounts, trades)

    def _pos_dict(p) -> dict:
        return {
            "key": p.key,
            "ticker": p.ticker,
            "country": p.country,
            "assetName": p.asset_name,
            "exchange": p.exchange,
            "holdingQuantity": p.holding_quantity,
            "avgBuyPrice": p.avg_buy_price,
            "costBasis": p.cost_basis,
            "realizedPnL": p.realized_pnl,
            "currentPrice": p.current_price,
            "evaluation": p.evaluation,
            "unrealizedPnL": p.unrealized_pnl,
            "lastNoteType": p.last_note_type,
            "lastNote": p.last_note,
            "lastTradedAt": p.last_traded_at,
            "accountIds": p.account_ids,
        }

    def _snap_dict(s) -> dict:
        a = s.account
        return {
            "account": {
                "id": a.id,
                "user_id": a.user_id,
                "name": a.name,
                "broker": a.broker,
                "cash_balance": a.cash_balance,
            },
            "stockEvaluation": s.stock_evaluation,
            "cashBalance": s.cash_balance,
            "totalValue": s.total_value,
        }

    def _totals_dict(t) -> dict:
        return {
            "totalEvaluation": t.total_evaluation,
            "totalUnrealizedPnL": t.total_unrealized_pnl,
            "totalRealizedPnL": t.total_realized_pnl,
            "totalCash": t.total_cash,
            "totalAssets": t.total_assets,
            "monthRealizedPnL": t.month_realized_pnl,
            "monthTradeCount": t.month_trade_count,
            "missingQuoteTickers": t.missing_quote_tickers,
        }

    return {
        "totals": _totals_dict(totals),
        "positions": [_pos_dict(p) for p in positions],
        "snapshots": [_snap_dict(s) for s in snapshots],
        "hasAccounts": len(accounts) > 0,
        "hasTrades": len(trades) > 0,
    }
