"""멀티 게시판 어드민 라우터 — /admin/boards* (게이트 = require_admin = JWT + allowlist).

⚠️ main.py 에서 admin.router 보다 **먼저** include 해야 한다. admin.py 의 catch-all
GET /admin/{table} 이 /admin/boards 를 table="boards" 로 흡수하기 때문(테스트로 가드).
응답은 어드민 관례대로 snake_case raw passthrough(CamelModel 미사용).
"""
from __future__ import annotations

import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Response

from invest_note_api.auth.admin import require_admin
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.db_ops import board_repo, notifications_repo
from invest_note_api.errors import APIError
from invest_note_api.schemas.admin import AdminListResponse
from invest_note_api.schemas.board import BoardCommentCreate, BoardPostCreate, BoardPostUpdate
from invest_note_api.services import push
from invest_note_api.storage import r2

router = APIRouter(prefix="/admin", tags=["admin-board"])

logger = logging.getLogger(__name__)

ERR_POST_NOT_FOUND = "해당 게시글을 찾을 수 없습니다."
ERR_COMMENT_NOT_FOUND = "해당 댓글을 찾을 수 없습니다."
ERR_ATTACHMENT_NOT_FOUND = "해당 첨부를 찾을 수 없습니다."

# 게시판 종류 → 알림 제목 라벨. 미지정 종류는 board_type 원문 fallback.
_BOARD_LABELS = {
    "feedback": "의견",
    "bug_report": "오류 신고",
    "broker_statement": "거래내역서 제보",
}
# 알림 본문 발췌 최대 길이(댓글/상태 본문이 길 때 잘라 미리보기로).
_NOTIFY_EXCERPT_LEN = 120


def _board_label(board_type: str | None) -> str:
    return _BOARD_LABELS.get(board_type or "", board_type or "게시판")


def _excerpt(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()
    return text if len(text) <= _NOTIFY_EXCERPT_LEN else text[:_NOTIFY_EXCERPT_LEN] + "…"


async def _notify_post_owner(conn, post: dict, *, notif_type: str, body: str | None) -> None:
    """글 소유자에게 알림 insert(best-effort). notice·소유자 없음(공지)은 skip.

    통지 대상은 글 소유자(관리자 본인 아님). 실패가 본 작업(댓글/상태변경)을 깨지 않도록
    호출부에서 예외를 삼킨다 — 여기서는 skip 조건만 판정한다.
    """
    board_type = post.get("board_type")
    owner_id = post.get("user_id")
    if board_type == "notice" or not owner_id:
        return
    notification = await notifications_repo.insert(
        conn,
        user_id=owner_id,
        type=notif_type,
        title=_board_label(board_type),
        body=_excerpt(body),
        board_type=board_type,
        ref_type="board_post",
        ref_id=post["id"],
    )
    # 시크릿 없으면 no-op. best-effort: sender 실패는 내부에서 삼켜 통지 insert/응답을
    # 깨지 않는다(호출부 try/except 가 이중 안전).
    await push.send_to_user(conn, user_id=owner_id, notification=notification)


@router.get("/boards", response_model=AdminListResponse)
async def list_boards(
    _: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
    board_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=board_repo.DEFAULT_PAGE_SIZE, ge=1),
    q: str | None = Query(default=None),
) -> AdminListResponse:
    async with pool.acquire() as conn:
        rows, total = await board_repo.list_posts(
            conn, board_type=board_type, page=page, page_size=page_size, q=q
        )
    return AdminListResponse(items=rows, total=total)


@router.get("/boards/attachments/{attachment_id}/download")
async def download_attachment(
    attachment_id: UUID,
    _: AuthenticatedUser = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """첨부 다운로드 — presigned GET URL JSON 반환(SPA 가 새 탭으로 연다). R2 미설정 시 503.

    ⚠️ /boards/{post_id} 보다 **먼저** 정의해야 한다 — 그렇지 않으면 'attachments' 가
    post_id(UUID) 로 파싱 시도되어 422 가 난다.
    """
    async with pool.acquire() as conn:
        attachment = await board_repo.get_attachment(conn, attachment_id)
    if attachment is None or not attachment.get("storage_key"):
        raise APIError(ERR_ATTACHMENT_NOT_FOUND, 404)
    download_url = r2.generate_get_url(
        settings,
        attachment["storage_key"],
        filename=attachment["original_name"],
        bucket=attachment.get("bucket"),
    )
    return {"download_url": download_url}


@router.get("/boards/{post_id}")
async def get_board(
    post_id: UUID,
    _: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    async with pool.acquire() as conn:
        detail = await board_repo.get_post(conn, post_id)
    if detail is None:
        raise APIError(ERR_POST_NOT_FOUND, 404)
    return detail


@router.post("/boards", status_code=201)
async def create_board(
    body: BoardPostCreate,
    user: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    async with pool.acquire() as conn:
        return await board_repo.create_post(
            conn,
            board_type=body.board_type,
            title=body.title,
            body=body.body,
            metadata=body.metadata,
            is_pinned=body.is_pinned,
            user_id=user.id,
        )


@router.patch("/boards/{post_id}")
async def update_board(
    post_id: UUID,
    body: BoardPostUpdate,
    _: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    fields = body.model_dump(exclude_unset=True)
    async with pool.acquire() as conn:
        row = await board_repo.update_post(conn, post_id, fields)
        if row is None:
            raise APIError(ERR_POST_NOT_FOUND, 404)
        # status 변경일 때만 소유자에게 통지(title/body/is_pinned 편집엔 발화 금지).
        # ②(broker_statement resolved)가 여기로 자연 포함. best-effort — 실패해도 상태변경 유지.
        if "status" in fields:
            try:
                await _notify_post_owner(
                    conn, row, notif_type="board_status", body=row.get("body")
                )
            except Exception:
                logger.warning(
                    "board_status 알림 insert 실패 post_id=%s", post_id, exc_info=True
                )
    return row


@router.delete("/boards/{post_id}", status_code=204, response_class=Response)
async def delete_board(
    post_id: UUID,
    _: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    async with pool.acquire() as conn:
        deleted = await board_repo.delete_post(conn, post_id)
    if not deleted:
        raise APIError(ERR_POST_NOT_FOUND, 404)
    return Response(status_code=204)


@router.post("/boards/{post_id}/comments", status_code=201)
async def create_board_comment(
    post_id: UUID,
    body: BoardCommentCreate,
    user: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    async with pool.acquire() as conn:
        row = await board_repo.create_comment(
            conn, post_id=post_id, body=body.body, user_id=user.id, is_admin=True
        )
        if row is None:
            raise APIError(ERR_POST_NOT_FOUND, 404)
        # create_comment 는 댓글 행만 반환 → post 를 조회해 소유자 user_id + board_type 획득.
        # 관리자 본인이 아닌 글 소유자에게 통지. best-effort — 실패해도 댓글 작성은 유지.
        try:
            post = await board_repo.get_post(conn, post_id, with_relations=False)
            if post is not None:
                await _notify_post_owner(
                    conn, post, notif_type="board_reply", body=body.body
                )
        except Exception:
            logger.warning(
                "board_reply 알림 insert 실패 post_id=%s", post_id, exc_info=True
            )
    return row


@router.delete("/boards/comments/{comment_id}", status_code=204, response_class=Response)
async def delete_board_comment(
    comment_id: UUID,
    _: AuthenticatedUser = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    async with pool.acquire() as conn:
        deleted = await board_repo.delete_comment(conn, comment_id)
    if not deleted:
        raise APIError(ERR_COMMENT_NOT_FOUND, 404)
    return Response(status_code=204)
