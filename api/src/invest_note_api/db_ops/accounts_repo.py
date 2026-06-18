"""Accounts row-level 변환 + patch 헬퍼.

API 응답 직전에 asyncpg.Record 의 cash_balance(Decimal) 를 JSON 직렬화
가능한 float 로 강제 변환하고, UUID 컬럼을 str 로 정규화한다.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

UPDATABLE_COLS: frozenset[str] = frozenset({"name", "broker", "cash_balance"})
RETURNING_COLS = "id, user_id, name, broker, cash_balance, created_at, updated_at"


def account_row_to_dict(row: Any) -> dict:
    d = dict(row)
    if "cash_balance" in d and d["cash_balance"] is not None:
        d["cash_balance"] = float(d["cash_balance"])
    for field in ("id", "user_id"):
        if isinstance(d.get(field), UUID):
            d[field] = str(d[field])
    return d


async def list_accounts(conn: Any, user_id: Any) -> list[dict]:
    """사용자 계좌 목록 — 응답 직렬화 가능한 dict 형태로 반환."""
    rows = await conn.fetch(
        f"SELECT {RETURNING_COLS} FROM accounts WHERE user_id = $1 ORDER BY created_at ASC",
        user_id,
    )
    return [account_row_to_dict(row) for row in rows]


async def patch_account(conn: Any, account_id: UUID, user_id: Any, patch: dict) -> dict | None:
    safe_patch = {k: v for k, v in patch.items() if k in UPDATABLE_COLS}
    # 호출자 (routers/accounts.update_account) 가 빈 fields 를 사전 차단하므로 unreachable.
    # 향후 직접 호출자가 생기면 빈 patch 를 ValueError 로 분리해 not-found `None` 과 구분 필요.
    if not safe_patch:
        return None

    set_clause = ", ".join(f"{k} = ${i + 3}" for i, k in enumerate(safe_patch))
    row = await conn.fetchrow(
        f"UPDATE accounts SET {set_clause}, updated_at = now()"
        f" WHERE id = $1 AND user_id = $2 RETURNING {RETURNING_COLS}",
        account_id,
        user_id,
        *safe_patch.values(),
    )
    return account_row_to_dict(row) if row else None
