from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    @property
    def jwks_uri(self) -> str:
        return f"{self.supabase_url}/auth/v1/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
