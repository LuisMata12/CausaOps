from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    causaops_api_url: str = "http://localhost:8000"
    service_name: str = "demo-payments"
    environment: str = "development"
    stable_delay_seconds: float = 0.05
    timeout_delay_seconds: float = 2.5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

