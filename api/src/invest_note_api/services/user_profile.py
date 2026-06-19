"""user_profiles upsert — IdP 로그인 시 프로필 수집 (Phase 2b-1).

OAuth 중개(routers/auth.callback)가 IdP userinfo 를 받아 이 모듈로 upsert 한다.

⚠️ B6 — null clobber 방지(재로그인 데이터 소실 차단):
- Apple 은 이름/email 을 **첫 인증에만** 제공한다(이후 null). Kakao email 도 optional.
- 따라서 IdP 가 null/미제공인 필드를 그대로 덮으면 백필/첫로그인이 보존한 값이 지워진다.
- upsert = COALESCE: `last_sign_in` 은 항상 갱신, email/display_name/avatar_url/email_verified 는
  `COALESCE(EXCLUDED.col, user_profiles.col)` 로 신규값 우선·null 이면 기존값 유지.
- providers 는 배열 union(append distinct) — 한 사용자가 여러 IdP 로 로그인 가능.

token_store 와 동일하게 server-side 호출이라 plain conn 으로 접근한다(RLS 없음).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

# providers union: 기존 배열에 provider 를 distinct append. EXCLUDED.providers 는
# 단일 원소 배열로 들어오고, COALESCE 후 array_cat → 중복 제거(SELECT array_agg DISTINCT)는
# SQL 로 표현하기 번거로워, 기존값과 신규를 합친 뒤 중복 제거를 PG array 함수로 처리한다.
_UPSERT_SQL = """
    INSERT INTO public.user_profiles
        (user_id, email, display_name, avatar_url, email_verified, providers, last_sign_in)
    VALUES ($1, $2, $3, $4, $5, ARRAY[$6]::text[], $7)
    ON CONFLICT (user_id) DO UPDATE SET
        email          = COALESCE(EXCLUDED.email,          user_profiles.email),
        display_name   = COALESCE(EXCLUDED.display_name,   user_profiles.display_name),
        avatar_url     = COALESCE(EXCLUDED.avatar_url,     user_profiles.avatar_url),
        email_verified = COALESCE(EXCLUDED.email_verified, user_profiles.email_verified),
        providers      = (
            SELECT array_agg(DISTINCT p)
            FROM unnest(user_profiles.providers || ARRAY[$6]::text[]) AS p
        ),
        last_sign_in   = EXCLUDED.last_sign_in
"""


async def upsert_profile(
    conn: Any,
    user_id: UUID,
    *,
    email: str | None,
    display_name: str | None,
    avatar_url: str | None,
    email_verified: bool | None,
    provider: str,
    last_sign_in: datetime,
) -> None:
    """로그인 프로필 upsert — COALESCE(B6). last_sign_in 항상 갱신, 나머지는 null 이면 보존.

    provider 는 providers 배열에 distinct union 된다(여러 IdP 로그인 누적).
    """
    await conn.execute(
        _UPSERT_SQL,
        user_id,
        email,
        display_name,
        avatar_url,
        email_verified,
        provider,
        last_sign_in,
    )
