from dataclasses import dataclass
from uuid import UUID

import jwt

from invest_note_api.auth.constants import AUTH_ROLE, JWT_ALGORITHMS


@dataclass
class AuthenticatedUser:
    id: UUID
    email: str | None
    raw: dict


def _verify_with_entry(token: str, entry: dict) -> AuthenticatedUser:
    """선택된 issuer entry 로 서명 검증.

    entry 의 `verify_key`(in-process public key 객체)로 직접 검증한다 — BE 토큰 자기검증 경로.
    be_jwks_uri self-fetch(틀린 호스트 placeholder + self-HTTP fragility)를 회피한다. 2c
    fallback 제거 후 registry entry 는 항상 verify_key 를 갖는다(_registry_with_be_key 주입).

    issuer 가 None(또는 빈 값)이면 iss 검증을 스킵한다(fail-safe). 값이 있으면 jwt.decode 에
    issuer 를 전달해 iss 클레임 일치/존재를 강제한다. audience 가 빈 값이면 기본 AUTH_ROLE 로
    정규화한다. BE entry 는 B7 가 빈 aud 를 기동 단계에서 차단한다.
    """
    payload = jwt.decode(
        token,
        entry["verify_key"],
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
    registry: dict[str, dict],
) -> AuthenticatedUser:
    """issuer registry 기반 OIDC JWT 검증. 실패 시 jwt.InvalidTokenError 발생.

    토큰 iss 를 미검증 peek → registry 에 그 iss 가 있으면 해당 entry 로 서명 검증, 없으면
    (또는 iss 누락) InvalidTokenError raise(→401). Supabase 검증 default fallback 은 2c 에서
    제거됐다 — registry 에 등록된 issuer(현재 BE issuer)만 통과한다.

    ⚠️ 불변식 역전(2c): registry 가 비면(be_token_signing_key 미설정) **모든 토큰이 401**.
    이전의 "registry 비면 Supabase entry 단독=dormant-safe" 안전속성은 의도적으로 폐기됐다.
    """
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        iss = unverified.get("iss")
    except jwt.InvalidTokenError:
        iss = None
    if iss is None or iss not in registry:
        raise jwt.InvalidTokenError("issuer 가 registry 에 없습니다 (fallback 제거, 2c)")

    return _verify_with_entry(token, registry[iss])
