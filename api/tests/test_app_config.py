from fastapi.testclient import TestClient

from invest_note_api.config import Settings, get_settings
from invest_note_api.main import create_app

TEST_SUPABASE_URL = "https://test.supabase.co"


def _client(
    min_v: str = "",
    ios: str = "",
    android: str = "",
    be_auth_enabled: bool = False,
) -> TestClient:
    settings = Settings(
        supabase_url=TEST_SUPABASE_URL,
        min_supported_version=min_v,
        store_url_ios=ios,
        store_url_android=android,
        be_auth_enabled=be_auth_enabled,
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
    # ① 응답에 beAuthEnabled(camelCase) 키가 항상 포함된다(FE 공유 캐시 seam).
    assert "beAuthEnabled" in body


def test_app_config_unset_env_means_no_force():
    # env 미설정 → 빈 문자열. FE 가 빈 minSupportedVersion 을 no-force 로 해석한다.
    client = _client()
    r = client.get("/app-config")
    assert r.status_code == 200
    body = r.json()
    assert body["minSupportedVersion"] == ""
    assert body["storeUrl"] == {"ios": "", "android": ""}
    # ② be_auth_enabled default False → cutover dormant(네이티브도 Supabase flow 폴백).
    assert body["beAuthEnabled"] is False


def test_app_config_be_auth_enabled_toggle():
    # ③ env/Settings 로 토글하면 응답에 그대로 passthrough 된다(Coolify flip → cutover ON).
    client = _client(be_auth_enabled=True)
    r = client.get("/app-config")
    assert r.status_code == 200
    assert r.json()["beAuthEnabled"] is True


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


def test_startup_rejects_empty_quote_providers():
    # QUOTE_PROVIDERS="" 는 빈 체인 → 전 종목 시세가 조용히 null 이므로 부팅 시 fail-fast.
    import pytest

    settings = Settings(supabase_url=TEST_SUPABASE_URL, quote_providers="")
    app = create_app(settings)
    with pytest.raises(ValueError, match="quotes"):
        with TestClient(app):
            pass


def test_stock_search_provider_rejects_unknown_value():
    # 오타는 라우터 if/elif 가 조용히 naver 로 fallthrough 하므로 Settings 생성 시 fail-fast.
    import pytest

    with pytest.raises(ValueError, match="stock_search_provider"):
        Settings(supabase_url=TEST_SUPABASE_URL, stock_search_provider="dbb")


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


def test_kis_settings_explicit_values_and_env_normalized():
    # 명시 전달 값과 kis_env 정규화(공백/대소문자) 검증.
    # (.env.local 은 conftest 가 dotenv 소스를 꺼 테스트에 새지 않는다.)
    s = Settings(
        supabase_url=TEST_SUPABASE_URL, kis_app_key="", kis_app_secret="", kis_env=" MOCK "
    )
    assert s.kis_app_key == ""
    assert s.kis_app_secret == ""
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


# --- Phase 2a: BE 토큰 / issuer registry 설정 ---


def test_be_token_dormant_by_default():
    # 기본(BE signing key 빈 값) → BE 토큰 비활성. registry 에 BE entry 없음(dormant).
    # Supabase 분기(default)만 살아 있어 기존 인증 무영향.
    s = Settings(supabase_url=TEST_SUPABASE_URL)
    assert s.be_token_enabled is False
    assert s.oidc_issuer_registry == {}
    # Supabase default entry: oidc_issuer 빈 값 → issuer=None(iss 검증 스킵, Phase 1 동일).
    sup = s.supabase_issuer_entry
    assert sup["issuer"] is None
    assert sup["audience"] == "authenticated"
    assert sup["jwks_uri"] == f"{TEST_SUPABASE_URL}/auth/v1/.well-known/jwks.json"


def test_be_token_registry_entry_when_enabled():
    # signing key + issuer 설정 → registry 에 BE entry 등장(iss→{jwks_uri,issuer,audience}).
    s = Settings(
        supabase_url=TEST_SUPABASE_URL,
        be_token_signing_key="-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----",
        be_token_issuer="https://api.invest-note.example/be",
        be_token_audience="invest-note-app",
        be_token_kid="be-key-1",
    )
    assert s.be_token_enabled is True
    reg = s.oidc_issuer_registry
    assert "https://api.invest-note.example/be" in reg
    be = reg["https://api.invest-note.example/be"]
    assert be["jwks_uri"] == f"{TEST_SUPABASE_URL}/auth/.well-known/jwks.json"
    assert be["issuer"] == "https://api.invest-note.example/be"
    # per-issuer audience(P6): BE aud 는 authenticated 가 아닌 별도 값.
    assert be["audience"] == "invest-note-app"


def test_be_token_enabled_empty_audience_fails_fast():
    # B7: BE 활성(signing key 있음)인데 be_token_audience 빈 값이면 기동 실패.
    # (Phase 2a 의 "빈 aud → authenticated 폴백" 은 per-issuer aud 격리를 격하하므로 제거됨.)
    import pytest

    with pytest.raises(ValueError, match="be_token_audience"):
        Settings(
            supabase_url=TEST_SUPABASE_URL,
            be_token_signing_key="-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----",
            be_token_issuer="https://api.invest-note.example/be",
        )


def test_be_token_dormant_empty_audience_ok():
    # dormant(signing key 빈 값)는 be_token_audience 빈 값이어도 무영향 — fail-fast 대상 아님.
    s = Settings(supabase_url=TEST_SUPABASE_URL, be_token_audience="")
    assert s.be_token_enabled is False
    assert s.oidc_issuer_registry == {}


# --- Phase 2b-1: OAuth provider 설정 + redirect/딥링크 + TTL (B-1) ---


def test_oauth_provider_credentials_default_empty():
    # provider 자격증명 미설정 → 빈 값(부분 활성 허용). 미설정 provider 는 라우터에서
    # 명시 에러(B-6) — Settings 단계는 빈 값 허용.
    s = Settings(supabase_url=TEST_SUPABASE_URL)
    assert s.google_client_id == ""
    assert s.google_client_secret == ""
    assert s.kakao_client_id == ""
    assert s.kakao_client_secret == ""
    assert s.apple_client_id == ""
    assert s.apple_team_id == ""
    assert s.apple_key_id == ""
    assert s.apple_private_key == ""


def test_oauth_provider_credentials_load():
    s = Settings(
        supabase_url=TEST_SUPABASE_URL,
        google_client_id="g-id",
        google_client_secret="g-secret",
        kakao_client_id="k-rest-key",
        kakao_client_secret="k-secret",
        apple_client_id="com.pixelwave.investnote.service",
        apple_team_id="TEAM123",
        apple_key_id="KEY123",
        apple_private_key="-----BEGIN PRIVATE KEY-----\napple\n-----END PRIVATE KEY-----",
    )
    assert s.google_client_id == "g-id"
    assert s.kakao_client_id == "k-rest-key"
    assert s.apple_client_id == "com.pixelwave.investnote.service"
    assert s.apple_team_id == "TEAM123"
    assert s.apple_key_id == "KEY123"


def test_oauth_redirect_and_deeplink_defaults():
    s = Settings(supabase_url=TEST_SUPABASE_URL)
    assert s.be_oauth_redirect_base == ""
    # 딥링크 스킴은 고정 기본값(앱 custom scheme).
    assert s.be_deeplink_scheme == "app.pixelwave.investnote://auth/callback"


def test_oauth_ttl_defaults_and_override():
    s = Settings(supabase_url=TEST_SUPABASE_URL)
    assert s.be_refresh_token_ttl == 60 * 60 * 24 * 30  # 30d
    assert s.oauth_code_ttl == 60  # 일회용 code 단명
    assert s.oauth_state_ttl == 600  # state/PKCE challenge

    s2 = Settings(
        supabase_url=TEST_SUPABASE_URL,
        be_refresh_token_ttl=3600,
        oauth_code_ttl=30,
        oauth_state_ttl=300,
    )
    assert s2.be_refresh_token_ttl == 3600
    assert s2.oauth_code_ttl == 30
    assert s2.oauth_state_ttl == 300


def test_jwt_algorithms_covers_supabase_and_be_alg():
    # JWT_ALGORITHMS 가 Supabase 광고 alg(ES256/RS256) + BE alg(ES256) 둘 다 포함해야 한다 —
    # 한쪽 누락 시 해당 issuer 토큰이 조용히 거부(P5/P6 인접 함정). A1 실측 header alg 확정 시 재확인.
    from invest_note_api.auth.constants import JWT_ALGORITHMS

    assert "ES256" in JWT_ALGORITHMS  # BE 토큰 서명 alg
    assert "RS256" in JWT_ALGORITHMS  # Supabase RS256 키 호환
