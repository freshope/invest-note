"""런타임 신원 생성 — BE OAuth 신규 가입자에게 user + auth_identities 매핑을 발급한다.

batch 적재(`auth_identity_import.run_import`)와 분리. callback 의 매핑 miss(= 진짜 신규)에서만 호출된다.

⚠️ gapless 전제: cutover 시 Supabase 신규가입을 동결한 뒤 최종 백필로 `auth_identities` 가
완전·확정되므로, "매핑에 없는 sub = 진짜 신규"가 항상 참이다(기존자 오판→고아화 없음).
따라서 **BE 활성화는 반드시 완전한 백필 이후**여야 한다(운영 runbook 가드). 사양: 2b-3.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import asyncpg


async def create_user_identity(conn: asyncpg.Connection, provider: str, sub: str) -> UUID:
    """신규 가입: `public.users` + `auth_identities` 매핑을 생성하고 user_id 를 반환한다.

    동시 첫 로그인(같은 provider+sub 다발) 경쟁은 (provider, sub) advisory xact lock 으로
    직렬화한다(`trades_repo.acquire_trade_group_lock` 패턴 — pooler 안전, 트랜잭션 종료 시 자동
    해제). 락 안에서 재조회 후 없을 때만 생성하므로 중복 user/매핑이 생기지 않는다.

    provider 는 소문자 정규화한다(적재기·`_resolve_user_id` 와 일관 — 대소문자 drift 차단).
    """
    provider = provider.lower()
    async with conn.transaction():
        await conn.execute("SET LOCAL lock_timeout = '2s'")
        await conn.fetchval(
            "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
            f"authid:{provider}:{sub}",
        )

        # 락 내 재조회 — 경쟁자가 먼저 만들었으면 그 UUID 채택(중복 생성 금지).
        existing = await conn.fetchrow(
            "SELECT user_id FROM auth_identities WHERE provider = $1 AND provider_id = $2",
            provider, sub,
        )
        if existing is not None:
            return existing["user_id"]

        new_id = uuid4()
        # FK 타깃 보장(auth_identities.user_id → users.id). acquire_for_user(db.py)와 동일 패턴.
        await conn.execute(
            "INSERT INTO public.users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
            new_id,
        )
        await conn.execute(
            "INSERT INTO public.auth_identities (provider, provider_id, user_id) "
            "VALUES ($1, $2, $3)",
            provider, sub, new_id,
        )
        return new_id
