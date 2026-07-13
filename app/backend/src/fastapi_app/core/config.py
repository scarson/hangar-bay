# ABOUTME: The single application Settings class + get_settings(); loads app/backend/src/.env.
# ABOUTME: Consolidates the former fastapi_app/config.py and core/config.py (ENV-1 trap).
from pathlib import Path
from typing import Any, List, Literal, Optional

from pydantic import Field, SecretStr, field_validator
from pydantic.networks import AnyUrl, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and app/backend/src/.env."""

    # General
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    LOG_LEVEL: str = "INFO"

    # ESI data API
    ESI_BASE_URL: str = "https://esi.evetech.net"
    ESI_USER_AGENT: str = Field(..., description="User-Agent header for ESI requests.")
    ESI_TIMEOUT: float = 20.0

    # EVE SSO (OAuth) — empty client id / cipher keys ⇒ SSO routes 503 "not configured"
    ESI_CLIENT_ID: str = ""
    ESI_CLIENT_SECRET: SecretStr = SecretStr("")
    ESI_SSO_AUTHORIZE_URL: str = "https://login.eveonline.com/v2/oauth/authorize"
    ESI_SSO_TOKEN_URL: str = "https://login.eveonline.com/v2/oauth/token"
    ESI_SSO_JWKS_URI: str = "https://login.eveonline.com/oauth/jwks"
    # Registered EVE callback — must match the dev-portal registration char-for-char.
    # Dev rides the Vite proxy over HTTPS; the proxy strips /api/v1 (PROXY-1, D-DELTA-1).
    ESI_SSO_CALLBACK_URL: str = "https://localhost:5173/api/v1/auth/sso/callback"
    FRONTEND_ORIGIN: str = "https://localhost:5173"

    # Server-side sessions + token vault
    SESSION_COOKIE_NAME: str = "hb_session"
    SESSION_IDLE_TTL_SECONDS: int = 604_800       # 7 days (sliding)
    SESSION_ABSOLUTE_TTL_SECONDS: int = 2_592_000  # 30 days (hard cap)
    TOKEN_CIPHER_KEYS: SecretStr = SecretStr("")   # comma-separated Fernet keys, first=primary

    # Aggregation
    AGGREGATION_SCHEDULER_INTERVAL_SECONDS: int = 3600
    AGGREGATION_REGION_IDS: List[int] = Field(default_factory=lambda: [10000002])
    AGGREGATION_DEV_CONTRACT_LIMIT: int | None = Field(  # DO NOT REMOVE UNLESS INSTRUCTED BY USER
        default=100,
        description="For dev, limit the number of contracts processed. Set to None or 0 to disable.",
    )

    # Database + cache
    DATABASE_URL: str = Field(..., description="SQLAlchemy database connection string.")
    CACHE_URL: str = Field(..., description="Redis/Valkey cache connection string.")
    DATABASE_URL_TESTS: Optional[PostgresDsn] = None   # conftest requires this
    CACHE_URL_TESTS: Optional[AnyUrl] = None

    @field_validator("AGGREGATION_REGION_IDS", mode="before")
    @classmethod
    def parse_aggregation_region_ids(cls, value: Any) -> List[int]:
        """Normalize AGGREGATION_REGION_IDS to a list of ints (ENV-1): env/dotenv sources
        JSON-decode complex fields before mode="before" validators run, so through real
        env sources only the JSON-list form reaches this code. The comma-separated-string
        and plain-list branches apply on direct construction (tests).
        """
        if isinstance(value, str):
            if not value.strip():
                return []
            if value.startswith("[") and value.endswith("]"):
                import json
                try:
                    return [int(item) for item in json.loads(value)]
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass  # fall through to comma-separated parsing
            return [int(rid.strip()) for rid in value.split(",") if rid.strip()]
        if isinstance(value, list):
            return [int(item) for item in value]
        raise ValueError(f"Invalid type for AGGREGATION_REGION_IDS: {type(value)}")

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",  # -> app/backend/src/.env
        env_file_encoding="utf-8",
        extra="ignore",  # unknown .env keys must not crash boot (token-cipher finding)
    )


settings = Settings()


def get_settings() -> Settings:
    """Return the process-wide Settings singleton (DI-friendly seam)."""
    return settings
