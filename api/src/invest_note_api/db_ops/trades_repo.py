"""asyncpg 쿼리 묶음 — trades 테이블 CRUD."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from invest_note_api.domain.realized_pnl import TradeGroupKey
from invest_note_api.errors import APIError
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


async def list_trades_in_group(
    conn: Any, user_id: str, key: TradeGroupKey
) -> list[Trade]:
    """단일 (account_id, ticker_or_name, country) 그룹의 거래만 반환.

    walk_trades / compute_group_pnl / validate_mutation 의 인자로 그대로 사용 가능 —
    내부에서 is_same_group 으로 다시 필터하지만 이미 그룹 단위라 no-op.
    """
    rows = await conn.fetch(
        """
        SELECT * FROM trades
        WHERE user_id = $1
          AND account_id = $2
          AND COALESCE(NULLIF(ticker_symbol, ''), asset_name) = $3
          AND COALESCE(NULLIF(country_code, ''), 'KR') = $4
        ORDER BY traded_at ASC
        """,
        user_id,
        key.account_id,
        key.ticker or key.asset_name,
        key.country,
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


async def assert_account_exists(conn: Any, account_id: str) -> None:
    """계좌 존재 확인 — 없으면 400 APIError raise."""
    exists = await conn.fetchval(
        "SELECT id FROM accounts WHERE id = $1", account_id
    )
    if not exists:
        raise APIError("올바른 계좌를 선택해주세요.", 400)


async def get_trade_by_id(conn: Any, trade_id: str, user_id: str) -> Trade | None:
    row = await conn.fetchrow(
        "SELECT * FROM trades WHERE id = $1 AND user_id = $2",
        trade_id,
        user_id,
    )
    if row is None:
        return None
    return _row_to_trade(row)


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


_TRADE_INSERT_SQL = """
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
"""

_TRADE_INSERT_PARAM_COUNT = 19


def _trade_insert_params(user_id: str, data: dict) -> tuple:
    return (
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


async def insert_trade(conn: Any, user_id: str, data: dict) -> dict:
    row = await conn.fetchrow(
        f"{_TRADE_INSERT_SQL} RETURNING id, trade_type",
        *_trade_insert_params(user_id, data),
    )
    return dict(row)


@dataclass(frozen=True)
class TradeFieldMeta:
    """trade patch 필드 속성 — 단일 source of truth.

    - patchable: PATCH /trades/{id}에서 사용자가 직접 수정 가능
    - pnl_affecting: 변경 시 PnL 재계산 필요
    - sell_auto_derived: SELL row에 자동 산출되어 사용자 patch 무시 대상
    """

    patchable: bool = False
    pnl_affecting: bool = False
    sell_auto_derived: bool = False


# 새 patch 필드 추가 시 이 dict 한 곳에만 등록한다.
# 아래 세 frozenset은 이 dict에서 자동 파생.
TRADE_FIELD_META: dict[str, TradeFieldMeta] = {
    "market_type":    TradeFieldMeta(patchable=True),
    "price":          TradeFieldMeta(patchable=True, pnl_affecting=True),
    "quantity":       TradeFieldMeta(patchable=True, pnl_affecting=True),
    "commission":     TradeFieldMeta(patchable=True, pnl_affecting=True),
    "tax":            TradeFieldMeta(patchable=True, pnl_affecting=True),
    "strategy_type":  TradeFieldMeta(patchable=True, pnl_affecting=True),
    "emotion":        TradeFieldMeta(patchable=True, pnl_affecting=True, sell_auto_derived=True),
    "reasoning_tags": TradeFieldMeta(patchable=True, pnl_affecting=True, sell_auto_derived=True),
    "buy_reason":     TradeFieldMeta(patchable=True),
    "sell_reason":    TradeFieldMeta(patchable=True),
    "result":         TradeFieldMeta(patchable=True, sell_auto_derived=True),
}

_PATCH_ALLOWED: frozenset[str] = frozenset(
    name for name, meta in TRADE_FIELD_META.items() if meta.patchable
)
PNL_AFFECTING_FIELDS: frozenset[str] = frozenset(
    name for name, meta in TRADE_FIELD_META.items() if meta.pnl_affecting
)
SELL_AUTO_DERIVED_FIELDS: frozenset[str] = frozenset(
    name for name, meta in TRADE_FIELD_META.items() if meta.sell_auto_derived
)


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


async def insert_trades_bulk(conn: Any, user_id: str, rows: list[dict]) -> list[Trade]:
    """거래 목록을 일괄 INSERT한다. 반환값: 삽입된 거래 목록."""
    if not rows:
        return []

    params = [_trade_insert_params(user_id, data) for data in rows]
    flattened = [value for row_params in params for value in row_params]
    values_sql = ", ".join(
        "("
        + ", ".join(
            f"${i * _TRADE_INSERT_PARAM_COUNT + j + 1}"
            for j in range(_TRADE_INSERT_PARAM_COUNT)
        )
        + ")"
        for i in range(len(params))
    )
    insert_columns_sql = _TRADE_INSERT_SQL.split(" VALUES ", 1)[0]
    rows_inserted = await conn.fetch(
        f"{insert_columns_sql} VALUES {values_sql} RETURNING *",
        *flattened,
    )
    return [_row_to_trade(row) for row in rows_inserted]


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
