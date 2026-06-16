from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import UUID

import asyncpg
from fastapi import Request

from invest_note_api.auth.constants import DB_APP_ROLE, DB_GUC_USER_ID


async def create_pool(database_url: str) -> asyncpg.Pool:
    # statement_cache_size=0 required for Supavisor transaction mode
    return await asyncpg.create_pool(database_url, min_size=1, max_size=10, statement_cache_size=0)


def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool


@asynccontextmanager
async def acquire_for_user(pool: asyncpg.Pool, user_id: UUID) -> AsyncGenerator[asyncpg.Connection, None]:
    """RLS 활성화 connection을 반환하는 context manager.

    owner 컨텍스트에서 public.users 를 프로비저닝(FK 타깃 보장)한 뒤, app_authenticated
    역할로 내려가고 app.current_user_id GUC 를 주입한다. RLS policy 의
    public.current_user_id() 가 이 GUC 를 읽어 본인 행만 노출한다(표준 PostgreSQL).
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO public.users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
                user_id,
            )
            await conn.execute(f"SET LOCAL ROLE {DB_APP_ROLE}")
            await conn.execute("SELECT set_config($1, $2, true)", DB_GUC_USER_ID, str(user_id))
            yield conn
