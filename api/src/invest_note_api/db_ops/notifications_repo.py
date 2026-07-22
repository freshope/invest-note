"""알림 피드 repo — notifications 테이블 + 공지(board_posts[notice]) UNION ALL 조회.

핵심 제약(spec): 공지(broadcast)는 notifications 에 per-user row 로 넣지 않는다. 이력/카운트는
SQL UNION ALL 로 두 이종 소스를 합쳐 조회하고, notice 의 read 판정은
`created_at <= COALESCE(notices_seen_at, users.created_at)` fallback 을 쓴다 —
`board_repo.has_unread_notice` 의 boolean 역(같은 fallback 식 재사용). bare notices_seen_at
IS NULL 로 새면 신규가입자에게 옛 공지 전부 unread 로 뜨는 0012 backfill 버그가 재발한다.

row→dict 는 board_repo 관례(UUID→str)를 따른다. metadata(jsonb)는 이 테이블에 없다.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# notice read 판정 fallback — has_unread_notice 와 동일 식(single source of truth 의도).
# state row 없으면 users.created_at(가입 시각)으로 fallback → 신규가입자 옛 공지 안 뜸.
_NOTICE_SEEN_FALLBACK = (
    "coalesce("
    "(select notices_seen_at from user_notice_state where user_id = $1), "
    "(select created_at from users where id = $1))"
)


def _to_str(value: Any) -> Any:
    return str(value) if isinstance(value, UUID) else value


def _row_to_dict(row: Any) -> dict:
    """notifications row → JSON 직렬화 가능한 dict(UUID→str)."""
    d = dict(row)
    for field in ("id", "user_id", "ref_id"):
        if isinstance(d.get(field), UUID):
            d[field] = str(d[field])
    return d


def _feed_row_to_dict(row: Any) -> dict:
    """UNION 피드 row → FeedItem dict(UUID→str). read/source/type 는 SQL 계산값."""
    d = dict(row)
    for field in ("id", "ref_id"):
        if isinstance(d.get(field), UUID):
            d[field] = str(d[field])
    return d


async def insert(
    conn: Any,
    *,
    user_id: Any,
    type: str,
    title: str,
    body: str | None,
    board_type: str | None,
    ref_type: str | None,
    ref_id: Any,
) -> dict:
    """알림 1건 insert → 생성된 행 dict. board_type/ref_id 는 딥링크용으로 저장."""
    row = await conn.fetchrow(
        "insert into notifications "
        "(user_id, type, title, body, board_type, ref_type, ref_id) "
        "values ($1, $2, $3, $4, $5, $6, $7) returning *",
        user_id,
        type,
        title,
        body,
        board_type,
        ref_type,
        ref_id,
    )
    return _row_to_dict(row)


async def list_feed(
    conn: Any,
    user_id: Any,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> tuple[list[dict], int]:
    """알림 피드 — (items, total). notifications(user 스코프) ∪ notice(broadcast) UNION ALL.

    단일 SQL 로 두 소스를 피드 컬럼으로 project 후 created_at DESC 로 합쳐 offset 페이징한다
    (in-memory merge 금지 — offset 페이징 깨짐). notice read 는 high-water fallback 판정.
    created_at 동률 시 id 로 tie-break 해 offset 페이징 결정성을 확보한다.
    """
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    offset = (page - 1) * page_size

    total = int(
        await conn.fetchval(
            "select "
            "(select count(*) from notifications where user_id = $1) + "
            "(select count(*) from board_posts where board_type = 'notice')",
            user_id,
        )
        or 0
    )

    rows = await conn.fetch(
        "select id, source, type, title, body, board_type, ref_id, created_at, read from ("
        "  select n.id as id, 'notification' as source, n.type as type, n.title as title, "
        "         n.body as body, n.board_type as board_type, n.ref_id as ref_id, "
        "         n.created_at as created_at, (n.read_at is not null) as read "
        "  from notifications n where n.user_id = $1 "
        "  union all "
        "  select bp.id as id, 'notice' as source, 'notice' as type, bp.title as title, "
        "         null as body, 'notice' as board_type, bp.id as ref_id, "
        "         bp.created_at as created_at, "
        f"        (bp.created_at <= {_NOTICE_SEEN_FALLBACK}) as read "
        "  from board_posts bp where bp.board_type = 'notice'"
        ") feed order by created_at desc, id desc limit $2 offset $3",
        user_id,
        page_size,
        offset,
    )
    return [_feed_row_to_dict(r) for r in rows], total


async def unread_count(conn: Any, user_id: Any) -> int:
    """미읽음 수 — notifications(read_at IS NULL) + 안읽은 notice(high-water fallback). 합."""
    count = await conn.fetchval(
        "select "
        "(select count(*) from notifications where user_id = $1 and read_at is null) + "
        "(select count(*) from board_posts where board_type = 'notice' "
        f"  and created_at > {_NOTICE_SEEN_FALLBACK})",
        user_id,
    )
    return int(count or 0)


async def mark_read(conn: Any, notification_id: Any, user_id: Any) -> bool:
    """알림 1건 읽음 처리 — 소유·존재 게이트, 멱등. 없거나 타인 소유면 False(라우터가 404).

    read_at = COALESCE(read_at, now()) 로 이미 읽은 행도 매칭되면 id 반환(멱등 204).
    """
    updated = await conn.fetchval(
        "update notifications set read_at = coalesce(read_at, now()) "
        "where id = $1 and user_id = $2 returning id",
        notification_id,
        user_id,
    )
    return updated is not None


async def mark_all_read(conn: Any, user_id: Any) -> None:
    """notifications 전체 읽음 처리(read_at=now()). notices_seen 은 라우터가 board_repo 로 별도.

    repo 경계 유지 — 공지 high-water(user_notice_state)는 board_repo.set_notices_seen_at 소유.
    """
    await conn.execute(
        "update notifications set read_at = now() "
        "where user_id = $1 and read_at is null",
        user_id,
    )
