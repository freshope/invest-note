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

from invest_note_api.auth.token_store import (
    consume_transient,
    generate_token,
    hash_token,
    peek_transient,
    put_transient,
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
        if "SELECT payload" in sql and "oauth_transient" in sql:
            # _PEEK_TRANSIENT_SQL: $1 key, $2 kind, $3 now — mutation 없는 조회.
            key, kind, now = args
            row = self.store.transient.get(key)
            if row is None or row["kind"] != kind or row["expires_at"] <= now:
                return None
            return {"payload": row["payload"]}  # 소비하지 않음
        if "DELETE FROM oauth_transient" in sql and "RETURNING" in sql:
            # _CONSUME_TRANSIENT_SQL(F2): $1 key, $2 now, $3 kind — 즉시 DELETE.
            key, now, kind = args
            row = self.store.transient.get(key)
            if row is None or row["kind"] != kind or row["expires_at"] <= now:
                return None
            del self.store.transient[key]  # single-use — 행 즉시 삭제(평문 잔존 제거)
            return {"payload": row["payload"]}
        if "UPDATE auth_refresh_tokens" in sql and "expires_at > $2" in sql:
            # 회전 revoke: 미revoke + 미만료(_ROTATE_REVOKE_SQL).
            token_hash, now = args
            for r in self.store.refresh:
                if (r["token_hash"] == token_hash and r["revoked_at"] is None
                        and r["expires_at"] > now):
                    r["revoked_at"] = now
                    return {"user_id": r["user_id"]}
            return None
        raise AssertionError(f"unhandled fetchrow SQL: {sql[:40]}")

    def _refresh_valid(self, token_hash, now) -> bool:
        # 테스트 probe(과거 lookup_refresh 대체) — 미revoke·미만료면 유효.
        return any(
            r["token_hash"] == token_hash and r["revoked_at"] is None and r["expires_at"] > now
            for r in self.store.refresh
        )


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
async def test_f2_consume_deletes_row_no_plaintext_lingering():
    # F2: 소비 시 row 즉시 삭제 — consumed 평문 access/refresh 가 TTL 까지 잔존하지 않는다.
    store = _FakeStore()
    conn = _FakeConn(store)
    await put_transient(conn, "code-f2", "code",
                        {"access_token": "AAA", "refresh_token": "RRR"}, _future())
    assert "code-f2" in store.transient
    payload = await consume_transient(conn, "code-f2", "code")
    assert payload == {"access_token": "AAA", "refresh_token": "RRR"}
    # 소비 후 행 자체가 사라진다(평문 잔존 0).
    assert "code-f2" not in store.transient


@pytest.mark.asyncio
async def test_f1_peek_does_not_consume():
    # F1: peek 은 single-use 를 소진하지 않는다 — 이후 consume 이 정상 동작.
    store = _FakeStore()
    conn = _FakeConn(store)
    await put_transient(conn, "code-f1", "code", {"x": 1}, _future())
    # peek 2회 모두 payload 반환(소진 없음).
    assert await peek_transient(conn, "code-f1", "code") == {"x": 1}
    assert await peek_transient(conn, "code-f1", "code") == {"x": 1}
    # peek 후에도 consume 가능.
    assert await consume_transient(conn, "code-f1", "code") == {"x": 1}
    # consume 후엔 peek 도 None.
    assert await peek_transient(conn, "code-f1", "code") is None


@pytest.mark.asyncio
async def test_f1_peek_expired_returns_none():
    store = _FakeStore()
    conn = _FakeConn(store)
    await put_transient(conn, "code-exp", "code", {"x": 1}, _past())
    assert await peek_transient(conn, "code-exp", "code") is None


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
    token = generate_token()
    # save_refresh 가 저장하는 값에 평문이 없어야 한다.
    h = hash_token(token)
    assert h != token
    assert len(h) == 64  # sha256 hex


@pytest.mark.asyncio
async def test_b5_refresh_saved_as_hash_no_plaintext_in_store():
    store = _FakeStore()
    conn = _FakeConn(store)
    token = generate_token()
    await save_refresh(conn, U1, token, _future(3600))
    # DB(store)에 평문 토큰이 없어야 한다(해시만).
    assert all(r["token_hash"] != token for r in store.refresh)
    assert store.refresh[0]["token_hash"] == hash_token(token)
    # 저장 직후 유효(probe — 미revoke·미만료).
    assert conn._refresh_valid(hash_token(token), datetime.now(timezone.utc))


@pytest.mark.asyncio
async def test_b5_refresh_rotation_invalidates_old():
    store = _FakeStore()
    conn = _FakeConn(store)
    old = generate_token()
    new = generate_token()
    await save_refresh(conn, U1, old, _future(3600))

    rotated_uid = await rotate_refresh(conn, old, new, _future(3600))
    assert rotated_uid == U1
    # 회전 후 구 refresh 재회전 → None(무효), 신 refresh 재회전 → 유효(user_id).
    assert await rotate_refresh(conn, old, generate_token(), _future(3600)) is None
    assert await rotate_refresh(conn, new, generate_token(), _future(3600)) == U1


@pytest.mark.asyncio
async def test_b5_refresh_rotation_rejects_already_rotated():
    # 이미 회전된(revoked) refresh 재사용 시 회전 거부(None, stale refresh 거부).
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
    # 만료 refresh → 회전 None(미만료 조건 불충족).
    assert await rotate_refresh(conn, expired, generate_token(), _future()) is None
