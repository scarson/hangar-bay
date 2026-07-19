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
    # Secure-by-default: an OMITTED ENVIRONMENT resolves to "production", never
    # "development" (P1). Every dev-only branch keyed on ENVIRONMENT == "development"
    # — the destructive create_db_tables recreate, SQL echo (db.py), the
    # cookie Secure flag (api/auth.py), and the SSO-unconfigured startup warning —
    # therefore takes its safe/off setting when the var is unset. .env.example
    # sets ENVIRONMENT=development, so copying it preserves the dev workflow.
    ENVIRONMENT: Literal["development", "production", "test"] = "production"
    LOG_LEVEL: str = "INFO"
    # When set, JSON logs are ALSO written to this file (one JSON object per line),
    # for shipping to Grafana Cloud Loki via the Alloy tailer (docker/alloy/config.alloy).
    LOG_FILE: str = ""
    # Fail-closed opt-in for the destructive dev-only drop_all/create_all recreate
    # cycle at startup (see main.create_db_tables). Requires BOTH this flag true
    # AND ENVIRONMENT == "development"; with ENVIRONMENT secure-by-default to
    # "production" (above), an unset environment never recreates even if this
    # flag was inherited/copied as true.
    DB_RECREATE_ON_STARTUP: bool = False

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

    # --- M3 account features ---
    # Per-user soft caps (best-effort count-checks, design §3.5).
    MAX_SAVED_SEARCHES_PER_USER: int = 100
    MAX_WATCHLIST_ITEMS_PER_USER: int = 200
    WATCHLIST_MATCH_INTERVAL_SECONDS: int = 900        # 15 min
    WATCHLIST_MATCH_LOCK_TTL_SECONDS: int = 900
    NOTIFICATION_RETENTION_DAYS: int = 90              # prune window (matcher §4.4 step 5)

    # Database + cache
    DATABASE_URL: str = Field(..., description="SQLAlchemy database connection string.")
    CACHE_URL: str = Field(..., description="Redis/Valkey cache connection string.")
    DATABASE_URL_TESTS: Optional[PostgresDsn] = None   # conftest requires this
    CACHE_URL_TESTS: Optional[AnyUrl] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url_driver(cls, value: Any) -> Any:
        """Render/most managed platforms inject postgresql:// URLs; the async engine and
        Alembic require the asyncpg driver scheme (design spec §4)."""
        if isinstance(value, str) and value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value[len("postgresql://"):]
        return value

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
