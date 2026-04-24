from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from jwt import PyJWKClient

from invest_note_api.auth.constants import AUTH_ROLE, JWT_ALGORITHMS


@dataclass
class AuthenticatedUser:
    id: UUID
    email: str | None
    raw: dict


@lru_cache(maxsize=4)
def _get_jwks_client(jwks_uri: str) -> PyJWKClient:
    # cache_keys=True로 JWKS를 메모리에 캐시 (매 요청마다 네트워크 호출 방지)
    return PyJWKClient(jwks_uri, cache_keys=True)


def decode_supabase_jwt(token: str, jwks_uri: str) -> AuthenticatedUser:
    """Supabase JWKS(ES256)로 JWT 검증. 실패 시 jwt.InvalidTokenError 발생."""
    client = _get_jwks_client(jwks_uri)
    signing_key = client.get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=JWT_ALGORITHMS,
        audience=AUTH_ROLE,
    )
    return AuthenticatedUser(
        id=UUID(payload["sub"]),
        email=payload.get("email"),
        raw=payload,
    )
