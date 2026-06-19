"""IdP(신원 공급자) 어댑터 — 토큰 검증 외의 IdP 관리 호출을 한 곳에 격리한다.

현재 IdP=Supabase(GoTrue). IdP 교체 시 이 파일의 호출만 갈아끼우면 된다.
secret 미설정 검사(503)·앱 데이터 삭제는 호출자(routers/me.py)의 책임으로 둔다 —
어댑터는 순수하게 IdP 신원 제거만 수행한다.
"""

import logging

import httpx

from invest_note_api.config import Settings
from invest_note_api.errors import APIError

logger = logging.getLogger(__name__)


async def delete_user(
    user_id: str,
    *,
    http_client: httpx.AsyncClient,
    settings: Settings,
) -> None:
    """IdP 에서 사용자 신원을 제거한다. 실패 시 APIError(502)."""
    url = f"{settings.supabase_url}/auth/v1/admin/users/{user_id}"
    headers = {
        "apikey": settings.supabase_secret_key,
        "Authorization": f"Bearer {settings.supabase_secret_key}",
    }
    try:
        response = await http_client.delete(url, headers=headers)
    except httpx.HTTPError:
        logger.exception("Supabase admin deleteUser 호출 실패 user_id=%s", user_id)
        raise APIError("계정 삭제에 실패했습니다. 잠시 후 다시 시도해주세요.", 502)

    if response.status_code not in (200, 204):
        logger.error(
            "Supabase admin deleteUser 응답 비정상 user_id=%s status=%s body=%s",
            user_id,
            response.status_code,
            response.text,
        )
        raise APIError("계정 삭제에 실패했습니다. 잠시 후 다시 시도해주세요.", 502)
