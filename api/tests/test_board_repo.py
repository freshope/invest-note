"""board_repo.list_my_posts 단위 테스트 — 사용자 격리 가드(SQL 자체는 통합 검증).

fake_pool 은 SQL 을 실행하지 않으므로 "notice 제외 / 타인 글 제외" 격리는 라우터 테스트로는
검증 불가다. 여기서 bind 인자를 직접 검사해 user_id 스코프 + board_type 화이트리스트 +
is_admin 댓글 필터가 쿼리에 정확히 실리는지 가드한다(RLS 제거됨 — 이 쿼리가 유일한 격리).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from invest_note_api.db_ops import board_repo

USER_ID = uuid4()


def _post(*, status: str = "open", comments=None, updated_at: str = "2026-06-25T00:00:00Z") -> dict:
    """_compute_unread 입력 dict — 어드민 댓글/상태/updated_at 조합."""
    return {
        "status": status,
        "updated_at": updated_at,
        "comments": comments or [],
    }


def _admin_comment(created_at: str) -> dict:
    return {"is_admin": True, "created_at": created_at}


@pytest.mark.asyncio
async def test_list_my_posts_scopes_to_user_and_three_board_types():
    """posts 쿼리에 user_id 와 (feedback/bug_report/broker_statement) 만 bind — notice 제외."""
    conn = AsyncMock()
    conn.fetch.return_value = []  # 빈 posts → comments 조회 생략
    await board_repo.list_my_posts(conn, USER_ID)

    query, *args = conn.fetch.call_args.args
    assert "user_id = $1" in query
    assert "board_type = any($2)" in query
    assert "notice" not in query
    assert args[0] == USER_ID
    assert args[1] == ["feedback", "bug_report", "broker_statement"]


@pytest.mark.asyncio
async def test_list_my_posts_empty_skips_join_queries():
    """본인 글 0건이면 comments/attachments fetch 자체를 안 한다(1회 호출)."""
    conn = AsyncMock()
    conn.fetch.return_value = []
    assert await board_repo.list_my_posts(conn, USER_ID) == []
    assert conn.fetch.call_count == 1


@pytest.mark.asyncio
async def test_list_my_posts_join_queries_scope_to_post_ids():
    """comments(is_admin=true)·attachments 모두 내 글 id 로 스코프(타 글 합본 차단)."""
    pid = uuid4()
    post_rows = [
        {
            "id": pid,
            "board_type": "feedback",
            "user_id": USER_ID,
            "title": "[feedback]",
            "body": "본문",
            "status": "open",
            "is_pinned": False,
            "metadata": '{"source": "app"}',
            "created_at": "2026-06-25T00:00:00Z",
            "updated_at": "2026-06-25T00:00:00Z",
        }
    ]
    comment_rows = [
        {
            "id": uuid4(),
            "post_id": pid,
            "user_id": uuid4(),
            "body": "반영",
            "is_admin": True,
            "created_at": "2026-06-26T00:00:00Z",
        }
    ]
    attachment_rows = [
        {
            "id": uuid4(),
            "post_id": pid,
            "comment_id": None,
            "user_id": USER_ID,
            "original_name": "a.xlsx",
            "content_type": "application/vnd.ms-excel",
            "size_bytes": 4096,
            "storage_key": f"broker_statement/{USER_ID}/x.xlsx",
            "bucket": "statements",
            "created_at": "2026-06-25T00:00:00Z",
        }
    ]
    conn = AsyncMock()
    conn.fetch.side_effect = [post_rows, comment_rows, attachment_rows]

    result = await board_repo.list_my_posts(conn, USER_ID)

    # call_args_list[0]=posts, [1]=comments, [2]=attachments
    comment_query, *cargs = conn.fetch.call_args_list[1].args
    assert "post_id = any($1)" in comment_query
    assert "is_admin = true" in comment_query
    assert cargs[0] == [pid]  # raw UUID(문자열 변환 전)로 bind

    att_query, *aargs = conn.fetch.call_args_list[2].args
    assert "from board_attachments" in att_query
    assert "post_id = any($1)" in att_query
    assert aargs[0] == [pid]

    assert len(result) == 1
    assert result[0]["id"] == str(pid)  # 응답은 str 화
    assert result[0]["metadata"] == {"source": "app"}  # jsonb → dict
    assert len(result[0]["comments"]) == 1
    assert result[0]["comments"][0]["post_id"] == str(pid)
    assert len(result[0]["attachments"]) == 1
    assert result[0]["attachments"][0]["storage_key"].startswith("broker_statement/")
    # JOIN reads 미제공(_my_post_row 에 read_at/popup_acked_at 컬럼 없음) → 어드민 댓글 있고
    # read 없음 → unread True, popup_acked False. reads 컬럼은 응답에 누출되지 않는다.
    assert result[0]["unread"] is True
    assert result[0]["popup_acked"] is False
    assert "read_at" not in result[0]
    assert "popup_acked_at" not in result[0]


# ─────────────────────────── _compute_unread (isMyPostUnread 복제) ───────────────────────────


def test_unread_false_when_no_admin_comment_and_open():
    """(d) 어드민 댓글 0 + status=open → 활동 없음 → not unread."""
    assert board_repo._compute_unread(_post(status="open"), None) is False


def test_unread_true_when_admin_comment_and_no_read():
    """(a) 어드민 댓글 있고 read 없음 → unread."""
    post = _post(comments=[_admin_comment("2026-06-26T00:00:00Z")])
    assert board_repo._compute_unread(post, None) is True


def test_unread_false_after_read_past_activity():
    """(b) 어드민 댓글 이후 더 늦게 read → unread 해제."""
    post = _post(comments=[_admin_comment("2026-06-26T00:00:00Z")])
    assert board_repo._compute_unread(post, "2026-06-27T00:00:00Z") is False


def test_unread_true_when_later_admin_comment_after_read():
    """(c) read 후 더 늦은 어드민 댓글 → 다시 unread."""
    post = _post(comments=[_admin_comment("2026-06-28T00:00:00Z")])
    assert board_repo._compute_unread(post, "2026-06-27T00:00:00Z") is True


def test_unread_uses_updated_at_only_when_status_changed():
    """(e) status!=open 이면 updated_at(상태변경 시각)을 활동신호로 본다 — 어드민 댓글 0이어도."""
    # status=resolved + updated_at 이 read 이후 → unread.
    post = _post(status="resolved", updated_at="2026-06-28T00:00:00Z")
    assert board_repo._compute_unread(post, "2026-06-27T00:00:00Z") is True


def test_unread_ignores_updated_at_when_open():
    """status=open 글은 updated_at(본문 편집 잡음)을 무시 — 어드민 댓글 0이면 not unread."""
    # updated_at 이 read 보다 늦어도 status=open + 어드민 댓글 0 이면 활동 없음.
    post = _post(status="open", updated_at="2026-06-28T00:00:00Z")
    assert board_repo._compute_unread(post, "2026-06-27T00:00:00Z") is False


def test_unread_numeric_tz_compare_not_lexical():
    """시각 비교는 수치(aware datetime) — `+00:00`(BE) vs `Z`(클라) 사전식 비교 버그 회피."""
    # read(+00:00 표기) 가 활동(Z 표기)보다 1초 늦음 → 사전식이면 오판하지만 수치는 정답(not unread).
    post = _post(comments=[_admin_comment("2026-06-26T00:00:00Z")])
    assert board_repo._compute_unread(post, "2026-06-26T00:00:01+00:00") is False


def test_to_dt_accepts_datetime_and_string():
    """_to_dt 는 asyncpg aware datetime 과 ISO 문자열 양쪽을 aware 로 정규화."""
    dt = datetime(2026, 6, 26, tzinfo=timezone.utc)
    assert board_repo._to_dt(dt) == dt
    assert board_repo._to_dt("2026-06-26T00:00:00Z") == dt
    # naive 입력은 UTC 로 간주(aware 비교 TypeError 방지).
    assert board_repo._to_dt("2026-06-26T00:00:00").tzinfo is not None


# ─────────────────────────── 읽음/알림 upsert·EXISTS SQL 가드 ───────────────────────────


@pytest.mark.asyncio
async def test_has_unread_notice_sql_has_coalesce_fallback():
    """has_unread_notice: notice EXISTS + state→users.created_at COALESCE fallback bind."""
    conn = AsyncMock()
    conn.fetchval.return_value = True
    assert await board_repo.has_unread_notice(conn, USER_ID) is True
    query, *args = conn.fetchval.call_args.args
    assert "board_type = 'notice'" in query
    assert "coalesce(" in query.lower()
    assert "from user_notice_state where user_id = $1" in query
    assert "from users where id = $1" in query
    assert args[0] == USER_ID


@pytest.mark.asyncio
async def test_set_notices_seen_at_upsert_idempotent_sql():
    """set_notices_seen_at: ON CONFLICT DO UPDATE(멱등) + now() bind. 두 번 호출 OK."""
    conn = AsyncMock()
    await board_repo.set_notices_seen_at(conn, USER_ID)
    await board_repo.set_notices_seen_at(conn, USER_ID)
    query, *args = conn.execute.call_args.args
    assert "insert into user_notice_state" in query
    assert "on conflict (user_id) do update set notices_seen_at = now()" in query
    assert args[0] == USER_ID


@pytest.mark.asyncio
async def test_upsert_post_read_touches_only_read_at():
    """upsert_post_read: read_at = now() 만 갱신(popup_acked_at 미언급) + ON CONFLICT 멱등."""
    conn = AsyncMock()
    pid = uuid4()
    await board_repo.upsert_post_read(conn, USER_ID, pid)
    query, *args = conn.execute.call_args.args
    assert "on conflict (user_id, post_id) do update set read_at = now()" in query
    assert "popup_acked_at" not in query
    assert args == [USER_ID, pid]


@pytest.mark.asyncio
async def test_upsert_popup_ack_touches_only_popup_acked_at():
    """upsert_popup_ack: popup_acked_at = now() 만 갱신(read_at 미갱신) + ON CONFLICT 멱등."""
    conn = AsyncMock()
    pid = uuid4()
    await board_repo.upsert_popup_ack(conn, USER_ID, pid)
    query, *args = conn.execute.call_args.args
    assert "on conflict (user_id, post_id) do update set popup_acked_at = now()" in query
    assert "do update set read_at" not in query
    assert args == [USER_ID, pid]
