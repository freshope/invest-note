"""멀티 게시판 repo — board_posts/comments/attachments asyncpg 쿼리.

응답은 admin 관례대로 DB 컬럼을 snake_case 그대로 통과한다. row→dict 시 UUID 를 str 로,
jsonb(metadata)를 dict 로 정규화한다 — 풀(db.py)에 json codec 이 없어 asyncpg 가 jsonb 를
str 로 반환하므로, 읽기는 json.loads, 쓰기는 json.dumps + $n::jsonb 로 처리한다.

테이블/컬럼명은 이 모듈 상수에서만 오므로(사용자 입력 미주입) 화이트리스트 SET 조립이 안전하다.
값은 항상 $n 파라미터.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncpg

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

# PATCH 편집 가능 컬럼(board_type 은 수정 불가). 명시적 null 은 스키마가 사전 거부.
_POST_UPDATABLE = ("title", "body", "status", "is_pinned")


def _escape_like(term: str) -> str:
    """ILIKE 패턴의 와일드카드를 이스케이프(기본 ESCAPE '\\')."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _post_row_to_dict(row: Any) -> dict:
    """board_posts row → JSON 직렬화 가능한 dict. UUID→str, metadata(jsonb str)→dict.

    목록·상세 양쪽에서 같은 헬퍼를 써 metadata shape(항상 dict)을 일치시킨다.
    """
    d = dict(row)
    for field in ("id", "user_id"):
        if isinstance(d.get(field), UUID):
            d[field] = str(d[field])
    meta = d.get("metadata")
    if isinstance(meta, str):
        d["metadata"] = json.loads(meta)
    return d


def _comment_row_to_dict(row: Any) -> dict:
    d = dict(row)
    for field in ("id", "post_id", "user_id"):
        if isinstance(d.get(field), UUID):
            d[field] = str(d[field])
    return d


def _attachment_row_to_dict(row: Any) -> dict:
    d = dict(row)
    for field in ("id", "post_id", "comment_id", "user_id"):
        if isinstance(d.get(field), UUID):
            d[field] = str(d[field])
    return d


async def list_posts(
    conn: Any,
    *,
    board_type: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    q: str | None = None,
    pinned_first: bool = False,
) -> tuple[list[dict], int]:
    """게시글 목록 — (rows, total). board_type 필터(없으면 전체), q 는 title 부분일치(ILIKE).

    page 1-base, page_size 는 [1, MAX_PAGE_SIZE] clamp. rows 는 snake_case dict(metadata=dict).
    pinned_first=True 면 is_pinned 글을 상단 고정(공지용). 기본 off 로 admin 정렬 불변.
    """
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    offset = (page - 1) * page_size

    clauses: list[str] = []
    args: list[Any] = []
    if board_type:
        args.append(board_type)
        clauses.append(f"board_type = ${len(args)}")
    if q and q.strip():
        args.append(f"%{_escape_like(q.strip())}%")
        clauses.append(f"title ilike ${len(args)}")
    where = f"where {' and '.join(clauses)}" if clauses else ""

    total = await conn.fetchval(f"select count(*) from board_posts {where}", *args)

    # user_profiles 에도 created_at 컬럼이 있어 JOIN 후 정렬절은 board_posts 로 한정한다.
    order = (
        "board_posts.is_pinned desc, board_posts.created_at desc"
        if pinned_first
        else "board_posts.created_at desc"
    )
    args.extend([page_size, offset])
    rows = await conn.fetch(
        f"select board_posts.*, p.display_name as author_display_name, "
        f"p.avatar_url as author_avatar_url from board_posts "
        f"left join user_profiles p on p.user_id = board_posts.user_id {where} "
        f"order by {order} limit ${len(args) - 1} offset ${len(args)}",
        *args,
    )
    return [_post_row_to_dict(r) for r in rows], int(total or 0)


async def get_post(conn: Any, post_id: Any, *, with_relations: bool = True) -> dict | None:
    """게시글 상세 — {...post, comments:[...], attachments:[...]} 또는 None.

    comments/attachments 는 created_at 오름차순. 이번 스펙은 comment 첨부 뷰어가 없으므로
    attachments 는 post 에 직접 달린 것(post_id=$1)만 묶는다(comment 첨부는 후속).
    with_relations=False 면 post 행만 조회한다(공지 상세처럼 comments/attachments 를 버리는
    호출에서 불필요한 2회 왕복 제거).
    """
    post = await conn.fetchrow(
        "select board_posts.*, p.display_name as author_display_name, "
        "p.avatar_url as author_avatar_url from board_posts "
        "left join user_profiles p on p.user_id = board_posts.user_id where id = $1",
        post_id,
    )
    if post is None:
        return None
    if not with_relations:
        return _post_row_to_dict(post)
    comments = await conn.fetch(
        "select board_comments.*, p.display_name as author_display_name, "
        "p.avatar_url as author_avatar_url from board_comments "
        "left join user_profiles p on p.user_id = board_comments.user_id "
        "where post_id = $1 order by board_comments.created_at asc",
        post_id,
    )
    attachments = await conn.fetch(
        "select * from board_attachments where post_id = $1 order by created_at asc", post_id
    )
    detail = _post_row_to_dict(post)
    detail["comments"] = [_comment_row_to_dict(c) for c in comments]
    detail["attachments"] = [_attachment_row_to_dict(a) for a in attachments]
    return detail


