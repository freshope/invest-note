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


def decode_oidc_jwt(
    token: str,
    *,
    jwks_uri: str,
    audience: str = AUTH_ROLE,
    issuer: str | None = None,
) -> AuthenticatedUser:
    """OIDC JWKS(ES256/RS256)로 JWT 검증. 실패 시 jwt.InvalidTokenError 발생.

    issuer 가 None(또는 빈 값)이면 iss 검증을 스킵한다(fail-safe). 값이 있으면
    jwt.decode 에 issuer 를 전달해 iss 클레임 일치/존재를 강제한다.
    audience 가 빈 값이면 기본 AUTH_ROLE 로 정규화한다 — 빈 문자열을 그대로
    넘기면 PyJWT 가 모든 토큰을 InvalidAudience 로 거부하기 때문(설정 누락 방어).
    """
    client = _get_jwks_client(jwks_uri)
    signing_key = client.get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=JWT_ALGORITHMS,
        audience=audience or AUTH_ROLE,
        issuer=issuer or None,
    )
    return AuthenticatedUser(
        id=UUID(payload["sub"]),
        email=payload.get("email"),
        raw=payload,
    )
