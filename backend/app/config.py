from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    app_name: str = "SalesIntel API"
    app_version: str = "0.1.0"
    app_env: str = "local"
    database_url: str = "sqlite:///./misi.db"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_upload_bytes: int = 5 * 1024 * 1024
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_model: str = "gpt-6.1-terra"
    openai_request_timeout_seconds: float = 45
    research_provider: Literal["openai", "anthropic"] = "openai"
    anthropic_api_key: str | None = Field(default=None, repr=False)
    anthropic_model: str = "claude-sonnet-4-6"
    companies_house_api_key: str | None = Field(default=None, repr=False)
    rightclick_x_url: str | None = None
    rightclick_x_token: str | None = Field(default=None, repr=False)

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("openai_api_key", "anthropic_api_key", "companies_house_api_key", mode="before")
    @classmethod
    def blank_openai_key_is_none(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value

    @field_validator("openai_model", "anthropic_model")
    @classmethod
    def model_name_must_be_set(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Model name must not be blank.")
        return value.strip()

    @field_validator("cors_origins")
    @classmethod
    def cors_origins_must_be_explicit(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS must contain at least one explicit origin.")
        if "*" in origins:
            raise ValueError("CORS_ORIGINS must not use a wildcard origin.")
        return ",".join(origins)

    @field_validator("max_upload_bytes")
    @classmethod
    def max_upload_bytes_must_be_reasonable(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_UPLOAD_BYTES must be greater than zero.")
        if value > 25 * 1024 * 1024:
            raise ValueError("MAX_UPLOAD_BYTES must not exceed 25MB.")
        return value

    @field_validator("openai_request_timeout_seconds")
    @classmethod
    def openai_timeout_must_be_reasonable(cls, value: float) -> float:
        if value < 5:
            raise ValueError("OPENAI_REQUEST_TIMEOUT_SECONDS must be at least 5 seconds.")
        if value > 120:
            raise ValueError("OPENAI_REQUEST_TIMEOUT_SECONDS must not exceed 120 seconds.")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def research_model(self) -> str:
        return self.openai_model if self.research_provider == "openai" else self.anthropic_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
