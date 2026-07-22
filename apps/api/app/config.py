from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CausaOps API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://causaops:causaops_local@localhost:5432/causaops"
    cors_origins_raw: str = Field(
        default="http://localhost:3000",
        validation_alias="CORS_ORIGINS",
    )
    detection_window_minutes: int = 5
    detection_interval_seconds: int = 30
    minimum_request_count: int = 5
    error_rate_threshold: float = 0.10
    latency_p95_threshold_ms: int = 2000
    health_check_failure_threshold: int = 3
    deployment_correlation_minutes: int = 15

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
