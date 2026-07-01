"""HTTP 레이어 cross-user 격리 테스트 — 라우터에 인라인된 `WHERE user_id` 필터의 회귀 가드.

`test_user_isolation_db.py` 는 repo 함수만 커버하고, `routers/accounts.py` 가 직접 작성한
인라인 SQL(`get_trade_count` exists-check / `delete_account` DELETE)은 미커버였다. 이 테스트는
실 PG + ASGI 앱 + 두 사용자 시드로, A 로 인증한 HTTP 요청이 B 데이터를 보거나 삭제하지
못하는지 검증한다 — 인라인 쿼리에서 `AND user_id` 가 누락되면 실패한다.

기존 HTTP 테스트(`test_accounts.py`)는 FakeConnection(mock)이라 SQL 내용과 무관하게 고정 행을
반환 → 필터 누락을 못 잡는다. 이 회귀 가드는 실 DB 가 필수다.

`INVEST_NOTE_TEST_DATABASE_URL`(마이그레이션 적용된 실 PG, plain postgresql://) 설정 시에만
실행한다. CI(ci-api.yml User isolation 스텝)에서 이 env 를 주입한다. 미설정 환경(기본 단위
테스트)에서는 skip.
"""
from __future__ import annotations

import os
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from httpx import ASGITransport

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser

from tests.conftest import _make_app

TEST_DB_URL = os.environ.get("INVEST_NOTE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DB_URL, reason="INVEST_NOTE_TEST_DATABASE_URL 미설정 — 실DB 격리 테스트 skip"
)


async def _seed_user(conn, *, name: str) -> tuple[str, str]:
    """user + account + BUY trade 1건 시드. (user_id, account_id) 반환."""
    user_id = str(uuid4())
    await conn.execute("INSERT INTO public.users (id) VALUES ($1)", user_id)
    account_id = await conn.fetchval(
        "INSERT INTO accounts (user_id, name, broker, cash_balance)"
        " VALUES ($1, $2, 'TEST', 0) RETURNING id",
        user_id,
        name,
    )
    await conn.execute(
        "INSERT INTO trades"
        " (user_id, account_id, asset_name, trade_type, price, quantity, ticker_symbol, exchange)"
        " VALUES ($1, $2, $3, 'BUY', 100, 1, 'TST', 'KRX')",
        user_id,
        account_id,
        name,
    )
    return user_id, str(account_id)


async def _empty_account(conn, user_id: str, *, name: str) -> str:
    """거래 없는 계좌 1건 시드 — delete 격리 검증용(NOT EXISTS(trades) 가드 우회 방지)."""
    return str(
        await conn.fetchval(
            "INSERT INTO accounts (user_id, name, broker, cash_balance)"
            " VALUES ($1, $2, 'TEST', 0) RETURNING id",
            user_id,
            name,
        )
    )


def _client_as(app, user_id: str) -> httpx.AsyncClient:
    """user_id 로 인증된 ASGI 클라이언트. sync TestClient 는 실 async 풀과 같은 루프에서
    portal 데드락 위험 → httpx.AsyncClient + ASGITransport 로 같은 이벤트 루프에서 구동한다."""
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=UUID(user_id), email="a@example.com", raw={}
    )
    return httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    )


async def test_http_routes_scope_to_user_after_rls_removed():
    pool = await asyncpg.create_pool(TEST_DB_URL, min_size=1, max_size=4, statement_cache_size=0)
    ua = ub = None  # 시드가 중간에 던져도 finally cleanup 이 NameError 로 원인을 가리지 않게.
    try:
        async with pool.acquire() as conn:
            ua, aa = await _seed_user(conn, name="userA")
            ub, ab = await _seed_user(conn, name="userB")
            ab_empty = await _empty_account(conn, ub, name="userB-empty")

        app = _make_app()
        app.state.pool = pool  # get_pool(request) 가 request.app.state.pool 을 읽는다.

        async with _client_as(app, ua) as ac:
            # GET /accounts: A 는 A 계좌만, B 계좌 누출 금지. trade_count 정확.
            r = await ac.get("/v1/accounts")
            assert r.status_code == 200
            ids = {a["id"] for a in r.json()}
            assert aa in ids
            assert ab not in ids and ab_empty not in ids
            a_acct = next(a for a in r.json() if a["id"] == aa)
            assert a_acct["trade_count"] == 1

            # GET /accounts/{B}/trade-count: 타인 계좌는 404 (exists-check 인라인 필터).
            # AND user_id 누락 시 200 으로 B 존재+카운트 노출 → 실패.
            r = await ac.get(f"/v1/accounts/{ab}/trade-count")
            assert r.status_code == 404

            # 본인 계좌는 정상 카운트.
            r = await ac.get(f"/v1/accounts/{aa}/trade-count")
            assert r.status_code == 200
            assert r.json() == {"count": 1}

            # DELETE /accounts/{B-empty}: 타인 빈 계좌 삭제 불가 → 404 (DELETE 인라인 필터).
            # AND user_id 누락 시 204 + 실제 삭제 → 실패.
            r = await ac.delete(f"/v1/accounts/{ab_empty}")
            assert r.status_code == 404

        # B 의 빈 계좌가 DB 에 그대로 살아있는지 raw 확인 (HTTP 404 가 실제 보존을 보장).
        async with pool.acquire() as conn:
            still = await conn.fetchval("SELECT id FROM accounts WHERE id = $1", UUID(ab_empty))
        assert still is not None
    finally:
        seeded = [u for u in (ua, ub) if u is not None]
        if seeded:
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM public.users WHERE id = ANY($1::uuid[])", seeded
                )
        await pool.close()
