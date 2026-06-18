from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import UUID

import asyncpg
from fastapi import Request


async def create_pool(database_url: str) -> asyncpg.Pool:
    # statement_cache_size=0 required for Supavisor transaction mode
    return await asyncpg.create_pool(database_url, min_size=1, max_size=10, statement_cache_size=0)


def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool


@asynccontextmanager
async def acquire_for_user(pool: asyncpg.Pool, user_id: UUID) -> AsyncGenerator[asyncpg.Connection, None]:
    """사용자 요청용 connection을 트랜잭션 안에서 반환하는 context manager.

    public.users 를 먼저 프로비저닝(FK 타깃 보장)한다. 사용자 격리는 RLS 가 아니라 각
    쿼리의 명시적 `WHERE user_id = $1` 로 보장한다(RLS 제거됨).

    트랜잭션 래퍼는 유지한다 — 엔드포인트의 다중 statement 원자성과 pg_advisory_xact_lock
    (트랜잭션 스코프 락)이 이에 의존한다.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO public.users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
                user_id,
            )
            yield conn
