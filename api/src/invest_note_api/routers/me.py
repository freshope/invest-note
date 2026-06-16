import logging

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Response, status

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.errors import APIError
from invest_note_api.external.http_client import get_http_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me")


@router.get("")
async def me(user: AuthenticatedUser = Depends(get_current_user)) -> dict:
    return {"user_id": str(user.id), "email": user.email}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
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
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM public.users WHERE id = $1", user.id)

    url = f"{settings.supabase_url}/auth/v1/admin/users/{user.id}"
    headers = {
        "apikey": settings.supabase_secret_key,
        "Authorization": f"Bearer {settings.supabase_secret_key}",
    }
    try:
        response = await http_client.delete(url, headers=headers)
    except httpx.HTTPError:
        logger.exception("Supabase admin deleteUser 호출 실패 user_id=%s", user.id)
        raise APIError("계정 삭제에 실패했습니다. 잠시 후 다시 시도해주세요.", 502)

    if response.status_code not in (200, 204):
        logger.error(
            "Supabase admin deleteUser 응답 비정상 user_id=%s status=%s body=%s",
            user.id,
            response.status_code,
            response.text,
        )
        raise APIError("계정 삭제에 실패했습니다. 잠시 후 다시 시도해주세요.", 502)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
