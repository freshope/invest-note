"""앱 게시판 라우터 — 거래내역서 제보(broker_statement) write 전용.

board 는 기본적으로 require_admin 이지만, 이 한 흐름만 get_current_user 로 app-side write 를
연다(docs/decisions.md 2026-06-22). 보안 불변식을 라우터에서 강제한다:
  - board_type='broker_statement' 서버 하드코딩(body 미수신, 전용 스키마).
  - 업로드 2단계: presign 은 temp/{user_id}/ key(build_temp_key)로만 서명. submit 이
    temp→broker_statement/ 로 서버측 copy(promote). 미등록 temp 는 lifecycle 청소.
  - user_id 는 토큰(get_current_user)에서, body 무시.
  - content_type/size 는 register(submit) 시점 재검증(PUT presign 은 size 강제 불가).
  - storage_key 가 temp/{user_id}/ prefix 미시작 → 403(남 user key 차단).
  - 스팸 = 최근 1시간 10건까지 허용, 11번째부터 429.

검증 순서(submit): consent·extra-forbid 는 스키마(Pydantic) 단계라 라우터 본문 진입 전에
422. 본문은 R2 enabled(503) → key-prefix(403) → content_type/size 재검증(415/413) → spam(429)
→ temp→정식 copy(400 if 업로드 미완료, threadpool) → insert(transaction). DB 실패 시 정식
객체 보상 삭제.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Response
from starlette.concurrency import run_in_threadpool

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.db_ops import board_repo
from invest_note_api.errors import APIError
from invest_note_api.schemas.board import (
    BugReportCreate,
    FeedbackCreate,
    MyPostsResponse,
)
from invest_note_api.schemas.broker_statement import PresignRequest, SubmitRequest
from invest_note_api.storage import r2

router = APIRouter(prefix="/board", tags=["board"])

# 첨부 화이트리스트 — trades import 와 동일(xlsx/xls/pdf). content_type 은 모바일 파일피커가
# octet-stream/빈 값을 보내는 경우가 있어 호환을 위해 포함(presign==PUT Content-Type 강제 때문).
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
_ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".pdf"}
_ALLOWED_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",  # .xls
    "application/pdf",  # .pdf
    "application/octet-stream",  # 모바일 파일피커 fallback
    "",  # 일부 피커가 빈 content-type 전송
}
# 오류신고 스크린샷 화이트리스트 — 이미지 전용(broker_statement 문서 첨부와 분리).
# content_type 은 모바일 피커가 octet-stream/빈 값을 보내므로 ext 를 실제 게이트로 삼고
# 호환을 위해 둘을 포함한다(broker_statement 와 동일 관용).
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
_ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".heic"}
_ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/heic",
    "application/octet-stream",  # 모바일 파일피커 fallback
    "",  # 일부 피커가 빈 content-type 전송
}
# 스팸 가드 — 최근 1시간 기존 제보가 이 건수 이상이면 거부(10건까지 허용, 11번째부터 429).
_SPAM_WINDOW = timedelta(hours=1)
_SPAM_MAX = 10

# 공지 상세 화이트리스트 — admin user_id/comments/attachments/status/board_type 비노출(D-2).
_NOTICE_DETAIL_FIELDS = ("id", "title", "body", "created_at", "is_pinned", "metadata")
# 공지 목록 화이트리스트 — 상세와 동일 취지(D-2)로 admin user_id·내부 필드 비노출.
# 본문(body)은 목록에서 제외하고 상세에서만 노출한다.
_NOTICE_LIST_FIELDS = ("id", "title", "created_at", "is_pinned")

# "내 제보/문의" 글 화이트리스트 — 본인 글이라 user_id 등은 비노출. comments 는 별도 합본.
_MY_POST_FIELDS = (
    "id",
    "board_type",
    "title",
    "body",
    "status",
    "metadata",
    "created_at",
    "updated_at",
)
# 어드민 답변 댓글 화이트리스트 — 작성자(admin) user_id·post_id 비노출.
_MY_POST_COMMENT_FIELDS = ("id", "body", "is_admin", "created_at")
# 첨부 메타 화이트리스트 — storage_key 비노출. url(presigned GET)은 라우터가 발급해 더한다.
_MY_POST_ATTACHMENT_FIELDS = ("id", "original_name", "content_type", "size_bytes")

ERR_BAD_EXT = "지원하지 않는 파일 형식입니다 (xlsx, xls, pdf만 허용)."
ERR_BAD_CONTENT_TYPE = "지원하지 않는 파일 형식입니다."
ERR_TOO_LARGE = "파일 크기가 너무 큽니다 (최대 20 MB)."
ERR_BAD_IMAGE_EXT = "지원하지 않는 이미지 형식입니다 (png, jpg, webp, heic만 허용)."
ERR_IMAGE_TOO_LARGE = "이미지 크기가 너무 큽니다 (최대 10 MB)."
ERR_FORBIDDEN_KEY = "잘못된 첨부 참조입니다."
ERR_DUP_ATTACHMENT = "중복된 첨부가 있습니다."
ERR_RATE_LIMITED = "너무 많은 제보가 접수되었습니다. 잠시 후 다시 시도해주세요."
ERR_NOTICE_NOT_FOUND = "공지를 찾을 수 없습니다."
ERR_POST_NOT_FOUND = "글을 찾을 수 없습니다."


def _ext_of(name: str) -> str:
    return "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _validate_file(*, original_name: str, content_type: str, size_bytes: int) -> str:
    """ext/content_type/size 화이트리스트 검증 후 점 없는 ext 반환."""
    ext = _ext_of(original_name)
    if ext not in _ALLOWED_EXTENSIONS:
        raise APIError(ERR_BAD_EXT, 415)
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise APIError(ERR_BAD_CONTENT_TYPE, 415)
    if size_bytes > _MAX_UPLOAD_BYTES:
        raise APIError(ERR_TOO_LARGE, 413)
    return ext.removeprefix(".")


def _validate_image(*, original_name: str, content_type: str, size_bytes: int) -> str:
    """오류신고 스크린샷 ext/content_type/size 화이트리스트 검증 후 점 없는 ext 반환."""
    ext = _ext_of(original_name)
    if ext not in _ALLOWED_IMAGE_EXTENSIONS:
        raise APIError(ERR_BAD_IMAGE_EXT, 415)
    if content_type not in _ALLOWED_IMAGE_CONTENT_TYPES:
        raise APIError(ERR_BAD_CONTENT_TYPE, 415)
    if size_bytes > _MAX_IMAGE_BYTES:
        raise APIError(ERR_IMAGE_TOO_LARGE, 413)
    return ext.removeprefix(".")


async def _check_spam(pool: asyncpg.Pool, user_id, board_type: str) -> None:
    """최근 1시간 동일 board_type 글이 _SPAM_MAX 이상이면 429."""
    since = datetime.now(timezone.utc) - _SPAM_WINDOW
    async with pool.acquire() as conn:
        recent = await board_repo.count_recent_submissions(
            conn, user_id, since, board_type=board_type
        )
    if recent >= _SPAM_MAX:
        raise APIError(ERR_RATE_LIMITED, 429)


@router.post("/broker-statement/presign")
async def presign_broker_statement(
    body: PresignRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    """업로드 presign — 서버가 storage_key 를 생성해 PUT URL 을 발급한다(R2 미설정 시 503)."""
    ext = _validate_file(
        original_name=body.original_name,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
    )
    storage_key = r2.build_temp_key(user.id, ext)
    upload_url = r2.generate_put_url(settings, storage_key, body.content_type)
    return {
        "upload_url": upload_url,
        "storage_key": storage_key,
        "bucket": settings.r2_bucket,
        "expires_in": settings.r2_presign_expiry,
    }


@router.post("/broker-statement", status_code=201)
async def submit_broker_statement(
    body: SubmitRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """제보 등록 — R2 미설정 시 503(presign 도 503 이므로 도달 불가하나 직접 호출 방어).

    consent 는 스키마가 422 로 강제. storage_key prefix·size·content_type 재검증 후
    트랜잭션으로 post + attachment 를 등록한다.
    """
    if not settings.r2_enabled:
        raise APIError(r2.ERR_R2_DISABLED, 503)

    att = body.attachment
    # 남 user / 임의 key 차단 — presign 이 서버 생성한 temp prefix 와 정확히 일치해야 한다.
    if not att.storage_key.startswith(f"{r2.TEMP_PREFIX}/{user.id}/"):
        raise APIError(ERR_FORBIDDEN_KEY, 403)

    _validate_file(
        original_name=att.original_name,
        content_type=att.content_type,
        size_bytes=att.size_bytes,
    )

    final_key = r2.promote_key(att.storage_key)

    await _check_spam(pool, user.id, "broker_statement")

    # rate-check 통과 후에만 temp→정식 copy(동기 R2 호출 → threadpool). 소스 부재(업로드
    # 미완료) → 400. temp 원본은 R2 lifecycle 이 청소하므로 명시 삭제하지 않는다.
    # copy(R2 왕복)는 DB 커넥션 점유 밖에서 수행 — 풀 고갈 방지.
    await run_in_threadpool(r2.copy_object, settings, att.storage_key, final_key)

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                post = await board_repo.create_post(
                    conn,
                    board_type="broker_statement",
                    title=f"[{body.type}] {body.broker}",
                    body=body.note or "",
                    metadata={
                        "type": body.type,
                        "broker": body.broker,
                        "country": body.country,
                        "consent": True,
                        "source": "app",
                    },
                    is_pinned=False,
                    user_id=user.id,
                )
                attachment = await board_repo.create_attachment(
                    conn,
                    post_id=post["id"],
                    user_id=user.id,
                    original_name=att.original_name,
                    content_type=att.content_type,
                    size_bytes=att.size_bytes,
                    storage_key=final_key,
                    bucket=settings.r2_bucket,
                )
    except Exception:
        # DB 실패 시 정식 위치 객체는 lifecycle 청소 대상이 아니므로 보상 삭제.
        await run_in_threadpool(r2.delete_object, settings, final_key)
        raise
    return {"post_id": post["id"], "attachment": attachment}


# ─────────────────────────── 공지(notice) 읽기 ───────────────────────────


@router.get("/notices")
async def list_notices(
    page: int = 1,
    page_size: int = 20,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """공지 목록 — board_type='notice' 만. status 는 publish 게이트가 아니므로 필터하지 않는다.

    items 는 화이트리스트 필드만(D-2 — admin user_id·내부 필드 비노출). 본문은 상세에서만.
    has_unread 는 서버 EXISTS(state 없으면 가입 시각 fallback) — pinned_first 정렬로 인한
    client-side 오판을 피한다.
    """
    async with pool.acquire() as conn:
        rows, total = await board_repo.list_posts(
            conn, board_type="notice", page=page, page_size=page_size, pinned_first=True
        )
        has_unread = await board_repo.has_unread_notice(conn, user.id)
    items = [{k: r[k] for k in _NOTICE_LIST_FIELDS} for r in rows]
    return {"items": items, "total": total, "page": max(page, 1), "has_unread": has_unread}


@router.get("/notices/{post_id}")
async def get_notice(
    post_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """공지 상세 — 화이트리스트 필드만(admin user_id/comments/attachments 비노출).

    board_type!='notice' 면 404(다른 게시판 글을 공지 경로로 우회 조회 차단).
    """
    async with pool.acquire() as conn:
        detail = await board_repo.get_post(conn, post_id, with_relations=False)
    if detail is None or detail.get("board_type") != "notice":
        raise APIError(ERR_NOTICE_NOT_FOUND, 404)
    return {k: detail[k] for k in _NOTICE_DETAIL_FIELDS}


# ─────────────────────────── 내 제보/문의 읽기 ───────────────────────────


def _my_post_attachment(att: dict, settings: Settings) -> dict:
    """첨부 메타(화이트리스트) + 소유자 스코프 presigned GET url. storage_key 비노출.

    어드민 다운로드와 동일한 r2.generate_get_url 재사용(행별 bucket 우선). my-posts 가 이미
    user_id 로 스코프돼 본인 글 첨부만 도달하므로 추가 소유권 검사 불필요.
    """
    return {
        **{k: att[k] for k in _MY_POST_ATTACHMENT_FIELDS},
        "url": r2.generate_get_url(
            settings,
            att["storage_key"],
            filename=att["original_name"],
            bucket=att.get("bucket"),
        ),
    }


@router.get("/my-posts", response_model=MyPostsResponse)
async def list_my_posts(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    pool: asyncpg.Pool = Depends(get_pool),
) -> MyPostsResponse:
    """본인이 쓴 글(feedback/bug_report/broker_statement)을 어드민 답변·첨부와 함께 최신순으로.

    user_id 는 토큰에서만 취한다(body/query 무시). notice·타인 글은 절대 비노출 — repo 의
    user_id 스코프 + board_type 화이트리스트가 유일한 가드다. 응답 필드는 화이트리스트로 통제.
    첨부는 storage_key 대신 presigned GET url 만 노출(R2 미설정 시 발급 단계에서 503).
    """
    async with pool.acquire() as conn:
        posts = await board_repo.list_my_posts(conn, user.id)
    items = [
        {
            **{k: p[k] for k in _MY_POST_FIELDS},
            "unread": p["unread"],
            "popup_acked": p["popup_acked"],
            "comments": [
                {k: c[k] for k in _MY_POST_COMMENT_FIELDS} for c in p["comments"]
            ],
            "attachments": [
                _my_post_attachment(a, settings) for a in p["attachments"]
            ],
        }
        for p in posts
    ]
    return MyPostsResponse(items=items)


# ─────────────────────────── 읽음/알림 상태 쓰기 ───────────────────────────


@router.post("/notices/seen")
async def mark_notices_seen(
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    """공지 메뉴 열람 — notices_seen_at = now() upsert(high-water mark). 본문 없음(204)."""
    async with pool.acquire() as conn:
        await board_repo.set_notices_seen_at(conn, user.id)
    return Response(status_code=204)


async def _mark_post_marker(
    pool: asyncpg.Pool,
    post_id: str,
    user_id: Any,
    upsert: Callable[[Any, Any, str], Awaitable[None]],
) -> Response:
    """read/ack-popup 공통: 소유권 게이트(미충족 404) → upsert → 204. 두 엔드포인트가 공유한다."""
    async with pool.acquire() as conn:
        if not await board_repo.post_is_owned_by(conn, post_id, user_id):
            raise APIError(ERR_POST_NOT_FOUND, 404)
        await upsert(conn, user_id, post_id)
    return Response(status_code=204)


@router.post("/posts/{post_id}/read")
async def mark_post_read(
    post_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    """내 글 상세 열람 — read_at = now() upsert. 본인 글만 허용(소유권 미충족 404). 본문 없음(204)."""
    return await _mark_post_marker(pool, post_id, user.id, board_repo.upsert_post_read)


@router.post("/posts/{post_id}/ack-popup")
async def ack_post_popup(
    post_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    """바텀시트 팝업 확인 — popup_acked_at = now() upsert. 본인 글만 허용(404). 본문 없음(204)."""
    return await _mark_post_marker(pool, post_id, user.id, board_repo.upsert_popup_ack)


# ─────────────────────────── 의견(feedback) 쓰기 ───────────────────────────


@router.post("/feedback", status_code=201)
async def submit_feedback(
    body: FeedbackCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """의견 보내기(텍스트 전용) — board_type='feedback' 하드코딩, title 미전송 시 합성."""
    await _check_spam(pool, user.id, "feedback")
    async with pool.acquire() as conn:
        async with conn.transaction():
            post = await board_repo.create_post(
                conn,
                board_type="feedback",
                title=body.title or "[의견]",
                body=body.body,
                metadata={"source": "app"},
                is_pinned=False,
                user_id=user.id,
            )
    return {"post_id": post["id"]}


# ─────────────────────────── 오류 신고(bug_report) 쓰기 ───────────────────────────


@router.post("/bug-report/presign")
async def presign_bug_report(
    body: PresignRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    """스크린샷 업로드 presign — 이미지 화이트리스트 검증 후 temp key PUT URL 발급(503 if 미설정)."""
    ext = _validate_image(
        original_name=body.original_name,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
    )
    storage_key = r2.build_temp_key(user.id, ext)
    upload_url = r2.generate_put_url(settings, storage_key, body.content_type)
    return {
        "upload_url": upload_url,
        "storage_key": storage_key,
        "bucket": settings.r2_bucket,
        "expires_in": settings.r2_presign_expiry,
    }


@router.post("/bug-report", status_code=201)
async def submit_bug_report(
    body: BugReportCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """오류 신고 등록 — 텍스트 + 선택적 이미지 첨부(다중). board_type='bug_report' 하드코딩.

    첨부 없으면 post 만 등록. 첨부 있으면 broker_statement submit 와 동일 순서로 장마다
    enabled(503)·prefix(403)·MIME/size(415/413) 재검증 → spam(429) → temp→bug_report
    copy(threadpool) → 트랜잭션 등록, DB 실패 시 승격한 정식 객체 전부 보상 삭제.
    최대 장수는 스키마(MAX_BUG_REPORT_ATTACHMENTS)가 422 로 강제.
    """
    atts = body.attachments
    final_keys: list[str] = []
    if atts:
        if not settings.r2_enabled:
            raise APIError(r2.ERR_R2_DISABLED, 503)
        # 동일 temp key 중복 차단 — 같은 final_key 로 attachment 행이 중복 생성되면
        # 한 객체를 두 행이 공유해 한쪽 삭제 시 다른 행 이미지가 깨진다. 정상 FE 는
        # 파일마다 고유 presign key 를 받으므로 중복은 버그/조작 신호.
        if len({att.storage_key for att in atts}) != len(atts):
            raise APIError(ERR_DUP_ATTACHMENT, 400)
        for att in atts:
            # 남 user / 임의 key 차단 — presign 이 서버 생성한 temp prefix 와 정확히 일치해야 한다.
            if not att.storage_key.startswith(f"{r2.TEMP_PREFIX}/{user.id}/"):
                raise APIError(ERR_FORBIDDEN_KEY, 403)
            _validate_image(
                original_name=att.original_name,
                content_type=att.content_type,
                size_bytes=att.size_bytes,
            )
        final_keys = [r2.promote_key(att.storage_key, r2.BUG_REPORT_PREFIX) for att in atts]

    await _check_spam(pool, user.id, "bug_report")

    # copy(temp→정식)와 DB 등록을 하나의 보상 범위로 묶는다 — copy 루프 중간 실패에도
    # 이미 승격된 정식 객체(lifecycle 청소 대상 아님)를 전부 되돌리기 위해 실제 복사된
    # 키만 copied 에 누적하고, 어느 단계 실패든 그것만 보상 삭제한다.
    copied: list[str] = []
    try:
        # rate-check 통과 후에만 temp→정식 copy(동기 R2 호출 → threadpool).
        for att, final_key in zip(atts, final_keys):
            await run_in_threadpool(r2.copy_object, settings, att.storage_key, final_key)
            copied.append(final_key)
        async with pool.acquire() as conn:
            async with conn.transaction():
                post = await board_repo.create_post(
                    conn,
                    board_type="bug_report",
                    title=body.title or "[오류신고]",
                    body=body.body,
                    metadata={"source": "app"},
                    is_pinned=False,
                    user_id=user.id,
                )
                attachments = [
                    await board_repo.create_attachment(
                        conn,
                        post_id=post["id"],
                        user_id=user.id,
                        original_name=att.original_name,
                        content_type=att.content_type,
                        size_bytes=att.size_bytes,
                        storage_key=final_key,
                        bucket=settings.r2_bucket,
                    )
                    for att, final_key in zip(atts, final_keys)
                ]
    except Exception:
        for final_key in copied:
            await run_in_threadpool(r2.delete_object, settings, final_key)
        raise
    return {"post_id": post["id"], "attachments": attachments}
