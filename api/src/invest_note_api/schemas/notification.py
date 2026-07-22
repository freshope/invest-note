"""알림 피드 응답 스키마 — 이종 소스(notification row + notice) UNION 피드.

wire 는 snake_case(admin/board 관례 passthrough). source/board_type 이 FE 라우팅 discriminator
라 load-bearing 이다. read 는 서버 계산값(FE 는 계산하지 않는다).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class NotificationItem(BaseModel):
    """피드 한 건 — notifications 행 또는 공지(board_post) 를 공통 shape 으로 project.

    source='notification'|'notice' 로 FE 딥링크 분기. notice 는 body=null, board_type='notice',
    ref_id=board_post.id(딥링크는 목록 레벨). read 는 서버 판정(notice 는 high-water fallback).
    """

    id: str
    source: str
    type: str
    title: str
    body: str | None = None
    board_type: str | None = None
    ref_id: str | None = None
    created_at: Any
    read: bool


class NotificationListResponse(BaseModel):
    """GET /notifications 응답 — 피드 목록(최신순) + 총 개수(두 소스 합) + page."""

    items: list[NotificationItem]
    total: int = 0
    page: int = 1


class UnreadCountResponse(BaseModel):
    """GET /notifications/unread-count 응답 — 미읽음 수(FE 벨은 boolean dot 으로만 사용)."""

    count: int
