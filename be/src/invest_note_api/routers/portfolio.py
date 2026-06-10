"""portfolio 라우터 — holding + summary."""
from __future__ import annotations

import logging
from uuid import UUID

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Query

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import acquire_for_user, get_pool
from invest_note_api.db_ops.accounts_repo import list_accounts
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
from invest_note_api.external.fx import (
    FxCacheState,
    get_fx_cache_state,
    usdkrw_if_foreign,
)
from invest_note_api.external.http_client import get_http_client
from invest_note_api.external.quotes import (
    QuoteCacheState,
    fetch_quotes_by_keys,
    get_quote_cache_state,
)
from invest_note_api.schemas.portfolio_response import PortfolioSummaryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio")


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
    account_id: UUID | None = Query(default=None, alias="accountId"),
    refresh: bool = Query(default=False),
    with_quotes: bool = Query(default=True, alias="withQuotes"),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
    quote_state: QuoteCacheState = Depends(get_quote_cache_state),
    fx_state: FxCacheState = Depends(get_fx_cache_state),
    http_client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings),
) -> PortfolioSummaryResponse:
    account_id_str = str(account_id) if account_id is not None else None
    async with acquire_for_user(pool, user.id) as conn:
        trades = await list_trades_with_account(conn, user.id, account_id=account_id_str)
        account_dicts = await list_accounts(conn)

    # has_accounts 는 글로벌 기준이라 응답 직전 account_dicts 길이로 따로 계산한다 —
    # 필터된 결과가 비어도 "계좌 만드세요" EmptyState 가 잘못 뜨면 안 된다.
    accounts = [
        Account(**d)
        for d in account_dicts
        if account_id_str is None or d["id"] == account_id_str
    ]

    positions0, lot_map = build_positions(trades)

    pnl_map = build_pnl_map(trades)

    # with_quotes=False (신규 FE): 시세 fetch 를 임계 경로에서 떼어내고 빈 quotes 로
    # 진행한다. 이후 merge_quotes / build_account_snapshots / build_totals 는 빈 quotes 를
    # graceful 하게 처리(가격/평가=null, 평가합=0)하며, FE 가 /stocks/quote overlay 로 채운다.
    # 파라미터 미전송(default True)인 구버전 앱은 기존 동작(시세 포함) 유지.
    #
    # 원가·실현손익은 거래 시점 환율로 KRW 고정(저장값)이라 환산 불필요. 현재 평가액(미실현)만
    # live 환율이 필요한데, lite 모드(with_quotes=False)는 quotes={} 라 usdkrw 가 전혀 소비되지
    # 않으므로(FE 가 useFxRate 로 자체 환산) fetch_usdkrw 를 with_quotes 블록 안으로 옮긴다.
    usdkrw = None
    quotes = {}
    if with_quotes:
        usdkrw = await usdkrw_if_foreign(
            trades, fx_state, http_client, force_refresh=refresh
        )
        try:
            quotes = await fetch_quotes_by_keys(
                quote_state,
                [p.key for p in positions0],
                client=http_client,
                force_refresh=refresh,
                providers=settings.quote_provider_list,
            )
        except Exception:
            logger.warning("fetch_quotes_by_keys 실패 user_id=%s", user.id, exc_info=True)

    positions = merge_quotes(positions0, quotes, usdkrw)
    snapshots = build_account_snapshots(accounts, lot_map, quotes, usdkrw)
    totals = build_totals(positions, accounts, trades, pnl_map)

    return PortfolioSummaryResponse.model_validate({
        "totals": totals,
        "positions": positions,
        "snapshots": snapshots,
        "has_accounts": len(account_dicts) > 0,
        "has_trades": len(trades) > 0,
    })
