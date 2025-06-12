from typing import List

from pydantic import Field, field_validator, version
from typing import Any # Import Any for type hinting in validator
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
    AGGREGATION_REGION_IDS: List[int] = Field(
        default_factory=lambda: [10000002], # Use default_factory for mutable default
        description="List of integer region IDs to scan for contracts. Parsed from env var."
    )

    # Database and Cache Configuration
    DATABASE_URL: str = Field(..., description="SQLAlchemy database connection string.")
    CACHE_URL: str = Field(..., description="Redis cache connection string.")

    @field_validator("AGGREGATION_REGION_IDS", mode="before")
    @classmethod
    def parse_aggregation_region_ids(cls, value: Any) -> List[int]:
        """Parses AGGREGATION_REGION_IDS from a comma-separated string or list of strings/ints to a list of ints."""
        # DEBUG: Validator for AGGREGATION_REGION_IDS - raw value
        print(f"VALIDATOR_AGG_IDS: Received raw value: {value!r} (type: {type(value)})", flush=True)
        if isinstance(value, str):
            if not value.strip():
                return []
            # Attempt to parse as JSON list first (e.g., "[10000002, 10000003]")
            if value.startswith('[') and value.endswith(']'):
                try:
                    import json
                    parsed_list = json.loads(value)
                    if not isinstance(parsed_list, list):
                        raise ValueError("JSON string did not parse to a list.")
                    # Ensure all elements are integers
                    int_list = [int(item) for item in parsed_list]
                    # DEBUG: Validator for AGGREGATION_REGION_IDS - parsed JSON string to list
                    print(f"VALIDATOR_AGG_IDS: Parsed JSON string to list: {int_list}. Returning.", flush=True)
                    return int_list
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    # DEBUG: Validator for AGGREGATION_REGION_IDS - JSON parsing failed, fallback to comma-separated
                    print(f"VALIDATOR_AGG_IDS: JSON parsing failed ('{e}'), falling back to comma-separated for: {value!r}", flush=True)
                    # Fall through to comma-separated parsing if JSON parsing fails or it's not a valid list of ints
            
            # Fallback to comma-separated string (e.g., "10000002,10000003")
            try:
                parsed_list = [int(rid.strip()) for rid in value.split(',') if rid.strip()]
                # DEBUG: Validator for AGGREGATION_REGION_IDS - parsed comma-separated string to list
                print(f"VALIDATOR_AGG_IDS: Parsed comma-separated string to list: {parsed_list}. Returning.", flush=True)
                return parsed_list
            except ValueError as e:
                raise ValueError(f"Invalid format for AGGREGATION_REGION_IDS. Could not parse '{value}' as comma-separated integers: {e}")
        elif isinstance(value, list):
            # If it's already a list, ensure all elements are integers (or can be converted)
            try:
                int_list = [int(item) for item in value]
                # DEBUG: Validator for AGGREGATION_REGION_IDS - received list (all ints)
                print(f"VALIDATOR_AGG_IDS: Received list (all ints): {int_list}. Returning as is.", flush=True)
                return int_list
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid list for AGGREGATION_REGION_IDS. All items must be convertible to integers: {e}")
        
        # DEBUG: Validator for AGGREGATION_REGION_IDS - unhandled type
        print(f"VALIDATOR_AGG_IDS: Unhandled type for value: {type(value)}. Raising ValueError.", flush=True)
        raise ValueError(
            f"AGGREGATION_REGION_IDS must be a comma-separated string of integers, a JSON string representing a list of integers, or a list of integers. Got: {type(value)}"
        )

    model_config = SettingsConfigDict(env_file="src/.env", env_file_encoding='utf-8')


# Instantiate settings
settings = Settings()
# DEBUG: Pydantic version check. Note: 'version' was imported from pydantic above.
print(f"PYDANTIC_VERSION_CHECK_PRINT: {version.VERSION}", flush=True)
# DEBUG: Global settings AGGREGATION_REGION_IDS value in config.py
print(f"CONFIG_PY_INIT_DEBUG: settings.AGGREGATION_REGION_IDS = {settings.AGGREGATION_REGION_IDS} (type: {type(settings.AGGREGATION_REGION_IDS)})", flush=True)
# DEBUG: Global settings object ID in config.py
print(f"CONFIG_PY_GLOBAL_SETTINGS_ID: id(settings)={id(settings)}, id(settings.AGGREGATION_REGION_IDS)={id(settings.AGGREGATION_REGION_IDS)}", flush=True)
