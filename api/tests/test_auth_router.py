"""Phase 2b-1 — OAuth 중개 라우터 통합 테스트(B1/B3/B4/B5/B11/B12).

IdP 는 B-5 provider 를 mock(get_provider patch). DB 는 라우터가 치는 SQL 을 해석하는 _FakePool
(공유 store)로 대체 — auth_identities 매핑·oauth_transient·auth_refresh_tokens·user_profiles.

핵심 검증:
  B1  매핑 hit → 원래 UUID sub 토큰(데이터 보존) / 매핑 miss → 신규 가입(user+매핑 생성, 토큰 sub=새 UUID, email 매칭 부재, 2b-3)
  B3  일회용 code single-use(2회 교환 시 2회차 reject)
  B4  딥링크 리다이렉트 URL 에 access/refresh 문자열 부재(code 만)
  B5  refresh 회전(구 refresh 401)
  B11 state 불일치/위조 callback reject
  B12 앱 PKCE verifier 불일치/누락 → /auth/token 401
"""

import base64
import hashlib
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
ORIGINAL_UID = uuid4()  # 2a 매핑된 원래 public.users UUID
PROVIDER_SUB = "google-sub-xyz"

_be_key = generate_private_key(SECP256R1())
_be_pem = _be_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()


def _settings() -> Settings:
    return Settings(
        supabase_url=TEST_SUPABASE_URL,
        be_token_signing_key=_be_pem,
        be_token_issuer=BE_ISSUER,
        be_token_audience=BE_AUDIENCE,
        be_token_kid=BE_KID,
        be_oauth_redirect_base="https://api.invest-note.example",
        google_client_id="gid",
        google_client_secret="gsec",
    )


def _challenge(verifier: str) -> str:
    d = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(d).rstrip(b"=").decode()


# --- Fake DB (라우터 SQL 해석, 공유 store) ---


class _FakeConn:
    def __init__(self, store):
        self.s = store

    async def fetchrow(self, sql, *args):
        if "INSERT INTO public.auth_identities" in sql:
            # 신규 가입(2b-3): (provider, sub) → 새 UUID 매핑. ON CONFLICT DO NOTHING RETURNING:
            # 이미 있으면 None(충돌), 없으면 삽입 후 {user_id}.
            provider, sub, uid = args
            if (provider, sub) in self.s["identities"]:
                return None
            self.s["identities"][(provider, sub)] = uid
            return {"user_id": uid}
        if "FROM auth_identities" in sql:
            provider, sub = args
            uid = self.s["identities"].get((provider, sub))
            return {"user_id": uid} if uid else None
        if "SELECT payload" in sql and "oauth_transient" in sql:
            # _PEEK_TRANSIENT_SQL(F1): $1 key, $2 kind, $3 now — mutation 없는 조회.
            key, kind, now = args
            row = self.s["transient"].get(key)
            if row is None or row["kind"] != kind or row["expires_at"] <= now:
                return None
            return {"payload": row["payload"]}  # 소비하지 않음
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
        if "UPDATE auth_refresh_tokens" in sql and "expires_at" not in sql:
            # _REVOKE_REFRESH_SQL(logout): $1 token_hash, $2 now — 만료 조건 없는 멱등 revoke.
            token_hash, now = args
            for r in self.s["refresh"]:
                if r["hash"] == token_hash and r["revoked"] is None:
                    r["revoked"] = now
                    return {"user_id": r["user_id"]}
            return None
        if "FROM user_profiles" in sql:
            (uid,) = args
            p = self.s["profiles"].get(uid)
            return {"email": p["email"]} if p else None
        raise AssertionError(f"unhandled fetchrow: {sql[:50]}")

    async def fetch(self, sql, *args):
        # link_user_by_verified_email — 같은 verified 이메일의 기존 user 조회(B1-link).
        if "FROM public.user_profiles" in sql:
            (email,) = args
            seen = []
            for uid, p in self.s["profiles"].items():
                pe = p.get("email")
                if pe and pe.lower() == email.lower() and p.get("email_verified") is True and uid not in seen:
                    seen.append(uid)
            return [{"user_id": u} for u in seen]
        raise AssertionError(f"unhandled fetch: {sql[:50]}")

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
            self.s["refresh"].append({
                "user_id": user_id, "hash": token_hash,
                "expires_at": expires_at, "revoked": None,
            })
            return
        if "INSERT INTO public.user_profiles" in sql:
            # upsert_profile — COALESCE 시맨틱 단순 재현(테스트 관심사는 라우터 호출 여부).
            user_id = args[0]
            self.s["profiles"][user_id] = {
                "email": args[1], "display_name": args[2], "avatar_url": args[3],
                "email_verified": args[4],
            }
            return
        if sql.startswith("SET LOCAL"):
            return  # lock_timeout — fake no-op
        if "INSERT INTO public.users" in sql:
            # 신규 가입(2b-3): public.users 프로비저닝.
            self.s["users"].add(args[0])
            return
        raise AssertionError(f"unhandled execute: {sql[:50]}")

    async def fetchval(self, sql, *args):
        if "pg_advisory_xact_lock" in sql:
            return 1  # 신규 가입 직렬화 락 — fake 는 단일 스레드라 no-op
        raise AssertionError(f"unhandled fetchval: {sql[:50]}")

    @asynccontextmanager
    async def transaction(self):
        yield


