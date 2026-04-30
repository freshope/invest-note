"""portfolio 라우터 — holding + summary."""
from __future__ import annotations

import logging

import asyncpg
from fastapi import APIRouter, Depends, Query

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import acquire_for_user, get_pool
from invest_note_api.domain.holdings import compute_holding_summary
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
from invest_note_api.schemas.portfolio_response import PortfolioSummaryResponse

logger = logging.getLogger(__name__)

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

    target_ticker = ticker or asset_name

    async with acquire_for_user(pool, user.id) as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM trades
            WHERE user_id = $1
              AND account_id = $2
              AND COALESCE(NULLIF(country_code, ''), 'KR') = $3
              AND (ticker_symbol = $4 OR asset_name = $5)
            ORDER BY traded_at ASC
            """,
            user.id,
            account_id,
            country,
            target_ticker,
            asset_name,
        )

    trades = [Trade(**dict(r)) for r in rows]

    holding = compute_holding_summary(
        trades,
        ticker=ticker,
        asset_name=asset_name,
        country=country,
        account_id=account_id,
    )

    return {"quantity": holding.quantity, "avgBuyPrice": holding.avg_buy_price}


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PortfolioSummaryResponse:
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
        logger.warning("fetch_quotes_by_keys 실패 user_id=%s", user.id, exc_info=True)

    positions = merge_quotes(positions0, quotes)
    snapshots = build_account_snapshots(accounts, trades, quotes)
    totals = build_totals(positions, accounts, trades)

    return PortfolioSummaryResponse.model_validate({
        "totals": totals,
        "positions": positions,
        "snapshots": snapshots,
        "has_accounts": len(accounts) > 0,
        "has_trades": len(trades) > 0,
    })
