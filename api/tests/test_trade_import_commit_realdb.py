"""import/commit 실DB 통합 테스트 — Fake harness 가 못 덮던 잔여 경로 커버.

`test_trade_import_http.py`(FakePool)는 commit 을 staging 가드(만료 400·타user 403)까지만
커버한다. commit 의 전체 INSERT/merge/skip 버킷팅과 `recalc_group_pnl`(SELL pnl 재계산)은
group·pnl mock 표면이 커 fragile → 실 PG + ASGI 로만 신뢰성 있게 검증된다. preview 의
`_validate_import_groups`(oversell) 도 함께 커버한다.

`INVEST_NOTE_TEST_DATABASE_URL`(마이그레이션 적용된 실 PG) 설정 시에만 실행하고, CI
(ci-api.yml User isolation 스텝의 실DB pytest invocation)에서 이 env 를 주입한다. 미설정
환경(기본 단위 테스트)에서는 skip.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from httpx import ASGITransport

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.routers.trades import _validate_import_groups

from tests.conftest import _make_app

TEST_DB_URL = os.environ.get("INVEST_NOTE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DB_URL, reason="INVEST_NOTE_TEST_DATABASE_URL 미설정 — 실DB import 테스트 skip"
)


def _row(ticker, name, ttype, qty, price, kst, *, commission=0.0, tax=0.0) -> dict:
    """preview 가 staging 하는 row dict 형태(commit 이 읽는 키만). traded_at_kst_full 없음
    → commit 은 KST 장 시작(09:00) 고정, 머지에서 traded_at 비교 안 함."""
    return {
        "asset_name": name,
        "ticker_symbol": ticker,
        "market_type": "STOCK",
        "trade_type": ttype,
        "price": price,
        "quantity": qty,
        "traded_at_kst": kst,
        "traded_at_kst_full": None,
        "commission": commission,
        "tax": tax,
        "country_code": "KR",
        "exchange_rate": 1.0,
        "exchange": "",
    }


async def _seed_account(conn, *, name: str) -> tuple[str, str]:
    """user + 빈 account 시드. (user_id, account_id) 반환."""
    user_id = str(uuid4())
    await conn.execute("INSERT INTO public.users (id) VALUES ($1)", user_id)
    account_id = await conn.fetchval(
        "INSERT INTO accounts (user_id, name, broker, cash_balance)"
        " VALUES ($1, $2, 'TEST', 0) RETURNING id",
        user_id,
        name,
    )
    return user_id, str(account_id)


async def _insert_trade(conn, user_id, account_id, *, ticker, name, ttype, qty, price, kst, commission, tax) -> None:
    """기존 IMPORT 거래 1건 raw 삽입 — merge/skip 대상. traded_at 은 KST date 09:00 → UTC."""
    traded_at = datetime.fromisoformat(kst).replace(hour=0, tzinfo=timezone.utc)  # KST 09:00 = UTC 00:00
    await conn.execute(
        "INSERT INTO trades (user_id, account_id, asset_name, ticker_symbol, market_type,"
        " trade_type, price, quantity, traded_at, commission, tax, country_code, exchange,"
        " exchange_rate, origin)"
        " VALUES ($1,$2,$3,$4,'STOCK',$5,$6,$7,$8,$9,$10,'KR','',1.0,'IMPORT')",
        user_id, account_id, name, ticker, ttype, price, qty, traded_at, commission, tax,
    )


async def _seed_ledger(conn, user_id: str, rows: list[dict]) -> str:
    """원장(batch + 거래 행)을 실DB 에 pre-seed 하고 batch_id(str) 반환.

    commit 이 batch_id(=staging_id 필드)로 원장을 읽어 재해소·물질화한다. ticker_hint=ticker 로
    두면 resolve_tickers 가 hint 를 권위로 즉시 해소(stocks 시드 불필요). raw 는 최소 더미.
    """
    batch_id = await conn.fetchval(
        "INSERT INTO import_batches (user_id, broker_key, parser_version, content_sha256)"
        " VALUES ($1, 'test', '1', $2) RETURNING id",
        UUID(user_id),
        str(uuid4()),
    )
    for i, r in enumerate(rows, start=1):
        # 거래 행은 trade_type 이 채워져 있어 get_ledger_trade_rows(trade_type IS NOT NULL)에 잡힌다.
        await conn.execute(
            "INSERT INTO import_ledger_entries (batch_id, user_id, source_row_no,"
            " traded_at_raw, trade_type, asset_name, ticker_hint, country_code,"
            " quantity, price, commission, tax, exchange_rate, raw)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'{}'::jsonb)",
            batch_id,
            UUID(user_id),
            i,
            r["traded_at_kst"],
            r["trade_type"],
            r["asset_name"],
            r["ticker_symbol"],
            r["country_code"],
            Decimal(str(r["quantity"])),
            Decimal(str(r["price"])),
            Decimal(str(r["commission"])),
            Decimal(str(r["tax"])),
            Decimal(str(r["exchange_rate"])),
        )
    return str(batch_id)


def _client_as(app, user_id: str) -> httpx.AsyncClient:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=UUID(user_id), email="a@example.com", raw={}
    )
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_commit_inserts_new_and_recomputes_sell_pnl():
    """BUY 10@70000 + SELL 5@80000 commit → inserted_count=2, SELL 행 pnl 재계산됨."""
    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=1, max_size=4, statement_cache_size=0)
    uid = None
    try:
        async with pool.acquire() as conn:
            uid, acct = await _seed_account(conn, name="commit-insert")
            sid = await _seed_ledger(conn, uid, [
                _row("005930", "삼성전자", "BUY", 10, 70000, "2024-01-10"),
                _row("005930", "삼성전자", "SELL", 5, 80000, "2024-01-20"),
            ])

        app = _make_app()
        app.state.pool = pool
        async with _client_as(app, uid) as ac:
            r = await ac.post("/v1/trades/import/commit", json={"staging_id": sid, "account_id": acct})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["inserted_count"] == 2
        assert body["merged_count"] == 0
        assert body["skipped_count"] == 0
        assert body["error_count"] == 0

        # recalc_group_pnl 검증: SELL 행이 실제로 pnl 계산값을 저장했는지 (200/count 로는 못 잡음).
        async with pool.acquire() as conn:
            sell = await conn.fetchrow(
                "SELECT profit_loss, avg_buy_price, holding_days FROM trades"
                " WHERE user_id = $1 AND trade_type = 'SELL'",
                UUID(uid),
            )
        assert sell is not None
        assert float(sell["profit_loss"]) == 50000.0  # (80000-70000)*5, 수수료 0
        assert float(sell["avg_buy_price"]) == 70000.0
        assert sell["holding_days"] == 10  # 2024-01-10 → 2024-01-20
    finally:
        if uid is not None:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM public.users WHERE id = $1", UUID(uid))
        await pool.close()


async def test_commit_merges_and_skips():
    """기존 IMPORT 거래 2건에 대해 동일행(skip) + commission 다른 행(merge) commit.

    merged_count=1·skipped_count=1·inserted_count=0, merge 대상 commission 이 실제 갱신된다.
    """
    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=1, max_size=4, statement_cache_size=0)
    uid = None
    try:
        async with pool.acquire() as conn:
            uid, acct = await _seed_account(conn, name="commit-merge")
            # A: skip 대상(완전 동일), B: merge 대상(commission 만 다름).
            await _insert_trade(conn, uid, acct, ticker="AAA", name="에이", ttype="BUY",
                                qty=3, price=1000, kst="2024-02-01", commission=5, tax=0)
            await _insert_trade(conn, uid, acct, ticker="BBB", name="비이", ttype="BUY",
                                qty=2, price=2000, kst="2024-02-02", commission=5, tax=0)
            sid = await _seed_ledger(conn, uid, [
                _row("AAA", "에이", "BUY", 3, 1000, "2024-02-01", commission=5),   # 동일 → skip
                _row("BBB", "비이", "BUY", 2, 2000, "2024-02-02", commission=9),   # commission 변경 → merge
            ])

        app = _make_app()
        app.state.pool = pool
        async with _client_as(app, uid) as ac:
            r = await ac.post("/v1/trades/import/commit", json={"staging_id": sid, "account_id": acct})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["inserted_count"] == 0
        assert body["merged_count"] == 1
        assert body["skipped_count"] == 1
        assert body["error_count"] == 0

        async with pool.acquire() as conn:
            b_comm = await conn.fetchval(
                "SELECT commission FROM trades WHERE user_id = $1 AND ticker_symbol = 'BBB'",
                UUID(uid),
            )
            total = await conn.fetchval(
                "SELECT count(*)::int FROM trades WHERE user_id = $1", UUID(uid)
            )
        assert float(b_comm) == 9.0  # merge 로 commission 갱신
        assert total == 2  # skip/merge 라 신규 INSERT 없음
    finally:
        if uid is not None:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM public.users WHERE id = $1", UUID(uid))
        await pool.close()


async def test_commit_sets_source_ledger_provenance():
    """물질화된 trade 의 source_ledger_entry_id 가 원본 원장 행 id 를 정확히 가리킨다."""
    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=1, max_size=4, statement_cache_size=0)
    uid = None
    try:
        async with pool.acquire() as conn:
            uid, acct = await _seed_account(conn, name="provenance")
            sid = await _seed_ledger(conn, uid, [
                _row("005930", "삼성전자", "BUY", 10, 70000, "2024-05-01"),
            ])
            entry_id = await conn.fetchval(
                "SELECT id FROM import_ledger_entries WHERE user_id = $1", UUID(uid)
            )

        app = _make_app()
        app.state.pool = pool
        async with _client_as(app, uid) as ac:
            r = await ac.post("/v1/trades/import/commit", json={"staging_id": sid, "account_id": acct})
        assert r.status_code == 200, r.text
        assert r.json()["inserted_count"] == 1

        async with pool.acquire() as conn:
            sle = await conn.fetchval(
                "SELECT source_ledger_entry_id FROM trades"
                " WHERE user_id = $1 AND trade_type = 'BUY'",
                UUID(uid),
            )
            batch = await conn.fetchrow(
                "SELECT committed_at, account_id FROM import_batches WHERE id = $1::uuid",
                sid,
            )
        assert sle == entry_id  # provenance 링크가 원장 행을 정확히 가리킴
        # 등록 생애주기 마커 — commit 후 committed_at·account_id 채워짐(미리보기만 한 배치와 구분).
        assert batch["committed_at"] is not None
        assert str(batch["account_id"]) == acct
    finally:
        if uid is not None:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM public.users WHERE id = $1", UUID(uid))
        await pool.close()


async def test_preview_validate_flags_oversell():
    """_validate_import_groups: 보유 없는 종목의 SELL 은 oversell → validation_errors + excluded_count."""
    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=1, max_size=4, statement_cache_size=0)
    uid = None
    try:
        async with pool.acquire() as conn:
            uid, acct = await _seed_account(conn, name="oversell")

        rows = [_row("CCC", "씨이", "SELL", 10, 1000, "2024-03-01")]
        errors, excluded = await _validate_import_groups(pool, UUID(uid), acct, rows)
        assert errors, "보유 없는 SELL 은 oversell 로 검출되어야 한다"
        assert excluded == 1  # 실패 그룹의 row 합계
    finally:
        if uid is not None:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM public.users WHERE id = $1", UUID(uid))
        await pool.close()
