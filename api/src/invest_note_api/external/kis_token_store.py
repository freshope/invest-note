"""KIS 접근토큰 DB 영속화 — kis_tokens 테이블 read/write + 발급 직렬화 락.

토큰은 서버 전용 비밀이라 RLS 정책 없는 테이블(owner 접속만 통과)을 plain
`pool.acquire()` 로 접근한다 (acquire_for_user 금지 — authenticated role 은 차단됨).
발급 직렬화는 트랜잭션 스코프 advisory lock 사용 — session-level 은 Supavisor
transaction mode 에서 leak (trades_repo.acquire_trade_group_lock 과 동일 패턴).

kis.py 가 이 모듈을 import 한다 (역방향 import 금지 — 순환 방지).
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

SCOPE_APP = "app"

_LOCK_KEY = "kis_tokens:" + SCOPE_APP

_SELECT_SQL = "SELECT access_token, expires_at FROM kis_tokens WHERE scope = $1"
_UPSERT_SQL = """
    INSERT INTO kis_tokens (scope, access_token, expires_at, issued_at)
    VALUES ($1, $2, $3, now())
    ON CONFLICT (scope) DO UPDATE
       SET access_token = excluded.access_token,
           expires_at   = excluded.expires_at,
           issued_at    = excluded.issued_at
"""


def _row_to_token(row: Any) -> tuple[str, float] | None:
    if row is None:
        return None
    return row["access_token"], row["expires_at"].timestamp()


async def load(pool: Any) -> tuple[str, float] | None:
    """저장된 토큰 (access_token, expires_at epoch) 반환. 없으면 None."""
    async with pool.acquire() as conn:
        return _row_to_token(await conn.fetchrow(_SELECT_SQL, SCOPE_APP))


async def load_in(conn: Any) -> tuple[str, float] | None:
    """issue_lock 트랜잭션 내 재조회(double-check)용."""
    return _row_to_token(await conn.fetchrow(_SELECT_SQL, SCOPE_APP))


async def save_in(conn: Any, token: str, expires_at: float) -> None:
    """issue_lock 트랜잭션 내 upsert — 락 해제(commit)와 함께 공개된다."""
    await conn.execute(
        _UPSERT_SQL, SCOPE_APP, token, datetime.fromtimestamp(expires_at, tz=timezone.utc)
    )


@asynccontextmanager
async def issue_lock(pool: Any) -> AsyncGenerator[Any, None]:
    """발급 직렬화 — 트랜잭션을 열고 advisory xact lock 을 잡은 conn 을 yield."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            # holder 의 정상 발급(레이트 슬롯 대기 + HTTP 5s)은 덮되, stuck holder 시
            # 요청 경로가 무기한 블록되지 않게 상한 — 초과(55P03)는 get_access_token 의
            # except 가 잡아 None 반환 → 공급자 체인 fallback.
            await conn.execute("SET LOCAL lock_timeout = '10s'")
            await conn.fetchval(
                "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", _LOCK_KEY
            )
            yield conn
