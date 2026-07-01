"""어드민 패널 CRUD 인증 의존성 — JWT + ADMIN_EMAILS allowlist."""
from __future__ import annotations

from fastapi import Depends

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.errors import ERR_FORBIDDEN, APIError


async def require_admin(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """어드민 패널 CRUD 게이트 — 기존 JWT 검증(get_current_user) 위에 allowlist 만 추가.

    provider-neutral: Supabase 결합 없이 email 클레임만 본다(추후 탈-Supabase 시 jwt.py 한 곳 교체).
    email 을 정규화(소문자/trim)해 settings.admin_email_set 과 정확 비교한다 — raw 콤마 문자열
    substring 매칭 함정(`"b.com" in "a@b.com,..."` → True)을 피한다. allowlist 외/이메일 없음 시 403.
    """
    email = (user.email or "").strip().lower()
    if not email or email not in settings.admin_email_set:
        raise APIError(ERR_FORBIDDEN, 403)
    return user