class _FakePool:
    def __init__(self, store):
        self.s = store

    @asynccontextmanager
    async def acquire(self):
        yield _FakeConn(self.s)


def _new_store(*, with_mapping=True):
    return {
        "identities": {("google", PROVIDER_SUB): ORIGINAL_UID} if with_mapping else {},
        "transient": {},
        "refresh": [],
        "profiles": {},
        "users": set(),  # 신규 가입(2b-3)에서 생성된 public.users id 추적
    }


def _client(store):
    settings = _settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_pool] = lambda: _FakePool(store)
    # callback 이 get_http_client 를 주입받지만 mock provider 가 http 를 무시하므로 None 로 대체
    # (lifespan 미기동 TestClient 에서 app.state.http_client 부재 회피).
    app.dependency_overrides[get_http_client] = lambda: None
    return TestClient(app)


class _MockProvider:
    name = "google"

    def __init__(self, *a, **kw):
        pass

    def build_authorize_url(self, *, state, idp_verifier, redirect_uri):
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    async def fetch_identity(self, *, code, idp_verifier, redirect_uri, http):
        return PROVIDER_SUB, UserInfo("u@gmail.com", "구글", "https://g/a.png", True)


@pytest.fixture
def patch_provider(monkeypatch):
    monkeypatch.setattr(
        "invest_note_api.routers.auth.get_provider",
        lambda name, settings: _MockProvider(),
    )


# --- 헬퍼: login → callback → 딥링크 code 추출 ---


def _do_login(client, verifier):
    r = client.get(
        "/auth/login",
        params={"provider": "google", "code_challenge": _challenge(verifier)},
        follow_redirects=False,
    )
    assert r.status_code == 302
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    return state


def _do_callback(client, state, code="idp-code"):
    return client.get(
        "/auth/callback", params={"code": code, "state": state},
        follow_redirects=False,
    )


# --- B1: 매핑 해석(고아화 방지) ---


def test_b1_mapping_hit_mints_original_uuid_token(patch_provider):
    store = _new_store(with_mapping=True)
    client = _client(store)
    verifier = "app-verifier-1234567890"
    state = _do_login(client, verifier)
    cb = _do_callback(client, state)
    assert cb.status_code == 302

    # 딥링크 code 교환 → access 토큰 sub == 원래 UUID(IdP sub 아님).
    code = parse_qs(urlparse(cb.headers["location"]).query)["code"][0]
    r = client.post("/auth/token", json={"code": code, "code_verifier": verifier})
    assert r.status_code == 200
    access = r.json()["access_token"]
    claims = jwt.decode(access, _be_key.public_key(), algorithms=["ES256"],
                        audience=BE_AUDIENCE, issuer=BE_ISSUER)
    assert claims["sub"] == str(ORIGINAL_UID)


