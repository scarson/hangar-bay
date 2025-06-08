from fastapi import FastAPI
from .config import get_settings

settings = get_settings()

app = FastAPI(
    title="Hangar Bay API",
    description="API for the Hangar Bay application, providing access to EVE Online public contract data and related services.",
    version="0.1.0",
    # Additional OpenAPI metadata can be added here
    # See: https://fastapi.tiangolo.com/tutorial/metadata/
)


@app.get("/")
async def read_root():
    return {
        "message": f"Welcome to Hangar Bay API - {settings.ENVIRONMENT} environment"
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Further application setup, routers, middleware, etc., will go here
