"""Phase 2b-1 — full OAuth flow 통합(B-8) + expand 무회귀(B9) + profile 보존(B6).

단위 테스트(test_auth_router/test_oauth_providers/test_issuer_registry)가 함정별로 가드하고,
이 파일은 **end-to-end 합류**를 검증한다:
  - provider 3종(google/kakao/apple) login→callback→token→refresh full flow.
  - B9 expand hard gate: BE 활성 Settings 에서 Supabase 토큰 /me 200(구 앱 lockout 0).
  - B6 profile: 첫 로그인(값) → 재로그인(null) → 기존값 보존 + last_sign_in 갱신(라우터 경유).
"""

import base64
import hashlib
import time
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from fastapi.testclient import TestClient

from invest_note_api.auth.oauth_providers import UserInfo
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.external.http_client import get_http_client
from invest_note_api.main import create_app

TEST_SUPABASE_URL = "https://test.supabase.co"
BE_ISSUER = "https://api.invest-note.example/be"
BE_AUDIENCE = "invest-note-app"
BE_KID = "be-test-key"

_be_key = generate_private_key(SECP256R1())
_be_pem = _be_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()

# provider 별 (sub, 원래 UUID) 매핑.
PROVIDER_SUBS = {"google": "g-sub", "kakao": "111222", "apple": "a-sub"}
PROVIDER_UIDS = {p: uuid4() for p in PROVIDER_SUBS}


def _settings() -> Settings:
    return Settings(
        be_token_signing_key=_be_pem,
        be_token_issuer=BE_ISSUER,
        be_token_audience=BE_AUDIENCE,
        be_token_kid=BE_KID,
        be_oauth_redirect_base="https://api.invest-note.example",
        google_client_id="g", google_client_secret="gs",
        kakao_client_id="k",
        apple_client_id="a", apple_team_id="t", apple_key_id="kid",
        apple_private_key=_be_pem,
    )


def _challenge(v):
    return base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()


# --- Fake DB (test_auth_router 와 동형, COALESCE 충실 재현) ---


class _FakeConn:
    def __init__(self, store):
        self.s = store

    async def fetchrow(self, sql, *args):
        if "FROM auth_identities" in sql:
            provider, sub = args
            uid = self.s["identities"].get((provider, sub))
            return {"user_id": uid} if uid else None
        if "SELECT payload" in sql and "oauth_transient" in sql:
            # _PEEK_TRANSIENT_SQL(F1): $1 key, $2 kind, $3 now — 소비하지 않음.
            key, kind, now = args
            row = self.s["transient"].get(key)
            if row is None or row["kind"] != kind or row["expires_at"] <= now:
                return None
            return {"payload": row["payload"]}
        if "DELETE FROM oauth_transient" in sql and "RETURNING" in sql:
            # _CONSUME_TRANSIENT_SQL(F2): $1 key, $2 now, $3 kind — 즉시 DELETE.
            key, now, kind = args
            row = self.s["transient"].get(key)
            if row is None or row["kind"] != kind or row["expires_at"] <= now:
                return None
            del self.s["transient"][key]
            return {"payload": row["payload"]}
        if "UPDATE auth_refresh_tokens" in sql and "expires_at > $2" in sql:
            token_hash, now = args
            for r in self.s["refresh"]:
                if r["hash"] == token_hash and r["revoked"] is None and r["expires_at"] > now:
                    r["revoked"] = now
                    return {"user_id": r["user_id"]}
            return None
        if "FROM user_profiles" in sql:
            (uid,) = args
            p = self.s["profiles"].get(uid)
            return {"email": p["email"]} if p else None
        raise AssertionError(f"fetchrow: {sql[:50]}")

    async def execute(self, sql, *args):
        import json

        if "INSERT INTO oauth_transient" in sql:
            key, kind, payload, expires_at = args
            self.s["transient"][key] = {
                "kind": kind, "payload": json.loads(payload),
                "expires_at": expires_at, "consumed": False,
            }
            return
        if "INSERT INTO auth_refresh_tokens" in sql:
            user_id, token_hash, expires_at = args
            self.s["refresh"].append(
                {"user_id": user_id, "hash": token_hash, "expires_at": expires_at, "revoked": None}
            )
            return
        if "INSERT INTO public.user_profiles" in sql:
            user_id, email, display_name, avatar_url, email_verified, provider, last = args
            ex = self.s["profiles"].get(user_id)

            def co(new, old):
                return new if new is not None else old

            if ex is None:
                self.s["profiles"][user_id] = {
                    "email": email, "display_name": display_name, "avatar_url": avatar_url,
                    "email_verified": email_verified, "last_sign_in": last,
                }
            else:
                self.s["profiles"][user_id] = {
                    "email": co(email, ex["email"]),
                    "display_name": co(display_name, ex["display_name"]),
                    "avatar_url": co(avatar_url, ex["avatar_url"]),
                    "email_verified": co(email_verified, ex["email_verified"]),
                    "last_sign_in": last,
                }
            return
        raise AssertionError(f"execute: {sql[:50]}")

    @asynccontextmanager
    async def transaction(self):
        yield


