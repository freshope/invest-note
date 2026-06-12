"""POST /live-update/manifest — OTA 매니페스트 결정 로직 회귀.

와이어 계약 SSOT: `_workspace/03_fe_changes.md`(플러그인 네이티브 소스 실측).
- 스큐/builtin 비교는 `version_build`(마케팅 버전)로 작성(추정 필드 금지).
- no-update 는 반드시 `{"kind":"up_to_date"}` — version/url 키 부재 단언(빈 200/204 회귀 가드).
"""
from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from invest_note_api.config import Settings, get_settings
from invest_note_api.external.http_client import get_http_client
from invest_note_api.main import create_app

TEST_SUPABASE_URL = "https://test.supabase.co"
MANIFEST_URL = "https://r2.example.com/manifest/latest.json"


def _client(manifest_handler, *, manifest_url: str = MANIFEST_URL) -> TestClient:
    """manifest GET 을 MockTransport 로 가로채는 테스트 클라이언트."""
    settings = Settings(
        supabase_url=TEST_SUPABASE_URL,
        live_update_manifest_url=manifest_url,
    )
    app = create_app(settings)

    transport = httpx.MockTransport(manifest_handler)
    mock_http = httpx.AsyncClient(transport=transport)

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_http_client] = lambda: mock_http
    return TestClient(app)


def _manifest(version: str, required_native: str) -> dict:
    return {
        "version": version,
        "url": f"https://r2.example.com/bundles/{version}.zip",
        "checksum": "a" * 64,
        "required_native_version": required_native,
    }


def _handler(manifest: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=manifest)

    return handler


def _post(client: TestClient, *, version_build: str, version_name: str) -> httpx.Response:
    return client.post(
        "/live-update/manifest",
        json={
            "platform": "ios",
            "device_id": "00000000-0000-0000-0000-000000000000",
            "app_id": "app.pixelwave.investnote",
            "custom_id": "",
            "version_build": version_build,
            "version_code": "42",
            "version_os": "17.0",
            "version_name": version_name,
            "plugin_version": "8.49.0",
            "is_emulator": False,
            "is_prod": True,
            "defaultChannel": "",  # 스키마 미정의 필드 — extra="ignore" 흡수 확인
        },
    )


# ① 정상 업데이트: published > installed.
def test_update_available_returns_version_url_checksum():
    client = _client(_handler(_manifest("1.2.0", required_native="1.0.0")))
    r = _post(client, version_build="1.1.0", version_name="1.1.0")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "1.2.0"
    assert body["url"] == "https://r2.example.com/bundles/1.2.0.zip"
    assert body["checksum"] == "a" * 64
    assert "kind" not in body


# ② 동일/구버전 → no-update.
def test_same_version_returns_no_update():
    client = _client(_handler(_manifest("1.1.0", required_native="1.0.0")))
    r = _post(client, version_build="1.1.0", version_name="1.1.0")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "up_to_date"
    assert "version" not in body and "url" not in body


def test_older_published_returns_no_update():
    client = _client(_handler(_manifest("1.0.0", required_native="1.0.0")))
    r = _post(client, version_build="1.1.0", version_name="1.1.0")
    assert r.status_code == 200
    assert r.json()["kind"] == "up_to_date"


# ③ 스큐 차단: required_native_version > version_build(기기 네이티브) → non-failure.
def test_skew_blocked_when_required_native_exceeds_version_build():
    # 새 번들(1.5.0)이 네이티브 2.0.0 을 요구하나 기기는 1.1.0 → 차단.
    client = _client(_handler(_manifest("1.5.0", required_native="2.0.0")))
    r = _post(client, version_build="1.1.0", version_name="1.1.0")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "up_to_date"  # non-failure
    assert "version" not in body and "url" not in body


# ④ builtin 신규설치: published == version_build → 중복 미반환.
def test_builtin_install_no_duplicate_when_published_equals_native():
    client = _client(_handler(_manifest("1.1.0", required_native="1.0.0")))
    r = _post(client, version_build="1.1.0", version_name="builtin")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "up_to_date"
    assert "version" not in body and "url" not in body


def test_builtin_install_returns_update_when_published_higher():
    # builtin(네이티브 1.1.0) 보다 발행본(1.2.0)이 높으면 업데이트 반환.
    client = _client(_handler(_manifest("1.2.0", required_native="1.0.0")))
    r = _post(client, version_build="1.1.0", version_name="builtin")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "1.2.0"


# ⑤ manifest 조회 실패 → fail-open(no-update).
def test_manifest_fetch_error_fails_open():
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client(boom)
    r = _post(client, version_build="1.1.0", version_name="1.1.0")
    assert r.status_code == 200
    assert r.json()["kind"] == "up_to_date"


def test_manifest_http_500_fails_open():
    def server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="oops")

    client = _client(server_error)
    r = _post(client, version_build="1.1.0", version_name="1.1.0")
    assert r.status_code == 200
    assert r.json()["kind"] == "up_to_date"


def test_manifest_malformed_json_fails_open():
    def bad(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    client = _client(bad)
    r = _post(client, version_build="1.1.0", version_name="1.1.0")
    assert r.status_code == 200
    assert r.json()["kind"] == "up_to_date"


# 빈 env → fail-open(조회 시도조차 안 함).
def test_empty_manifest_url_returns_no_update():
    client = _client(_handler(_manifest("9.9.9", required_native="1.0.0")), manifest_url="")
    r = _post(client, version_build="1.1.0", version_name="1.1.0")
    assert r.status_code == 200
    assert r.json()["kind"] == "up_to_date"


# ⑥ no-update 응답 회귀 가드: 인증 없이 접근 가능 + kind 존재 + version/url 부재.
def test_no_auth_required():
    client = _client(_handler(_manifest("1.1.0", required_native="1.0.0")))
    # Authorization 헤더 없이 200 + no-update 계약(kind 존재, version/url 부재 — 빈 200/204 아님).
    r = _post(client, version_build="1.1.0", version_name="1.1.0")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "up_to_date"
    assert "version" not in body and "url" not in body
