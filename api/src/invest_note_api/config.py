from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from invest_note_api.auth.constants import AUTH_ROLE

# 공급자 체인 기본값 — 단일 출처. 도메인 모듈(quotes/stock_seed)의 함수 기본 인자도
# 이 상수를 import 해 사용한다(Settings 기본 문자열과의 drift 방지).
DEFAULT_QUOTE_PROVIDERS = ("naver", "yahoo")
DEFAULT_STOCK_SEED_SOURCES = ("data_go_kr", "stock_prices", "securities")
# 해외(US) 공급자 기본값 — 현재 단일 출처지만 KR 과 동일한 registry/env 구조로 통일.
DEFAULT_US_QUOTE_PROVIDERS = ("yahoo",)
DEFAULT_US_STOCK_SEED_SOURCES = ("nasdaqtrader",)
# 환율(FX) 공급자 체인 — Yahoo 1순위, 실패 시 open.er-api.com(무인증) 폴백.
DEFAULT_FX_PROVIDERS = ("yahoo", "er_api")


class Settings(BaseSettings):
    supabase_url: str
    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://localhost:3000",
        "capacitor://localhost",
        "https://localhost",
        # 어드민 패널 dev 서버(별도 포트 3001, app 3000 과 분리). 운영 origin 은 Coolify env.
        "http://localhost:3001",
        "https://localhost:3001",
    ]
    database_url: str = ""
    supabase_secret_key: str = ""

    # 강제 업데이트: 빈 문자열이면 강제하지 않음(no-force). 양 플랫폼 공통 min 버전.
    min_supported_version: str = ""
    store_url_ios: str = ""
    store_url_android: str = ""

    # Capacitor OTA 라이브 업데이트: R2 의 발행 매니페스트 JSON 절대 URL.
    # 빈 값이면 /live-update/manifest 가 fail-open(no-update) 한다(앱 부팅 차단 금지).
    live_update_manifest_url: str = ""

    # 종목 마스터 적재(scripts/seed_stocks.py)용 공공데이터포털 인증키. 런타임 미사용 — batch 전용.
    # 빈 값이면 data.go.kr coverage pass 를 건너뛴다(다른 소스만 적재).
    data_go_kr_api_key: str = ""

    # KIS Open API(한국투자증권) 인증 정보. 빈 값이면 kis 공급자는 호출 시 토큰 발급에 실패한다.
    kis_app_key: str = ""
    kis_app_secret: str = ""

    # KIS 환경. "real"(실전) | "mock"(모의투자) — 도메인·TR ID prefix(T↔V) 분기에 사용.
    kis_env: str = "real"

    # 종목 검색(GET /stocks/search) provider. "naver" | "db".
    # "naver": Naver 자동완성 라이브 호출(external/naver_search.search_kr).
    # "db": 로컬 stocks 마스터 조회(data.go.kr seed). data.go.kr 모니터링 후 "db"로 복귀.
    stock_search_provider: str = "naver"

    # 시세(external/quotes.py) 공급자 우선순위 체인. 콤마 구분, 앞 항목부터 시도.
    # 등록 공급자: "naver"(realtime→basic 내부 fallback), "yahoo"(.KS→.KQ 내부 시도),
    # "kis"(국내주식 현재가 — KIS_APP_KEY/KIS_APP_SECRET 필요).
    quote_providers: str = ",".join(DEFAULT_QUOTE_PROVIDERS)

    # 해외(US) 시세 공급자 체인. 등록: "yahoo"(suffix 없는 bare 티커). KR 과 동일 fallback 구조.
    us_quote_providers: str = ",".join(DEFAULT_US_QUOTE_PROVIDERS)

    # 환율(FX, external/fx.py) 공급자 체인. 콤마 구분, 앞 항목부터 시도해 첫 성공값 사용.
    # 등록 공급자: "yahoo"({quote}=X chart), "er_api"(open.er-api.com, 무인증).
    fx_providers: str = ",".join(DEFAULT_FX_PROVIDERS)

    # 종목 마스터 seed(services/stock_seed.py) 소스 체인. 콤마 구분, 순서=우선순위.
    # 첫 번째로 데이터를 반환한 소스가 authority(종목명 overwrite), 나머지는 preserve.
    # 등록 소스: "data_go_kr", "stock_prices", "securities", "kis"(종목마스터 파일, 키 불필요).
    stock_seed_sources: str = ",".join(DEFAULT_STOCK_SEED_SOURCES)

    # 해외(US) 종목 마스터 seed(stock_seed.seed_us) 소스 체인. 등록: "nasdaqtrader"(공개 심볼 파일).
    us_stock_seed_sources: str = ",".join(DEFAULT_US_STOCK_SEED_SOURCES)

    # 일별 종가(services/daily_price_seed.py) primary 공급자. 등록: "data_go_kr", "kis".
    daily_price_provider: str = "data_go_kr"

    # 해외(US) 일별 종가 primary 공급자. 등록: "yahoo"(chart v8 range). US 는 T+1 gap 개념이 없어 gap 없음.
    us_daily_price_provider: str = "yahoo"

    # 일별 종가 T+1 tail-gap 보충 공급자. 등록: "naver", "kis"(T+0 반영).
    # "none" 또는 빈 값이면 보충 비활성.
    daily_price_gap_provider: str = "naver"

    # 종목 교차검증(services/stock_seed.py crossvalidate_stocks) 공급자.
    # 등록: "naver"(종목별 자동완성 조회), "kis"(종목마스터 파일 일괄 대조, 키 불필요).
    crossvalidate_provider: str = "naver"

    # NPS 보유내역 seed(services/nps_seed.py) 공급자. 등록: "odcloud".
    nps_provider: str = "odcloud"

    # 관리자 트리거 라우터(POST /admin/seed/*) 인증 토큰. X-Admin-Token 헤더와 constant-time 비교.
    # 빈 값이면 admin 엔드포인트는 항상 거부(미설정=차단).
    admin_token: str = ""

    # 어드민 패널(신규 /admin CRUD) allowlist — 쉼표구분 이메일. Supabase JWT email 클레임과
    # 정확 비교(admin_email_set property). 빈 값이면 어떤 계정도 require_admin 통과 못 함.
    admin_emails: str = ""

    # OIDC 토큰 검증 — IdP 교체 시 어댑터 seam. 현재 IdP=Supabase.
    # oidc_issuer: 빈 값이면 iss 검증을 스킵한다(fail-safe). 실제 Supabase iss 는
    # f"{supabase_url}/auth/v1" — 정확한 문자열 검증 후 prod 에서만 활성화한다.
    # 잘못 설정하면 전체 인증이 붕괴하므로 기본은 비활성(빈 값).
    oidc_issuer: str = ""
    # oidc_audience: 토큰 aud 클레임 기대값. 기본은 Supabase 컨벤션(authenticated).
    oidc_audience: str = AUTH_ROLE

    # BE 자체 토큰(Phase 2a) — token-broker 모델의 BE 발급 토큰 검증/서명 설정.
    # 2a 는 dormant: 클라이언트가 BE 토큰을 발급받지 않으며, 검증 경로만 추가(유닛 전용).
    # be_token_signing_key 가 빈 값이면 BE 토큰 발급/검증이 비활성(빈 JWKS) → Supabase 경로
    # 무영향. 실사용 발급(fail-fast)은 2b.
    # be_token_issuer: BE 발급 토큰 iss(Supabase iss 와 충돌하지 않는 고유 안정 문자열).
    be_token_issuer: str = ""
    # be_token_audience: BE 토큰 aud. Supabase(authenticated)와 반드시 구분(per-issuer aud).
    be_token_audience: str = ""
    # be_token_signing_key: ES256(EC P-256) private key PEM. env 로드(DB 저장 아님, 단일 키).
    be_token_signing_key: str = ""
    # be_token_kid: BE JWKS 의 kid(서명 토큰 header.kid 와 JWKS 항목을 잇는다).
    be_token_kid: str = ""

    # OAuth 중개(Phase 2b) — BE 가 IdP 와 직접 대화하기 위한 provider 별 client 자격증명.
    # 빈 값이면 해당 provider 는 /auth/login 시 명시 에러(부분 활성 허용 — 일부 provider 만 설정 가능).
    # Google: OIDC discovery. client_id/secret 한 쌍.
    google_client_id: str = ""
    google_client_secret: str = ""
    # Kakao: full OIDC 아님 → REST API key(=client_id) + admin/secret. /v2/user/me 로 userinfo.
    kakao_client_id: str = ""
    kakao_client_secret: str = ""
    # Apple: Service ID(=client_id) 재사용(sub 보존). client secret 은 team_id/key_id/private_key 로
    # 서명 JWT 를 BE 가 동적 생성한다(Authlib Apple 특정 — 범용 secret 아님).
    apple_client_id: str = ""
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key: str = ""

    # OAuth 중개 redirect/딥링크 설정.
    # be_oauth_redirect_base: BE 공개 호스트(https://api...) — IdP redirect_uri 는
    # {be_oauth_redirect_base}/auth/callback. ⚠️ be_jwks_uri 호스트 정정의 출처(B8): BE 자기
    # 검증은 in-process key 직접 주입이라 self-fetch 안 하지만, 외부 JWKS 엔드포인트 절대 URL 도
    # 이 호스트 기준이어야 한다(현재 be_jwks_uri 가 supabase_url 파생이라 placeholder).
    be_oauth_redirect_base: str = ""
    # be_deeplink_scheme: callback 이 일회용 code 를 실어 앱으로 돌려보내는 딥링크 URL.
    # IdP redirect_uri 가 아니라 BE→앱 최종 단계 전용(스킴 고정, 바뀌는 건 BE 뿐).
    be_deeplink_scheme: str = "app.pixelwave.investnote://auth/callback"

    # OAuth/refresh transient TTL(초). token_store 가 settings 에서 읽는다.
    # be_refresh_token_ttl: refresh token 수명(기본 30d). oauth_code_ttl: 일회용 code(딥링크↔
    # /auth/token, 기본 60s 단명). oauth_state_ttl: state/PKCE challenge(login↔callback, 기본 600s).
    be_refresh_token_ttl: int = 60 * 60 * 24 * 30
    oauth_code_ttl: int = 60
    oauth_state_ttl: int = 600

    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    # 공급자류 env 는 공백/대소문자를 정규화한다 — 운영 콘솔(Coolify)에서 "none "(후행 공백)·
    # "NONE" 같은 입력이 registry 미일치로 ValueError → 라우터 500 이 되는 것을 방지.
    # os.environ 값은 pydantic-settings 가 strip 하지 않으므로 여기서 처리해야 한다.
    @field_validator(
        "quote_providers",
        "us_quote_providers",
        "fx_providers",
        "stock_seed_sources",
        "us_stock_seed_sources",
        "daily_price_provider",
        "us_daily_price_provider",
        "daily_price_gap_provider",
        "crossvalidate_provider",
        "nps_provider",
    )
    @classmethod
    def _normalize_provider(cls, v: str) -> str:
        return v.strip().lower()

    # stock_search_provider 오타는 라우터 if/elif 가 조용히 naver 로 fallthrough 하므로
    # Settings 생성 시 fail-fast (kis_env 와 동일 패턴).
    @field_validator("stock_search_provider")
    @classmethod
    def _validate_stock_search_provider(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("naver", "db"):
            raise ValueError(
                f"stock_search_provider 는 'naver' 또는 'db' 여야 합니다 (입력: {v!r})"
            )
        return v

    # kis_env 오타는 잘못된 도메인 호출로 조용히 실패하므로 Settings 생성 시 fail-fast.
    @field_validator("kis_env")
    @classmethod
    def _validate_kis_env(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("real", "mock"):
            raise ValueError(f"kis_env 는 'real' 또는 'mock' 이어야 합니다 (입력: {v!r})")
        return v

    # B7 fail-fast: BE 토큰이 활성(signing key 있음)인데 be_token_audience 가 빈 값이면
    # per-issuer aud 격리가 Supabase authenticated 로 조용히 폴백돼 격하된다(인수노트#1).
    # → 활성 시 빈 aud 는 기동 실패. dormant(키 없음)는 무영향. field_validator 가 아니라
    # model_validator(after) 인 이유: 필드 정의 순서상 audience 검증 시점에 signing_key 가
    # 아직 info.data 에 없어 field 단위로는 교차 참조가 불가능하다.
    @model_validator(mode="after")
    def _validate_be_token_audience(self) -> "Settings":
        if self.be_token_enabled and not self.be_token_audience:
            raise ValueError(
                "be_token_signing_key 설정 시 be_token_audience 는 필수입니다 "
                "(빈 값이면 per-issuer aud 격리가 Supabase 'authenticated' 로 격하됨, B7)"
            )
        return self

    @property
    def jwks_uri(self) -> str:
        return f"{self.supabase_url}/auth/v1/.well-known/jwks.json"

    # BE 자체 토큰 검증용 JWKS URI(BE 가 스스로 서빙하는 /auth/.well-known/jwks.json).
    # registry 빌드 시 BE entry 의 jwks_uri 로 쓰인다. dormant 라 prod 도달성은 nominal.
    @property
    def be_jwks_uri(self) -> str:
        return f"{self.supabase_url}/auth/.well-known/jwks.json"

    # BE 토큰 발급/검증 활성 여부 — signing key 가 있어야만 활성(없으면 dormant).
    @property
    def be_token_enabled(self) -> bool:
        return bool(self.be_token_signing_key)

    # issuer registry — iss discriminator 기반 검증 설정.
    # ⚠️ dict-lookup-reject 아님(그건 dormant prod 에서 Supabase 토큰을 iss-miss 로 거부 →
    # 전원 lockout). 검증 분기(decode_oidc_jwt)는 **Supabase=default / BE=명시 매칭** 으로
    # 구현한다. 이 property 는 BE entry(있을 때만)를 iss→{jwks_uri,issuer,audience} 로 노출 →
    # decode_oidc_jwt 가 peek 한 iss 가 BE iss 와 정확히 일치하면 BE entry 선택, 아니면 Supabase.
    # Supabase entry 의 issuer 는 oidc_issuer(빈 값이면 iss 검증 스킵, Phase 1 동일).
    @property
    def oidc_issuer_registry(self) -> dict[str, dict[str, str]]:
        registry: dict[str, dict[str, str]] = {}
        if self.be_token_enabled and self.be_token_issuer:
            registry[self.be_token_issuer] = {
                "jwks_uri": self.be_jwks_uri,
                "issuer": self.be_token_issuer,
                # B7: be_token_enabled 면 be_token_audience 는 비어있을 수 없다(model_validator
                # 가 강제). per-issuer aud 격리를 위해 AUTH_ROLE 폴백을 두지 않는다.
                "audience": self.be_token_audience,
            }
        return registry

    # Supabase(default) issuer entry — registry 에서 BE iss 가 매칭되지 않은 모든 토큰의 검증 설정.
    @property
    def supabase_issuer_entry(self) -> dict[str, str | None]:
        return {
            "jwks_uri": self.jwks_uri,
            "issuer": self.oidc_issuer or None,
            "audience": self.oidc_audience or AUTH_ROLE,
        }

    # admin_emails(쉼표 문자열) → 정규화(소문자/trim) set. require_admin 이 email 클레임을
    # 동일 정규화 후 `in` 으로 정확 비교한다. raw 문자열 substring 매칭(함정)을 피하기 위해 set 화.
    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    # 콤마 체인 필드는 pydantic list[str](JSON 파싱)이 아니라 str + 파싱 property 로 처리.
    @property
    def quote_provider_list(self) -> list[str]:
        return [p.strip() for p in self.quote_providers.split(",") if p.strip()]

    @property
    def us_quote_provider_list(self) -> list[str]:
        return [p.strip() for p in self.us_quote_providers.split(",") if p.strip()]

    @property
    def fx_provider_list(self) -> list[str]:
        return [p.strip() for p in self.fx_providers.split(",") if p.strip()]

    @property
    def stock_seed_source_list(self) -> list[str]:
        return [s.strip() for s in self.stock_seed_sources.split(",") if s.strip()]

    @property
    def us_stock_seed_source_list(self) -> list[str]:
        return [s.strip() for s in self.us_stock_seed_sources.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
