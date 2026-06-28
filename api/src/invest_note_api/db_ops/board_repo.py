"""멀티 게시판 repo — board_posts/comments/attachments asyncpg 쿼리.

응답은 admin 관례대로 DB 컬럼을 snake_case 그대로 통과한다. row→dict 시 UUID 를 str 로,
jsonb(metadata)를 dict 로 정규화한다 — 풀(db.py)에 json codec 이 없어 asyncpg 가 jsonb 를
str 로 반환하므로, 읽기는 json.loads, 쓰기는 json.dumps + $n::jsonb 로 처리한다.

테이블/컬럼명은 이 모듈 상수에서만 오므로(사용자 입력 미주입) 화이트리스트 SET 조립이 안전하다.
값은 항상 $n 파라미터.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import asyncpg

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

# PATCH 편집 가능 컬럼(board_type 은 수정 불가). 명시적 null 은 스키마가 사전 거부.
_POST_UPDATABLE = ("title", "body", "status", "is_pinned")

# "내 제보/문의" 가 노출하는 board_type — notice 절대 제외(공지는 전용 경로).
_MY_POST_BOARD_TYPES = ("feedback", "bug_report", "broker_statement")


def _to_dt(value: Any) -> datetime:
    """timestamptz 값을 timezone-aware datetime 으로 정규화한다.

    asyncpg 는 timestamptz 를 aware datetime 으로 주지만, fake_pool/테스트는 ISO 문자열
    (`...Z` 또는 `+00:00`)을 준다. 양쪽을 모두 받아 수치 비교 가능한 aware datetime 으로 만든다
    (FE isMyPostUnread 와 동일하게 사전식 문자열 비교 금지 — `+00:00` vs `Z` 버그 회피).
    naive 면 UTC 로 간주(aware 와 비교 시 TypeError 방지).
    """
    if isinstance(value, datetime):
        dt = value
    else:
        # Python 3.10 fromisoformat 은 'Z' 를 못 받으므로 '+00:00' 으로 치환.
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _compute_unread(post: dict, read_at: Any) -> bool:
    """내 글 안읽음 판정 — FE isMyPostUnread(board-post.ts) 규칙을 정확히 복제.

    - 어드민 댓글 0 + status=='open' → False(갓 쓴 본인 글, 활동 없음).
    - 활동시각 = max(어드민 댓글 created_at, status!='open' 일 때만 updated_at).
      updated_at 은 status 미변경(open) 글에선 본문 편집 잡음이므로 활동신호에서 제외.
    - read_at 없으면 True, 있으면 활동시각 > read_at.
    """
    comments = post.get("comments", [])
    admin_comments = [c for c in comments if c.get("is_admin")]
    status_changed = post.get("status") != "open"
    if not admin_comments and not status_changed:
        return False
    candidates = [_to_dt(c["created_at"]) for c in admin_comments]
    if status_changed:
        candidates.append(_to_dt(post["updated_at"]))
    activity = max(candidates)
    if read_at is None:
        return True
    return activity > _to_dt(read_at)


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


async def list_my_posts(conn: Any, user_id: Any) -> list[dict]:
    """본인이 쓴 글(feedback/bug_report/broker_statement) + 어드민 답변 댓글 합본.

    사용자 격리는 posts 의 `user_id = $1` 과 comments 의 `post_id = any(<내 글 id>)` 가 전부다
    (RLS 제거됨). notice 는 board_type 화이트리스트로 제외한다. 각 글에 is_admin=true 댓글만
    created_at 오름차순으로 묶는다(작성자 표시 불필요라 get_post 의 user_profiles JOIN 은 생략).
    첨부(board_attachments)도 글별로 합본하되 storage_key 는 raw 로 싣고 라우터가 presigned
    GET URL 로 치환한다. 정렬은 list_posts 컨벤션대로 created_at desc(updated_at 은 status 외
    수정에도 갱신돼 부정확).

    각 글에 board_post_reads(현재 user)를 LEFT JOIN 해 read_at/popup_acked_at 을 끌어와
    unread(_compute_unread)·popup_acked(popup_acked_at IS NOT NULL)를 계산해 더한다. 별도
    fetch 가 아닌 단일 쿼리 JOIN 이라 호출 횟수는 늘지 않는다.
    """
    posts = await conn.fetch(
        "select board_posts.*, r.read_at, r.popup_acked_at from board_posts "
        "left join board_post_reads r "
        "on r.post_id = board_posts.id and r.user_id = $1 "
        "where board_posts.user_id = $1 and board_posts.board_type = any($2) "
        "order by board_posts.created_at desc",
        user_id,
        list(_MY_POST_BOARD_TYPES),
    )
    if not posts:
        return []

    # raw row 의 UUID id 로 합본 대상을 조회한다(_post_row_to_dict 가 str 로 바꾸기 전 값).
    post_ids = [row["id"] for row in posts]
    comments = await conn.fetch(
        "select * from board_comments "
        "where post_id = any($1) and is_admin = true "
        "order by created_at asc",
        post_ids,
    )
    comments_by_post: dict[str, list[dict]] = {}
    for c in comments:
        cd = _comment_row_to_dict(c)
        comments_by_post.setdefault(cd["post_id"], []).append(cd)

    # 첨부도 내 글 id 로만 스코프(post_id=any) — 타인 첨부 발급 경로 없음.
    attachments = await conn.fetch(
        "select * from board_attachments where post_id = any($1) order by created_at asc",
        post_ids,
    )
    attachments_by_post: dict[str, list[dict]] = {}
    for a in attachments:
        ad = _attachment_row_to_dict(a)
        attachments_by_post.setdefault(ad["post_id"], []).append(ad)

    result = []
    for row in posts:
        d = _post_row_to_dict(row)
        # JOIN 으로 끌어온 reads 컬럼은 응답에 직접 노출하지 않고 파생 플래그로만 쓴다.
        read_at = d.pop("read_at", None)
        popup_acked_at = d.pop("popup_acked_at", None)
        d["comments"] = comments_by_post.get(d["id"], [])
        d["attachments"] = attachments_by_post.get(d["id"], [])
        d["unread"] = _compute_unread(d, read_at)
        d["popup_acked"] = popup_acked_at is not None
        result.append(d)
    return result


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


# ─────────────────────────── 읽음/알림 상태 ───────────────────────────


async def set_notices_seen_at(conn: Any, user_id: Any) -> None:
    """공지 high-water mark upsert — notices_seen_at = now()(공지 메뉴 열 때). 멱등."""
    await conn.execute(
        "insert into user_notice_state (user_id, notices_seen_at) values ($1, now()) "
        "on conflict (user_id) do update set notices_seen_at = now()",
        user_id,
    )


async def has_unread_notice(conn: Any, user_id: Any) -> bool:
    """안읽은 공지 존재 여부(서버 EXISTS).

    state row 없으면 users.created_at(가입 시각)으로 fallback → 신규가입자에게 가입 전
    옛 공지는 안 뜬다. pinned_first 정렬로 인한 client-side 오판도 서버 EXISTS 가 해소.
    """
    return bool(
        await conn.fetchval(
            "select exists("
            "select 1 from board_posts bp where bp.board_type = 'notice' "
            "and bp.created_at > coalesce("
            "(select notices_seen_at from user_notice_state where user_id = $1), "
            "(select created_at from users where id = $1)))",
            user_id,
        )
    )


async def _upsert_post_read_field(
    conn: Any, user_id: Any, post_id: Any, column: str
) -> None:
    """board_post_reads 의 read_at|popup_acked_at 한 컬럼을 now() 로 upsert. 멱등.

    column 은 내부 호출 전용(아래 두 래퍼의 리터럴) — 외부 입력 아니므로 f-string 안전.
    한쪽 컬럼만 set 하고 다른 컬럼은 보존한다.
    """
    await conn.execute(
        f"insert into board_post_reads (user_id, post_id, {column}) "
        f"values ($1, $2, now()) "
        f"on conflict (user_id, post_id) do update set {column} = now()",
        user_id,
        post_id,
    )


async def upsert_post_read(conn: Any, user_id: Any, post_id: Any) -> None:
    """내 글 상세 열람 — read_at = now() upsert. popup_acked_at 은 건드리지 않음. 멱등."""
    await _upsert_post_read_field(conn, user_id, post_id, "read_at")


async def upsert_popup_ack(conn: Any, user_id: Any, post_id: Any) -> None:
    """바텀시트 팝업 확인 — popup_acked_at = now() upsert. read_at 은 건드리지 않음. 멱등."""
    await _upsert_post_read_field(conn, user_id, post_id, "popup_acked_at")


async def post_is_owned_by(conn: Any, post_id: Any, user_id: Any) -> bool:
    """post 가 해당 user 의 글인지 — read/ack-popup 소유권 게이트. notice(미소유)는 자연 제외.

    post_id 가 UUID 형식이 아니면(스캐너·오타) asyncpg 가 uuid 컬럼 인코딩에서 터져 500 이
    나므로, 먼저 파싱해 미충족이면 False(→ 404)로 떨군다.
    """
    try:
        UUID(str(post_id))
    except (ValueError, TypeError):
        return False
    return bool(
        await conn.fetchval(
            "select 1 from board_posts where id = $1 and user_id = $2",
            post_id,
            user_id,
        )
    )
