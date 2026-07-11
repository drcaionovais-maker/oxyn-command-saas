from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OXYN Command API"
    environment: str = "development"
    secret_key: str = "development-only-change-this-secret-key"
    database_url: str = "sqlite:///./oxyn.db"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    cors_origins: list[str] = ["http://localhost:3000"]
    bootstrap_admin_email: str = "admin@oxyn.health"
    bootstrap_admin_password: str = "ChangeMe123!"
    bootstrap_tenant_name: str = "OXYN Health Anest"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
