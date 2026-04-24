"""asyncpg 쿼리 묶음 — trades 테이블 CRUD."""
from __future__ import annotations

from typing import Any

from invest_note_api.domain.trade_types import DEFAULT_COUNTRY, MARKET_TYPE_STOCK, Trade, TradeWithAccount

PG_UPDATE_ZERO = "UPDATE 0"
PG_DELETE_ZERO = "DELETE 0"


def _row_to_trade(row: Any) -> Trade:
    return Trade(**dict(row))


def _row_to_trade_with_account(row: Any) -> TradeWithAccount:
    d = dict(row)
    return TradeWithAccount(**d)


async def list_trades(conn: Any, user_id: str) -> list[Trade]:
    rows = await conn.fetch(
        """
        SELECT * FROM trades
        WHERE user_id = $1
        ORDER BY traded_at DESC
        """,
        user_id,
    )
    return [_row_to_trade(r) for r in rows]


async def list_trades_with_account(conn: Any, user_id: str) -> list[TradeWithAccount]:
    rows = await conn.fetch(
        """
        SELECT t.*,
               a.name  AS account_name,
               a.broker AS account_broker
        FROM trades t
        LEFT JOIN accounts a ON a.id = t.account_id
        WHERE t.user_id = $1
        ORDER BY t.traded_at DESC
        """,
        user_id,
    )
    return [_row_to_trade_with_account(r) for r in rows]


async def get_trade_with_account(conn: Any, trade_id: str, user_id: str) -> TradeWithAccount | None:
    row = await conn.fetchrow(
        """
        SELECT t.*,
               a.name  AS account_name,
               a.broker AS account_broker
        FROM trades t
        LEFT JOIN accounts a ON a.id = t.account_id
        WHERE t.id = $1 AND t.user_id = $2
        """,
        trade_id,
        user_id,
    )
    if row is None:
        return None
    return _row_to_trade_with_account(row)


async def insert_trade(conn: Any, user_id: str, data: dict) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO trades (
            user_id, account_id, asset_name, ticker_symbol, market_type,
            trade_type, price, quantity, traded_at, commission, tax,
            country_code, exchange,
            strategy_type, reasoning_tags, buy_reason, sell_reason,
            emotion, result, reflection_note, improvement_note
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8, $9, $10, $11,
            $12, $13,
            $14, $15, $16, $17,
            $18, $19, $20, $21
        )
        RETURNING id, trade_type
        """,
        user_id,
        data["account_id"],
        data["asset_name"],
        data["ticker_symbol"],
        data.get("market_type", MARKET_TYPE_STOCK),
        data["trade_type"],
        data["price"],
        data["quantity"],
        data["traded_at"],
        data.get("commission", 0),
        data.get("tax", 0),
        data.get("country_code", DEFAULT_COUNTRY),
        data.get("exchange", ""),
        data.get("strategy_type"),
        data.get("reasoning_tags", []),
        data.get("buy_reason"),
        data.get("sell_reason"),
        data.get("emotion"),
        data.get("result"),
        data.get("reflection_note"),
        data.get("improvement_note"),
    )
    return dict(row)


_PATCH_ALLOWED = {
    "market_type", "price", "quantity", "commission", "tax",
    "strategy_type", "emotion", "reasoning_tags",
    "buy_reason", "sell_reason", "result", "reflection_note", "improvement_note",
}

PNL_AFFECTING_FIELDS = {"price", "quantity", "commission", "tax"}


async def patch_trade(conn: Any, trade_id: str, user_id: str, patch: dict) -> bool:
    safe_patch = {k: v for k, v in patch.items() if k in _PATCH_ALLOWED}
    if not safe_patch:
        return False

    set_clause = ", ".join(f"{k} = ${i + 3}" for i, k in enumerate(safe_patch))
    values = list(safe_patch.values())

    result = await conn.execute(
        f"UPDATE trades SET {set_clause} WHERE id = $1 AND user_id = $2",
        trade_id,
        user_id,
        *values,
    )
    return result != PG_UPDATE_ZERO


async def delete_trade(conn: Any, trade_id: str, user_id: str) -> bool:
    result = await conn.execute(
        "DELETE FROM trades WHERE id = $1 AND user_id = $2",
        trade_id,
        user_id,
    )
    return result != PG_DELETE_ZERO
