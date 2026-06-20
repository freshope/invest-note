"""services.auth_identity.create_user_identity — 신규 가입 단건 생성(2b-3).

race-safety 의 핵심 로직(락 안에서 재조회 후 없을 때만 생성)을 fake conn 으로 검증한다.
true 동시성은 실 DB 가 필요하나, "이미 매핑이 있으면 재생성하지 않고 같은 UUID 채택"이
중복 user/매핑을 막는 불변식이므로 이를 단위로 행사한다.
"""
from contextlib import asynccontextmanager
from uuid import UUID

from invest_note_api.services.auth_identity import create_user_identity


class _Conn:
    """create_user_identity 가 치는 SQL 만 해석하는 최소 fake."""

    def __init__(self):
        self.identities: dict[tuple[str, str], UUID] = {}
        self.users: set[UUID] = set()

    @asynccontextmanager
    async def transaction(self):
        yield

    async def fetchval(self, sql, *args):
        assert "pg_advisory_xact_lock" in sql
        return 1

    async def fetchrow(self, sql, *args):
        assert "FROM auth_identities" in sql
        uid = self.identities.get((args[0], args[1]))
        return {"user_id": uid} if uid else None

    async def execute(self, sql, *args):
        if sql.startswith("SET LOCAL"):
            return
        if "INSERT INTO public.users" in sql:
            self.users.add(args[0])
            return
        if "INSERT INTO public.auth_identities" in sql:
            self.identities[(args[0], args[1])] = args[2]
            return
        raise AssertionError(sql)


async def test_create_new_identity():
    conn = _Conn()
    uid = await create_user_identity(conn, "google", "sub-1")
    assert isinstance(uid, UUID)
    assert conn.users == {uid}
    assert conn.identities[("google", "sub-1")] == uid


async def test_reresolve_no_duplicate():
    # 동일 (provider, sub) 재호출(경쟁 시뮬) → 같은 UUID, user/매핑 중복 0.
    conn = _Conn()
    uid1 = await create_user_identity(conn, "google", "sub-1")
    uid2 = await create_user_identity(conn, "google", "sub-1")
    assert uid2 == uid1
    assert len(conn.users) == 1
    assert len(conn.identities) == 1


async def test_provider_lowercased():
    conn = _Conn()
    await create_user_identity(conn, "GOOGLE", "sub-x")
    assert ("google", "sub-x") in conn.identities
