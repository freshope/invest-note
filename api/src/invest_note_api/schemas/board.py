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


class MyPostComment(BaseModel):
    """내 글에 달린 어드민 답변(is_admin=true) — wire 는 snake_case."""

    id: str
    body: str
    is_admin: bool
    created_at: Any


class MyPostAttachment(BaseModel):
    """내 글 첨부 — storage_key 대신 소유자 스코프 presigned GET url 만 노출."""

    id: str
    original_name: str
    content_type: str | None = None
    size_bytes: int | None = None
    url: str


class MyPostItem(BaseModel):
    """"내 제보/문의" 한 건 — 본인 글 + 어드민 답변 + 첨부. 노출 필드는 이 모델이 화이트리스트.

    user_id 등 내부 필드는 의도적으로 비포함(본인 글이라 작성자 표시 불필요). 첨부 storage_key 도
    비노출 — presigned url 로만 접근.
    """

    id: str
    board_type: str
    title: str
    body: str
    status: str
    metadata: dict[str, Any]
    created_at: Any
    updated_at: Any
    # 읽음 점(서버 판정, isMyPostUnread 복제) / 바텀시트 팝업 1회 노출 dedup.
    unread: bool
    popup_acked: bool
    comments: list[MyPostComment] = Field(default_factory=list)
    attachments: list[MyPostAttachment] = Field(default_factory=list)


class MyPostsResponse(BaseModel):
    """GET /board/my-posts 응답 — 본인 글 목록(최신순). notice/타인 글 비포함.

    total/page 는 additive — 라이브 v1.3.4 는 `.items` 만 읽어 무해. board_type 무인자(레거시)
    호출은 전량 반환 + total=len + page=1.
    """

    items: list[MyPostItem]
    total: int = 0
    page: int = 1


class PopupTarget(BaseModel):
    """진입 팝업 1건 — resolved broker_statement 미확인 글. broker 없으면 null(FE fallback)."""

    post_id: str
    broker: str | None = None


class UnreadSummaryResponse(BaseModel):
    """GET /board/unread-summary 응답 — board_type별 unread bool + 진입 팝업 1건(page 비의존).

    unread 는 feedback/bug_report/broker_statement 3키 bool. popup 은 PopupTarget 또는 null.
    """

    unread: dict[str, bool]
    popup: PopupTarget | None = None


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
