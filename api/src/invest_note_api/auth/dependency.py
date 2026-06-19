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
        return decode_oidc_jwt(
            token,
            jwks_uri=settings.jwks_uri,
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
        )
    except (jwt.InvalidTokenError, jwt.exceptions.PyJWKClientError, ValueError):
        raise APIError(ERR_UNAUTHORIZED, 401)
