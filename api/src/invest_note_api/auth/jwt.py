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


def _verify_with_entry(token: str, entry: dict) -> AuthenticatedUser:
    """선택된 issuer entry({jwks_uri, issuer, audience})로 JWKS 서명 검증.

    issuer 가 None(또는 빈 값)이면 iss 검증을 스킵한다(fail-safe). 값이 있으면
    jwt.decode 에 issuer 를 전달해 iss 클레임 일치/존재를 강제한다.
    audience 가 빈 값이면 기본 AUTH_ROLE 로 정규화한다 — 빈 문자열을 그대로
    넘기면 PyJWT 가 모든 토큰을 InvalidAudience 로 거부하기 때문(설정 누락 방어).
    """
    client = _get_jwks_client(entry["jwks_uri"])
    signing_key = client.get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=JWT_ALGORITHMS,
        audience=entry.get("audience") or AUTH_ROLE,
        issuer=entry.get("issuer") or None,
    )
    return AuthenticatedUser(
        id=UUID(payload["sub"]),
        email=payload.get("email"),
        raw=payload,
    )


def decode_oidc_jwt(
    token: str,
    *,
    jwks_uri: str | None = None,
    audience: str = AUTH_ROLE,
    issuer: str | None = None,
    registry: dict[str, dict] | None = None,
    supabase_entry: dict | None = None,
) -> AuthenticatedUser:
    """issuer registry 기반 OIDC JWT 검증. 실패 시 jwt.InvalidTokenError 발생.

    검증 분기는 **Supabase=default / BE=명시 매칭** (P1/P4 lockout 방지). registry 를
    dict-lookup-reject 로 쓰면 dormant prod 에서 Supabase 토큰이 iss-miss 로 거부돼
    전원 lockout 이 되므로 그렇게 하지 않는다:
      - 토큰 iss 를 미검증 peek → registry 에 그 iss 가 있으면(=BE issuer) BE entry 선택.
      - 그 외 모든 토큰은 supabase_entry(default)로 검증. Supabase entry 의 issuer 가
        설정돼 있으면(prod 핀 활성) iss 불일치/누락은 거기서 InvalidIssuer 로 거부된다.

    registry/supabase_entry 미전달(레거시 호출) 시 jwks_uri/audience/issuer 단일 인자로
    단일 entry 를 구성한다 — Phase 1 호출부 호환.
    """
    # 레거시 단일-인자 경로(테스트/직접 호출 호환): registry 미구성 시 단일 entry.
    if supabase_entry is None:
        supabase_entry = {
            "jwks_uri": jwks_uri,
            "issuer": issuer,
            "audience": audience,
        }

    # 미검증 iss peek — registry(=BE issuer) 매칭이면 해당 entry, 아니면 Supabase default.
    entry = supabase_entry
    if registry:
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            iss = unverified.get("iss")
        except jwt.InvalidTokenError:
            iss = None
        if iss is not None and iss in registry:
            entry = registry[iss]

    return _verify_with_entry(token, entry)
