"""asyncpg 쿼리 묶음 — trades 테이블 CRUD."""
from __future__ import annotations

from typing import Any

from invest_note_api.domain.realized_pnl import TradeGroupKey
from invest_note_api.domain.trade_types import (
    DEFAULT_COUNTRY,
    MARKET_TYPE_STOCK,
    TRADE_TYPE_SELL,
    Trade,
    TradeWithAccount,
)

PG_UPDATE_ZERO = "UPDATE 0"
PG_DELETE_ZERO = "DELETE 0"


async def acquire_trade_group_lock(conn: Any, user_id: str, key: TradeGroupKey) -> None:
    """같은 (user, account, ticker, country) 그룹의 동시 mutation을 직렬화.

    트랜잭션 종료 시 자동 해제 — Supavisor transaction mode에서도 안전.
    session-level pg_advisory_lock은 사용 금지 (pooler에서 leak).
    lock_timeout = 2s 적용 — 초과 시 LockNotAvailableError (55P03) 발생.
    """
    lock_key = f"{user_id}:{key.account_id}:{key.ticker or key.asset_name}:{key.country}"
    await conn.execute("SET LOCAL lock_timeout = '2s'")
    await conn.fetchval(
        "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
        lock_key,
    )


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
            emotion, result
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8, $9, $10, $11,
            $12, $13,
            $14, $15, $16, $17,
            $18, $19
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
    )
    return dict(row)


_PATCH_ALLOWED = {
    "market_type", "price", "quantity", "commission", "tax",
    "strategy_type", "emotion", "reasoning_tags",
    "buy_reason", "sell_reason", "result",
}

PNL_AFFECTING_FIELDS = {
    "price",
    "quantity",
    "commission",
    "tax",
    "strategy_type",
    "reasoning_tags",
    "emotion",
}

# SELL row에 자동 산출되어 저장되는 메타 필드 — 사용자 patch 무시 대상.
# 새 자동 산출 필드 추가 시 여기에 등록.
SELL_AUTO_DERIVED_FIELDS = frozenset({"reasoning_tags", "emotion", "result"})


def strip_sell_auto_derived(
    patch: dict, fields: set[str], trade_type: str
) -> tuple[dict, set[str]]:
    """SELL은 자동 산출 필드를 patch/fields에서 제거 — BUY는 그대로."""
    if trade_type != TRADE_TYPE_SELL:
        return patch, fields
    return (
        {k: v for k, v in patch.items() if k not in SELL_AUTO_DERIVED_FIELDS},
        fields - SELL_AUTO_DERIVED_FIELDS,
    )


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


async def insert_trades_bulk(conn: Any, user_id: str, rows: list[dict]) -> int:
    """거래 목록을 일괄 INSERT한다. 반환값: 삽입된 행 수."""
    if not rows:
        return 0

    params = [
        (
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
        )
        for data in rows
    ]
    await conn.executemany(
        """
        INSERT INTO trades (
            user_id, account_id, asset_name, ticker_symbol, market_type,
            trade_type, price, quantity, traded_at, commission, tax,
            country_code, exchange,
            strategy_type, reasoning_tags, buy_reason, sell_reason,
            emotion, result
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8, $9, $10, $11,
            $12, $13,
            $14, $15, $16, $17,
            $18, $19
        )
        """,
        params,
    )
    return len(rows)


async def list_trades_in_range(
    conn: Any, user_id: str, start_date: str, end_date: str
) -> list[Trade]:
    """traded_at 이 [start_date, end_date] (날짜 기준) 범위인 거래를 반환한다."""
    rows = await conn.fetch(
        """
        SELECT * FROM trades
        WHERE user_id = $1
          AND traded_at::date >= $2::date
          AND traded_at::date <= $3::date
        ORDER BY traded_at ASC
        """,
        user_id,
        start_date,
        end_date,
    )
    return [_row_to_trade(r) for r in rows]
