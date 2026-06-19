"""멀티 게시판 어드민 라우터 — /admin/boards* (게이트 = require_admin = JWT + allowlist).

⚠️ main.py 에서 admin.router 보다 **먼저** include 해야 한다. admin.py 의 catch-all
GET /admin/{table} 이 /admin/boards 를 table="boards" 로 흡수하기 때문(테스트로 가드).
응답은 어드민 관례대로 snake_case raw passthrough(CamelModel 미사용).
"""
from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Response

from invest_note_api.auth.admin import require_admin
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import get_pool
from invest_note_api.db_ops import board_repo
from invest_note_api.errors import APIError
from invest_note_api.schemas.admin import AdminListResponse
from invest_note_api.schemas.board import BoardCommentCreate, BoardPostCreate, BoardPostUpdate

router = APIRouter(prefix="/admin", tags=["admin-board"])

ERR_POST_NOT_FOUND = "해당 게시글을 찾을 수 없습니다."
ERR_COMMENT_NOT_FOUND = "해당 댓글을 찾을 수 없습니다."


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
