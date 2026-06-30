import time
from uuid import UUID

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.external.http_client import get_http_client
from invest_note_api.main import create_app
from tests.conftest import (
    BE_AUDIENCE,
    BE_ISSUER,
    BE_KID,
    TEST_EMAIL,
    TEST_SUPABASE_URL,
    TEST_USER_ID,
    _be_private_pem,
    make_jwt,
)
from tests.fake_pool import FakeConnection, make_fake_pool


class _RecordingConn(FakeConnection):
    """execute 호출의 (query, args) 를 기록하는 fake — account_deletions INSERT 검증용."""

    def __init__(self, *responses: object) -> None:
        super().__init__(*responses)
        self.executed: list[tuple[str, tuple]] = []

    async def execute(self, query: str, *args: object) -> str:
        self.executed.append((query, args))
        return await super().execute(query, *args)


def test_me_no_header(auth_client: TestClient) -> None:
    r = auth_client.get("/me")
    assert r.status_code == 401


def test_me_invalid_token(auth_client: TestClient) -> None:
    r = auth_client.get("/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401


def test_me_expired_token(auth_client: TestClient) -> None:
    # 만료된 BE 토큰(등록 iss/aud) → 401 (ExpiredSignatureError). iss 게이트가 아니라 만료가
    # 거부 사유가 되도록 등록 issuer 로 발급한다(2c: 음성 케이스 단락 방지).
    expired = jwt.encode(
        {
            "sub": TEST_USER_ID,
            "email": TEST_EMAIL,
            "aud": BE_AUDIENCE,
            "iss": BE_ISSUER,
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,
        },
        _be_private_pem,
        algorithm="ES256",
        headers={"kid": BE_KID},
    )
    r = auth_client.get("/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_me_valid_token(auth_client: TestClient) -> None:
    token = make_jwt()
    r = auth_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == TEST_USER_ID
    assert data["email"] == TEST_EMAIL


def test_me_unknown_issuer_rejected(auth_client: TestClient) -> None:
    # 2c: registry 에 없는 iss → 401(Supabase default fallback 제거). 서명은 BE 키지만 iss 미등록.
    token = make_jwt(iss="https://evil.example.com/auth/v1")
    r = auth_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_me_missing_issuer_rejected(auth_client: TestClient) -> None:
    # 2c: iss 클레임 없는 토큰 → 401(registry 미매칭). fallback 제거로 iss 누락은 더 이상 허용 안 됨.
    token = make_jwt(iss=None)
    r = auth_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_me_wrong_audience_rejected(auth_client: TestClient) -> None:
    # 등록 iss + 잘못된 aud → 401(per-issuer aud 격리). iss 게이트 통과 후 aud 검증에서 거부.
    token = make_jwt(aud="authenticated")
    r = auth_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def _make_delete_client(
    *,
    secret_key: str,
    handler,
    conn: FakeConnection | None = None,
) -> TestClient:
    """DELETE /me 테스트용 클라이언트 — http_client/settings/auth override."""
    settings = Settings(
        supabase_url=TEST_SUPABASE_URL,
        supabase_secret_key=secret_key,
    )
    app = create_app(settings)

    async def mock_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=UUID(TEST_USER_ID), email=TEST_EMAIL, raw={})

    transport = httpx.MockTransport(handler)
    mock_http = httpx.AsyncClient(transport=transport)

    def override_http_client():
        return mock_http

    fake_pool = make_fake_pool(conn)

    app.dependency_overrides[get_current_user] = mock_user
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_http_client] = override_http_client
    app.dependency_overrides[get_pool] = lambda: fake_pool
    return TestClient(app)


def test_delete_me_no_auth(auth_client: TestClient) -> None:
    r = auth_client.delete("/me")
    assert r.status_code == 401


def test_delete_me_service_key_missing() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(204)

    client = _make_delete_client(secret_key="", handler=handler)
    r = client.delete("/me")
    assert r.status_code == 503
    assert "비활성화" in r.json()["error"]
    assert captured == []  # Supabase 호출 안 됨


def test_delete_me_success() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": TEST_USER_ID})

    client = _make_delete_client(secret_key="test-service-key", handler=handler)
    r = client.delete("/me")
    assert r.status_code == 204
    assert len(captured) == 1
    req = captured[0]
    assert req.method == "DELETE"
    assert str(req.url) == f"{TEST_SUPABASE_URL}/auth/v1/admin/users/{TEST_USER_ID}"
    assert req.headers["apikey"] == "test-service-key"
    assert req.headers["authorization"] == "Bearer test-service-key"


def test_delete_me_records_audit_with_reason() -> None:
    # 탈퇴 시 account_deletions 에 1건 INSERT(...SELECT) 후 users DELETE.
    # signup_at 은 SQL 내부(SELECT created_at)라 INSERT args 에 노출되지 않음 → 실DB 에서 검증.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": TEST_USER_ID})

    conn = _RecordingConn()
    client = _make_delete_client(
        secret_key="test-service-key", handler=handler, conn=conn
    )
    r = client.request("DELETE", "/me", json={"reason": "not_useful"})
    assert r.status_code == 204

    inserts = [q for q in conn.executed if "INSERT INTO public.account_deletions" in q[0]]
    assert len(inserts) == 1
    query, args = inserts[0]
    assert "SELECT id, created_at" in query  # INSERT ... SELECT (멱등 — 행 없으면 0건)
    assert args == (UUID(TEST_USER_ID), "not_useful")

    # 감사 INSERT 가 users DELETE 보다 먼저 실행됨.
    queries = [q[0] for q in conn.executed]
    insert_idx = next(i for i, q in enumerate(queries) if "account_deletions" in q)
    delete_idx = next(i for i, q in enumerate(queries) if "DELETE FROM public.users" in q)
    assert insert_idx < delete_idx


def test_delete_me_records_audit_without_reason() -> None:
    # 사유 미전송(바디 없음)도 204 + reason NULL 로 기록.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": TEST_USER_ID})

    conn = _RecordingConn()
    client = _make_delete_client(
        secret_key="test-service-key", handler=handler, conn=conn
    )
    r = client.delete("/me")
    assert r.status_code == 204

    inserts = [q for q in conn.executed if "INSERT INTO public.account_deletions" in q[0]]
    assert len(inserts) == 1
    _, args = inserts[0]
    assert args == (UUID(TEST_USER_ID), None)


def test_delete_me_rejects_invalid_reason() -> None:
    # reason 은 Literal 고정 코드값만 허용 — 임의 문자열은 422, DB 쓰기 없음(사유 분포 오염 차단).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": TEST_USER_ID})

    conn = _RecordingConn()
    client = _make_delete_client(
        secret_key="test-service-key", handler=handler, conn=conn
    )
    r = client.request("DELETE", "/me", json={"reason": "spam_garbage"})
    assert r.status_code == 422
    assert conn.executed == []


@pytest.mark.parametrize("status_code", [400, 401, 403, 500])
def test_delete_me_supabase_error_status(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "boom"})

    client = _make_delete_client(secret_key="test-service-key", handler=handler)
    r = client.delete("/me")
    assert r.status_code == 502
    assert "실패" in r.json()["error"]


def test_delete_me_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _make_delete_client(secret_key="test-service-key", handler=handler)
    r = client.delete("/me")
    assert r.status_code == 502
