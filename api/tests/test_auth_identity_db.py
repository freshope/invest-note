"""실DB 신규 가입 테스트 — create_user_identity 의 de-dup 안전속성(2b-3) 검증.

fake conn 은 advisory lock·FK·UNIQUE(provider, provider_id) 제약을 행사할 수 없어, 이 기능의
핵심 보장("동시 첫 로그인 → 단일 user, 중복/고아 0")을 검증하지 못한다. 그 보장은 실 PG 에서만
드러나므로 여기서 행사한다. `INVEST_NOTE_TEST_DATABASE_URL`(마이그레이션 적용된 실 PG) 설정
시에만 실행하고 미설정 환경(기본 단위 테스트)에서는 skip. CI(migrate-verify)에서 env 주입.
"""
from __future__ import annotations

import asyncio
import os
from uuid import UUID, uuid4

import asyncpg
import pytest

from invest_note_api.services.auth_identity import create_user_identity

TEST_DB_URL = os.environ.get("INVEST_NOTE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DB_URL, reason="INVEST_NOTE_TEST_DATABASE_URL 미설정 — 실DB 신규가입 테스트 skip"
)


async def test_create_user_identity_sequential():
    """신규 생성 → users+auth_identities 행, provider 소문자, 재호출 idempotent(UNIQUE 행사)."""
    conn = await asyncpg.connect(TEST_DB_URL)
    sub = f"newuser-{uuid4()}"
    uid: UUID | None = None
    try:
        uid = await create_user_identity(conn, "Google", sub)  # mixed-case → 소문자 정규화
        assert isinstance(uid, UUID)
        assert await conn.fetchval("SELECT count(*) FROM public.users WHERE id = $1", uid) == 1
        row = await conn.fetchrow(
            "SELECT user_id, provider FROM auth_identities"
            " WHERE provider = 'google' AND provider_id = $1",
            sub,
        )
        assert row is not None and row["user_id"] == uid and row["provider"] == "google"

        # 재호출(같은 provider+sub) → 락 내 재조회로 같은 UUID, 매핑 중복 0.
        uid2 = await create_user_identity(conn, "google", sub)
        assert uid2 == uid
        assert await conn.fetchval(
            "SELECT count(*) FROM auth_identities WHERE provider = 'google' AND provider_id = $1",
            sub,
        ) == 1
    finally:
        if uid is not None:
            # users CASCADE 로 auth_identities 동반 삭제.
            await conn.execute("DELETE FROM public.users WHERE id = $1", uid)
        await conn.close()


async def test_create_user_identity_concurrent_single_user():
    """동시 첫 로그인(같은 provider+sub, 두 연결) → advisory lock + UNIQUE 로 단일 user/매핑."""
    conn1 = await asyncpg.connect(TEST_DB_URL)
    conn2 = await asyncpg.connect(TEST_DB_URL)
    sub = f"race-{uuid4()}"
    uids: list[UUID] = []
    try:
        uids = list(
            await asyncio.gather(
                create_user_identity(conn1, "google", sub),
                create_user_identity(conn2, "google", sub),
            )
        )
        # 둘 다 같은 UUID(경쟁자는 락 내 재조회로 승자 채택).
        assert uids[0] == uids[1]
        winner = uids[0]
        # 정확히 1개 매핑 + 1개 user(중복/고아 0).
        assert await conn1.fetchval(
            "SELECT count(*) FROM auth_identities WHERE provider = 'google' AND provider_id = $1",
            sub,
        ) == 1
        assert await conn1.fetchval(
            "SELECT count(*) FROM public.users WHERE id = $1", winner
        ) == 1
    finally:
        if uids:
            await conn1.execute(
                "DELETE FROM public.users WHERE id = ANY($1::uuid[])",
                list({u for u in uids}),
            )
        await conn1.close()
        await conn2.close()
