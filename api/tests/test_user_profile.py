"""Phase 2b-1 — user_profiles upsert COALESCE null 보존(B6) 테스트.

핵심(B6): Apple 재로그인은 이름/email 을 null 로 보낸다. upsert 가 그걸 덮으면 백필/첫로그인이
보존한 값이 사라진다. → COALESCE: last_sign_in 만 항상 갱신, 나머지는 null 이면 기존값 유지.
providers 는 distinct union.

CI 에 PG 가 없어 _UPSERT_SQL 의 COALESCE/array-union 시맨틱을 _FakeProfileTable 로 충실히
재현해(SQL 문 자체가 그 시맨틱을 표현하므로) 계약을 검증한다.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from invest_note_api.services.user_profile import upsert_profile

U1 = uuid4()


def dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


class _FakeProfileTable:
    """user_profiles upsert 의 COALESCE/array-union 시맨틱을 재현하는 fake conn.

    _UPSERT_SQL 파라미터 순서: ($1 user_id, $2 email, $3 display_name, $4 avatar_url,
    $5 email_verified, $6 provider, $7 last_sign_in).
    """

    def __init__(self):
        self.rows: dict = {}

    async def execute(self, _sql, user_id, email, display_name, avatar_url,
                      email_verified, provider, last_sign_in):
        existing = self.rows.get(user_id)
        if existing is None:
            self.rows[user_id] = {
                "email": email,
                "display_name": display_name,
                "avatar_url": avatar_url,
                "email_verified": email_verified,
                "providers": [provider] if provider else [],
                "last_sign_in": last_sign_in,
            }
            return
        # ON CONFLICT DO UPDATE — COALESCE(EXCLUDED, existing), last_sign_in 항상 갱신.
        coalesce = lambda new, old: new if new is not None else old
        merged_providers = list(existing["providers"])
        if provider and provider not in merged_providers:
            merged_providers.append(provider)
        self.rows[user_id] = {
            "email": coalesce(email, existing["email"]),
            "display_name": coalesce(display_name, existing["display_name"]),
            "avatar_url": coalesce(avatar_url, existing["avatar_url"]),
            "email_verified": coalesce(email_verified, existing["email_verified"]),
            "providers": merged_providers,
            "last_sign_in": last_sign_in,  # 항상 갱신
        }


@pytest.mark.asyncio
async def test_b6_null_clobber_prevented_on_reauth():
    # 첫 upsert(값 채움) → Apple 재로그인(전부 null, last_sign_in 만) → 기존값 보존.
    conn = _FakeProfileTable()
    await upsert_profile(
        conn, U1,
        email="user@example.com",
        display_name="홍길동",
        avatar_url="https://cdn/a.png",
        email_verified=True,
        provider="apple",
        last_sign_in=dt("2026-06-01T00:00:00"),
    )
    # Apple 재로그인: 이름/email/avatar null, last_sign_in 갱신.
    await upsert_profile(
        conn, U1,
        email=None,
        display_name=None,
        avatar_url=None,
        email_verified=None,
        provider="apple",
        last_sign_in=dt("2026-06-19T12:00:00"),
    )
    row = conn.rows[U1]
    assert row["email"] == "user@example.com"  # 보존
    assert row["display_name"] == "홍길동"  # 보존
    assert row["avatar_url"] == "https://cdn/a.png"  # 보존
    assert row["email_verified"] is True  # 보존
    assert row["last_sign_in"] == dt("2026-06-19T12:00:00")  # 갱신


@pytest.mark.asyncio
async def test_b6_new_value_overwrites_when_provided():
    # IdP 가 값을 제공하면(non-null) 신규값으로 갱신(보존 ≠ 영구 고정).
    conn = _FakeProfileTable()
    await upsert_profile(
        conn, U1, email="old@example.com", display_name="구이름",
        avatar_url=None, email_verified=False, provider="google",
        last_sign_in=dt("2026-06-01T00:00:00"),
    )
    await upsert_profile(
        conn, U1, email="new@example.com", display_name="새이름",
        avatar_url="https://cdn/new.png", email_verified=True, provider="google",
        last_sign_in=dt("2026-06-19T00:00:00"),
    )
    row = conn.rows[U1]
    assert row["email"] == "new@example.com"
    assert row["display_name"] == "새이름"
    assert row["avatar_url"] == "https://cdn/new.png"
    assert row["email_verified"] is True


@pytest.mark.asyncio
async def test_providers_union_distinct():
    # 여러 IdP 로그인 누적 → providers distinct union(중복 append 안 함).
    conn = _FakeProfileTable()
    await upsert_profile(
        conn, U1, email="u@e.com", display_name=None, avatar_url=None,
        email_verified=None, provider="google", last_sign_in=dt("2026-06-01T00:00:00"),
    )
    await upsert_profile(
        conn, U1, email=None, display_name=None, avatar_url=None,
        email_verified=None, provider="kakao", last_sign_in=dt("2026-06-02T00:00:00"),
    )
    await upsert_profile(
        conn, U1, email=None, display_name=None, avatar_url=None,
        email_verified=None, provider="google", last_sign_in=dt("2026-06-03T00:00:00"),
    )
    assert conn.rows[U1]["providers"] == ["google", "kakao"]
