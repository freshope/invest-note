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

from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.db_ops import board_repo
from invest_note_api.errors import APIError
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
# 스팸 가드 — 최근 1시간 기존 제보가 이 건수 이상이면 거부(10건까지 허용, 11번째부터 429).
_SPAM_WINDOW = timedelta(hours=1)
_SPAM_MAX = 10

ERR_BAD_EXT = "지원하지 않는 파일 형식입니다 (xlsx, xls, pdf만 허용)."
ERR_BAD_CONTENT_TYPE = "지원하지 않는 파일 형식입니다."
ERR_TOO_LARGE = "파일 크기가 너무 큽니다 (최대 20 MB)."
ERR_FORBIDDEN_KEY = "잘못된 첨부 참조입니다."
ERR_RATE_LIMITED = "너무 많은 제보가 접수되었습니다. 잠시 후 다시 시도해주세요."


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

    since = datetime.now(timezone.utc) - _SPAM_WINDOW
    async with pool.acquire() as conn:
        recent = await board_repo.count_recent_submissions(conn, user.id, since)
    if recent >= _SPAM_MAX:
        raise APIError(ERR_RATE_LIMITED, 429)

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
