import time
from uuid import UUID

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from invest_note_api.auth.constants import AUTH_ROLE
from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.external.http_client import get_http_client
from invest_note_api.main import create_app
from tests.conftest import TEST_EMAIL, TEST_SUPABASE_URL, TEST_USER_ID, _kid, _private_key, make_jwt
from tests.fake_pool import make_fake_pool


def test_me_no_header(auth_client: TestClient) -> None:
    r = auth_client.get("/me")
    assert r.status_code == 401


def test_me_invalid_token(auth_client: TestClient) -> None:
    r = auth_client.get("/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401


def test_me_expired_token(auth_client: TestClient) -> None:
    expired = jwt.encode(
        {
            "sub": TEST_USER_ID,
            "email": TEST_EMAIL,
            "aud": AUTH_ROLE,
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,
        },
        _private_key,
        algorithm="ES256",
        headers={"kid": _kid},
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


def _make_delete_client(
    *,
    secret_key: str,
    handler,
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

    fake_pool = make_fake_pool()

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
