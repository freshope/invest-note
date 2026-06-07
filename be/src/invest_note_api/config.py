from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 공급자 체인 기본값 — 단일 출처. 도메인 모듈(quotes/stock_seed)의 함수 기본 인자도
# 이 상수를 import 해 사용한다(Settings 기본 문자열과의 drift 방지).
DEFAULT_QUOTE_PROVIDERS = ("naver", "yahoo")
DEFAULT_STOCK_SEED_SOURCES = ("data_go_kr", "stock_prices", "securities")


class Settings(BaseSettings):
    supabase_url: str
    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://localhost:3000",
        "capacitor://localhost",
        "https://localhost",
    ]
    database_url: str = ""
    supabase_secret_key: str = ""

    # 강제 업데이트: 빈 문자열이면 강제하지 않음(no-force). 양 플랫폼 공통 min 버전.
    min_supported_version: str = ""
    store_url_ios: str = ""
    store_url_android: str = ""

    # 종목 마스터 적재(scripts/seed_stocks.py)용 공공데이터포털 인증키. 런타임 미사용 — batch 전용.
    # 빈 값이면 data.go.kr coverage pass 를 건너뛴다(다른 소스만 적재).
    data_go_kr_api_key: str = ""

    # 종목 검색(GET /stocks/search) provider. "naver" | "db".
    # "naver": Naver 자동완성 라이브 호출(external/naver_search.search_kr).
    # "db": 로컬 stocks 마스터 조회(data.go.kr seed). data.go.kr 모니터링 후 "db"로 복귀.
    stock_search_provider: str = "naver"

    # 시세(external/quotes.py) 공급자 우선순위 체인. 콤마 구분, 앞 항목부터 시도.
    # 등록 공급자: "naver"(realtime→basic 내부 fallback), "yahoo"(.KS→.KQ 내부 시도).
    # 새 공급자(예: kis)를 registry 에 등록하면 env 변경만으로 활성화 가능.
    quote_providers: str = ",".join(DEFAULT_QUOTE_PROVIDERS)

    # 종목 마스터 seed(services/stock_seed.py) 소스 체인. 콤마 구분, 순서=우선순위.
    # 첫 번째로 데이터를 반환한 소스가 authority(종목명 overwrite), 나머지는 preserve.
    # 등록 소스: "data_go_kr", "stock_prices", "securities".
    stock_seed_sources: str = ",".join(DEFAULT_STOCK_SEED_SOURCES)

    # 일별 종가(services/daily_price_seed.py) primary 공급자. 등록: "data_go_kr".
    daily_price_provider: str = "data_go_kr"

    # 일별 종가 T+1 tail-gap 보충 공급자. 등록: "naver". "none" 또는 빈 값이면 보충 비활성.
    daily_price_gap_provider: str = "naver"

    # NPS 보유내역 seed(services/nps_seed.py) 공급자. 등록: "odcloud".
    nps_provider: str = "odcloud"

    # 관리자 트리거 라우터(POST /admin/seed/*) 인증 토큰. X-Admin-Token 헤더와 constant-time 비교.
    # 빈 값이면 admin 엔드포인트는 항상 거부(미설정=차단).
    admin_token: str = ""

    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    # 공급자류 env 는 공백/대소문자를 정규화한다 — 운영 콘솔(Coolify)에서 "none "(후행 공백)·
    # "NONE" 같은 입력이 registry 미일치로 ValueError → 라우터 500 이 되는 것을 방지.
    # os.environ 값은 pydantic-settings 가 strip 하지 않으므로 여기서 처리해야 한다.
    @field_validator(
        "stock_search_provider",
        "quote_providers",
        "stock_seed_sources",
        "daily_price_provider",
        "daily_price_gap_provider",
        "nps_provider",
    )
    @classmethod
    def _normalize_provider(cls, v: str) -> str:
        return v.strip().lower()

    @property
    def jwks_uri(self) -> str:
        return f"{self.supabase_url}/auth/v1/.well-known/jwks.json"

    # 콤마 체인 필드는 pydantic list[str](JSON 파싱)이 아니라 str + 파싱 property 로 처리.
    @property
    def quote_provider_list(self) -> list[str]:
        return [p.strip() for p in self.quote_providers.split(",") if p.strip()]

    @property
    def stock_seed_source_list(self) -> list[str]:
        return [s.strip() for s in self.stock_seed_sources.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
