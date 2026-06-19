"""Phase 2b-1 — token_store: transient(B2/B3) + refresh(B5) 시맨틱 테스트.

CI 에 PG 가 없어, 공유 dict 를 백킹하는 _FakeStore 로 token_store SQL 의 시맨틱을 충실히
재현한다. ⚠️ B2 핵심: 한 _FakeStore(=DB)를 가리키는 **두 개의 다른 conn** 으로 put/consume 을
나눠 호출해 "인스턴스 무관(다른 워커 소비 성공)"을 증명한다. in-process dict 모듈 전역이었다면
다른 conn 으로 분리할 수 없다.

검증: B2 다른 conn 소비, B3 single-use replay 거부, 만료 None, B5 해시 저장(평문 부재)·회전(구
무효)·만료 회전 거부.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from invest_note_api.auth import token_store
from invest_note_api.auth.token_store import (
    consume_transient,
    generate_token,
    hash_token,
    lookup_refresh,
    put_transient,
    revoke_refresh,
    rotate_refresh,
    save_refresh,
)

U1 = uuid4()


def _future(seconds: int = 600) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def _past(seconds: int = 600) -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=seconds)


class _FakeStore:
    """oauth_transient + auth_refresh_tokens 를 백킹하는 공유 DB 시뮬레이터(인스턴스 = DB)."""

    def __init__(self):
        self.transient: dict = {}  # key -> {kind, payload, expires_at, consumed_at}
        self.refresh: list = []  # [{user_id, token_hash, expires_at, revoked_at}]


class _FakeConn:
    """_FakeStore 를 가리키는 conn — token_store SQL 을 식별해 시맨틱 적용.

    여러 _FakeConn 이 동일 _FakeStore 를 공유 → B2(다른 conn 소비) 시뮬레이션.
    """

    def __init__(self, store: _FakeStore):
        self.store = store

    async def execute(self, sql, *args):
        import json

        if "INSERT INTO oauth_transient" in sql:
            key, kind, payload, expires_at = args
            self.store.transient[key] = {
                "kind": kind,
                "payload": payload,  # json str
                "expires_at": expires_at,
                "consumed_at": None,
            }
            return "INSERT 0 1"
        if "INSERT INTO auth_refresh_tokens" in sql:
            user_id, token_hash, expires_at = args
            self.store.refresh.append({
                "user_id": user_id,
                "token_hash": token_hash,
                "expires_at": expires_at,
                "revoked_at": None,
            })
            return "INSERT 0 1"
        if "DELETE FROM oauth_transient" in sql:
            (now,) = args
            before = len(self.store.transient)
            self.store.transient = {
                k: v for k, v in self.store.transient.items() if v["expires_at"] >= now
            }
            return f"DELETE {before - len(self.store.transient)}"
        raise AssertionError(f"unhandled execute SQL: {sql[:40]}")

    async def fetchrow(self, sql, *args):
        if "UPDATE oauth_transient" in sql:
            key, now, kind = args  # _CONSUME_TRANSIENT_SQL: $1 key, $2 now, $3 kind
            row = self.store.transient.get(key)
            if (row is None or row["kind"] != kind or row["consumed_at"] is not None
                    or row["expires_at"] <= now):
                return None
            row["consumed_at"] = now  # single-use 표시
            return {"payload": row["payload"]}
        if "UPDATE auth_refresh_tokens" in sql and "expires_at > $2" in sql:
            # 회전 revoke: 미revoke + 미만료
            token_hash, now = args
            for r in self.store.refresh:
                if (r["token_hash"] == token_hash and r["revoked_at"] is None
                        and r["expires_at"] > now):
                    r["revoked_at"] = now
                    return {"user_id": r["user_id"]}
            return None
        if "UPDATE auth_refresh_tokens" in sql:
            # 일반 revoke: 미revoke (만료 무관)
            token_hash, now = args
            for r in self.store.refresh:
                if r["token_hash"] == token_hash and r["revoked_at"] is None:
                    r["revoked_at"] = now
                    return {"user_id": r["user_id"]}
            return None
        if "SELECT user_id" in sql and "auth_refresh_tokens" in sql:
            # lookup: 미revoke + 미만료
            token_hash, now = args
            for r in self.store.refresh:
                if (r["token_hash"] == token_hash and r["revoked_at"] is None
                        and r["expires_at"] > now):
                    return {"user_id": r["user_id"]}
            return None
        raise AssertionError(f"unhandled fetchrow SQL: {sql[:40]}")


# --- B2: transient 인스턴스 무관(다른 conn 소비) ---


@pytest.mark.asyncio
async def test_b2_transient_consumed_by_different_conn():
    store = _FakeStore()
    conn_login = _FakeConn(store)  # 워커 A (login 생성)
    conn_token = _FakeConn(store)  # 워커 B (token 소비) — 다른 conn

    await put_transient(conn_login, "code-abc", "code", {"access": "tok"}, _future())
    # 다른 conn 으로 소비 성공해야 한다(인스턴스 무관, in-process 였다면 불가).
    payload = await consume_transient(conn_token, "code-abc", "code")
    assert payload == {"access": "tok"}


# --- B3: single-use replay 거부 ---


@pytest.mark.asyncio
async def test_b3_transient_single_use_replay_rejected():
    store = _FakeStore()
    conn = _FakeConn(store)
    await put_transient(conn, "code-1", "code", {"x": 1}, _future())
    first = await consume_transient(conn, "code-1", "code")
    assert first == {"x": 1}
    # 2회차 소비 → None(replay 거부).
    second = await consume_transient(conn, "code-1", "code")
    assert second is None


@pytest.mark.asyncio
async def test_transient_expired_returns_none():
    store = _FakeStore()
    conn = _FakeConn(store)
    await put_transient(conn, "code-exp", "code", {"x": 1}, _past())
    assert await consume_transient(conn, "code-exp", "code") is None


@pytest.mark.asyncio
async def test_transient_wrong_kind_returns_none():
    store = _FakeStore()
    conn = _FakeConn(store)
    await put_transient(conn, "s-1", "state", {"state": "v"}, _future())
    # kind 불일치(code 로 state 소비 시도) → None.
    assert await consume_transient(conn, "s-1", "code") is None


# --- B5: refresh 해시 저장 + 회전 + 만료 ---


def test_b5_refresh_stored_as_hash_not_plaintext():
    store = _FakeStore()
    token = generate_token()
    # save_refresh 가 저장하는 값에 평문이 없어야 한다.
    h = hash_token(token)
    assert h != token
    assert len(h) == 64  # sha256 hex


@pytest.mark.asyncio
async def test_b5_refresh_save_lookup_no_plaintext_in_store():
    store = _FakeStore()
    conn = _FakeConn(store)
    token = generate_token()
    await save_refresh(conn, U1, token, _future(3600))
    # DB(store)에 평문 토큰이 없어야 한다(해시만).
    assert all(r["token_hash"] != token for r in store.refresh)
    assert store.refresh[0]["token_hash"] == hash_token(token)
    # 유효 lookup → user_id.
    assert await lookup_refresh(conn, token) == U1


@pytest.mark.asyncio
async def test_b5_refresh_rotation_invalidates_old():
    store = _FakeStore()
    conn = _FakeConn(store)
    old = generate_token()
    new = generate_token()
    await save_refresh(conn, U1, old, _future(3600))

    rotated_uid = await rotate_refresh(conn, old, new, _future(3600))
    assert rotated_uid == U1
    # 회전 후 구 refresh → 무효(None), 신 refresh → 유효.
    assert await lookup_refresh(conn, old) is None
    assert await lookup_refresh(conn, new) == U1


@pytest.mark.asyncio
async def test_b5_refresh_rotation_rejects_already_rotated():
    # 이미 회전된(revoked) refresh 재사용 시 회전 거부(None, 재사용 탐지).
    store = _FakeStore()
    conn = _FakeConn(store)
    old = generate_token()
    await save_refresh(conn, U1, old, _future(3600))
    await rotate_refresh(conn, old, generate_token(), _future(3600))
    # old 재사용 → None(이미 revoked).
    assert await rotate_refresh(conn, old, generate_token(), _future(3600)) is None


@pytest.mark.asyncio
async def test_b5_expired_refresh_rejected():
    store = _FakeStore()
    conn = _FakeConn(store)
    expired = generate_token()
    await save_refresh(conn, U1, expired, _past())
    # 만료 refresh → lookup None, 회전 None.
    assert await lookup_refresh(conn, expired) is None
    assert await rotate_refresh(conn, expired, generate_token(), _future()) is None


@pytest.mark.asyncio
async def test_revoke_refresh_marks_revoked():
    store = _FakeStore()
    conn = _FakeConn(store)
    token = generate_token()
    await save_refresh(conn, U1, token, _future(3600))
    assert await revoke_refresh(conn, token) == U1
    assert await lookup_refresh(conn, token) is None
