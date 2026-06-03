"""관리자 트리거 라우터용 토큰 인증 의존성."""
from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header

from invest_note_api.config import Settings, get_settings
from invest_note_api.errors import ERR_FORBIDDEN, APIError


async def require_admin_token(
    x_admin_token: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """X-Admin-Token 헤더를 settings.admin_token 과 constant-time 비교. 불일치/미설정 시 403.

    토큰 미설정(빈 문자열)이면 hmac.compare_digest("", "")가 True 가 되는 함정을 피하기 위해
    compare_digest 앞에서 명시적으로 거부한다.
    """
    if not settings.admin_token:
        raise APIError(ERR_FORBIDDEN, 403)
    if not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token):
        raise APIError(ERR_FORBIDDEN, 403)
