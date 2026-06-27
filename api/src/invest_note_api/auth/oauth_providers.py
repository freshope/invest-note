"""Authlib provider clients — IdP OAuth/OIDC code flow 중개 (Phase 2b-1).

⚠️ 비균일(설계 노트): Google=OIDC discovery, Kakao=OAuth2+userinfo(full OIDC 아님),
Apple=JWT-client-secret(서명 JWT). 균일 인터페이스로 감싸되 내부 차이를 명시한다.

각 provider:
  - build_authorize_url(state, idp_verifier) → IdP authorize 리다이렉트 URL.
  - fetch_identity(code, idp_verifier) → (sub:str, userinfo) — code 교환 + identity 추출.

⚠️ PKCE 두 층 구분(혼동 시 보안 버그):
  - Layer1 (이 모듈): BE↔IdP PKCE. `idp_verifier` = BE 가 생성해 IdP 와 쓰는 verifier.
  - Layer2 (routers/auth, B12): app↔BE PKCE. 별개 — 이 모듈은 관여하지 않는다.

⚠️ B10 — sub 추출이 2a auth_identities 적재값과 정확히 일치해야 한다(불일치=B1 고아화):
  - Google: id_token `sub`(OIDC).
  - Kakao: /v2/user/me `id`(숫자) → **str** (2a 가 provider_id 를 "1234567" text 로 적재).
  - Apple: id_token `sub`(Service ID 재사용으로 Supabase 시절 sub 보존).

⚠️ B6 userinfo 정규화 — {email, display_name, avatar_url, email_verified}. IdP 가 미제공이면
None(upsert COALESCE 가 기존값 보존). Apple 은 첫 인증만 name 제공.

테스트는 IdP 응답을 fixture/mock 으로 주입한다(네트워크 미접속). discovery·token 교환·userinfo·
Apple JWKS 4곳 모두 mockable.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
import jwt

from invest_note_api.auth.pkce import pkce_s256
from invest_note_api.config import Settings

# Google OIDC id_token iss(둘 다 유효 — Google 이 둘을 혼용).
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

# IdP 고정 엔드포인트.
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

KAKAO_AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"

APPLE_AUTHORIZE_URL = "https://appleid.apple.com/auth/authorize"
APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"


@dataclass(frozen=True)
class UserInfo:
    """B6 upsert 입력 — IdP 가 미제공인 필드는 None(COALESCE 가 기존값 보존)."""
    email: str | None
    display_name: str | None
    avatar_url: str | None
    email_verified: bool | None


class ProviderNotConfigured(Exception):
    """해당 provider 의 client 자격증명이 미설정(부분 활성) — /auth/login 503 매핑."""


class OAuthProvider(Protocol):
    name: str

    def build_authorize_url(self, *, state: str, idp_verifier: str, redirect_uri: str) -> str: ...

    async def fetch_identity(
        self, *, code: str, idp_verifier: str, redirect_uri: str, http: httpx.AsyncClient
    ) -> tuple[str, UserInfo]: ...


# --- Google (OIDC) ------------------------------------------------------------


class GoogleProvider:
    name = "google"

    def __init__(self, settings: Settings):
        if not (settings.google_client_id and settings.google_client_secret):
            raise ProviderNotConfigured("google")
        self._client_id = settings.google_client_id
        self._client_secret = settings.google_client_secret

    def build_authorize_url(self, *, state: str, idp_verifier: str, redirect_uri: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": pkce_s256(idp_verifier),
            "code_challenge_method": "S256",
        }
        return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"

    async def fetch_identity(
        self, *, code: str, idp_verifier: str, redirect_uri: str, http: httpx.AsyncClient
    ) -> tuple[str, UserInfo]:
        resp = await http.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": idp_verifier,
            },
        )
        resp.raise_for_status()
        id_token = resp.json()["id_token"]
        # Google id_token 검증은 Google JWKS 가 필요하나, BE 는 직접 교환한 토큰이라(코드↔토큰
        # 1:1, TLS 채널) 클레임 추출에 집중한다. sub = OIDC sub. (서명 검증 강화는 후속.)
        claims = jwt.decode(id_token, options={"verify_signature": False})
        # F3: aud/iss 강제(Apple 과 대칭) — aud 가 우리 client_id 아니면 다른 앱 토큰 주입.
        if claims.get("iss") not in GOOGLE_ISSUERS:
            raise jwt.InvalidIssuerError(f"Google id_token iss 불일치: {claims.get('iss')}")
        if claims.get("aud") != self._client_id:
            raise jwt.InvalidAudienceError(
                f"Google id_token aud 불일치: {claims.get('aud')} ≠ {self._client_id}"
            )
        sub = str(claims["sub"])
        userinfo = UserInfo(
            email=claims.get("email"),
            display_name=claims.get("name"),
            avatar_url=claims.get("picture"),
            email_verified=claims.get("email_verified"),
        )
        return sub, userinfo


# --- Kakao (OAuth2 + userinfo, full OIDC 아님) ---------------------------------


class KakaoProvider:
    name = "kakao"

    def __init__(self, settings: Settings):
        if not settings.kakao_client_id:
            raise ProviderNotConfigured("kakao")
        self._client_id = settings.kakao_client_id
        self._client_secret = settings.kakao_client_secret  # optional(콘솔 설정 시)

    def build_authorize_url(self, *, state: str, idp_verifier: str, redirect_uri: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "code_challenge": pkce_s256(idp_verifier),
            "code_challenge_method": "S256",
        }
        return f"{KAKAO_AUTHORIZE_URL}?{urlencode(params)}"

    async def fetch_identity(
        self, *, code: str, idp_verifier: str, redirect_uri: str, http: httpx.AsyncClient
    ) -> tuple[str, UserInfo]:
        data = {
            "grant_type": "authorization_code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "code": code,
            "code_verifier": idp_verifier,
        }
        if self._client_secret:
            data["client_secret"] = self._client_secret
        token_resp = await http.post(KAKAO_TOKEN_URL, data=data)
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        # Kakao 는 OIDC 아님 → userinfo 별도 호출(/v2/user/me).
        me_resp = await http.get(
            KAKAO_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        me_resp.raise_for_status()
        me = me_resp.json()
        # ⚠️ B10: Kakao id 는 숫자 — str 로 변환해야 2a provider_id("1234567") 와 매칭(B1).
        sub = str(me["id"])
        account = me.get("kakao_account") or {}
        profile = account.get("profile") or {}
        userinfo = UserInfo(
            email=account.get("email"),  # optional(동의 안 하면 미제공)
            display_name=profile.get("nickname"),
            avatar_url=profile.get("profile_image_url"),
            email_verified=account.get("is_email_verified"),
        )
        return sub, userinfo


# --- Apple (JWT-client-secret) ------------------------------------------------


def build_apple_client_secret(settings: Settings) -> str:
    """Apple client secret = BE 가 동적 서명하는 단명 JWT(범용 secret 아님, Authlib Apple 특정).

    header: alg=ES256, kid=apple_key_id. claims: iss=team_id, sub=client_id(Service ID),
    aud=https://appleid.apple.com, iat/exp(단명, 5분). private key = apple_private_key(.p8).
    """
    if not (settings.apple_client_id and settings.apple_team_id
            and settings.apple_key_id and settings.apple_private_key):
        raise ProviderNotConfigured("apple")
    now = int(time.time())
    return jwt.encode(
        {
            "iss": settings.apple_team_id,
            "iat": now,
            "exp": now + 300,
            "aud": APPLE_ISSUER,
            "sub": settings.apple_client_id,
        },
        settings.apple_private_key,
        algorithm="ES256",
        headers={"kid": settings.apple_key_id},
    )


class AppleProvider:
    name = "apple"

    def __init__(self, settings: Settings):
        if not settings.apple_client_id:
            raise ProviderNotConfigured("apple")
        self._settings = settings
        self._client_id = settings.apple_client_id

    def build_authorize_url(self, *, state: str, idp_verifier: str, redirect_uri: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            # Apple 은 form_post 응답 + name/email scope(첫 인증만 제공).
            "response_mode": "form_post",
            "scope": "name email",
            "state": state,
            "code_challenge": pkce_s256(idp_verifier),
            "code_challenge_method": "S256",
        }
        return f"{APPLE_AUTHORIZE_URL}?{urlencode(params)}"

    async def fetch_identity(
        self, *, code: str, idp_verifier: str, redirect_uri: str, http: httpx.AsyncClient
    ) -> tuple[str, UserInfo]:
        client_secret = build_apple_client_secret(self._settings)
        resp = await http.post(
            APPLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": self._client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": idp_verifier,
            },
        )
        resp.raise_for_status()
        id_token = resp.json()["id_token"]
        claims = self._verify_id_token(id_token)
        # B10: Apple sub = id_token sub(Service ID 재사용으로 보존).
        sub = str(claims["sub"])
        userinfo = UserInfo(
            email=claims.get("email"),
            display_name=None,  # Apple name 은 첫 인증 form_post 에만(id_token 미포함)
            avatar_url=None,
            email_verified=_apple_bool(claims.get("email_verified")),
        )
        return sub, userinfo

    def _verify_id_token(self, id_token: str) -> dict:
        """Apple id_token 검증 — aud=client_id, iss=Apple. 서명 검증은 Apple JWKS 필요(후속).

        여기서는 클레임 무결성(aud/iss)을 강제한다 — aud 가 우리 Service ID 가 아니면 다른 앱
        토큰 주입이므로 거부.
        """
        claims = jwt.decode(id_token, options={"verify_signature": False})
        if claims.get("iss") != APPLE_ISSUER:
            raise jwt.InvalidIssuerError(f"Apple id_token iss 불일치: {claims.get('iss')}")
        if claims.get("aud") != self._client_id:
            raise jwt.InvalidAudienceError(
                f"Apple id_token aud 불일치: {claims.get('aud')} ≠ {self._client_id}"
            )
        return claims


def _apple_bool(v: Any) -> bool | None:
    # Apple email_verified 는 "true"/true 혼재.
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    return str(v).lower() == "true"


# ⚠️ 보안 불변식: 여기 등록하는 provider 의 userinfo.email_verified 는 **실제 이메일 소유 증명**을
# 의미해야 한다. cross-provider 자동 계정연결(auth_identity.link_user_by_verified_email)이 이 값을
# 신뢰하므로, 사용자가 임의 이메일을 verified 로 self-assert 할 수 있는 IdP 를 추가하면 같은 이메일의
# 기존 계정에 자동 연결돼 하이재킹이 가능하다. 현재 3사(Google OIDC·Apple OIDC·Kakao is_email_verified)는
# 모두 소유를 검증한다. self-assert 가능한 provider 를 추가하려면 link 측에 originator allowlist 를 먼저 둘 것.
_PROVIDERS = {"google": GoogleProvider, "kakao": KakaoProvider, "apple": AppleProvider}


def get_provider(name: str, settings: Settings) -> OAuthProvider:
    """provider 이름 → client. 미등록 이름이면 KeyError(라우터가 400 매핑),
    미설정 자격증명이면 ProviderNotConfigured(라우터가 503 매핑)."""
    cls = _PROVIDERS[name]
    return cls(settings)
