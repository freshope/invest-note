"""실DB 신규 가입 테스트 — create_user_identity 의 de-dup 안전속성(2b-3) 검증.

fake conn 은 advisory lock·FK·UNIQUE(provider, provider_id) 제약을 행사할 수 없어, 이 기능의
핵심 보장("동시 첫 로그인 → 단일 user, 중복/고아 0")을 검증하지 못한다. 그 보장은 실 PG 에서만
드러나므로 여기서 행사한다. `INVEST_NOTE_TEST_DATABASE_URL`(마이그레이션 적용된 실 PG) 설정
시에만 실행하고 미설정 환경(기본 단위 테스트)에서는 skip. CI(migrate-verify)에서 env 주입.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

import asyncpg
import pytest

from invest_note_api.services.auth_identity import (
    create_user_identity,
    link_user_by_verified_email,
)
from invest_note_api.services.user_profile import upsert_profile

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


async def test_link_verified_email_cross_provider():
    """카카오(verified) 가입자 → 같은 이메일 구글 로그인 시 동일 user 로 연결(중복 user 생성 안 함)."""
    conn = await asyncpg.connect(TEST_DB_URL)
    email = f"link-{uuid4()}@example.com"
    uid: UUID | None = None
    try:
        # 1) 카카오 첫 로그인 = 신규 user + verified 프로필
        uid = await create_user_identity(conn, "kakao", f"kakao-{uuid4()}")
        await upsert_profile(
            conn, uid, email=email, display_name=None, avatar_url=None,
            email_verified=True, provider="kakao", last_sign_in=datetime.now(timezone.utc),
        )
        # 2) 같은 이메일 구글 로그인 → resolve miss → link 로 같은 uid 채택(새 user 생성 X)
        linked = await link_user_by_verified_email(
            conn, "google", f"google-{uuid4()}", email=email, email_verified=True
        )
        assert linked == uid
        # auth_identities 2행(kakao+google)이 같은 user_id, users 는 1개.
        assert await conn.fetchval(
            "SELECT count(*) FROM auth_identities WHERE user_id = $1", uid
        ) == 2
    finally:
        if uid is not None:
            await conn.execute("DELETE FROM public.users WHERE id = $1", uid)
        await conn.close()


async def test_link_not_fooled_by_stale_verified_after_email_change():
    """보안: 이메일이 새 값(미인증)으로 바뀌면 verified 가 stale true 로 남지 않아 link 가 속지 않는다.

    upsert_profile 의 email↔verified 결합(user_profile.py)을 실 PG 로 행사 — 결합이 깨지면
    link_user_by_verified_email 이 미인증 새 이메일을 인증된 것으로 오인해 하이재킹이 가능하다.
    """
    conn = await asyncpg.connect(TEST_DB_URL)
    victim_email = f"victim-{uuid4()}@example.com"
    uid: UUID | None = None
    try:
        # 1) 기존 계정: 인증된 이메일 A 로 프로필 생성(verified=true).
        uid = await create_user_identity(conn, "google", f"google-{uuid4()}")
        await upsert_profile(
            conn, uid, email=f"a-{uuid4()}@example.com", display_name=None, avatar_url=None,
            email_verified=True, provider="google", last_sign_in=datetime.now(timezone.utc),
        )
        # 2) 다른 IdP 가 victim 이메일을 **미인증(null)** 으로 제공 → email 만 바뀌고 verified 는 false/null 이어야.
        await upsert_profile(
            conn, uid, email=victim_email, display_name=None, avatar_url=None,
            email_verified=None, provider="kakao", last_sign_in=datetime.now(timezone.utc),
        )
        stored = await conn.fetchrow(
            "SELECT email, email_verified FROM public.user_profiles WHERE user_id = $1", uid
        )
        assert stored["email"] == victim_email
        assert stored["email_verified"] is not True  # stale true 가 새 이메일로 이월되지 않음
        # 3) victim 이메일 진짜 주인이 구글(verified)로 첫 로그인 → 위 미인증 프로필에 연결되면 안 됨.
        linked = await link_user_by_verified_email(
            conn, "google", f"google-{uuid4()}", email=victim_email, email_verified=True
        )
        assert linked is None  # 후보 0(미인증 프로필은 제외) → 신규 생성 폴백
    finally:
        if uid is not None:
            await conn.execute("DELETE FROM public.users WHERE id = $1", uid)
        await conn.close()


async def test_link_skips_when_existing_unverified():
    """기존 프로필 email_verified=false → 양쪽-verified 가드로 연결 안 함(None) → 신규 생성 폴백."""
    conn = await asyncpg.connect(TEST_DB_URL)
    email = f"unv-{uuid4()}@example.com"
    uid: UUID | None = None
    try:
        uid = await create_user_identity(conn, "kakao", f"kakao-{uuid4()}")
        await upsert_profile(
            conn, uid, email=email, display_name=None, avatar_url=None,
            email_verified=False, provider="kakao", last_sign_in=datetime.now(timezone.utc),
        )
        linked = await link_user_by_verified_email(
            conn, "google", f"google-{uuid4()}", email=email, email_verified=True
        )
        assert linked is None
    finally:
        if uid is not None:
            await conn.execute("DELETE FROM public.users WHERE id = $1", uid)
        await conn.close()
