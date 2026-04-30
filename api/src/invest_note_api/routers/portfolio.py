"""portfolio 라우터 — holding + summary."""
from __future__ import annotations

import logging

import asyncpg
from fastapi import APIRouter, Depends, Query

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import acquire_for_user, get_pool
from invest_note_api.db_ops.accounts_repo import account_row_to_dict
from invest_note_api.db_ops.trades_repo import (
    list_trades_in_group,
    list_trades_with_account,
)
from invest_note_api.domain.holdings import compute_holding_summary
from invest_note_api.domain.portfolio import (
    Account,
    build_account_snapshots,
    build_positions,
    build_totals,
    merge_quotes,
)
from invest_note_api.domain.realized_pnl import TradeGroupKey, build_pnl_map
from invest_note_api.errors import APIError
from invest_note_api.external.quotes import fetch_quotes_by_keys
from invest_note_api.schemas.portfolio_response import PortfolioSummaryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio")


def _account_from_row(row) -> Account:
    d = account_row_to_dict(row)
    for field in ("id", "user_id"):
        if field in d and d[field] is not None:
            d[field] = str(d[field])
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

    key = TradeGroupKey(
        ticker=ticker,
        asset_name=asset_name,
        country=country,
        account_id=account_id,
    )

    async with acquire_for_user(pool, user.id) as conn:
        trades = await list_trades_in_group(conn, user.id, key)

    holding = compute_holding_summary(trades, key)

    return {"quantity": holding.quantity, "avgBuyPrice": holding.avg_buy_price}


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PortfolioSummaryResponse:
    async with acquire_for_user(pool, user.id) as conn:
        trades = await list_trades_with_account(conn, user.id)
        account_rows = await conn.fetch(
            "SELECT * FROM accounts ORDER BY created_at ASC"
        )

    accounts = [_account_from_row(r) for r in account_rows]

    positions0, lot_map = build_positions(trades)
    pnl_map = build_pnl_map(trades)

    quotes = {}
    try:
        quotes = await fetch_quotes_by_keys([p.key for p in positions0])
    except Exception:
        logger.warning("fetch_quotes_by_keys 실패 user_id=%s", user.id, exc_info=True)

    positions = merge_quotes(positions0, quotes)
    snapshots = build_account_snapshots(accounts, lot_map, quotes)
    totals = build_totals(positions, accounts, trades, pnl_map)

    return PortfolioSummaryResponse.model_validate({
        "totals": totals,
        "positions": positions,
        "snapshots": snapshots,
        "has_accounts": len(accounts) > 0,
        "has_trades": len(trades) > 0,
    })
