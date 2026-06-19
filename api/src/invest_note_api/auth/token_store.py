"""OAuth transient + refresh token DB 저장 (Phase 2b-1).

OAuth 중개 flow 의 server-only secret 을 DB 에 영속한다. kis_token_store 패턴 준용 —
RLS 없는 테이블을 plain conn 으로 접근(acquire_for_user 금지).

⚠️ B2(HINGE): transient(state/PKCE challenge/일회용 code)를 **in-process 가 아니라 DB** 에 둔다.
login(생성)과 callback/token(소비)이 다른 워커·replica 일 수 있어(uvicorn --workers↑/Coolify
replica↑), in-process dict 면 즉시 lockout. DB 테이블은 인스턴스 무관 — 다른 conn 으로도 소비된다.

⚠️ B3: 일회용 code/state 는 single-use — consume 이 consumed_at 을 set 하고, 이미 소비/만료면
None 반환(replay 거부). ⚠️ B5: refresh 는 평문 저장 금지 — sha256 해시만 저장하고, 조회/회전도
해시로 한다. 회전 = 신 refresh 발급 + 구 refresh revoke.

TTL(oauth_code_ttl/oauth_state_ttl/be_refresh_token_ttl)은 호출부가 settings 에서 읽어
expires_at 으로 넘긴다(이 모듈은 시간 계산을 호출부에 위임 — 테스트 용이).
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


def generate_token() -> str:
    """불투명 secret(state/일회용 code/refresh 원본) 생성 — URL-safe 256bit."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """refresh token 해시(B5) — 평문은 저장하지 않고 이 해시만 DB 에 둔다."""
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- OAuth transient (state / 일회용 code) — B2/B3 -------------------------------

_PUT_TRANSIENT_SQL = """
    INSERT INTO oauth_transient (key, kind, payload, expires_at)
    VALUES ($1, $2, $3::jsonb, $4)
"""

# single-use consume: 미소비·미만료 행을 consumed 로 표시하며 payload 반환(원자적).
# 이미 소비됐거나(consumed_at NOT NULL) 만료됐으면(now > expires_at) 매칭 0행 → None(B3 replay 거부).
_CONSUME_TRANSIENT_SQL = """
    UPDATE oauth_transient
       SET consumed_at = $2
     WHERE key = $1
       AND kind = $3
       AND consumed_at IS NULL
       AND expires_at > $2
    RETURNING payload
"""

_CLEANUP_TRANSIENT_SQL = "DELETE FROM oauth_transient WHERE expires_at < $1"


async def put_transient(
    conn: Any, key: str, kind: str, payload: dict, expires_at: datetime
) -> None:
    """transient 항목 저장(state 또는 일회용 code). payload 는 jsonb 직렬화된다."""
    await conn.execute(_PUT_TRANSIENT_SQL, key, kind, json.dumps(payload), expires_at)


async def consume_transient(conn: Any, key: str, kind: str) -> dict | None:
    """single-use 소비(B3) — 미소비·미만료면 payload 반환 후 consumed 표시. 아니면 None.

    원자적 UPDATE...RETURNING 이라 동시 2회 소비 시 1회만 payload 를 얻는다(replay 거부).
    """
    row = await conn.fetchrow(_CONSUME_TRANSIENT_SQL, key, _now(), kind)
    if row is None:
        return None
    payload = row["payload"]
    # asyncpg jsonb 는 str 로 올 수 있어 dict 로 정규화.
    return json.loads(payload) if isinstance(payload, str) else dict(payload)


async def cleanup_transient(conn: Any) -> int:
    """만료된 transient 청소(배치/주기 호출). 삭제 행수 반환."""
    result = await conn.execute(_CLEANUP_TRANSIENT_SQL, _now())
    # asyncpg execute 는 "DELETE <n>" 문자열 반환.
    try:
        return int(str(result).split()[-1])
    except (ValueError, IndexError):
        return 0


# --- refresh token (해시 저장 + 회전 + 만료) — B5 -------------------------------

_SAVE_REFRESH_SQL = """
    INSERT INTO auth_refresh_tokens (user_id, token_hash, expires_at)
    VALUES ($1, $2, $3)
"""

# 유효 refresh 조회: 해시 일치 + 미revoke + 미만료. 매칭 시 user_id 반환.
_LOOKUP_REFRESH_SQL = """
    SELECT user_id
      FROM auth_refresh_tokens
     WHERE token_hash = $1
       AND revoked_at IS NULL
       AND expires_at > $2
"""

# revoke: 미revoke 행을 무효화(만료 여부 무관 — 명시적 폐기/로그아웃 경로).
_REVOKE_REFRESH_SQL = """
    UPDATE auth_refresh_tokens
       SET revoked_at = $2
     WHERE token_hash = $1
       AND revoked_at IS NULL
    RETURNING user_id
"""

# 회전용 revoke: 미revoke **그리고 미만료** 인 행만 무효화(만료 토큰으로 회전 금지).
# 매칭 0행이면 None → 회전 거부(만료/이미회전/없음). 원자적이라 동시 회전 시 1회만 성공.
_ROTATE_REVOKE_SQL = """
    UPDATE auth_refresh_tokens
       SET revoked_at = $2
     WHERE token_hash = $1
       AND revoked_at IS NULL
       AND expires_at > $2
    RETURNING user_id
"""


async def save_refresh(
    conn: Any, user_id: UUID, token: str, expires_at: datetime
) -> None:
    """refresh token 저장 — 평문이 아니라 해시(B5)만 저장한다."""
    await conn.execute(_SAVE_REFRESH_SQL, user_id, hash_token(token), expires_at)


async def lookup_refresh(conn: Any, token: str) -> UUID | None:
    """유효 refresh(미revoke·미만료)면 user_id, 아니면 None. 해시로 대조."""
    row = await conn.fetchrow(_LOOKUP_REFRESH_SQL, hash_token(token), _now())
    return row["user_id"] if row else None


async def revoke_refresh(conn: Any, token: str) -> UUID | None:
    """refresh 무효화(회전 시 구 토큰). 무효화된 user_id 반환(이미 revoked/없으면 None)."""
    row = await conn.fetchrow(_REVOKE_REFRESH_SQL, hash_token(token), _now())
    return row["user_id"] if row else None


async def rotate_refresh(
    conn: Any, old_token: str, new_token: str, expires_at: datetime
) -> UUID | None:
    """refresh 회전(B5) — old 를 revoke 하고 new 를 저장. old 가 유효했으면 user_id 반환.

    old 가 무효(이미 revoked/만료/없음)면 None 반환하고 new 를 저장하지 않는다(재사용 탐지).
    회전 revoke 는 미만료 조건을 포함하므로 만료 토큰으로는 회전되지 않는다(원자적 UPDATE).
    호출부(B-6 /auth/refresh)가 conn.transaction() 안에서 호출해 revoke+save 원자성을 보장한다.
    """
    row = await conn.fetchrow(_ROTATE_REVOKE_SQL, hash_token(old_token), _now())
    if row is None:
        return None
    user_id = row["user_id"]
    await save_refresh(conn, user_id, new_token, expires_at)
    return user_id
