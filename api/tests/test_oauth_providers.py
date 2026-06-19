"""Phase 2b-1 — Authlib provider 비균일 + sub 추출(B10) 테스트.

IdP 응답(token 교환·userinfo·id_token)은 fixture/mock httpx 로 주입(네트워크 미접속).
핵심: provider 별 sub 추출이 2a auth_identities 적재값과 일치(B10→B1 고아화 방지), userinfo
정규화(B6 입력), Apple client_secret JWT round-trip + id_token aud/iss 검증.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

from invest_note_api.auth.oauth_providers import (
    APPLE_ISSUER,
    AppleProvider,
    GoogleProvider,
    KakaoProvider,
    ProviderNotConfigured,
    UserInfo,
    build_apple_client_secret,
    get_provider,
)
from invest_note_api.config import Settings

TEST_SUPABASE_URL = "https://test.supabase.co"
REDIRECT_URI = "https://api.invest-note.example/auth/callback"

_apple_key = generate_private_key(SECP256R1())
_apple_pem = _apple_key.private_bytes(
    Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
).decode()


def _settings(**kw) -> Settings:
    return Settings(supabase_url=TEST_SUPABASE_URL, **kw)


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeHttp:
    """post/get 응답을 URL 별로 라우팅하는 mock httpx.AsyncClient."""

    def __init__(self, routes):
        self._routes = routes  # url substring -> payload

    def _match(self, url):
        for frag, payload in self._routes.items():
            if frag in url:
                return _FakeResp(payload)
        raise AssertionError(f"unmocked URL: {url}")

    async def post(self, url, **kw):
        return self._match(url)

    async def get(self, url, **kw):
        return self._match(url)


# --- Google ---


def test_google_not_configured_raises():
    with pytest.raises(ProviderNotConfigured):
        GoogleProvider(_settings())


def test_google_authorize_url_has_pkce_and_state():
    p = GoogleProvider(_settings(google_client_id="gid", google_client_secret="gsec"))
    url = p.build_authorize_url(state="st8", idp_verifier="ver", redirect_uri=REDIRECT_URI)
    assert "accounts.google.com" in url
    assert "state=st8" in url
    assert "code_challenge_method=S256" in url
    assert "client_id=gid" in url


@pytest.mark.asyncio
async def test_google_extract_sub_and_userinfo():
    # Google id_token claims → sub(OIDC) + userinfo 정규화(B6).
    id_token = jwt.encode(
        {
            "sub": "google-sub-123",
            "email": "u@gmail.com",
            "email_verified": True,
            "name": "구글유저",
            "picture": "https://g/a.png",
        },
        "secret",
        algorithm="HS256",
    )
    p = GoogleProvider(_settings(google_client_id="gid", google_client_secret="gsec"))
    http = _FakeHttp({"oauth2.googleapis.com/token": {"id_token": id_token}})
    sub, info = await p.fetch_identity(
        code="c", idp_verifier="v", redirect_uri=REDIRECT_URI, http=http
    )
    assert sub == "google-sub-123"  # str(OIDC sub)
    assert info == UserInfo("u@gmail.com", "구글유저", "https://g/a.png", True)


# --- Kakao (B10: 숫자 id → str) ---


@pytest.mark.asyncio
async def test_kakao_numeric_id_extracted_as_str():
    # ⚠️ B10 핵심: Kakao id 는 숫자 → str("1234567") 로 추출돼야 2a provider_id 와 매칭(B1).
    p = KakaoProvider(_settings(kakao_client_id="krest"))
    http = _FakeHttp({
        "kauth.kakao.com/oauth/token": {"access_token": "kat"},
        "kapi.kakao.com/v2/user/me": {
            "id": 1234567,  # 숫자!
            "kakao_account": {
                "email": "u@kakao.com",
                "is_email_verified": True,
                "profile": {"nickname": "카카오유저", "profile_image_url": "https://k/a.png"},
            },
        },
    })
    sub, info = await p.fetch_identity(
        code="c", idp_verifier="v", redirect_uri=REDIRECT_URI, http=http
    )
    assert sub == "1234567"  # str, not int — 2a provider_id 매칭
    assert isinstance(sub, str)
    assert info == UserInfo("u@kakao.com", "카카오유저", "https://k/a.png", True)


@pytest.mark.asyncio
async def test_kakao_email_optional_none():
    # Kakao email 미동의 시 None(B6 COALESCE 가 기존값 보존).
    p = KakaoProvider(_settings(kakao_client_id="krest"))
    http = _FakeHttp({
        "kauth.kakao.com/oauth/token": {"access_token": "kat"},
        "kapi.kakao.com/v2/user/me": {"id": 99, "kakao_account": {}},
    })
    sub, info = await p.fetch_identity(
        code="c", idp_verifier="v", redirect_uri=REDIRECT_URI, http=http
    )
    assert sub == "99"
    assert info.email is None
    assert info.display_name is None


# --- Apple (client_secret JWT + id_token 검증) ---


def _apple_settings(**kw):
    return _settings(
        apple_client_id="com.pixelwave.investnote.service",
        apple_team_id="TEAM123",
        apple_key_id="KEY123",
        apple_private_key=_apple_pem,
        **kw,
    )


def test_apple_client_secret_jwt_round_trip():
    # Apple client secret = ES256 서명 JWT. header.kid/iss/sub/aud 정확.
    secret = build_apple_client_secret(_apple_settings())
    header = jwt.get_unverified_header(secret)
    assert header["alg"] == "ES256"
    assert header["kid"] == "KEY123"
    claims = jwt.decode(
        secret, _apple_key.public_key(), algorithms=["ES256"], audience=APPLE_ISSUER
    )
    assert claims["iss"] == "TEAM123"
    assert claims["sub"] == "com.pixelwave.investnote.service"
    assert claims["aud"] == APPLE_ISSUER
    assert claims["exp"] > claims["iat"]


def test_apple_client_secret_missing_key_raises():
    with pytest.raises(ProviderNotConfigured):
        build_apple_client_secret(_settings(apple_client_id="svc"))  # team/key/pem 없음


def _apple_id_token(*, sub="apple-sub-1", aud="com.pixelwave.investnote.service",
                    iss=APPLE_ISSUER, email="u@privaterelay.appleid.com"):
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "aud": aud, "iss": iss, "email": email,
         "email_verified": "true", "iat": now, "exp": now + 600},
        "secret", algorithm="HS256",
    )


@pytest.mark.asyncio
async def test_apple_extract_sub_from_id_token():
    p = AppleProvider(_apple_settings())
    http = _FakeHttp({"appleid.apple.com/auth/token": {"id_token": _apple_id_token()}})
    sub, info = await p.fetch_identity(
        code="c", idp_verifier="v", redirect_uri=REDIRECT_URI, http=http
    )
    assert sub == "apple-sub-1"  # id_token sub(Service ID 보존)
    assert info.email == "u@privaterelay.appleid.com"
    assert info.email_verified is True
    assert info.display_name is None  # Apple name 은 id_token 미포함


@pytest.mark.asyncio
async def test_apple_id_token_wrong_aud_rejected():
    # 다른 앱 토큰 주입 방어 — aud 가 우리 Service ID 가 아니면 거부.
    p = AppleProvider(_apple_settings())
    http = _FakeHttp({
        "appleid.apple.com/auth/token": {"id_token": _apple_id_token(aud="other.app")}
    })
    with pytest.raises(jwt.InvalidAudienceError):
        await p.fetch_identity(code="c", idp_verifier="v", redirect_uri=REDIRECT_URI, http=http)


@pytest.mark.asyncio
async def test_apple_id_token_wrong_iss_rejected():
    p = AppleProvider(_apple_settings())
    http = _FakeHttp({
        "appleid.apple.com/auth/token": {"id_token": _apple_id_token(iss="https://evil")}
    })
    with pytest.raises(jwt.InvalidIssuerError):
        await p.fetch_identity(code="c", idp_verifier="v", redirect_uri=REDIRECT_URI, http=http)


# --- get_provider registry ---


def test_get_provider_unknown_name_raises_keyerror():
    with pytest.raises(KeyError):
        get_provider("naver", _settings())


def test_get_provider_returns_configured():
    p = get_provider("google", _settings(google_client_id="g", google_client_secret="s"))
    assert p.name == "google"
