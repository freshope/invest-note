import pytest
from fastapi.testclient import TestClient

from invest_note_api.config import Settings
from invest_note_api.main import create_app

CAPACITOR_ORIGINS = ["capacitor://localhost", "https://localhost"]


def test_default_cors_origins_includes_capacitor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    s = Settings()
    for origin in CAPACITOR_ORIGINS:
        assert origin in s.cors_origins


@pytest.fixture
def cors_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    settings = Settings(
        cors_origins=["http://localhost:3000", *CAPACITOR_ORIGINS],
    )
    return TestClient(create_app(settings))


@pytest.mark.parametrize("origin", CAPACITOR_ORIGINS)
def test_cors_preflight_allows_capacitor_origin(cors_client: TestClient, origin: str) -> None:
    r = cors_client.options(
        "/healthz",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == origin
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_rejects_unknown_origin(cors_client: TestClient) -> None:
    r = cors_client.options(
        "/healthz",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in r.headers


@pytest.mark.parametrize("origin", CAPACITOR_ORIGINS)
def test_cors_actual_request_allows_capacitor_origin(cors_client: TestClient, origin: str) -> None:
    r = cors_client.get("/healthz", headers={"Origin": origin})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == origin
