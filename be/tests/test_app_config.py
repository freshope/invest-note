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


def test_startup_rejects_unknown_quote_provider():
    # QUOTE_PROVIDERS 오타는 요청 경로에서 조용히 null 시세가 되므로 부팅 시 fail-fast 해야 한다.
    import pytest

    settings = Settings(supabase_url=TEST_SUPABASE_URL, quote_providers="naverr")
    app = create_app(settings)
    with pytest.raises(ValueError, match="quotes"):
        with TestClient(app):  # with 블록이 lifespan(startup) 실행
            pass


def test_provider_env_values_normalized():
    # 운영 콘솔의 공백/대소문자 입력("none ", "NONE")이 registry 미일치 ValueError 로
    # 라우터 500 을 내지 않도록 공급자류 env 는 strip+lower 정규화된다.
    s = Settings(
        supabase_url=TEST_SUPABASE_URL,
        stock_search_provider=" DB ",
        quote_providers=" Naver,Yahoo ",
        daily_price_provider=" DATA_GO_KR ",
        daily_price_gap_provider=" NONE ",
        nps_provider=" Odcloud ",
    )
    assert s.stock_search_provider == "db"
    assert s.quote_provider_list == ["naver", "yahoo"]
    assert s.daily_price_provider == "data_go_kr"
    assert s.daily_price_gap_provider == "none"
    assert s.nps_provider == "odcloud"


def test_kis_settings_defaults_and_env_normalized():
    # 기본값: 키 미설정(빈 값) + 실전 환경. kis_env 는 공백/대소문자 정규화.
    s = Settings(supabase_url=TEST_SUPABASE_URL)
    assert s.kis_app_key == ""
    assert s.kis_app_secret == ""
    assert s.kis_env == "real"

    s = Settings(supabase_url=TEST_SUPABASE_URL, kis_env=" MOCK ")
    assert s.kis_env == "mock"


def test_kis_env_rejects_unknown_value():
    # kis_env 오타는 잘못된 도메인 호출로 조용히 실패하므로 Settings 생성 시 fail-fast.
    import pytest

    with pytest.raises(ValueError, match="kis_env"):
        Settings(supabase_url=TEST_SUPABASE_URL, kis_env="prod")


def test_provider_list_properties_default_and_parse():
    # 콤마 체인 env(str 필드)는 property 가 trim + 빈 항목 제거로 파싱한다.
    s = Settings(supabase_url=TEST_SUPABASE_URL)
    assert s.quote_provider_list == ["naver", "yahoo"]
    assert s.stock_seed_source_list == ["data_go_kr", "stock_prices", "securities"]

    s = Settings(
        supabase_url=TEST_SUPABASE_URL,
        quote_providers=" yahoo , naver ,",
        stock_seed_sources="securities",
    )
    assert s.quote_provider_list == ["yahoo", "naver"]
    assert s.stock_seed_source_list == ["securities"]