def test_b1_mapping_miss_creates_new_user(patch_provider):
    # 매핑 없는 sub = 진짜 신규 가입(2b-3). user+매핑 생성, 토큰 sub=새 UUID, profile 생성.
    # (email 매칭 안 함 — B1 정책 유지. gapless 는 cutover 동결+백필이 보장.)
    store = _new_store(with_mapping=False)
    client = _client(store)
    verifier = "app-verifier-new-0001"
    state = _do_login(client, verifier)
    cb = _do_callback(client, state)
    assert cb.status_code == 302

    # 신규 user + 매핑 생성(단일).
    assert len(store["users"]) == 1
    new_uid = next(iter(store["users"]))
    assert store["identities"][("google", PROVIDER_SUB)] == new_uid

    # 토큰 sub == 새 UUID(IdP sub 아님).
    code = parse_qs(urlparse(cb.headers["location"]).query)["code"][0]
    r = client.post("/auth/token", json={"code": code, "code_verifier": verifier})
    assert r.status_code == 200
    claims = jwt.decode(r.json()["access_token"], _be_key.public_key(),
                        algorithms=["ES256"], audience=BE_AUDIENCE, issuer=BE_ISSUER)
    assert claims["sub"] == str(new_uid)

    # profile 첫 레코드 생성.
    assert new_uid in store["profiles"]


def test_b1_link_to_existing_verified_email(patch_provider):
    # 매핑 miss 라도 같은 verified 이메일의 기존 계정이 있으면 새 user 생성 없이 그 계정에 연결(B1-link).
    # (카카오↔구글 동일 이메일 중복 계정 방지. _MockProvider 가 verified 'u@gmail.com' 제공.)
    existing_uid = uuid4()
    store = _new_store(with_mapping=False)
    store["profiles"][existing_uid] = {
        "email": "u@gmail.com", "display_name": "기존", "avatar_url": None,
        "email_verified": True,
    }
    client = _client(store)
    verifier = "app-verifier-link-001"
    state = _do_login(client, verifier)
    cb = _do_callback(client, state)
    assert cb.status_code == 302

    # 새 user 생성 안 함(create_user_identity 미호출 → public.users INSERT 없음).
    assert store["users"] == set()
    # 새 provider 매핑은 기존 user_id 로 추가됨(연결).
    assert store["identities"][("google", PROVIDER_SUB)] == existing_uid

    # 토큰 sub == 기존 UUID(데이터 연속성 — 같은 계정).
    code = parse_qs(urlparse(cb.headers["location"]).query)["code"][0]
    r = client.post("/auth/token", json={"code": code, "code_verifier": verifier})
    assert r.status_code == 200
    claims = jwt.decode(r.json()["access_token"], _be_key.public_key(),
                        algorithms=["ES256"], audience=BE_AUDIENCE, issuer=BE_ISSUER)
    assert claims["sub"] == str(existing_uid)


# --- B4: 딥링크에 토큰 직접 미노출 ---


def test_b4_deeplink_has_code_only_no_tokens(patch_provider):
    store = _new_store()
    client = _client(store)
    verifier = "app-verifier-abcdefghij"
    state = _do_login(client, verifier)
    cb = _do_callback(client, state)
    loc = cb.headers["location"]
    # 일회용 code 발급한 access/refresh 원본을 추출해 URL 에 없는지 확인.
    code = parse_qs(urlparse(loc).query)["code"][0]
    payload = store["transient"][code]["payload"]
    assert payload["access_token"] not in loc
    assert payload["refresh_token"] not in loc
    assert "access_token" not in loc
    assert "refresh_token" not in loc


# --- B3: 일회용 code single-use ---


