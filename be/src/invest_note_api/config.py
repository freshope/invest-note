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

    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    @property
    def jwks_uri(self) -> str:
        return f"{self.supabase_url}/auth/v1/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
