"""Stage 1 캡처 서비스 실DB 통합 테스트 — 파일/거래 dedup(keep-last).

ON CONFLICT UPSERT·partial-unique 동작은 FakePool 로 못 덮으므로 실 PG 로만 검증된다.
`INVEST_NOTE_TEST_DATABASE_URL`(마이그레이션 적용된 실 PG) 설정 시에만 실행, 미설정 시 skip.
R2 는 미설정(r2_enabled=False)으로 두어 원본 파일 저장을 건너뛴다(storage_key=NULL).
"""
from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from uuid import uuid4

import asyncpg
import pytest

from invest_note_api.services.broker_capture import capture_statement

from tests.test_broker_parsers import _buy_row, _make_samsung_xlsx

TEST_DB_URL = os.environ.get("INVEST_NOTE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DB_URL, reason="INVEST_NOTE_TEST_DATABASE_URL 미설정 — 실DB 캡처 테스트 skip"
)

_SETTINGS = SimpleNamespace(r2_enabled=False)
_XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _capture(pool, user_id, file_bytes):
    return await capture_statement(
        pool,
        _SETTINGS,
        user_id=user_id,
        broker_key="samsung_xlsx",
        filename="삼성증권 거래내역서.xlsx",
        content_type=_XLSX_CT,
        file_bytes=file_bytes,
    )


def test_same_file_twice_single_batch_no_dup_rows():
    async def scenario():
        pool = await asyncpg.create_pool(
            TEST_DB_URL, min_size=1, max_size=2, statement_cache_size=0
        )
        try:
            uid = uuid4()
            xlsx = _make_samsung_xlsx([_buy_row()])
            r1 = await _capture(pool, uid, xlsx)
            r2 = await _capture(pool, uid, xlsx)  # 같은 파일 재업로드
            async with pool.acquire() as c:
                nbatch = await c.fetchval(
                    "SELECT count(*) FROM import_batches WHERE user_id=$1", uid
                )
                nrows = await c.fetchval(
                    "SELECT count(*) FROM import_ledger_entries WHERE user_id=$1", uid
                )
            return r1, r2, nbatch, nrows
        finally:
            await pool.close()

    r1, r2, nbatch, nrows = asyncio.run(scenario())
    assert r1.is_new_file is True
    assert r1.trade_row_count == 1
    assert r2.is_new_file is False           # sha256 dedup → batch 재생성 안 함
    assert r2.batch_id == r1.batch_id
    assert nbatch == 1                        # 파일 1개
    assert nrows == 1                         # 거래 1행, 중복 적재 없음
    # 프리뷰만 하고 커밋 안 한 파일을 재업로드해도 preview/commit 은 스킵되지 않는다:
    # is_new=False 는 '원장 재적재·R2 재업로드'만 건너뛸 뿐, parse_result 는 매번 새로 파싱돼
    # 프리뷰 카운트와 commit 물질화 소스(안정적 batch_id 로 기존 원장 행 조회)가 그대로 유효하다.
    assert r2.trade_row_count == 1            # 재업로드도 거래를 그대로 노출(프리뷰 정상)
    assert len(r2.parse_result.trades) == 1
    assert r2.row_count == 0                  # 재적재만 스킵(원장 무중복)


def test_same_trade_different_file_appends_both_renderings():
    """원장은 append-only — 같은 거래가 다른 파일에 또 나타나면 두 렌더링이 모두 남는다.

    (중복 trade 방지는 물질화 Stage 2 의 trade-signature 담당; 원장은 무손실 캡처.)
    """
    async def scenario():
        pool = await asyncpg.create_pool(
            TEST_DB_URL, min_size=1, max_size=2, statement_cache_size=0
        )
        try:
            uid = uuid4()
            # 같은 거래(date/name/qty/price 동일) + 배당(비거래). 수수료만 다름 → 다른 파일.
            file_a = _make_samsung_xlsx([_buy_row(fee=22), _buy_row(name="배당금입금")])
            file_b = _make_samsung_xlsx([_buy_row(fee=99), _buy_row(name="배당금입금")])
            await _capture(pool, uid, file_a)
            await _capture(pool, uid, file_b)
            async with pool.acquire() as c:
                n_trade = await c.fetchval(
                    "SELECT count(*) FROM import_ledger_entries "
                    "WHERE user_id=$1 AND trade_type IS NOT NULL",
                    uid,
                )
                n_non_trade = await c.fetchval(
                    "SELECT count(*) FROM import_ledger_entries "
                    "WHERE user_id=$1 AND trade_type IS NULL",
                    uid,
                )
                fees = await c.fetch(
                    "SELECT raw->>'수수료/Fee' AS fee FROM import_ledger_entries "
                    "WHERE user_id=$1 AND trade_type IS NOT NULL ORDER BY fee",
                    uid,
                )
                nbatch = await c.fetchval(
                    "SELECT count(*) FROM import_batches WHERE user_id=$1", uid
                )
            return n_trade, n_non_trade, [r["fee"] for r in fees], nbatch
        finally:
            await pool.close()

    n_trade, n_non_trade, fees, nbatch = asyncio.run(scenario())
    assert nbatch == 2                        # 서로 다른 파일 2개
    assert n_trade == 2                        # append — 두 렌더링 모두 보존
    assert fees == ["22", "99"]                # 두 파일의 수수료가 각각 남음
    assert n_non_trade == 2                     # 비거래 행도 각 파일에서 보존


