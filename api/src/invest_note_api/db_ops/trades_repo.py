"""asyncpg 쿼리 묶음 — trades 테이블 CRUD."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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


async def list_trades(
    conn: Any,
    user_id: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[Trade]:
    """user 의 거래 목록. `date_from` / `date_to` 가 지정되면 `traded_at` 으로 SQL push.

    `date_to` 는 exclusive 상한 권장 (`< date_to`) — 호출자가 [from, to) 형태로 전달.
    """
    where = ["user_id = $1"]
    params: list[Any] = [user_id]
    if date_from is not None:
        params.append(date_from)
        where.append(f"traded_at >= ${len(params)}")
    if date_to is not None:
        params.append(date_to)
        where.append(f"traded_at < ${len(params)}")
    rows = await conn.fetch(
        f"SELECT * FROM trades WHERE {' AND '.join(where)} ORDER BY traded_at DESC",
        *params,
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


async def list_trades_with_account(
    conn: Any,
    user_id: str,
    *,
    ticker: str | None = None,
    country: str | None = None,
    account_id: str | None = None,
) -> list[TradeWithAccount]:
    """user 의 거래 + 계좌 join. `ticker` / `country` / `account_id` 가 지정되면 SQL WHERE 로 push.

    `country` 정규화는 `domain.trade_types.trade_country` 와 같은 의미의
    `COALESCE(NULLIF(country_code, ''), 'KR')` 사용.
    """
    where = ["t.user_id = $1"]
    params: list[Any] = [user_id]
    if ticker is not None:
        params.append(ticker)
        where.append(f"t.ticker_symbol = ${len(params)}")
    if country is not None:
        params.append(country)
        where.append(f"COALESCE(NULLIF(t.country_code, ''), 'KR') = ${len(params)}")
    if account_id is not None:
        params.append(account_id)
        where.append(f"t.account_id = ${len(params)}")
    rows = await conn.fetch(
        f"""
        SELECT t.*,
               a.name  AS account_name,
               a.broker AS account_broker
        FROM trades t
        LEFT JOIN accounts a ON a.id = t.account_id
        WHERE {' AND '.join(where)}
        ORDER BY t.traded_at DESC
        """,
        *params,
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


async def list_trades_by_ids(conn: Any, ids: list[str], user_id: str) -> list[Trade]:
    """여러 거래를 단일 쿼리로 조회 (bulk-delete N+1 회피).

    malformed UUID 는 asyncpg 가 DataError(InvalidTextRepresentationError 포함) 를
    던지므로 호출자가 422 로 변환한다. 반환 개수가 입력 개수와 다르면 누락 → 호출자가 404.
    """
    if not ids:
        return []
    rows = await conn.fetch(
        "SELECT * FROM trades WHERE id = ANY($1::uuid[]) AND user_id = $2",
        ids,
        user_id,
    )
    return [_row_to_trade(r) for r in rows]


async def delete_trades_by_ids(conn: Any, ids: list[str], user_id: str) -> None:
    """여러 거래를 단일 쿼리로 삭제 (bulk-delete N+1 회피).

    호출자가 이미 list_trades_by_ids 로 소유/존재를 검증한 id 만 넘긴다.
    """
    if not ids:
        return
    await conn.execute(
        "DELETE FROM trades WHERE id = ANY($1::uuid[]) AND user_id = $2",
        ids,
        user_id,
    )


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
    country_code, exchange, exchange_rate,
    strategy_type, reasoning_tags, buy_reason, sell_reason,
    emotion, result, custom_tags
) VALUES (
    $1, $2, $3, $4, $5,
    $6, $7, $8, $9, $10, $11,
    $12, $13, $14,
    $15, $16, $17, $18,
    $19, $20, $21
)
"""

_TRADE_INSERT_PARAM_COUNT = 21


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
        data.get("exchange_rate", 1.0),
        data.get("strategy_type"),
        data.get("reasoning_tags", []),
        data.get("buy_reason"),
        data.get("sell_reason"),
        data.get("emotion"),
        data.get("result"),
        data.get("custom_tags", []),
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
    "exchange_rate":  TradeFieldMeta(patchable=True, pnl_affecting=True),
    "commission":     TradeFieldMeta(patchable=True, pnl_affecting=True),
    "tax":            TradeFieldMeta(patchable=True, pnl_affecting=True),
    "strategy_type":  TradeFieldMeta(patchable=True, pnl_affecting=True),
    "emotion":        TradeFieldMeta(patchable=True, pnl_affecting=True, sell_auto_derived=True),
    "reasoning_tags": TradeFieldMeta(patchable=True, pnl_affecting=True, sell_auto_derived=True),
    "custom_tags":    TradeFieldMeta(patchable=True, pnl_affecting=True, sell_auto_derived=True),
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


# 거래내역서 머지에서만 update 가능한 필드. 사용자 PATCH 엔드포인트는 traded_at 변경
# 불허(시그니처/그룹키에 영향). 머지는 시그니처 일치 하에 시각 정밀도 향상이 목적이라 허용.
_IMPORT_MERGE_ALLOWED: frozenset[str] = frozenset({"commission", "tax", "traded_at"})


async def update_trade_from_import(
    conn: Any, trade_id: str, user_id: str, patch: dict
) -> bool:
    """거래내역서 머지 전용 update. 허용 필드 = {commission, tax, traded_at}.

    patch_trade 와 분리한 이유: traded_at 는 PATCH 엔드포인트에서 사용자가 직접 변경할
    수 없도록 의도된 보안 모델. 머지는 시그니처가 일치하는 거래의 시각 정밀도 향상이라
    별도 경로로 좁힌 화이트리스트로 update.
    """
    safe_patch = {k: v for k, v in patch.items() if k in _IMPORT_MERGE_ALLOWED}
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
