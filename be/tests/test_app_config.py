from fastapi.testclient import TestClient

from invest_note_api.config import Settings, get_settings
from invest_note_api.main import create_app

TEST_SUPABASE_URL = "https://test.supabase.co"


def _client(min_v: str = "", ios: str = "", android: str = "") -> TestClient:
    settings = Settings(
        supabase_url=TEST_SUPABASE_URL,
        min_supported_version=min_v,
        store_url_ios=ios,
        store_url_android=android,
    )
    app = create_app(settings)
    # 라우터는 Depends(get_settings)(lru_cache 싱글톤)로 해석하므로 override 필요.
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_app_config_maps_settings_to_response():
    client = _client(
        min_v="1.1.13",
        ios="https://apps.apple.com/app/id123",
        android="https://play.google.com/store/apps/details?id=app.pixelwave.investnote",
    )
    r = client.get("/app-config")
    assert r.status_code == 200
    body = r.json()
    assert body["minSupportedVersion"] == "1.1.13"
    assert body["storeUrl"]["ios"] == "https://apps.apple.com/app/id123"
    assert body["storeUrl"]["android"] == "https://play.google.com/store/apps/details?id=app.pixelwave.investnote"


def test_app_config_unset_env_means_no_force():
    # env 미설정 → 빈 문자열. FE 가 빈 minSupportedVersion 을 no-force 로 해석한다.
    client = _client()
    r = client.get("/app-config")
    assert r.status_code == 200
    body = r.json()
    assert body["minSupportedVersion"] == ""
    assert body["storeUrl"] == {"ios": "", "android": ""}


def test_app_config_requires_no_auth():
    client = _client(min_v="1.0.0")
    # Authorization 헤더 없이 접근 가능해야 한다(로그인 전 사용자 차단 목적).
    r = client.get("/app-config")
    assert r.status_code == 200
