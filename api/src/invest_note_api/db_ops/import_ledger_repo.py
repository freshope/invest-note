"""asyncpg 쿼리 묶음 — 거래내역서 원장(import_batches / import_ledger_entries).

Stage 1 캡처가 파일→파싱→원장 적재에 쓴다. 원장은 **append-only** — 거래 dedup 을 하지 않고
모든 행을 그대로 적재한다(무손실). 파일 통째 재업로드만 content_sha256 UNIQUE 로 skip 한다.
같은 거래의 중복 제거는 물질화(Stage 2)의 trade-signature dedup/merge 가 담당한다(계좌 단위).
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

# 원장은 append-only — dedup 없이 모든 행을 그대로 적재(무손실). 같은 거래가 다른 파일에 또
# 나타나면 행이 하나 더 쌓이고, 중복 trade 방지는 물질화(Stage 2)가 계좌 단위로 처리한다.
_INSERT_LEDGER_SQL = """
INSERT INTO import_ledger_entries (
    batch_id, user_id, source_row_no, traded_at_raw, traded_at,
    trade_type, asset_name, ticker_hint, isin, country_code,
    quantity, price, commission, tax, exchange_rate, raw
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16::jsonb
)
"""

# Stage 2 물질화 소스 — batch 의 거래 행(trade_type 有; 비거래/오류 행은 NULL). id 는
# trades.source_ledger_entry_id 링크용.
_SELECT_TRADE_ROWS_SQL = """
SELECT id, source_row_no, traded_at_raw, trade_type, asset_name,
       ticker_hint, isin, country_code, quantity, price,
       commission, tax, exchange_rate
  FROM import_ledger_entries
 WHERE batch_id = $1 AND user_id = $2 AND trade_type IS NOT NULL
 ORDER BY source_row_no
"""

# 등록(commit) 생애주기 마커 — 미리보기만 한 배치(committed_at NULL)와 구분.
# account_id 는 keep-first(COALESCE) — 같은 파일(batch)을 다른 계좌로 재커밋해도 첫 귀속을
# 덮어쓰지 않는다. (batch→account 는 본래 1:1 표기라 다중 계좌 물질화는 설계상 완전 표기 불가;
# 여기서는 조용한 덮어쓰기만 막는다.)
_MARK_COMMITTED_SQL = """
UPDATE import_batches
   SET committed_at = now(),
       account_id = COALESCE(import_batches.account_id, $3)
 WHERE id = $1 AND user_id = $2
"""


def _num(value: object) -> Decimal | None:
    """float/int → numeric(Decimal). asyncpg numeric 은 Decimal 을 요구."""
    if value is None:
        return None
    return Decimal(str(value))


def _row_params(batch_id: UUID, user_id: UUID, row: ParsedRow) -> tuple:
    # traded_at(정규화 timestamptz)은 채우지 않는다 — 진실은 traded_at_raw(원문)이고 정밀 시각은
    # Stage 2 가 raw 에서 도출한다(KST→UTC 변환 중복·tz 버그 회피).
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
        _num(row.commission),
        _num(row.tax),
        _num(row.exchange_rate),
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


async def insert_ledger_entries(
    conn: Any, *, batch_id: UUID, user_id: UUID, rows: list[ParsedRow]
) -> int:
    """원장 행 bulk 적재(append-only). 반환 적재 행 수(입력 rows 길이)."""
    if not rows:
        return 0
    params = [_row_params(batch_id, user_id, r) for r in rows]
    await conn.executemany(_INSERT_LEDGER_SQL, params)
    return len(rows)


async def get_ledger_trade_rows(
    conn: Any, *, batch_id: UUID, user_id: UUID
) -> list[Any]:
    """Stage 2 물질화 소스 — batch 의 거래 행(asyncpg Record 리스트). 없으면 빈 리스트."""
    return await conn.fetch(_SELECT_TRADE_ROWS_SQL, batch_id, user_id)


async def mark_batch_committed(
    conn: Any, *, batch_id: UUID, user_id: UUID, account_id: str
) -> None:
    """등록 완료 마커 — committed_at·account_id 채움(미리보기만 한 배치와 구분).

    account_id 는 요청 문자열 그대로 전달(asyncpg 가 uuid 컬럼으로 변환) — 다른 import 경로와 동일.
    """
    await conn.execute(_MARK_COMMITTED_SQL, batch_id, user_id, account_id)
