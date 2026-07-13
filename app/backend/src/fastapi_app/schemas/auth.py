# ABOUTME: Pydantic response schemas for the auth routes — the SPA's only identity source.
from pydantic import BaseModel, ConfigDict


class CurrentUserSchema(BaseModel):
    character_id: int
    character_name: str

    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    """The FastAPI HTTPException / JSONResponse error body shape ({"detail": ...}),
    declared so the login/callback 400 and 503 responses carry their real JSON
    body in the OpenAPI contract instead of an empty one."""

    detail: str