def test_b3_one_time_code_replay_rejected(patch_provider):
    store = _new_store()
    client = _client(store)
    verifier = "app-verifier-replay00"
    state = _do_login(client, verifier)
    cb = _do_callback(client, state)
    code = parse_qs(urlparse(cb.headers["location"]).query)["code"][0]

    r1 = client.post("/auth/token", json={"code": code, "code_verifier": verifier})
    assert r1.status_code == 200
    # 2회차 → reject(B3).
    r2 = client.post("/auth/token", json={"code": code, "code_verifier": verifier})
    assert r2.status_code == 401


# --- B12: 앱 PKCE 대조 ---


def test_b12_wrong_verifier_rejected(patch_provider):
    store = _new_store()
    client = _client(store)
    state = _do_login(client, "correct-verifier-123")
    cb = _do_callback(client, state)
    code = parse_qs(urlparse(cb.headers["location"]).query)["code"][0]
    # 다른 verifier → challenge 불일치 → 401(악성 앱 code 탈취 차단).
    r = client.post("/auth/token", json={"code": code, "code_verifier": "WRONG-verifier"})
    assert r.status_code == 401


def test_f1_wrong_verifier_does_not_burn_code(patch_provider):
    # ⚠️ F1(HINGE 역전): 가로챈 code + 틀린 verifier → 401 이지만 code 를 **소진하지 않는다**.
    # 그래서 정당 앱이 이후 올바른 verifier 로 같은 code 를 교환할 수 있다(DoS 방지).
    # (구 구현은 PKCE 대조 전에 consume 해 정당 교환이 401 되던 버그 — 본 fix 로 역전.)
    correct = "correct-verifier-987"
    store = _new_store()
    client = _client(store)
    state = _do_login(client, correct)
    cb = _do_callback(client, state)
    code = parse_qs(urlparse(cb.headers["location"]).query)["code"][0]

    bad = client.post("/auth/token", json={"code": code, "code_verifier": "WRONG"})
    assert bad.status_code == 401
    # code 미소진 → 정상 verifier 로 교환 성공(F1 핵심).
    ok = client.post("/auth/token", json={"code": code, "code_verifier": correct})
    assert ok.status_code == 200
    assert "access_token" in ok.json()
    # 정상 교환 후엔 single-use 소진 → 재교환 401.
    again = client.post("/auth/token", json={"code": code, "code_verifier": correct})
    assert again.status_code == 401


def test_b12_missing_verifier_rejected(patch_provider):
    # code_verifier 누락 = 422(필수 필드). 거부(B12 enforce-always).
    store = _new_store()
    client = _client(store)
    state = _do_login(client, "v-missing-verifier-1")
    cb = _do_callback(client, state)
    code = parse_qs(urlparse(cb.headers["location"]).query)["code"][0]
    r = client.post("/auth/token", json={"code": code})
    assert r.status_code == 422


# --- B11: state 위조 ---


def test_b11_forged_state_callback_rejected(patch_provider):
    store = _new_store()
    client = _client(store)
    _do_login(client, "v-state-test-0001")
    # login 이 저장한 state 가 아닌 위조 state → 401.
    cb = _do_callback(client, "forged-state-not-stored")
    assert cb.status_code == 401
    # #3: 콜백 실패는 raw JSON 이 아니라 generic HTML 안내 페이지로 응답(브라우저 노출 위생).
    assert "text/html" in cb.headers["content-type"]
    assert "application/json" not in cb.headers["content-type"]


# --- B5: refresh 회전 ---


def test_b5_refresh_rotation_old_rejected(patch_provider):
    store = _new_store()
    client = _client(store)
    verifier = "app-verifier-refresh1"
    state = _do_login(client, verifier)
    cb = _do_callback(client, state)
    code = parse_qs(urlparse(cb.headers["location"]).query)["code"][0]
    tok = client.post("/auth/token", json={"code": code, "code_verifier": verifier}).json()
    old_refresh = tok["refresh_token"]

    # 회전 → 신 refresh, 신 access.
    r = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200
    new_refresh = r.json()["refresh_token"]
    assert new_refresh != old_refresh
    # 구 refresh 재사용 → 401.
    r2 = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401
    # 신 refresh 는 유효.
    r3 = client.post("/auth/refresh", json={"refresh_token": new_refresh})
    assert r3.status_code == 200