def test_r2_disabled_storage_key_null():
    async def scenario():
        pool = await asyncpg.create_pool(
            TEST_DB_URL, min_size=1, max_size=2, statement_cache_size=0
        )
        try:
            uid = uuid4()
            r = await _capture(pool, uid, _make_samsung_xlsx([_buy_row()]))
            async with pool.acquire() as c:
                storage_key = await c.fetchval(
                    "SELECT storage_key FROM import_batches WHERE id=$1::uuid",
                    r.batch_id,
                )
            return storage_key
        finally:
            await pool.close()

    assert asyncio.run(scenario()) is None


def test_cascade_delete_and_set_null():
    """FK 무결성 — 원장 행 삭제 시 trade.source_ledger_entry_id=NULL(SET NULL),
    사용자 삭제 시 batch·원장·trades 전부 CASCADE 삭제.
    """
    async def scenario():
        pool = await asyncpg.create_pool(
            TEST_DB_URL, min_size=1, max_size=2, statement_cache_size=0
        )
        try:
            uid = uuid4()
            await _capture(pool, uid, _make_samsung_xlsx([_buy_row()]))
            async with pool.acquire() as c:
                acct = await c.fetchval(
                    "INSERT INTO accounts (user_id, name, broker, cash_balance)"
                    " VALUES ($1, 'cascade', 'T', 0) RETURNING id",
                    uid,
                )
                entry_id = await c.fetchval(
                    "SELECT id FROM import_ledger_entries"
                    " WHERE user_id=$1 AND trade_type IS NOT NULL LIMIT 1",
                    uid,
                )
                trade_id = await c.fetchval(
                    "INSERT INTO trades (user_id, account_id, asset_name, ticker_symbol,"
                    " market_type, trade_type, price, quantity, traded_at, country_code,"
                    " exchange, exchange_rate, origin, source_ledger_entry_id)"
                    " VALUES ($1,$2,'삼성전자','005930','STOCK','BUY',70000,10, now(),"
                    " 'KR','',1.0,'IMPORT',$3) RETURNING id",
                    uid, acct, entry_id,
                )
                # (a) SET NULL — 원장 행만 삭제 → trade 는 남고 링크만 끊긴다.
                await c.execute("DELETE FROM import_ledger_entries WHERE id=$1", entry_id)
                sle = await c.fetchval(
                    "SELECT source_ledger_entry_id FROM trades WHERE id=$1", trade_id
                )
                # (b) CASCADE — 사용자 삭제 → batch·원장·trades 전부 소멸.
                await c.execute("DELETE FROM public.users WHERE id=$1", uid)
                counts = await c.fetchrow(
                    "SELECT (SELECT count(*) FROM import_batches WHERE user_id=$1) AS b,"
                    " (SELECT count(*) FROM import_ledger_entries WHERE user_id=$1) AS l,"
                    " (SELECT count(*) FROM trades WHERE user_id=$1) AS t",
                    uid,
                )
            return sle, counts["b"], counts["l"], counts["t"]
        finally:
            await pool.close()

    sle, nbatch, nledger, ntrade = asyncio.run(scenario())
    assert sle is None                         # SET NULL 적용
    assert nbatch == 0 and nledger == 0 and ntrade == 0   # user CASCADE
