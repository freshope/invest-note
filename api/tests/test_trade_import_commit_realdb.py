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

import asyncio
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


async def test_concurrent_recommit_no_duplicate_trades():
    """같은 batch_id 동시 재커밋(더블클릭·재시도·두 탭) → 거래 중복 INSERT 없음 (H1 회귀).

    조회-후-INSERT dedup 을 advisory lock 안으로 재배치 + 부분 UNIQUE(0015)로 TOCTOU 를 막는다.
    단일 그룹(같은 ticker) 이라 두 커밋이 같은 advisory lock 을 직접 경합한다. lock 전 조회하던
    구조에선 둘 다 빈 그룹을 읽어 각자 INSERT → trades 2건(중복)이 됐을 시나리오.
    """
    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=2, max_size=6, statement_cache_size=0)
    uid = None
    try:
        async with pool.acquire() as conn:
            uid, acct = await _seed_account(conn, name="concurrent-recommit")
            sid = await _seed_ledger(conn, uid, [
                _row("005930", "삼성전자", "BUY", 10, 70000, "2024-01-10"),
            ])

        app = _make_app()
        app.state.pool = pool
        async with _client_as(app, uid) as ac:
            r1, r2 = await asyncio.gather(
                ac.post("/v1/trades/import/commit", json={"staging_id": sid, "account_id": acct}),
                ac.post("/v1/trades/import/commit", json={"staging_id": sid, "account_id": acct}),
            )
        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text

        # 핵심: 동시 커밋에도 원장 거래 1행 → trades 정확히 1건(중복 INSERT 없음).
        async with pool.acquire() as conn:
            n = await conn.fetchval(
                "SELECT count(*) FROM trades WHERE user_id = $1", UUID(uid)
            )
        assert n == 1, f"동시 재커밋으로 중복 INSERT 발생: trades={n} (기대 1)"
        # 한쪽이 먼저 INSERT 하면 다른 쪽은 skip(재조회로 발견) 또는 중복 거절 → insert 합 ≤ 1.
        assert r1.json()["inserted_count"] + r2.json()["inserted_count"] <= 1
    finally:
        if uid is not None:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM public.users WHERE id = $1", UUID(uid))
        await pool.close()


async def test_commit_rejects_other_users_batch():
    """user 격리 — A 의 batch_id 로 B 가 commit 시도해도 A 의 원장을 물질화하지 못한다.

    commit 격리는 오직 get_ledger_trade_rows 의 `WHERE ... AND user_id = $2` 에 의존한다.
    B 로 커밋하면 그 필터가 A 의 원장 행을 걸러내 빈 결과 → 400(등록할 거래 없음)이고 B 계좌엔
    아무것도 남지 않는다. FakePool 단위 테스트는 이 SQL 을 실행하지 못하므로(mock) 실DB 로만
    이 필터의 회귀를 잡을 수 있다.
    """
    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=1, max_size=4, statement_cache_size=0)
    uid_a = uid_b = None
    try:
        async with pool.acquire() as conn:
            uid_a, _ = await _seed_account(conn, name="ledger-owner")
            uid_b, acct_b = await _seed_account(conn, name="other-user")
            sid = await _seed_ledger(conn, uid_a, [
                _row("005930", "삼성전자", "BUY", 10, 70000, "2024-01-10"),
            ])

        app = _make_app()
        app.state.pool = pool
        async with _client_as(app, uid_b) as ac:
            r = await ac.post(
                "/v1/trades/import/commit",
                json={"staging_id": sid, "account_id": acct_b},
            )
        assert r.status_code == 400, r.text  # 타 user 원장 → 거래 없음

        # 핵심: B 계좌에 A 의 거래가 물질화되지 않았다.
        async with pool.acquire() as conn:
            n = await conn.fetchval(
                "SELECT count(*)::int FROM trades WHERE user_id = $1", UUID(uid_b)
            )
        assert n == 0, f"타 user 원장이 물질화됨: trades={n} (기대 0)"
    finally:
        async with pool.acquire() as conn:
            for u in (uid_a, uid_b):
                if u is not None:
                    await conn.execute("DELETE FROM public.users WHERE id = $1", UUID(u))
        await pool.close()


async def test_recommit_after_ticker_reresolve_is_idempotent():
    """재커밋 사이 원장 entry 의 ticker 재해소가 바뀌어도 dead-end 없이 멱등 skip 된다.

    ticker 가 달라지면 group_key 가 바뀌어 signature dedup 이 기존 trade 를 못 찾는다. 예전엔
    이때 INSERT 가 (account_id, source_ledger_entry_id) 부분 UNIQUE 를 위반→그룹 전체가 '중복
    거래' 오류로 롤백되는 dead-end 였다. 이제 insert_trades_bulk 의 ON CONFLICT DO NOTHING 이
    DB 레벨에서 조용히 건너뛴다 → 오류 없이, entry 는 계좌당 1회만 물질화(중복 trade 없음).
    """
    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=1, max_size=4, statement_cache_size=0)
    uid = None
    try:
        async with pool.acquire() as conn:
            uid, acct = await _seed_account(conn, name="reresolve")
            sid = await _seed_ledger(conn, uid, [
                _row("005930", "삼성전자", "BUY", 10, 70000, "2024-01-10"),
            ])

        app = _make_app()
        app.state.pool = pool
        async with _client_as(app, uid) as ac:
            r1 = await ac.post("/v1/trades/import/commit", json={"staging_id": sid, "account_id": acct})
        assert r1.status_code == 200, r1.text
        assert r1.json()["inserted_count"] == 1

        # ticker 재해소 drift 시뮬레이션 — 같은 entry 의 hint 를 바꿔 다음 커밋이 다른 ticker 로 해소되게.
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE import_ledger_entries SET ticker_hint = '000660' WHERE batch_id = $1",
                UUID(sid),
            )

        async with _client_as(app, uid) as ac:
            r2 = await ac.post("/v1/trades/import/commit", json={"staging_id": sid, "account_id": acct})
        assert r2.status_code == 200, r2.text
        assert r2.json()["error_count"] == 0, r2.text  # dead-end('중복 거래') 없음

        # entry 는 계좌당 1회만 물질화 — 재해소 재커밋으로 중복 trade 없음.
        async with pool.acquire() as conn:
            n = await conn.fetchval(
                "SELECT count(*)::int FROM trades WHERE user_id = $1", UUID(uid)
            )
        assert n == 1, f"재해소 재커밋으로 중복 trade 발생: trades={n} (기대 1)"
    finally:
        if uid is not None:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM public.users WHERE id = $1", UUID(uid))
        await pool.close()
