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
    # SalesIntel has no sign-in: it answers only local hosts and loopback clients.
    allowed_hosts: str = "127.0.0.1,localhost,[::1],testserver"
    allow_remote_clients: bool = False
    # Identity. local: one person on this machine, no sign-in, loopback only.
    # oidc: a managed identity provider (Microsoft Entra ID, Auth0, Clerk, WorkOS...) issues signed tokens.
    # dev: locally signed tokens for automated tests and demos only; refused outside demo and test.
    auth_mode: Literal["local", "oidc", "dev"] = "local"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_algorithms: str = "RS256"
    dev_auth_key_file: str | None = None  # PEM private key for dev tokens; generated per run when unset
    # Provider profile: generic OIDC, or Microsoft Entra ID (multi-tenant issuer, tid and xms_edov claims).
    oidc_provider: Literal["generic", "entra"] = "generic"
    oidc_required_scope: str | None = None  # an API scope or app role the access token must carry
    oidc_allowed_tenants: str = ""  # Entra: comma-separated directory (tenant) ids allowed to sign in
    # Daily AI spending limits in US cents at provider list price. Unset: hosted 0 (off), local $10, demo/test $1.
    ai_daily_limit_cents_per_workspace: int | None = None
    ai_daily_limit_cents_per_user: int | None = None
    research_worker: Literal["inline", "off"] = "inline"  # off: run backend/scripts/research_worker.py separately
    research_lease_seconds: int = 120
    # Fetch a buyer's published procurement contact from the official notice when a workspace asks.
    navigator_fetch_published_notices: bool = False
    # Licensed contact-data providers, by registered name. Empty: none is called (Hunter and Apollo are evaluated, not integrated).
    contact_enrichment_providers: str = ""
    max_upload_bytes: int = 5 * 1024 * 1024
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_model: str = "gpt-6.1-terra"
    openai_request_timeout_seconds: float = 45
    research_provider: Literal["openai", "anthropic", "replay"] = "openai"  # replay: offline synthetic research, demo and test only
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

    def check_safe_to_serve(self) -> None:
        """Refuse configurations that would expose records or accept forged identities."""
        if self.auth_mode == "dev" and self.app_env not in {"demo", "test"}:
            raise RuntimeError("AUTH_MODE=dev signs its own tokens and is only allowed with APP_ENV=demo or test.")
        if self.auth_mode == "oidc":
            missing = [n for n in ("oidc_issuer", "oidc_audience", "oidc_jwks_url") if not getattr(self, n)]
            if missing:
                raise RuntimeError(f"AUTH_MODE=oidc needs {', '.join(m.upper() for m in missing)}.")
            if not self.oidc_jwks_url.startswith("https://"):
                raise RuntimeError("OIDC_JWKS_URL must use https.")
            if {a.strip() for a in self.oidc_algorithms.split(",")} - {"RS256", "RS384", "RS512", "ES256", "ES384", "PS256"}:
                raise RuntimeError("OIDC_ALGORITHMS must be asymmetric signature algorithms.")
        if self.research_provider == "replay" and self.app_env not in {"demo", "test"}:
            raise RuntimeError("RESEARCH_PROVIDER=replay serves synthetic research and is only allowed with APP_ENV=demo or test.")
        if self.auth_mode == "oidc" and self.database_url.startswith("sqlite"):
            raise RuntimeError("A hosted workspace needs PostgreSQL: row-level security is part of tenant isolation.")
        if self.auth_mode == "oidc" and self.oidc_provider == "entra" and "{tid}" in (self.oidc_issuer or "") and not self.oidc_allowed_tenants.strip():
            raise RuntimeError("A multi-tenant Entra issuer needs OIDC_ALLOWED_TENANTS: list the directories allowed to sign in.")
        if self.allow_remote_clients and self.auth_mode == "local":
            raise RuntimeError("ALLOW_REMOTE_CLIENTS requires sign-in (AUTH_MODE=oidc). A local install has no sign-in.")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def research_model(self) -> str:
        return self.openai_model if self.research_provider == "openai" else self.anthropic_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
