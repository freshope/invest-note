from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status

from invest_note_api.auth.jwt import AuthenticatedUser, decode_supabase_jwt
from invest_note_api.config import Settings, get_settings


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """Bearer 토큰을 JWKS로 검증해 AuthenticatedUser 반환. 실패 시 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    token = authorization.removeprefix("Bearer ")
    try:
        return decode_supabase_jwt(token, settings.jwks_uri)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
