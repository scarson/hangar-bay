from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # General App Configuration
    ENVIRONMENT: str = "development"

    # ESI Configuration
    ESI_BASE_URL: str = "https://esi.evetech.net/latest"
    ESI_USER_AGENT: str = Field(..., description="User-Agent header for ESI requests.")

    # Aggregation Service Configuration
    AGGREGATION_SCHEDULER_INTERVAL_SECONDS: int = 3600
    AGGREGATION_REGION_IDS: str = Field(
        "10000002", 
        description="Comma-separated string of region IDs to scan for contracts."
    )

    # Database and Cache Configuration
    DATABASE_URL: str = Field(..., description="SQLAlchemy database connection string.")
    CACHE_URL: str = Field(..., description="Redis cache connection string.")

    @property
    def region_ids_list(self) -> List[int]:
        """Returns a list of integer region IDs."""
        return [int(rid.strip()) for rid in self.AGGREGATION_REGION_IDS.split(',')]

    model_config = SettingsConfigDict(env_file="src/.env", env_file_encoding='utf-8')


# Instantiate settings
settings = Settings()
