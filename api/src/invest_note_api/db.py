import json
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
    """RLS 활성화 connection을 반환하는 context manager.

    transaction 내부에서 role + jwt.claims GUC를 주입해 auth.uid()가
    Supabase RLS policy에서 올바르게 동작하도록 한다.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('role', 'authenticated', true),"
                "       set_config('request.jwt.claims', $1, true)",
                json.dumps({"sub": str(user_id), "role": "authenticated"}),
            )
            yield conn
