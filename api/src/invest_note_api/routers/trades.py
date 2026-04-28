"""trades 라우터 — 6 endpoints."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, Query, Response

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import acquire_for_user, get_pool
from invest_note_api.db_ops.pnl_sync import recalc_group_pnl
from invest_note_api.db_ops.trades_repo import (
    PNL_AFFECTING_FIELDS,
    acquire_trade_group_lock,
    delete_trade,
    get_trade_with_account,
    insert_trade,
    list_trades,
    list_trades_with_account,
    patch_trade,
    strip_sell_auto_derived,
)
from invest_note_api.domain.holdings import (
    SellBreakdown,
    compute_flexible_breakdown,
    compute_total_holding,
)
from invest_note_api.domain.analysis.strategy_adherence import evaluate_strategy_for_sell
from invest_note_api.domain.realized_pnl import trade_to_group_key, validate_mutation
from invest_note_api.domain.trade_types import (
    DEFAULT_COUNTRY,
    RESULT_BREAKEVEN,
    RESULT_FAIL,
    RESULT_SUCCESS,
    TRADE_TYPE_SELL,
    Trade,
)
from invest_note_api.errors import ERR_TRADE_NOT_FOUND, APIError, validate_body
from invest_note_api.schemas.trade import TradeCreate, TradeUpdate

router = APIRouter(prefix="/api/trades")

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-_가-힣]+$")


def _trade_dict(trade) -> dict:
    return trade.model_dump(mode="json")


def _trade_with_account_dict(trade) -> dict:
    d = _trade_dict(trade)
    d["account"] = {"name": d.pop("account_name", None), "broker": d.pop("account_broker", None)}
    return d


def _breakdown_dict(bd: SellBreakdown) -> dict:
    return {
        "sellPrice": bd.sell_price,
        "quantity": bd.quantity,
        "avgCostPrice": bd.avg_cost_price,
        "sellAmount": bd.sell_amount,
        "costBasis": bd.cost_basis,
        "commission": bd.commission,
        "tax": bd.tax,
        "pnl": bd.pnl,
        "isManualInput": bd.is_manual_input,
    }


def _derive_result(pnl: float) -> str:
    if pnl > 0:
        return RESULT_SUCCESS
    if pnl < 0:
        return RESULT_FAIL
    return RESULT_BREAKEVEN


@router.get("")
async def list_trades_endpoint(
    ticker: str | None = Query(default=None),
    country: str = Query(default=DEFAULT_COUNTRY),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    if ticker is not None:
        ticker = ticker[:30]
        if not _TICKER_RE.match(ticker):
            raise APIError("잘못된 ticker 형식입니다.", 400)

    async with acquire_for_user(pool, user.id) as conn:
        trades = await list_trades_with_account(conn, user.id)
        accounts_rows = await conn.fetch(
            "SELECT * FROM accounts ORDER BY created_at ASC"
        )

    if ticker:
        trades = [
            t for t in trades
            if (t.country_code or DEFAULT_COUNTRY) == country
            and (t.ticker_symbol == ticker or t.asset_name == ticker)
        ]

    accounts = [dict(r) for r in accounts_rows]
    for a in accounts:
        if "cash_balance" in a and a["cash_balance"] is not None:
            a["cash_balance"] = float(a["cash_balance"])

    return {"trades": [_trade_with_account_dict(t) for t in trades], "accounts": accounts}


@router.post("", status_code=201)
async def create_trade(
    body: dict,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    data = validate_body(TradeCreate, body)

    async with acquire_for_user(pool, user.id) as conn:
        # 계좌 존재 확인
        acct_exists = await conn.fetchval(
            "SELECT id FROM accounts WHERE id = $1", data.account_id
        )
        if not acct_exists:
            raise APIError("올바른 계좌를 선택해주세요.", 400)

        now = datetime.now(timezone.utc)
        new_trade = Trade(
            id="__new__",
            user_id=str(user.id),
            account_id=data.account_id,
            asset_name=data.asset_name,
            ticker_symbol=data.ticker_symbol,
            market_type=data.market_type,
            trade_type=data.trade_type,
            price=data.price,
            quantity=data.quantity,
            total_amount=data.price * data.quantity,
            traded_at=data.traded_at,
            country_code=data.country_code or DEFAULT_COUNTRY,
            exchange=data.exchange or "",
            commission=data.commission,
            tax=data.tax,
            created_at=now,
            updated_at=now,
        )

        # BUY도 lock — recalc_group_pnl이 같은 그룹 SELL들을 UPDATE하므로 BUY/SELL 모두 직렬화 필요
        await acquire_trade_group_lock(conn, str(user.id), trade_to_group_key(new_trade))

        all_trades = await list_trades(conn, user.id)

        if data.trade_type == TRADE_TYPE_SELL:
            holding = compute_total_holding(
                all_trades,
                ticker=data.ticker_symbol,
                asset_name=data.asset_name,
                country=data.country_code or DEFAULT_COUNTRY,
                account_id=data.account_id,
            )
            if holding <= 0:
                raise APIError("보유하지 않은 종목입니다.", 400)
            if data.quantity > holding:
                raise APIError(f"보유 수량이 부족합니다 (현재 {holding}주).", 400)

        if data.trade_type == TRADE_TYPE_SELL:
            ok, msg, _ = validate_mutation(all_trades, "insert", new_trade)
            if not ok:
                raise APIError(msg, 400)

        row = await insert_trade(conn, user.id, {
            "account_id": data.account_id,
            "asset_name": data.asset_name,
            "ticker_symbol": data.ticker_symbol,
            "market_type": data.market_type,
            "trade_type": data.trade_type,
            "price": data.price,
            "quantity": data.quantity,
            "traded_at": data.traded_at,
            "commission": data.commission,
            "tax": data.tax,
            "country_code": data.country_code or DEFAULT_COUNTRY,
            "exchange": data.exchange or "",
        })

        key = trade_to_group_key(new_trade)
        fresh_trades = [*all_trades, Trade(**{**new_trade.model_dump(), "id": row["id"]})]
        await recalc_group_pnl(conn, fresh_trades, key)

    return row


@router.get("/{trade_id}/summary")
async def get_trade_summary(
    trade_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    async with acquire_for_user(pool, user.id) as conn:
        sell_row = await conn.fetchrow(
            "SELECT * FROM trades WHERE id = $1 AND user_id = $2",
            trade_id, user.id,
        )
        if not sell_row:
            raise APIError(ERR_TRADE_NOT_FOUND, 404)

        sell = Trade(**dict(sell_row))
        if sell.trade_type != TRADE_TYPE_SELL:
            raise APIError("매도 거래만 조회할 수 있습니다.", 400)

        all_trades = await list_trades(conn, user.id)

    breakdown = compute_flexible_breakdown(sell)
    evaluation = evaluate_strategy_for_sell(sell, all_trades, None)
    holding_days = sell.holding_days
    strategy_eval = None
    if evaluation is not None:
        strategy_eval = {
            "planned": evaluation.planned,
            "actual": evaluation.actual,
            "holdingDays": evaluation.holding_days,
            "adherence": evaluation.adherence,
        }

    return {
        "pnl": breakdown.pnl,
        "result": _derive_result(breakdown.pnl),
        "holdingDays": holding_days,
        "strategyEvaluation": strategy_eval,
        "breakdown": _breakdown_dict(breakdown),
    }


@router.get("/{trade_id}")
async def get_trade(
    trade_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    async with acquire_for_user(pool, user.id) as conn:
        trade = await get_trade_with_account(conn, trade_id, user.id)

    if trade is None:
        raise APIError("거래를 찾을 수 없습니다.", 404)
    d = _trade_dict(trade)
    account_name = d.pop("account_name", None)
    account_broker = d.pop("account_broker", None)
    d["account"] = {"name": account_name, "broker": account_broker}
    return d


@router.patch("/{trade_id}", responses={204: {"description": "No fields to update"}})
async def update_trade(
    trade_id: str,
    body: dict,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
):
    data = validate_body(TradeUpdate, body)
    fields = data.model_fields_set
    if not fields:
        return Response(status_code=204)

    patch = {k: v for k, v in data.model_dump(include=fields).items() if v is not None or k in fields}

    async with acquire_for_user(pool, user.id) as conn:
        existing_row = await conn.fetchrow(
            "SELECT * FROM trades WHERE id = $1 AND user_id = $2",
            trade_id, user.id,
        )
        if not existing_row:
            raise APIError(ERR_TRADE_NOT_FOUND, 404)

        existing = Trade(**dict(existing_row))
        patch, fields = strip_sell_auto_derived(patch, fields, existing.trade_type)
        if not patch:
            return Response(status_code=204)

        if fields & PNL_AFFECTING_FIELDS:
            await acquire_trade_group_lock(conn, str(user.id), trade_to_group_key(existing))
            all_trades = await list_trades(conn, user.id)
            ok, msg, _ = validate_mutation(all_trades, "update", existing, patch)
            if not ok:
                raise APIError(msg, 400)

            await patch_trade(conn, trade_id, user.id, patch)

            fresh_trades = [Trade(**{**t.model_dump(), **patch}) if t.id == trade_id else t for t in all_trades]
            key = trade_to_group_key(existing)
            await recalc_group_pnl(conn, fresh_trades, key)
        else:
            # 파생 SELL 값에 영향을 주지 않는 메타 필드는 lock/recalc 없이 수정.
            # PNL_AFFECTING_FIELDS에 없는 필드 추가 시 이 분기를 재검토할 것.
            await patch_trade(conn, trade_id, user.id, patch)

    return Response(status_code=204)


@router.delete("/{trade_id}", status_code=204)
async def delete_trade_endpoint(
    trade_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    async with acquire_for_user(pool, user.id) as conn:
        target_row = await conn.fetchrow(
            "SELECT * FROM trades WHERE id = $1 AND user_id = $2",
            trade_id, user.id,
        )
        if target_row is None:
            raise APIError(ERR_TRADE_NOT_FOUND, 404)
        target = Trade(**dict(target_row))

        await acquire_trade_group_lock(conn, str(user.id), trade_to_group_key(target))

        all_trades = await list_trades(conn, user.id)
        ok, msg, _ = validate_mutation(all_trades, "delete", target)
        if not ok:
            raise APIError(msg, 400)

        key = trade_to_group_key(target)
        await delete_trade(conn, trade_id, user.id)

        remaining = [t for t in all_trades if t.id != trade_id]
        await recalc_group_pnl(conn, remaining, key)

    return Response(status_code=204)
