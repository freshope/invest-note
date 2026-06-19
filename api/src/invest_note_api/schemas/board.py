"""멀티 게시판 쓰기 입력 스키마 — 게시글 작성/수정/관리자 댓글.

응답 row 는 admin 관례대로 DB 컬럼을 snake_case 그대로 통과한다(CamelModel 미사용).
여기서는 편집 가능 필드를 막는 보안 경계인 쓰기 입력만 정의한다 — extra='forbid' 로
미허용 키를 거부하고, board_type 은 Literal 로 CHECK 제약과 이중 검증한다.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

BoardType = Literal["notice", "feedback", "bug_report", "broker_statement"]


class BoardPostCreate(BaseModel):
    """게시글 작성 입력 — 관리자 공지 등. board_type 은 Literal(CHECK 제약과 이중)."""

    model_config = ConfigDict(extra="forbid")

    board_type: BoardType
    title: str
    body: str = ""
    metadata: dict[str, Any] = {}
    is_pinned: bool = False


class BoardPostUpdate(BaseModel):
    """게시글 부분 수정(PATCH) — board_type 은 수정 불가(미포함). 전 필드 Optional.

    title/body/status/is_pinned 는 DB NOT NULL. 명시적 null 을 보내면 UPDATE ...=NULL 로
    제약 위반(500)이 나므로, omit(무수정)은 허용하되 명시적 null 만 422 로 거부한다.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    body: str | None = None
    status: str | None = None
    is_pinned: bool | None = None

    @field_validator("title", "body", "status", "is_pinned")
    @classmethod
    def _reject_explicit_null(cls, v: Any) -> Any:
        if v is None:
            raise ValueError("null 로 설정할 수 없습니다 (NOT NULL 컬럼)")
        return v


class BoardCommentCreate(BaseModel):
    """관리자 댓글 작성 입력 — is_admin/user_id 는 라우터가 현재 어드민으로 채운다."""

    model_config = ConfigDict(extra="forbid")

    body: str
