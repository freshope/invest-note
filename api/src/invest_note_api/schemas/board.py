"""멀티 게시판 쓰기 입력 스키마 — 게시글 작성/수정/관리자 댓글.

응답 row 는 admin 관례대로 DB 컬럼을 snake_case 그대로 통과한다(CamelModel 미사용).
여기서는 편집 가능 필드를 막는 보안 경계인 쓰기 입력만 정의한다 — extra='forbid' 로
미허용 키를 거부하고, board_type 은 Literal 로 CHECK 제약과 이중 검증한다.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from invest_note_api.schemas.broker_statement import AttachmentRef

BoardType = Literal["notice", "feedback", "bug_report", "broker_statement"]

# 오류신고 스크린샷 첨부 최대 장수(장당 10MB 게이트는 라우터에서 재검증).
MAX_BUG_REPORT_ATTACHMENTS = 5


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


class FeedbackCreate(BaseModel):
    """앱 의견 보내기 입력 — 텍스트 전용. board_type 미수신(서버 'feedback' 하드코딩).

    title 미전송 시 라우터가 고정 prefix 로 합성(NOT NULL). extra='forbid' 로 board_type
    주입 차단. wire 는 snake_case.
    """

    model_config = ConfigDict(extra="forbid")

    body: str
    title: str | None = None


class BugReportCreate(BaseModel):
    """앱 오류 신고 입력 — 텍스트 + 선택적 이미지 첨부(다중). board_type 미수신(서버 'bug_report').

    attachments 는 broker_statement 의 AttachmentRef 를 재사용한다(presign 응답을 그대로
    되받는 형태). 최대 MAX_BUG_REPORT_ATTACHMENTS 장(초과 시 422). 첨부 MIME/ext
    화이트리스트(이미지)는 라우터가 장마다 재검증한다.
    """

    model_config = ConfigDict(extra="forbid")

    body: str
    title: str | None = None
    attachments: list[AttachmentRef] = Field(
        default_factory=list, max_length=MAX_BUG_REPORT_ATTACHMENTS
    )