def test_logout_revokes_refresh_token(patch_provider):
    store = _new_store()
    client = _client(store)
    verifier = "app-verifier-logout"
    state = _do_login(client, verifier)
    cb = _do_callback(client, state)
    code = parse_qs(urlparse(cb.headers["location"]).query)["code"][0]
    tok = client.post("/auth/token", json={"code": code, "code_verifier": verifier}).json()
    refresh = tok["refresh_token"]

    # 로그아웃 → refresh revoke(200, revoked=True).
    r = client.post("/auth/logout", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert r.json()["revoked"] is True
    # revoke 후 그 refresh 로 회전 거부(401) — 서버측 세션 종료 확인.
    r2 = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 401
    # 멱등: 이미 revoked 토큰·미존재 토큰 재로그아웃도 200(revoked=False, 존재 여부 미노출).
    r3 = client.post("/auth/logout", json={"refresh_token": refresh})
    assert r3.status_code == 200 and r3.json()["revoked"] is False
    r4 = client.post("/auth/logout", json={"refresh_token": "unknown-token"})
    assert r4.status_code == 200 and r4.json()["revoked"] is False


# --- 무인증 mount ---


def test_auth_routes_unauthenticated(patch_provider):
    # /auth/login 은 Authorization 헤더 없이 접근 가능(로그인 진입점).
    store = _new_store()
    client = _client(store)
    r = client.get(
        "/auth/login",
        params={"provider": "google", "code_challenge": _challenge("v1234567890ab")},
        follow_redirects=False,
    )
    assert r.status_code == 302  # 401 아님


# --- Apple form_post(POST) callback ---


class _AppleMockProvider:
    name = "apple"

    def __init__(self, *a, **kw):
        pass

    def build_authorize_url(self, *, state, idp_verifier, redirect_uri):
        return f"https://appleid.apple.com/auth/authorize?state={state}"

    async def fetch_identity(self, *, code, idp_verifier, redirect_uri, http):
        # Apple id_token 엔 이름 없음(첫 인증 form_post 의 user 필드가 유일 출처).
        return "apple-sub-1", UserInfo("a@privaterelay.appleid.com", None, None, True)


@pytest.fixture
def patch_apple_provider(monkeypatch):
    monkeypatch.setattr(
        "invest_note_api.routers.auth.get_provider",
        lambda name, settings: _AppleMockProvider(),
    )


def test_apple_callback_post_form_with_user_name(patch_apple_provider):
    # ⚠️ Apple callback 은 POST form_post — GET 아님. 첫 인증 user 필드의 이름을 profile 에 보강.
    import json as _json

    store = _new_store(with_mapping=False)
    store["identities"][("apple", "apple-sub-1")] = ORIGINAL_UID
    client = _client(store)
    verifier = "apple-verifier-12345"
    # login 으로 state 발급.
    r = client.get("/auth/login",
                   params={"provider": "apple", "code_challenge": _challenge(verifier)},
                   follow_redirects=False)
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    # Apple form_post callback(POST body) — code/state + user(이름 JSON).
    user_json = _json.dumps({"name": {"firstName": "길동", "lastName": "홍"}})
    cb = client.post(
        "/auth/callback",
        data={"code": "apple-code", "state": state, "user": user_json},
        follow_redirects=False,
    )
    assert cb.status_code == 302
    # 이름이 profile 에 보강됐는지(id_token 엔 없던 값).
    assert store["profiles"][ORIGINAL_UID]["display_name"] == "길동 홍"


def test_apple_callback_post_without_user_field(patch_apple_provider):
    # 재인증(첫 인증 아님) — user 필드 부재. display_name None(B6 COALESCE 가 추후 보존).
    store = _new_store(with_mapping=False)
    store["identities"][("apple", "apple-sub-1")] = ORIGINAL_UID
    client = _client(store)
    verifier = "apple-verifier-67890"
    r = client.get("/auth/login",
                   params={"provider": "apple", "code_challenge": _challenge(verifier)},
                   follow_redirects=False)
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    cb = client.post(
        "/auth/callback",
        data={"code": "apple-code", "state": state},
        follow_redirects=False,
    )
    assert cb.status_code == 302
    assert store["profiles"][ORIGINAL_UID]["display_name"] is None


# --- F15: dormant(BE 토큰 미활성) 시 OAuth 엔드포인트 503(500 금지) ---


def _dormant_client(store):
    # be_token_signing_key 없음 = dormant. callback/refresh 가 mint_be_token RuntimeError→500
    # 대신 503 을 명시해야 한다(F15).
    settings = Settings(
        supabase_url=TEST_SUPABASE_URL,
        be_oauth_redirect_base="https://api.invest-note.example",
        google_client_id="gid",
        google_client_secret="gsec",
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_pool] = lambda: _FakePool(store)
    app.dependency_overrides[get_http_client] = lambda: None
    return TestClient(app)


def test_f15_callback_dormant_returns_503(patch_provider):
    store = _new_store()
    client = _dormant_client(store)
    state = _do_login(client, "v-dormant-12345678")
    cb = _do_callback(client, state)
    assert cb.status_code == 503  # 500 아님


def test_f15_refresh_dormant_returns_503(patch_provider):
    store = _new_store()
    client = _dormant_client(store)
    r = client.post("/auth/refresh", json={"refresh_token": "anything"})
    assert r.status_code == 503  # 500 아님


def test_login_rejects_non_s256(patch_provider):
    store = _new_store()
    client = _client(store)
    r = client.get(
        "/auth/login",
        params={"provider": "google", "code_challenge": "x",
                "code_challenge_method": "plain"},
        follow_redirects=False,
    )
    assert r.status_code == 400


# --- client=admin (어드민 웹 패널 BE flow) ---

ADMIN_REDIRECT_URL = "https://invest-note-admin.example/auth/callback/"


def _admin_settings() -> Settings:
    return Settings(
        supabase_url=TEST_SUPABASE_URL,
        be_token_signing_key=_be_pem,
        be_token_issuer=BE_ISSUER,
        be_token_audience=BE_AUDIENCE,
        be_token_kid=BE_KID,
        be_oauth_redirect_base="https://api.invest-note.example",
        be_admin_redirect_url=ADMIN_REDIRECT_URL,
        google_client_id="gid",
        google_client_secret="gsec",
    )


def _admin_client(store):
    settings = _admin_settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_pool] = lambda: _FakePool(store)
    app.dependency_overrides[get_http_client] = lambda: None
    return TestClient(app)


