from typing import Annotated

import jwt
from fastapi import Depends, Header

from invest_note_api.auth.jwt import AuthenticatedUser, decode_oidc_jwt
from invest_note_api.config import Settings, get_settings
from invest_note_api.errors import ERR_UNAUTHORIZED, APIError


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """Bearer 토큰을 JWKS로 검증해 AuthenticatedUser 반환. 실패 시 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise APIError(ERR_UNAUTHORIZED, 401)

    token = authorization.removeprefix("Bearer ")
    try:
        # issuer registry 경유 검증 — Supabase(default) + BE(명시 매칭) 양 issuer.
        # registry 가 비면(BE dormant) Supabase entry 단독으로 Phase 1 과 동일하게 동작.
        return decode_oidc_jwt(
            token,
            registry=settings.oidc_issuer_registry,
            supabase_entry=settings.supabase_issuer_entry,
        )
    except (jwt.InvalidTokenError, jwt.exceptions.PyJWKClientError, ValueError):
        raise APIError(ERR_UNAUTHORIZED, 401)
