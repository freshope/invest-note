from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Response

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import acquire_for_user, get_pool
from invest_note_api.db_ops.accounts_repo import (
    UPDATABLE_COLS,
    account_row_to_dict,
    list_accounts as repo_list_accounts,
    patch_account,
)
from invest_note_api.errors import ERR_ACCOUNT_NOT_FOUND, APIError
from invest_note_api.schemas.account import AccountCreate, AccountUpdate

router = APIRouter(prefix="/accounts")


@router.get("")
async def list_accounts(
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[dict]:
    async with acquire_for_user(pool, user.id) as conn:
        accounts = await repo_list_accounts(conn)
        counts = await conn.fetch(
            "SELECT account_id, count(*)::int AS c FROM trades"
            " WHERE user_id = $1 GROUP BY account_id",
            user.id,
        )

    count_map: dict[str, int] = {str(r["account_id"]): r["c"] for r in counts}
    return [
        {**a, "trade_count": count_map.get(a["id"], 0)}
        for a in accounts
    ]


@router.post("", status_code=201)
async def create_account(
    data: AccountCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
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
    return account_row_to_dict(row)


@router.patch("/{account_id}", responses={204: {"description": "No fields to update"}})
async def update_account(
    account_id: UUID,
    data: AccountUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
):
    fields = data.model_fields_set & UPDATABLE_COLS
    if not fields:
        return Response(status_code=204)

    async with acquire_for_user(pool, user.id) as conn:
        result = await patch_account(conn, account_id, data.model_dump(include=fields))

    if result is None:
        raise APIError(ERR_ACCOUNT_NOT_FOUND, 404)
    return result


@router.delete("/{account_id}", status_code=204)
async def delete_account(
    account_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    async with acquire_for_user(pool, user.id) as conn:
        # RLS 가 격리하지만 `delete_trade` 와의 일관성을 위해 user_id 필터 명시 (defense-in-depth)
        deleted = await conn.fetchval(
            "DELETE FROM accounts"
            " WHERE id = $1 AND user_id = $2"
            " AND NOT EXISTS (SELECT 1 FROM trades WHERE account_id = $1)"
            " RETURNING id",
            account_id,
            user.id,
        )
        if deleted is not None:
            return Response(status_code=204)

        # 삭제 실패 — account 미존재 vs 거래 잔존 분기
        exists = await conn.fetchval(
            "SELECT id FROM accounts WHERE id = $1 AND user_id = $2",
            account_id,
            user.id,
        )

    if exists is None:
        raise APIError(ERR_ACCOUNT_NOT_FOUND, 404)
    raise APIError("거래 기록이 있는 계좌는 삭제할 수 없습니다.", 409)


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
            raise APIError(ERR_ACCOUNT_NOT_FOUND, 404)

        count = await conn.fetchval(
            "SELECT count(*)::int FROM trades WHERE account_id = $1", account_id
        )

    return {"count": count or 0}
