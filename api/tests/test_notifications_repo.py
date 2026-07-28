"""notifications_repo 단위 테스트 — FakeConnection 호출순서 + row→dict shape.

⚠️ FakeConnection 은 SQL 을 실행하지 않는다 — UNION 병합·COALESCE fallback·멱등 UPDATE 의
SQL 정합성은 여기서 보장되지 않는다(로컬 실DB 검증 + #16 E2E 담당). 여기서는 fetch 호출
순서와 dict 정규화(UUID→str)만 가드한다.
"""
from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from invest_note_api.db_ops import notifications_repo

from .fake_pool import FakeConnection

USER_ID = UUID("11111111-1111-1111-1111-111111111111")


def _run(coro):
    return asyncio.run(coro)


def _notif_row(**over) -> dict:
    row = {
        "id": uuid4(),
        "user_id": USER_ID,
        "type": "board_reply",
        "title": "거래내역서 제보",
        "body": "확인했습니다",
        "board_type": "broker_statement",
        "ref_type": "board_post",
        "ref_id": uuid4(),
        "created_at": "2026-07-22T00:00:00Z",
        "read_at": None,
    }
    row.update(over)
    return row


def _feed_row(**over) -> dict:
    row = {
        "id": uuid4(),
        "source": "notification",
        "type": "board_reply",
        "title": "거래내역서 제보",
        "body": "확인했습니다",
        "board_type": "broker_statement",
        "ref_id": uuid4(),
        "created_at": "2026-07-22T00:00:00Z",
        "read": False,
    }
    row.update(over)
    return row


def test_insert_returns_dict_uuid_to_str():
    row = _notif_row()
    conn = FakeConnection(row)
    result = _run(
        notifications_repo.insert(
            conn,
            user_id=USER_ID,
            type="board_reply",
            title="거래내역서 제보",
            body="확인했습니다",
            board_type="broker_statement",
            ref_type="board_post",
            ref_id=row["ref_id"],
        )
    )
    assert isinstance(result["id"], str)
    assert isinstance(result["user_id"], str)
    assert isinstance(result["ref_id"], str)
    assert result["type"] == "board_reply"


def test_list_feed_shape_and_order():
    """fetchval(total) → fetch(rows) 순서. rows 는 SQL 정렬 그대로(fake 는 순서 보존)."""
    notif = _feed_row(source="notification", created_at="2026-07-22T02:00:00Z")
    notice = _feed_row(
        source="notice",
        type="notice",
        board_type="notice",
        body=None,
        read=True,
        created_at="2026-07-22T01:00:00Z",
    )
    conn = FakeConnection(2, [notif, notice])
    items, total = _run(notifications_repo.list_feed(conn, USER_ID, page=1, page_size=20))
    assert total == 2
    assert [i["source"] for i in items] == ["notification", "notice"]
    assert isinstance(items[0]["id"], str)
    assert items[1]["body"] is None
    assert items[1]["read"] is True


def test_list_feed_total_zero():
    conn = FakeConnection(0, [])
    items, total = _run(notifications_repo.list_feed(conn, USER_ID))
    assert items == []
    assert total == 0


def test_unread_count_int():
    conn = FakeConnection(3)
    assert _run(notifications_repo.unread_count(conn, USER_ID)) == 3


def test_unread_count_none_coerced_zero():
    conn = FakeConnection(None)
    assert _run(notifications_repo.unread_count(conn, USER_ID)) == 0


def test_mark_read_true_when_row_matched():
    """UPDATE ... RETURNING id → id 반환 시 True(소유·존재)."""
    conn = FakeConnection(uuid4())
    assert _run(notifications_repo.mark_read(conn, uuid4(), USER_ID)) is True


def test_mark_read_false_when_not_found_or_foreign():
    """RETURNING None(없음/타인) → False(라우터가 404)."""
    conn = FakeConnection(None)
    assert _run(notifications_repo.mark_read(conn, uuid4(), USER_ID)) is False


def test_mark_all_read_noop_returns_none():
    conn = FakeConnection()
    assert _run(notifications_repo.mark_all_read(conn, USER_ID)) is None
