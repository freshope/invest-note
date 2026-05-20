import logging

import httpx
from fastapi import APIRouter, Depends, Response, status

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.errors import APIError
from invest_note_api.external.http_client import get_http_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me")


@router.get("")
async def me(user: AuthenticatedUser = Depends(get_current_user)) -> dict:
    return {"user_id": str(user.id), "email": user.email}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> Response:
    """Supabase Auth 사용자 삭제 — accounts/trades 등은 FK on delete cascade 로 자동 정리."""
    if not settings.supabase_secret_key:
        raise APIError("계정 삭제 기능이 비활성화되었습니다. 관리자에게 문의해주세요.", 503)

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
