from typing import Annotated

import jwt
from fastapi import Depends, Header

from invest_note_api.auth.be_token import be_verify_key
from invest_note_api.auth.jwt import AuthenticatedUser, decode_oidc_jwt
from invest_note_api.config import Settings, get_settings
from invest_note_api.errors import ERR_UNAUTHORIZED, APIError


def _registry_with_be_key(settings: Settings) -> dict[str, dict]:
    """issuer registry 에 BE entry 의 in-process verify_key 를 주입한다(B8).

    config.oidc_issuer_registry 는 str-only dict 라 key 객체를 못 싣는다 → 검증 시점에
    be_verify_key(메모리 public key)를 BE entry 에 얹는다. 그러면 _verify_with_entry 가
    BE 토큰을 self-fetch(틀린 호스트) 없이 검증한다. dormant 면 registry 가 비어 무영향.
    """
    registry = settings.oidc_issuer_registry
    if not registry:
        return registry
    verify_key = be_verify_key(settings)
    if verify_key is None:
        return registry
    return {
        iss: {**entry, "verify_key": verify_key} for iss, entry in registry.items()
    }


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
            registry=_registry_with_be_key(settings),
            supabase_entry=settings.supabase_issuer_entry,
        )
    except (jwt.InvalidTokenError, jwt.exceptions.PyJWKClientError, ValueError):
        raise APIError(ERR_UNAUTHORIZED, 401)
