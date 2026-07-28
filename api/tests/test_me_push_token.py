"""POST /v1/me/push-token 테스트 — 토큰 upsert(204) + 검증(422). (Phase 2)

실DB 미사용: get_current_user override + FakePool/FakeConnection. upsert 는 execute no-op.
"""
from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.main import create_app

from .fake_pool import FakeConnection, FakePool

USER_ID = UUID("11111111-1111-1111-1111-111111111111")


def _client(*, pool=...) -> TestClient:
    settings = Settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings

    async def mock_user() -> AuthenticatedUser:
        return AuthenticatedUser(id=USER_ID, email="u@example.com", raw={})

    app.dependency_overrides[get_current_user] = mock_user
    if pool is not ...:
        app.dependency_overrides[get_pool] = lambda: pool
    return TestClient(app)


def test_push_token_upsert_204():
    conn = FakeConnection()  # upsert execute → no-op
    client = _client(pool=FakePool(conn))
    resp = client.post("/v1/me/push-token", json={"token": "abc123", "platform": "ios"})
    assert resp.status_code == 204


def test_push_token_android_204():
    conn = FakeConnection()
    client = _client(pool=FakePool(conn))
    resp = client.post(
        "/v1/me/push-token", json={"token": "def456", "platform": "android"}
    )
    assert resp.status_code == 204


def test_push_token_invalid_platform_422():
    client = _client(pool=FakePool())
    resp = client.post("/v1/me/push-token", json={"token": "x", "platform": "web"})
    assert resp.status_code == 422


def test_push_token_missing_token_422():
    client = _client(pool=FakePool())
    assert client.post("/v1/me/push-token", json={"platform": "ios"}).status_code == 422


def test_push_token_extra_field_422():
    client = _client(pool=FakePool())
    resp = client.post(
        "/v1/me/push-token", json={"token": "x", "platform": "ios", "foo": "bar"}
    )
    assert resp.status_code == 422
