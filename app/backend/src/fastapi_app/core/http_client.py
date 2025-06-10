import httpx
from fastapi import FastAPI
from ..config import get_settings

settings = get_settings()

def init_http_client(app: FastAPI) -> None:
    """
    Initializes and attaches a shared httpx.AsyncClient to the application state.
    """
    headers = {
        "User-Agent": settings.ESI_USER_AGENT,
        "Accept-Language": "en",
        "accept": "application/json",
    }
    http_client = httpx.AsyncClient(
        base_url=settings.ESI_BASE_URL,
        headers=headers,
        timeout=15.0, # Sensible default timeout
    )
    app.state.http_client = http_client


async def close_http_client(app: FastAPI) -> None:
    """
    Closes the shared httpx.AsyncClient attached to the application state.
    """
    if hasattr(app.state, "http_client") and app.state.http_client:
        await app.state.http_client.aclose()
