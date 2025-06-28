from typing import Literal, Optional, Union


from pydantic.networks import PostgresDsn, AnyUrl
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, field_validator # Removed computed_field, added model_validator
from typing import Any, List # For type hinting in validator


class Settings(BaseSettings):
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    LOG_LEVEL: str = "INFO"
    BASE_DIR: Path = Path(__file__).resolve().parent.parent # Points to app/backend/src/

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
    AGGREGATION_REGION_IDS: List[int] # Removed default value, now required from .env

    @field_validator("AGGREGATION_REGION_IDS", mode="before")
    @classmethod
    def parse_aggregation_region_ids(cls, v: Any) -> List[int]:
        print(f"VALIDATOR_AGG_IDS: Received raw value: '{v}' (type: {type(v)})")
        if isinstance(v, str):
            ids_str = v.strip().strip('[]').replace(" ", "")
            if not ids_str:
                print("VALIDATOR_AGG_IDS: Parsed to empty list from empty/bracket-only string.")
                return []
            try:
                parsed_list = [int(id_str) for id_str in ids_str.split(',') if id_str]
                print(f"VALIDATOR_AGG_IDS: Parsed string '{v}' to list: {parsed_list}")
                return parsed_list
            except ValueError as e:
                print(f"VALIDATOR_AGG_IDS_ERROR: Could not parse string '{v}': {e}")
                raise ValueError(f"Invalid format for AGGREGATION_REGION_IDS string: {v}") from e
        elif isinstance(v, list):
            if all(isinstance(item, int) for item in v):
                print(f"VALIDATOR_AGG_IDS: Received list (all ints): {v}. Returning as is.")
                return v
            else:
                try:
                    converted_list = [int(item) for item in v]
                    print(f"VALIDATOR_AGG_IDS: Converted list with non-ints {v} to: {converted_list}")
                    return converted_list
                except ValueError as e:
                    print(f"VALIDATOR_AGG_IDS_ERROR: Could not convert list elements {v} to int: {e}")
                    raise ValueError(f"Invalid list elements for AGGREGATION_REGION_IDS: {v}") from e
        
        print(f"VALIDATOR_AGG_IDS_ERROR: Unexpected type for AGGREGATION_REGION_IDS: {type(v)}. Value: '{v}'. Raising ValueError.")
        raise ValueError(f"Invalid type for AGGREGATION_REGION_IDS: {type(v)}. Expected string or list of (convertible) integers.")

    DATABASE_URL: Optional[Union[PostgresDsn, AnyUrl]] = None # Will be loaded from .env if present
    DATABASE_URL_TESTS: Optional[PostgresDsn] = None # For test environment
    CACHE_URL_TESTS: Optional[AnyUrl] = None # For test environment

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env", env_file_encoding="utf-8", extra="ignore"
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

settings = Settings()
print(f"CONFIG_PY_GLOBAL_SETTINGS_ID: id(settings)={id(settings)}, id(settings.AGGREGATION_REGION_IDS)={id(settings.AGGREGATION_REGION_IDS)}", flush=True)
print(f"CONFIG_PY_INIT_DEBUG: settings.AGGREGATION_REGION_IDS = {settings.AGGREGATION_REGION_IDS!r} (type: {type(settings.AGGREGATION_REGION_IDS)})", flush=True)
