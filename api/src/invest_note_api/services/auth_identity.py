"""런타임 신원 생성 — BE OAuth 신규 가입자에게 user + auth_identities 매핑을 발급한다.

batch 적재(`auth_identity_import.run_import`)와 분리. callback 의 매핑 miss(= 진짜 신규)에서만 호출된다.

⚠️ gapless 전제: cutover 시 Supabase 신규가입을 동결한 뒤 최종 백필로 `auth_identities` 가
완전·확정되므로, "매핑에 없는 sub = 진짜 신규"가 항상 참이다(기존자 오판→고아화 없음).
따라서 **클라이언트 BE flow 노출(B안: 서버 플래그 flip)은 반드시 완전한 백필 이후**여야 한다
(운영 runbook 가드 — flip 시점이 신규 생성 시작점). 사양: 2b-3.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import asyncpg


async def resolve_user_id(conn: asyncpg.Connection, provider: str, sub: str) -> UUID | None:
    """(provider, IdP sub) → 매핑된 public.users UUID 해석. miss = None.

    ⚠️ B1(HINGE): BE 토큰 sub 는 반드시 이 매핑된 UUID(IdP sub 아님) — 기존자 데이터 고아화 방지.
    provider 는 소문자 정규화한다(적재기·신규 생성과 일관 — 대소문자 drift 로 인한 lockout 차단, F14).
    callback(hit 판정)과 create_user_identity(락 내 재조회)가 공유하는 단일 조회 지점.
    """
    row = await conn.fetchrow(
        "SELECT user_id FROM auth_identities WHERE provider = $1 AND provider_id = $2",
        provider.lower(), sub,
    )
    return row["user_id"] if row else None


async def create_user_identity(conn: asyncpg.Connection, provider: str, sub: str) -> UUID:
    """신규 가입: `public.users` + `auth_identities` 매핑을 생성하고 user_id 를 반환한다.

    동시 첫 로그인(같은 provider+sub 다발) 경쟁은 (provider, sub) advisory xact lock 으로
    직렬화한다(`trades_repo.acquire_trade_group_lock` 패턴 — pooler 안전, 트랜잭션 종료 시 자동
    해제). 락 안에서 재조회 후 없을 때만 생성하므로 중복 user/매핑·orphan users 행이 생기지 않는다.

    provider 는 소문자 정규화한다(적재기·`resolve_user_id` 와 일관 — 대소문자 drift 차단).
    """
    provider = provider.lower()
    async with conn.transaction():
        await conn.execute("SET LOCAL lock_timeout = '2s'")
        await conn.fetchval(
            "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
            f"authid:{provider}:{sub}",
        )

        # 락 내 재조회 — 경쟁자가 먼저 만들었으면 그 UUID 채택(중복 생성·orphan users 행 방지).
        existing = await resolve_user_id(conn, provider, sub)
        if existing is not None:
            return existing

        new_id = uuid4()
        # FK 타깃 보장(auth_identities.user_id → users.id). acquire_for_user(db.py)와 동일 패턴.
        await conn.execute(
            "INSERT INTO public.users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
            new_id,
        )
        # ON CONFLICT: advisory lock 을 잡지 않는 동시 writer(예: 백필 batch import)가 같은 매핑을
        # 선점한 경우에도 500(UniqueViolation) 대신 승자 UUID 채택(위 users INSERT 와 대칭).
        row = await conn.fetchrow(
            "INSERT INTO public.auth_identities (provider, provider_id, user_id) "
            "VALUES ($1, $2, $3) "
            "ON CONFLICT (provider, provider_id) DO NOTHING RETURNING user_id",
            provider, sub, new_id,
        )
        if row is not None:
            return row["user_id"]
        # 경쟁 writer(락 미보유 backfill batch)가 매핑을 선점 → 방금 만든 users(new_id) 는
        # 어떤 auth_identities 도 가리키지 않는 고아. uuid4 라 우리 행만 정리(고아 방지) 후 승자 채택.
        await conn.execute("DELETE FROM public.users WHERE id = $1", new_id)
        winner = await resolve_user_id(conn, provider, sub)
        if winner is None:
            # ON CONFLICT 발생 = 행 존재 의미(런타임에 auth_identities 삭제 경로 없음 → 도달 불가).
            raise RuntimeError("auth_identities conflict but mapping vanished")
        return winner
