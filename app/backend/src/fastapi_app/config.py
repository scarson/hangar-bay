from typing import Literal, Optional, Union


from pydantic.networks import PostgresDsn, AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator # Removed computed_field, added model_validator


class Settings(BaseSettings):
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    LOG_LEVEL: str = "INFO"

    # PostgreSQL specific settings (optional, for production/staging)
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_SERVER: Optional[str] = None  # e.g., localhost, or a remote server
    POSTGRES_DB: Optional[str] = None  # e.g., hangar_bay_db

    # SQLite specific settings (default for local development)
    SQLITE_DB_NAME: str = (
        "hangar_bay_dev.db"  # Will be created in the root of `app/backend/src/` or where app runs
    )

    # Cache settings
    CACHE_URL: str = "redis://localhost:6379/0"

    # ESI (EVE Swagger Interface) settings
    ESI_BASE_URL: str = "https://esi.evetech.net"
    ESI_USER_AGENT: str = "HangarBayApp/0.1.0 (contact@example.com; backend data aggregation)"
    ESI_CLIENT_ID: str = ""
    ESI_CLIENT_SECRET: str = ""

    # Background Aggregation Service settings
    AGGREGATION_SCHEDULER_INTERVAL_SECONDS: int = 900  # 15 minutes
    # The Forge, Domain, Heimatar, Metropolis, Sinq Laison
    AGGREGATION_REGION_IDS: list[int] = [10000002, 10000043, 10000030, 10000042, 10000032]

    DATABASE_URL: Optional[Union[PostgresDsn, AnyUrl]] = None # Will be loaded from .env if present

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @model_validator(mode="after")
    def set_database_url_if_not_provided(self) -> 'Settings':
        if self.DATABASE_URL is None: # If not set directly in .env
            if all(
                [
                    self.POSTGRES_USER,
                    self.POSTGRES_PASSWORD,
                    self.POSTGRES_SERVER,
                    self.POSTGRES_DB,
                ]
            ):
                self.DATABASE_URL = PostgresDsn.build(
                    scheme="postgresql+asyncpg",
                    username=self.POSTGRES_USER,
                    password=self.POSTGRES_PASSWORD,
                    host=self.POSTGRES_SERVER,
                    path=f"/{self.POSTGRES_DB}",
                )
            else:
                # Default to SQLite if no full DATABASE_URL or individual PG vars are provided
                self.DATABASE_URL = f"sqlite+aiosqlite:///./{self.SQLITE_DB_NAME}"
        return self


def get_settings() -> Settings:
    return Settings()
