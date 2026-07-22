"""알림 피드 라우터 — /v1/notifications* (게이트 = get_current_user, 토큰 user_id 스코프).

피드는 notifications 행(per-user) + 공지(broadcast)를 UNION ALL 로 합쳐 조회한다(repo 소유).
read-all 은 두 소스(notifications read + 공지 high-water)를 한 트랜잭션으로 함께 처리한다 —
하나만 하면 벨 점이 남는다(패널 진입 시 미읽음 해소 메커니즘).
"""
from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Response

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import get_pool
from invest_note_api.db_ops import board_repo, notifications_repo
from invest_note_api.errors import APIError
from invest_note_api.schemas.notification import (
    NotificationListResponse,
    UnreadCountResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])

ERR_NOTIFICATION_NOT_FOUND = "해당 알림을 찾을 수 없습니다."


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=notifications_repo.DEFAULT_PAGE_SIZE, ge=1),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> NotificationListResponse:
    """알림 피드 — notifications ∪ 공지 UNION ALL, created_at DESC, offset 페이징."""
    async with pool.acquire() as conn:
        items, total = await notifications_repo.list_feed(
            conn, user.id, page=page, page_size=page_size
        )
    return NotificationListResponse(items=items, total=total, page=max(page, 1))


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> UnreadCountResponse:
    """미읽음 수 — notifications(read_at IS NULL) + 안읽은 공지(high-water). FE 벨은 boolean dot."""
    async with pool.acquire() as conn:
        count = await notifications_repo.unread_count(conn, user.id)
    return UnreadCountResponse(count=count)


@router.post("/read-all", status_code=204, response_class=Response)
async def mark_all_read(
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    """패널 진입 시 전체 읽음 — notifications read + 공지 high-water upsert(한 트랜잭션).

    본인 상태 write 라 둘 다 성공/실패여야 한다(부분 성공 시 벨 점 잔존). producer 의
    best-effort 와 반대 방향.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await notifications_repo.mark_all_read(conn, user.id)
            await board_repo.set_notices_seen_at(conn, user.id)
    return Response(status_code=204)


@router.post("/{notification_id}/read", status_code=204, response_class=Response)
async def mark_read(
    notification_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    """알림 1건 읽음 — source=notification 만 유효(공지는 이 경로 아님). 없음/타인 → 404, 멱등 204."""
    async with pool.acquire() as conn:
        ok = await notifications_repo.mark_read(conn, notification_id, user.id)
    if not ok:
        raise APIError(ERR_NOTIFICATION_NOT_FOUND, 404)
    return Response(status_code=204)
