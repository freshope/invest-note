from typing import Literal

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.identity_provider import delete_user as idp_delete_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.errors import APIError
from invest_note_api.external.http_client import get_http_client

router = APIRouter(prefix="/me")


class DeleteAccountRequest(BaseModel):
    # 고정 코드값만 허용(자유 텍스트 없음) — 임의 문자열 저장 시 어드민 사유 분포 버킷이
    # 오염되므로 Literal 로 강제한다. 미선택은 None.
    reason: Literal["not_useful", "not_using", "privacy", "other"] | None = None


@router.get("")
async def me(user: AuthenticatedUser = Depends(get_current_user)) -> dict:
    return {"user_id": str(user.id), "email": user.email}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    body: DeleteAccountRequest = DeleteAccountRequest(),
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    http_client: httpx.AsyncClient = Depends(get_http_client),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    """계정 삭제 — public.users 행 삭제(accounts/trades/custom_tags 는 FK cascade) 후
    Supabase Auth 신원을 제거한다.

    DB 삭제 → Auth 삭제 순서. Auth 삭제가 실패해도 사용자 데이터는 이미 제거됐고, 재로그인
    시 빈 상태로 재프로비저닝되므로 데이터 잔존 위험은 없다.
    """
    if not settings.supabase_secret_key:
        raise APIError("계정 삭제 기능이 비활성화되었습니다. 관리자에게 문의해주세요.", 503)

    # owner(plain acquire) 컨텍스트 — RLS 우회, cascade 로 본인 데이터 정리.
    # 감사 INSERT 와 users DELETE 를 한 트랜잭션으로 묶어 한쪽만 남는 상태를 막는다.
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 감사 1건 INSERT 후 users DELETE 를 한 트랜잭션으로 묶는다. INSERT ... SELECT 라
            # users 행이 없으면(Auth 삭제 실패 후 재시도) 0 rows 삽입 → 탈퇴수 중복 집계 방지
            # (signup_at 은 users.created_at 스냅샷, 별도 멱등성 분기 불필요).
            await conn.execute(
                "INSERT INTO public.account_deletions (user_id, signup_at, reason) "
                "SELECT id, created_at, $2 FROM public.users WHERE id = $1",
                user.id,
                body.reason,
            )
            await conn.execute("DELETE FROM public.users WHERE id = $1", user.id)

    await idp_delete_user(str(user.id), http_client=http_client, settings=settings)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
