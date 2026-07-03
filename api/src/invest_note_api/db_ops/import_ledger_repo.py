"""asyncpg 쿼리 묶음 — 거래내역서 원장(import_batches / import_ledger_entries).

Stage 1 캡처가 파일→파싱→원장 적재에 쓴다. 파일 dedup(sha256)·거래 dedup(keep-last UPSERT)이
DB 제약(UNIQUE (user_id, content_sha256) / PARTIAL UNIQUE (user_id, dedup_key))에 얹힌다.
다른 db_ops 와 동일하게 호출부가 conn 을 소유한다(acquire_for_user 트랜잭션 안에서 호출).
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from ..broker_import.base import ParsedRow

# 파일 통째 dedup — 같은 user 가 같은 파일(sha256)을 재업로드하면 새 batch 를 만들지 않는다.
_INSERT_BATCH_SQL = """
INSERT INTO import_batches (
    id, user_id, broker_key, parser_version, filename, content_type,
    size_bytes, storage_key, content_sha256, account_hint, parsed_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, now())
ON CONFLICT (user_id, content_sha256) DO NOTHING
RETURNING id
"""

_SELECT_BATCH_SQL = """
SELECT id FROM import_batches WHERE user_id = $1 AND content_sha256 = $2
"""

# 거래 dedup = keep-last: 같은 (user_id, dedup_key) 재적재 시 raw·식별 필드·batch_id 를 최신으로
# 갱신한다(재업로드 정정 채널). dedup_key IS NULL(비거래 행)은 partial index 밖이라 항상 INSERT.
_UPSERT_LEDGER_SQL = """
INSERT INTO import_ledger_entries (
    batch_id, user_id, source_row_no, traded_at_raw, traded_at,
    trade_type, asset_name, ticker_hint, isin, country_code,
    quantity, price, dedup_key, raw
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb
)
ON CONFLICT (user_id, dedup_key) WHERE dedup_key IS NOT NULL
DO UPDATE SET
    batch_id = excluded.batch_id,
    source_row_no = excluded.source_row_no,
    traded_at_raw = excluded.traded_at_raw,
    traded_at = excluded.traded_at,
    trade_type = excluded.trade_type,
    asset_name = excluded.asset_name,
    ticker_hint = excluded.ticker_hint,
    isin = excluded.isin,
    country_code = excluded.country_code,
    quantity = excluded.quantity,
    price = excluded.price,
    raw = excluded.raw
"""


def _num(value: object) -> Decimal | None:
    """float/int → numeric(Decimal). asyncpg numeric 은 Decimal 을 요구."""
    if value is None:
        return None
    return Decimal(str(value))


def _row_params(batch_id: UUID, user_id: UUID, row: ParsedRow) -> tuple:
    # traded_at(정규화 timestamptz)은 이번 스코프에선 채우지 않는다 — 진실은 traded_at_raw(원문)이고
    # 정밀 시각은 Stage 2 가 raw 에서 도출한다(KST→UTC 변환 중복·tz 버그 회피).
    return (
        batch_id,
        user_id,
        row.source_row_no,
        row.traded_at_kst,
        None,
        row.trade_type,
        row.asset_name,
        row.ticker_hint,
        row.isin,
        row.country_code,
        _num(row.quantity),
        _num(row.price),
        row.dedup_key,
        json.dumps(row.raw, ensure_ascii=False),
    )


async def insert_batch(
    conn: Any,
    *,
    batch_id: UUID,
    user_id: UUID,
    broker_key: str,
    parser_version: str,
    filename: str | None,
    content_type: str | None,
    size_bytes: int | None,
    storage_key: str | None,
    content_sha256: str,
    account_hint: str | None,
) -> tuple[UUID, bool]:
    """batch 적재. 반환 (batch_id, is_new). 같은 파일(sha256) 재업로드면 기존 id + False."""
    row = await conn.fetchrow(
        _INSERT_BATCH_SQL,
        batch_id,
        user_id,
        broker_key,
        parser_version,
        filename,
        content_type,
        size_bytes,
        storage_key,
        content_sha256,
        account_hint,
    )
    if row is not None:
        return row["id"], True
    existing = await conn.fetchrow(_SELECT_BATCH_SQL, user_id, content_sha256)
    return existing["id"], False


async def upsert_ledger_entries(
    conn: Any, *, batch_id: UUID, user_id: UUID, rows: list[ParsedRow]
) -> int:
    """원장 행 bulk 적재(keep-last UPSERT). 반환 처리 행 수(입력 rows 길이)."""
    if not rows:
        return 0
    params = [_row_params(batch_id, user_id, r) for r in rows]
    await conn.executemany(_UPSERT_LEDGER_SQL, params)
    return len(rows)