def test_admin_login_stores_client_in_state(patch_provider):
    # client=admin & env 설정 → 302 IdP, state payload 에 client=="admin" 저장.
    store = _new_store()
    client = _admin_client(store)
    r = client.get(
        "/auth/login",
        params={"provider": "google", "code_challenge": _challenge("v-admin-login-001"),
                "client": "admin"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    assert store["transient"][state]["payload"]["client"] == "admin"


def test_admin_login_empty_env_fails_fast(patch_provider):
    # client=admin 인데 be_admin_redirect_url 빈 값(_settings) → 503, state 저장 안 함(fail-fast).
    store = _new_store()
    client = _client(store)  # 기본 settings = be_admin_redirect_url 빈 값
    r = client.get(
        "/auth/login",
        params={"provider": "google", "code_challenge": _challenge("v-admin-noenv-1"),
                "client": "admin"},
        follow_redirects=False,
    )
    assert r.status_code == 503
    assert store["transient"] == {}  # IdP 왕복·state 소모 전 fail-fast


def test_admin_callback_web_redirects_to_admin_url(patch_provider):
    # admin client callback → be_admin_redirect_url?code=... 로 302(딥링크 아님).
    store = _new_store()
    client = _admin_client(store)
    verifier = "v-admin-callback-01"
    r = client.get(
        "/auth/login",
        params={"provider": "google", "code_challenge": _challenge(verifier),
                "client": "admin"},
        follow_redirects=False,
    )
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    cb = _do_callback(client, state)
    assert cb.status_code == 302
    loc = cb.headers["location"]
    assert loc.startswith(ADMIN_REDIRECT_URL)
    assert not loc.startswith("app.pixelwave.investnote://")  # 딥링크 아님
    code = parse_qs(urlparse(loc).query)["code"][0]
    assert code  # 일회용 code 부착
    # 교환 가능(기존 shape 유지) — admin web flow 도 동일 /auth/token.
    tok = client.post("/auth/token", json={"code": code, "code_verifier": verifier})
    assert tok.status_code == 200
    assert "access_token" in tok.json()


def test_native_callback_still_deeplink(patch_provider):
    # client 미지정(default native) → 기존 딥링크 302(무회귀). admin env 설정돼 있어도 영향 없음.
    store = _new_store()
    client = _admin_client(store)
    state = _do_login(client, "v-native-default-01")
    cb = _do_callback(client, state)
    assert cb.status_code == 302
    assert cb.headers["location"].startswith("app.pixelwave.investnote://")


# --- client=web (개발 편의용 app 웹 BE flow — admin 패턴 미러링, 값만 상이) ---

WEB_REDIRECT_URL = "http://localhost:3000/auth/callback"


def _web_settings() -> Settings:
    return Settings(
        supabase_url=TEST_SUPABASE_URL,
        be_token_signing_key=_be_pem,
        be_token_issuer=BE_ISSUER,
        be_token_audience=BE_AUDIENCE,
        be_token_kid=BE_KID,
        be_oauth_redirect_base="https://api.invest-note.example",
        be_app_web_redirect_url=WEB_REDIRECT_URL,
        google_client_id="gid",
        google_client_secret="gsec",
    )


def _web_client(store):
    settings = _web_settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_pool] = lambda: _FakePool(store)
    app.dependency_overrides[get_http_client] = lambda: None
    return TestClient(app)


def test_web_login_stores_client_in_state(patch_provider):
    # client=web & env 설정 → 302 IdP, state payload 에 client=="web" 저장.
    store = _new_store()
    client = _web_client(store)
    r = client.get(
        "/auth/login",
        params={"provider": "google", "code_challenge": _challenge("v-web-login-0001"),
                "client": "web"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    assert store["transient"][state]["payload"]["client"] == "web"


def test_web_login_empty_env_fails_fast(patch_provider):
    # client=web 인데 be_app_web_redirect_url 빈 값(_settings) → 503, state 저장 안 함(dormant).
    store = _new_store()
    client = _client(store)  # 기본 settings = be_app_web_redirect_url 빈 값
    r = client.get(
        "/auth/login",
        params={"provider": "google", "code_challenge": _challenge("v-web-noenv-01"),
                "client": "web"},
        follow_redirects=False,
    )
    assert r.status_code == 503
    assert store["transient"] == {}  # IdP 왕복·state 소모 전 fail-fast


def test_web_callback_redirects_to_web_url(patch_provider):
    # web client callback → be_app_web_redirect_url?code=... 로 302(딥링크 아님).
    store = _new_store()
    client = _web_client(store)
    verifier = "v-web-callback-001"
    r = client.get(
        "/auth/login",
        params={"provider": "google", "code_challenge": _challenge(verifier),
                "client": "web"},
        follow_redirects=False,
    )
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    cb = _do_callback(client, state)
    assert cb.status_code == 302
    loc = cb.headers["location"]
    assert loc.startswith(WEB_REDIRECT_URL)
    assert not loc.startswith("app.pixelwave.investnote://")  # 딥링크 아님
    code = parse_qs(urlparse(loc).query)["code"][0]
    assert code  # 일회용 code 부착
    # 교환 가능(기존 shape 유지) — web flow 도 동일 /auth/token.
    tok = client.post("/auth/token", json={"code": code, "code_verifier": verifier})
    assert tok.status_code == 200
    assert "access_token" in tok.json()
