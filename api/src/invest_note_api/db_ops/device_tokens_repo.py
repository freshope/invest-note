"""디바이스 푸시 토큰 repo — device_tokens upsert/조회/정리.

UNIQUE(user_id, token) 로 재등록은 last_seen_at 만 갱신(중복 행 방지). services/push 가
전송 대상 토큰을 조회하고 폐기된 토큰을 지우며, 로그아웃/탈퇴 경로도 정리한다.
"""
from __future__ import annotations

from typing import Any


async def upsert(conn: Any, *, user_id: Any, token: str, platform: str) -> None:
    """토큰 등록 — (user_id, token) 충돌 시 platform·last_seen_at 갱신. 멱등."""
    await conn.execute(
        "insert into device_tokens (user_id, token, platform) values ($1, $2, $3) "
        "on conflict (user_id, token) do update set "
        "platform = excluded.platform, last_seen_at = now()",
        user_id,
        token,
        platform,
    )


async def list_tokens(conn: Any, user_id: Any) -> list[dict]:
    """해당 user 의 토큰 목록 — 푸시 전송 대상. [{token, platform}, ...]."""
    rows = await conn.fetch(
        "select token, platform from device_tokens where user_id = $1",
        user_id,
    )
    return [dict(r) for r in rows]


async def delete_token(conn: Any, user_id: Any, token: str) -> None:
    """단일 토큰 삭제(로그아웃 시 해당 기기 토큰 정리). 멱등."""
    await conn.execute(
        "delete from device_tokens where user_id = $1 and token = $2",
        user_id,
        token,
    )
