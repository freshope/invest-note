"""services.auth_identity.create_user_identity — 신규 가입 단건 생성(2b-3).

race-safety 의 핵심 로직(락 안에서 재조회 후 없을 때만 생성)을 fake conn 으로 검증한다.
true 동시성은 실 DB 가 필요하나, "이미 매핑이 있으면 재생성하지 않고 같은 UUID 채택"이
중복 user/매핑을 막는 불변식이므로 이를 단위로 행사한다.
"""
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from invest_note_api.services.auth_identity import (
    create_user_identity,
    link_user_by_verified_email,
)


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
        if "INSERT INTO public.auth_identities" in sql:
            # ON CONFLICT DO NOTHING RETURNING: 이미 있으면 None, 없으면 삽입 후 {user_id}.
            provider, sub, uid = args
            if (provider, sub) in self.identities:
                return None
            self.identities[(provider, sub)] = uid
            return {"user_id": uid}
        assert "FROM auth_identities" in sql
        uid = self.identities.get((args[0], args[1]))
        return {"user_id": uid} if uid else None

    async def execute(self, sql, *args):
        if sql.startswith("SET LOCAL"):
            return
        if "INSERT INTO public.users" in sql:
            self.users.add(args[0])
            return
        if "DELETE FROM public.users" in sql:
            self.users.discard(args[0])
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


class _RaceConn(_Conn):
    """락 미보유 동시 writer(backfill batch) 가 재조회 직후 매핑을 선점한 상황 시뮬.

    resolve#1(락 내 재조회)=miss → users INSERT → auth_identities INSERT=ON CONFLICT(None)
    → resolve#2(패배 후 재조회)=winner. 이 경로에서 방금 만든 users(new_id) 고아가 정리되는지 검증.
    """

    def __init__(self, winner: UUID):
        super().__init__()
        self._winner = winner
        self._select_calls = 0

    async def fetchrow(self, sql, *args):
        if "INSERT INTO public.auth_identities" in sql:
            return None  # 경쟁자가 이미 선점 → ON CONFLICT DO NOTHING → row 없음
        assert "FROM auth_identities" in sql
        self._select_calls += 1
        return None if self._select_calls == 1 else {"user_id": self._winner}


async def test_backfill_race_no_orphan_user():
    winner = uuid4()
    conn = _RaceConn(winner)
    uid = await create_user_identity(conn, "google", "sub-r")
    assert uid == winner  # 승자 UUID 채택(중복 user 생성 안 함)
    assert conn.users == set()  # 방금 INSERT 한 new_id 고아가 DELETE 로 정리됨


class _LinkConn:
    """link_user_by_verified_email 이 치는 SQL(user_profiles SELECT + auth_identities INSERT/SELECT)만 해석."""

    def __init__(self, profiles=(), identities=None):
        # profiles: [(email, email_verified, user_id), ...]
        self.profiles = list(profiles)
        self.identities: dict[tuple[str, str], UUID] = dict(identities or {})

    async def fetch(self, sql, *args):
        # WHERE lower(email)=lower($1) AND email_verified IS TRUE → distinct user_id.
        assert "FROM public.user_profiles" in sql
        email = args[0]
        seen: list[UUID] = []
        for e, verified, uid in self.profiles:
            if e is not None and e.lower() == email.lower() and verified is True and uid not in seen:
                seen.append(uid)
        return [{"user_id": u} for u in seen]

    async def fetchrow(self, sql, *args):
        if "INSERT INTO public.auth_identities" in sql:
            provider, sub, uid = args
            if (provider, sub) in self.identities:
                return None  # ON CONFLICT DO NOTHING → 경쟁자 선점
            self.identities[(provider, sub)] = uid
            return {"user_id": uid}
        assert "FROM auth_identities" in sql  # resolve_user_id 재조회
        uid = self.identities.get((args[0], args[1]))
        return {"user_id": uid} if uid else None


async def test_link_single_verified_match():
    # 카카오로 만든 verified 프로필 1개 → 구글 첫 로그인이 같은 user 에 연결(중복 user 생성 안 함).
    target = uuid4()
    conn = _LinkConn(profiles=[("a@x.com", True, target)])
    uid = await link_user_by_verified_email(
        conn, "google", "g-sub", email="a@x.com", email_verified=True
    )
    assert uid == target
    assert conn.identities[("google", "g-sub")] == target


async def test_link_new_side_unverified_returns_none():
    # 가드: 새 IdP 이메일 미인증 → 연결 안 함(하이재킹 방지). 신규 생성으로 폴백.
    conn = _LinkConn(profiles=[("a@x.com", True, uuid4())])
    uid = await link_user_by_verified_email(
        conn, "google", "g-sub", email="a@x.com", email_verified=False
    )
    assert uid is None
    assert conn.identities == {}


async def test_link_new_side_no_email_returns_none():
    # 가드: 카카오 email scope 미동의(email=None) → 연결 안 함.
    conn = _LinkConn(profiles=[("a@x.com", True, uuid4())])
    uid = await link_user_by_verified_email(
        conn, "google", "g-sub", email=None, email_verified=True
    )
    assert uid is None


async def test_link_existing_side_unverified_excluded():
    # 가드: 기존 계정이 email_verified=False/null → 후보 제외. 신고 케이스(카카오 먼저)는 카카오가
    # is_email_verified=true 를 줄 때만 연결됨을 명시 검증.
    conn = _LinkConn(profiles=[("a@x.com", False, uuid4()), ("a@x.com", None, uuid4())])
    uid = await link_user_by_verified_email(
        conn, "google", "g-sub", email="a@x.com", email_verified=True
    )
    assert uid is None


async def test_link_no_match_returns_none():
    conn = _LinkConn(profiles=[])
    uid = await link_user_by_verified_email(
        conn, "google", "g-sub", email="a@x.com", email_verified=True
    )
    assert uid is None


async def test_link_ambiguous_multiple_matches_returns_none():
    # 이미 중복 계정이 2개 존재 → 어디 붙일지 모호 → 자동 연결 보류(오연결 방지).
    conn = _LinkConn(profiles=[("a@x.com", True, uuid4()), ("a@x.com", True, uuid4())])
    uid = await link_user_by_verified_email(
        conn, "google", "g-sub", email="a@x.com", email_verified=True
    )
    assert uid is None


async def test_link_case_insensitive_and_provider_lowercased():
    target = uuid4()
    conn = _LinkConn(profiles=[("A@X.com", True, target)])
    uid = await link_user_by_verified_email(
        conn, "GOOGLE", "g-sub", email="a@x.COM", email_verified=True
    )
    assert uid == target
    assert ("google", "g-sub") in conn.identities


async def test_link_race_existing_mapping_adopted():
    # 동시 첫 로그인: 경쟁자가 같은 (provider,sub) 선점 → INSERT None → resolve 재조회로 승자 채택.
    winner = uuid4()
    conn = _LinkConn(
        profiles=[("a@x.com", True, uuid4())],
        identities={("google", "g-sub"): winner},
    )
    uid = await link_user_by_verified_email(
        conn, "google", "g-sub", email="a@x.com", email_verified=True
    )
    assert uid == winner