class _FakePool:
    def __init__(self, store):
        self.s = store

    @asynccontextmanager
    async def acquire(self):
        yield _FakeConn(self.s)


def _store():
    return {
        "identities": {(p, PROVIDER_SUBS[p]): PROVIDER_UIDS[p] for p in PROVIDER_SUBS},
        "transient": {}, "refresh": [], "profiles": {},
    }


class _MockProvider:
    def __init__(self, name, userinfo):
        self.name = name
        self._userinfo = userinfo

    def build_authorize_url(self, *, state, idp_verifier, redirect_uri):
        return f"https://idp/authorize?state={state}"

    async def fetch_identity(self, *, code, idp_verifier, redirect_uri, http):
        return PROVIDER_SUBS[self.name], self._userinfo


def _client(store, userinfo_by_provider, monkeypatch):
    settings = _settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_pool] = lambda: _FakePool(store)
    app.dependency_overrides[get_http_client] = lambda: None  # mock provider 가 http 무시
    monkeypatch.setattr(
        "invest_note_api.routers.auth.get_provider",
        lambda name, s: _MockProvider(name, userinfo_by_provider[name]),
    )
    return TestClient(app)


def _full_flow(client, provider):
    verifier = f"verifier-{provider}-0123456789"
    r = client.get("/auth/login",
                   params={"provider": provider, "code_challenge": _challenge(verifier)},
                   follow_redirects=False)
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    cb = client.get("/auth/callback", params={"code": "idp-c", "state": state},
                    follow_redirects=False)
    code = parse_qs(urlparse(cb.headers["location"]).query)["code"][0]
    tok = client.post("/auth/token", json={"code": code, "code_verifier": verifier})
    return tok


@pytest.mark.parametrize("provider", ["google", "kakao", "apple"])
def test_full_flow_per_provider(provider, monkeypatch):
    store = _store()
    info = {p: UserInfo(f"{p}@e.com", p, None, True) for p in PROVIDER_SUBS}
    client = _client(store, info, monkeypatch)

    tok = _full_flow(client, provider)
    assert tok.status_code == 200
    body = tok.json()
    # access sub == 원래 UUID(B1).
    claims = jwt.decode(body["access_token"], _be_key.public_key(), algorithms=["ES256"],
                        audience=BE_AUDIENCE, issuer=BE_ISSUER)
    assert claims["sub"] == str(PROVIDER_UIDS[provider])
    # refresh 회전 동작.
    rr = client.post("/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert rr.status_code == 200
    assert rr.json()["refresh_token"] != body["refresh_token"]


def test_b6_profile_preserved_on_reauth_through_router(monkeypatch):
    # 첫 로그인(값 채움) → 재로그인(null, Apple 재인증 시뮬) → 기존값 보존 + last_sign_in 갱신.
    store = _store()
    info_first = {"apple": UserInfo("a@e.com", "애플유저", "https://a/x.png", True)}
    client1 = _client(store, info_first, monkeypatch)
    _full_flow(client1, "apple")
    uid = PROVIDER_UIDS["apple"]
    first_last = store["profiles"][uid]["last_sign_in"]
    assert store["profiles"][uid]["display_name"] == "애플유저"

    time.sleep(0.01)
    # 재로그인 — Apple 이 name/email null.
    info_reauth = {"apple": UserInfo(None, None, None, None)}
    client2 = _client(store, info_reauth, monkeypatch)
    _full_flow(client2, "apple")
    p = store["profiles"][uid]
    assert p["display_name"] == "애플유저"  # 보존(B6)
    assert p["email"] == "a@e.com"  # 보존
    assert p["last_sign_in"] > first_last  # 갱신


# --- 2c contract: cutover 후 Supabase(레거시) 토큰은 거부 ---


def test_legacy_supabase_token_rejected_when_be_active(monkeypatch):
    # 2c 불변식 역전(구 B9 expand gate 의 반전): Supabase fallback 제거 후, BE 활성 운영에서
    # 레거시 Supabase 토큰(BE registry 미등록 iss)은 /me 401. cutover 후 구 앱 거부 = 의도된 동작.
    from tests.conftest import _kid, _private_key, TEST_USER_ID, TEST_EMAIL
    from invest_note_api.auth.constants import AUTH_ROLE

    settings = _settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings

    now = int(time.time())
    sup_token = jwt.encode(
        {"sub": TEST_USER_ID, "email": TEST_EMAIL, "aud": AUTH_ROLE,
         "iss": f"{TEST_SUPABASE_URL}/auth/v1", "iat": now, "exp": now + 3600},
        _private_key, algorithm="ES256", headers={"kid": _kid},
    )

    with TestClient(app) as client:
        r = client.get("/v1/me", headers={"Authorization": f"Bearer {sup_token}"})
        assert r.status_code == 401
