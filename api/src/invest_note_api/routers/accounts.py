from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Response
from pydantic import ValidationError

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import acquire_for_user, get_pool
from invest_note_api.errors import APIError
from invest_note_api.schemas.account import AccountCreate, AccountUpdate

router = APIRouter(prefix="/api/accounts")

_UPDATABLE_COLS = frozenset({"name", "broker", "cash_balance"})


def _row_to_dict(row: Any) -> dict:
    d = dict(row)
    if "cash_balance" in d and d["cash_balance"] is not None:
        d["cash_balance"] = float(d["cash_balance"])
    return d


@router.get("")
async def list_accounts(
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[dict]:
    async with acquire_for_user(pool, user.id) as conn:
        accounts = await conn.fetch(
            "SELECT id, user_id, name, broker, cash_balance, created_at, updated_at"
            " FROM accounts ORDER BY created_at ASC"
        )
        counts = await conn.fetch(
            "SELECT account_id, count(*)::int AS c FROM trades GROUP BY account_id"
        )

    count_map: dict[UUID, int] = {r["account_id"]: r["c"] for r in counts}
    return [
        {**_row_to_dict(row), "trade_count": count_map.get(row["id"], 0)}
        for row in accounts
    ]


@router.post("", status_code=201)
async def create_account(
    body: dict,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    try:
        data = AccountCreate.model_validate(body)
    except ValidationError as e:
        first = e.errors()[0]
        raise APIError(first.get("msg", "올바르지 않은 입력입니다."), 400)

    async with acquire_for_user(pool, user.id) as conn:
        row = await conn.fetchrow(
            "INSERT INTO accounts (user_id, name, broker, cash_balance)"
            " VALUES (auth.uid(), $1, $2, $3)"
            " RETURNING id, user_id, name, broker, cash_balance, created_at, updated_at",
            data.name,
            data.broker,
            data.cash_balance,
        )

    if row is None:
        raise APIError("계좌를 추가할 수 없습니다. 다시 시도해주세요.", 500)
    return _row_to_dict(row)


@router.patch("/{account_id}")
async def update_account(
    account_id: UUID,
    body: dict,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
):
    try:
        data = AccountUpdate.model_validate(body)
    except ValidationError as e:
        first = e.errors()[0]
        raise APIError(first.get("msg", "올바르지 않은 입력입니다."), 400)

    fields = data.model_fields_set & _UPDATABLE_COLS
    if not fields:
        return Response(status_code=204)

    values = data.model_dump(include=fields)
    cols = list(fields)
    set_clause = ", ".join(f"{col} = ${i + 2}" for i, col in enumerate(cols))
    params: list[Any] = [account_id] + [values[col] for col in cols]

    async with acquire_for_user(pool, user.id) as conn:
        row = await conn.fetchrow(
            f"UPDATE accounts SET {set_clause}, updated_at = now()"
            " WHERE id = $1"
            " RETURNING id, user_id, name, broker, cash_balance, created_at, updated_at",
            *params,
        )

    if row is None:
        raise APIError("계좌를 찾을 수 없습니다.", 404)
    return _row_to_dict(row)


@router.delete("/{account_id}", status_code=204)
async def delete_account(
    account_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    async with acquire_for_user(pool, user.id) as conn:
        trade_count = await conn.fetchval(
            "SELECT count(*)::int FROM trades WHERE account_id = $1",
            account_id,
        )
        if trade_count is None:
            raise APIError("계좌 정보를 확인할 수 없습니다.", 500)
        if trade_count > 0:
            raise APIError("거래 기록이 있는 계좌는 삭제할 수 없습니다.", 409)

        result = await conn.execute("DELETE FROM accounts WHERE id = $1", account_id)

    if result == "DELETE 0":
        raise APIError("계좌를 찾을 수 없습니다.", 404)
    return Response(status_code=204)


@router.get("/{account_id}/trade-count")
async def get_trade_count(
    account_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    async with acquire_for_user(pool, user.id) as conn:
        exists = await conn.fetchval(
            "SELECT id FROM accounts WHERE id = $1", account_id
        )
        if exists is None:
            raise APIError("계좌를 찾을 수 없습니다.", 404)

        count = await conn.fetchval(
            "SELECT count(*)::int FROM trades WHERE account_id = $1", account_id
        )

    return {"count": count or 0}
