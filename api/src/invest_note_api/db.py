from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import UUID

import asyncpg
from fastapi import Request

from invest_note_api.auth.constants import DB_GUC_USER_ID


async def create_pool(database_url: str) -> asyncpg.Pool:
    # statement_cache_size=0 required for Supavisor transaction mode
    return await asyncpg.create_pool(database_url, min_size=1, max_size=10, statement_cache_size=0)


def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool


@asynccontextmanager
async def acquire_for_user(pool: asyncpg.Pool, user_id: UUID) -> AsyncGenerator[asyncpg.Connection, None]:
    """RLS 활성화 connection을 반환하는 context manager.

    owner 컨텍스트에서 public.users 를 프로비저닝(FK 타깃 보장)한 뒤 app.current_user_id
    GUC 를 주입한다. 사용자 데이터 테이블(accounts/trades/custom_tags)은 FORCE ROW LEVEL
    SECURITY 라 owner 도 정책 대상이 되어, RLS policy 의 public.current_user_id() 가 이 GUC 를
    읽어 본인 행만 노출한다(표준 PostgreSQL). public.users 는 FORCE 미적용 owner-only 테이블
    이라 위 INSERT 가 owner 권한으로 통과한다.

    ⚠️ 앱 접속 역할은 비-superuser owner 여야 한다 — superuser 는 FORCE 여도 RLS 를 우회한다.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO public.users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
                user_id,
            )
            await conn.execute("SELECT set_config($1, $2, true)", DB_GUC_USER_ID, str(user_id))
            yield conn