async def create_post(
    conn: Any,
    *,
    board_type: str,
    title: str,
    body: str,
    metadata: dict,
    is_pinned: bool,
    user_id: Any,
) -> dict:
    """게시글 작성 — metadata 는 json.dumps + $n::jsonb(풀에 json codec 미등록)."""
    row = await conn.fetchrow(
        "insert into board_posts (board_type, title, body, metadata, is_pinned, user_id) "
        "values ($1, $2, $3, $4::jsonb, $5, $6) returning *",
        board_type,
        title,
        body,
        json.dumps(metadata),
        is_pinned,
        user_id,
    )
    return _post_row_to_dict(row)


async def update_post(conn: Any, post_id: Any, fields: dict[str, Any]) -> dict | None:
    """게시글 부분 수정. fields 는 BoardPostUpdate 화이트리스트 통과분(전달된 키만).

    빈 fields 면 갱신 없이 현재 행 반환(spurious 404 방지). 없는 행이면 None(라우터가 404).
    updated_at 은 트리거가 갱신.
    """
    edits = {k: v for k, v in fields.items() if k in _POST_UPDATABLE}
    if not edits:
        # 빈 PATCH — 현재 post 행만 반환(BoardPostRow shape 유지, get_post 의 상세 합본 아님).
        row = await conn.fetchrow("select * from board_posts where id = $1", post_id)
        return _post_row_to_dict(row) if row else None

    cols = list(edits)
    set_clause = ", ".join(f"{c} = ${i + 1}" for i, c in enumerate(cols))
    values = [edits[c] for c in cols]
    values.append(post_id)
    row = await conn.fetchrow(
        f"update board_posts set {set_clause} where id = ${len(cols) + 1} returning *",
        *values,
    )
    return _post_row_to_dict(row) if row else None


async def delete_post(conn: Any, post_id: Any) -> bool:
    """게시글 삭제(cascade 로 comments/attachments 동반 삭제). 없는 행 False(라우터가 404)."""
    result = await conn.execute("delete from board_posts where id = $1", post_id)
    return result.endswith(" 1")


async def create_comment(
    conn: Any, *, post_id: Any, body: str, user_id: Any, is_admin: bool = True
) -> dict | None:
    """관리자 댓글 작성. post 부재 시 None(라우터가 404).

    선검증(select 1)으로 일반적 not-found 를 잡되, 선검증과 insert 사이에 post 가 삭제되는
    race 는 FK 위반으로 나타나므로 ForeignKeyViolationError 도 None(404)으로 환원한다 —
    그렇지 않으면 동시 삭제 시 의도한 404 대신 500 이 난다."""
    exists = await conn.fetchval("select 1 from board_posts where id = $1", post_id)
    if not exists:
        return None
    try:
        row = await conn.fetchrow(
            "insert into board_comments (post_id, body, user_id, is_admin) "
            "values ($1, $2, $3, $4) returning *",
            post_id,
            body,
            user_id,
            is_admin,
        )
    except asyncpg.ForeignKeyViolationError:
        return None
    return _comment_row_to_dict(row)


async def delete_comment(conn: Any, comment_id: Any) -> bool:
    """댓글 삭제. 없는 행 False(라우터가 404)."""
    result = await conn.execute("delete from board_comments where id = $1", comment_id)
    return result.endswith(" 1")


async def create_attachment(
    conn: Any,
    *,
    post_id: Any,
    user_id: Any,
    original_name: str,
    content_type: str | None,
    size_bytes: int | None,
    storage_key: str | None,
    bucket: str | None,
) -> dict:
    """첨부 메타 insert(파일 바이트는 R2). storage_key/bucket 은 라우터가 서버 생성한 값."""
    row = await conn.fetchrow(
        "insert into board_attachments "
        "(post_id, user_id, original_name, content_type, size_bytes, storage_key, bucket) "
        "values ($1, $2, $3, $4, $5, $6, $7) returning *",
        post_id,
        user_id,
        original_name,
        content_type,
        size_bytes,
        storage_key,
        bucket,
    )
    return _attachment_row_to_dict(row)


async def get_attachment(conn: Any, attachment_id: Any) -> dict | None:
    """첨부 단건 조회(어드민 다운로드용). 없으면 None(라우터가 404)."""
    row = await conn.fetchrow(
        "select * from board_attachments where id = $1", attachment_id
    )
    return _attachment_row_to_dict(row) if row else None


async def count_recent_submissions(
    conn: Any, user_id: Any, since: Any, *, board_type: str = "broker_statement"
) -> int:
    """스팸 가드 — since(timestamptz) 이후 user 가 작성한 해당 board_type 글 수.

    board_type 기본값으로 broker_statement 제보 동작을 보존하고, feedback/bug_report 도
    같은 가드를 재사용한다.
    """
    total = await conn.fetchval(
        "select count(*) from board_posts "
        "where user_id = $1 and board_type = $3 and created_at >= $2",
        user_id,
        since,
        board_type,
    )
    return int(total or 0)
