"""board_repo.list_my_posts 단위 테스트 — 사용자 격리 가드(SQL 자체는 통합 검증).

fake_pool 은 SQL 을 실행하지 않으므로 "notice 제외 / 타인 글 제외" 격리는 라우터 테스트로는
검증 불가다. 여기서 bind 인자를 직접 검사해 user_id 스코프 + board_type 화이트리스트 +
is_admin 댓글 필터가 쿼리에 정확히 실리는지 가드한다(RLS 제거됨 — 이 쿼리가 유일한 격리).
"""
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from invest_note_api.db_ops import board_repo

USER_ID = uuid4()


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
