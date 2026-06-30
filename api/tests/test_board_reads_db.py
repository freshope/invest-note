"""실DB 게시판 읽음/알림 상태 테스트 — fake_pool 로 검증 불가한 SQL 동작을 실측한다.

has_unread_notice 의 COALESCE→users.created_at fallback 과 세 upsert 의 멱등성은 순수 SQL
이라 AsyncMock 으로는 문자열만 가드된다(동작 미검증). list_my_posts 의 reads LEFT JOIN→unread
도 실 JOIN 이라야 의미가 있다. `INVEST_NOTE_TEST_DATABASE_URL`(0012 적용된 실 PG) 설정 시에만
실행하고 미설정 시 skip(test_user_isolation_db 와 동일 관습). CI migrate-verify 가 env 주입.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import pytest

from invest_note_api.db_ops import board_repo

TEST_DB_URL = os.environ.get("INVEST_NOTE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DB_URL, reason="INVEST_NOTE_TEST_DATABASE_URL 미설정 — 실DB 읽음상태 테스트 skip"
)


async def _seed_user(conn, *, created_at: datetime) -> str:
    """users 행 1건(가입 시각 명시). user_id 반환."""
    user_id = str(uuid4())
    await conn.execute(
        "INSERT INTO public.users (id, created_at) VALUES ($1, $2)", user_id, created_at
    )
    return user_id


async def _seed_notice(conn, *, created_at: datetime) -> str:
    return await conn.fetchval(
        "INSERT INTO public.board_posts (board_type, title, created_at) "
        "VALUES ('notice', '공지', $1) RETURNING id::text",
        created_at,
    )


async def _seed_my_post(conn, user_id: str) -> str:
    return await conn.fetchval(
        "INSERT INTO public.board_posts (board_type, user_id, title) "
        "VALUES ('feedback', $1, '[feedback]') RETURNING id::text",
        user_id,
    )


async def test_has_unread_notice_fallback_to_signup_time():
    """state 없으면 users.created_at fallback — 가입 전 공지는 not unread, 이후 공지만 unread."""
    conn = await asyncpg.connect(TEST_DB_URL)
    user_id = None
    try:
        # 가입 시각을 과거(1h 전)로 둬 "가입 후 공지"도 wall-clock now() 이전이게 한다.
        # 실제 공지는 미래일 수 없으므로(seen=now() 가 항상 최신 공지보다 늦음) 이 앵커가
        # 현실을 반영한다 — now+α 미래 공지를 시드하면 seen 후에도 unread 로 남아 오판.
        signup = datetime.now(timezone.utc) - timedelta(hours=1)
        user_id = await _seed_user(conn, created_at=signup)
        # 가입 전 공지만 있을 때 → state 없음 → fallback(users.created_at) → not unread.
        await _seed_notice(conn, created_at=signup - timedelta(days=1))
        assert await board_repo.has_unread_notice(conn, user_id) is False
        # 가입 후(가입~now 사이) 공지 추가 → unread.
        await _seed_notice(conn, created_at=signup + timedelta(minutes=30))
        assert await board_repo.has_unread_notice(conn, user_id) is True
        # 공지 메뉴 열람(seen=now()) → 더 늦은 공지 없음 → 해제.
        await board_repo.set_notices_seen_at(conn, user_id)
        assert await board_repo.has_unread_notice(conn, user_id) is False
    finally:
        if user_id:
            await conn.execute("DELETE FROM public.users WHERE id = $1::uuid", user_id)
            await conn.execute(
                "DELETE FROM public.board_posts WHERE board_type = 'notice'"
            )
        await conn.close()


async def test_set_notices_seen_at_idempotent():
    """set_notices_seen_at 두 번 호출 → user 당 1행 유지(PK upsert), 값 갱신."""
    conn = await asyncpg.connect(TEST_DB_URL)
    user_id = None
    try:
        user_id = await _seed_user(conn, created_at=datetime.now(timezone.utc))
        await board_repo.set_notices_seen_at(conn, user_id)
        first = await conn.fetchval(
            "SELECT notices_seen_at FROM public.user_notice_state WHERE user_id = $1::uuid",
            user_id,
        )
        await board_repo.set_notices_seen_at(conn, user_id)
        rows = await conn.fetchval(
            "SELECT count(*) FROM public.user_notice_state WHERE user_id = $1::uuid", user_id
        )
        second = await conn.fetchval(
            "SELECT notices_seen_at FROM public.user_notice_state WHERE user_id = $1::uuid",
            user_id,
        )
        assert rows == 1
        assert second >= first
    finally:
        if user_id:
            await conn.execute("DELETE FROM public.users WHERE id = $1::uuid", user_id)
        await conn.close()


async def test_post_read_and_popup_ack_independent_and_idempotent():
    """read/ack 는 한 행의 독립 컬럼 — 한쪽 upsert 가 다른쪽 NULL 보존, 두 번 호출 멱등(1행)."""
    conn = await asyncpg.connect(TEST_DB_URL)
    user_id = post_id = None
    try:
        user_id = await _seed_user(conn, created_at=datetime.now(timezone.utc))
        post_id = await _seed_my_post(conn, user_id)

        await board_repo.upsert_post_read(conn, user_id, post_id)
        await board_repo.upsert_post_read(conn, user_id, post_id)  # 멱등
        read_at, popup = await conn.fetchrow(
            "SELECT read_at, popup_acked_at FROM public.board_post_reads "
            "WHERE user_id = $1::uuid AND post_id = $2::uuid",
            user_id,
            post_id,
        )
        assert read_at is not None
        assert popup is None  # read upsert 는 popup_acked_at 을 건드리지 않음

        await board_repo.upsert_popup_ack(conn, user_id, post_id)
        read_at2, popup2 = await conn.fetchrow(
            "SELECT read_at, popup_acked_at FROM public.board_post_reads "
            "WHERE user_id = $1::uuid AND post_id = $2::uuid",
            user_id,
            post_id,
        )
        assert popup2 is not None
        assert read_at2 is not None  # ack upsert 가 read_at 을 보존

        rows = await conn.fetchval(
            "SELECT count(*) FROM public.board_post_reads "
            "WHERE user_id = $1::uuid AND post_id = $2::uuid",
            user_id,
            post_id,
        )
        assert rows == 1  # 두 upsert 가 같은 (user, post) 행을 공유
    finally:
        # board_posts.user_id 는 ON DELETE SET NULL 이라 user 삭제만으론 글이 orphan 으로
        # 남는다 — 시드한 글을 명시 삭제(post FK CASCADE 로 board_post_reads 동반 정리).
        if post_id:
            await conn.execute("DELETE FROM public.board_posts WHERE id = $1::uuid", post_id)
        if user_id:
            await conn.execute("DELETE FROM public.users WHERE id = $1::uuid", user_id)
        await conn.close()


async def test_list_my_posts_unread_cleared_by_read_join():
    """list_my_posts 의 reads LEFT JOIN — 어드민 댓글 후 read 없으면 unread, read 후 해제."""
    conn = await asyncpg.connect(TEST_DB_URL)
    user_id = post_id = None
    try:
        user_id = await _seed_user(conn, created_at=datetime.now(timezone.utc))
        post_id = await _seed_my_post(conn, user_id)
        # 어드민 답변 추가 → 활동 발생.
        await conn.execute(
            "INSERT INTO public.board_comments (post_id, is_admin, body) "
            "VALUES ($1::uuid, true, '반영')",
            post_id,
        )
        posts, _ = await board_repo.list_my_posts(conn, user_id)
        assert len(posts) == 1
        assert posts[0]["unread"] is True
        assert posts[0]["popup_acked"] is False

        # 상세 열람(read=now() > 댓글 시각) → 해제.
        await board_repo.upsert_post_read(conn, user_id, post_id)
        posts, _ = await board_repo.list_my_posts(conn, user_id)
        assert posts[0]["unread"] is False
    finally:
        # board_posts.user_id ON DELETE SET NULL — 시드 글 명시 삭제(댓글/reads 는 post CASCADE).
        if post_id:
            await conn.execute("DELETE FROM public.board_posts WHERE id = $1::uuid", post_id)
        if user_id:
            await conn.execute("DELETE FROM public.users WHERE id = $1::uuid", user_id)
        await conn.close()
