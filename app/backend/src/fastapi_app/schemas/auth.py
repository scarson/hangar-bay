# ABOUTME: Pydantic response schema for GET /me — the SPA's only identity source.
from pydantic import BaseModel, ConfigDict


class CurrentUserSchema(BaseModel):
    character_id: int
    character_name: str

    model_config = ConfigDict(from_attributes=True)
