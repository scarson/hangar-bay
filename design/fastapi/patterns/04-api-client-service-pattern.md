---
description: Defines the standard pattern for creating services that act as clients to external APIs.
---

# Pattern: API Client Service

## 1. Context

When our backend needs to communicate with an external REST API (like the EVE ESI API), we must do so in a way that is efficient, maintainable, and easy to test. Creating new HTTP connections for every single request is highly inefficient and can lead to performance degradation and potential resource exhaustion.

This pattern establishes a standardized way to create service classes that encapsulate external API interactions.

## 2. The Pattern

An API Client Service MUST adhere to the following principles:

- **Single, Shared Client:** The service class must create and manage a single, long-lived `httpx.AsyncClient` instance.
- **Lifecycle Management:** The client should be initialized when the service is used as a context manager (i.e., via `async with`). The `__aenter__` method should create the client, and the `__aexit__` method must ensure it is closed.
- **Shared Instance Usage:** All public and private methods within the service that make HTTP requests MUST use the shared client instance (e.g., `self.http_client`).
- **Dependency Injection:** The service should receive its dependencies, like `settings`, via its `__init__` method.

## 3. Example Implementation

This shows a simplified but complete example adhering to the pattern.

```python
import httpx
import logging
from types import TracebackType
from typing import Optional, Type

logger = logging.getLogger(__name__)

class ExternalServiceClient:
    """
    Manages interaction with an external API, reusing a single httpx.AsyncClient.
    """
    def __init__(self, settings):
        self.base_url = settings.EXTERNAL_API_URL
        self.headers = {"User-Agent": settings.USER_AGENT}
        self.http_client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "ExternalServiceClient":
        """Initializes the shared httpx.AsyncClient.
        Allows the class to be used as an async context manager.
        """
        self.http_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=30.0
        )
        logger.info("ExternalServiceClient http_client entered.")
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Closes the shared httpx.AsyncClient.
        Ensures cleanup when the context is exited.
        """
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
            logger.info("ExternalServiceClient http_client exited.")

    async def get_some_data(self, item_id: int) -> dict:
        """Example method that uses the shared client.

        This is the CORRECT way to implement a method.
        """
        if not self.http_client:
            raise RuntimeError("HTTP client not available. Use within an 'async with' block.")

        response = await self.http_client.get(f"/items/{item_id}")
        response.raise_for_status()
        return response.json()

    async def do_not_do_this(self, item_id: int):
        """Example of the ANTI-PATTERN.

        DO NOT create a new client inside a method. This is inefficient.
        """
        # ANTI-PATTERN: Do not do this!
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            response = await client.get(f"/items/{item_id}")
            return response.json()

```
