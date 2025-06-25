# Pattern: Dual-Mode Service for Background Jobs

## 1. Context and Problem

A critical challenge in an architecture that uses `apscheduler` for background tasks is that the scheduler requires jobs (and their dependencies) to be *picklable*. However, high-performance services often rely on unpicklable resources like database connections or HTTP clients, which are typically managed as long-lived, shared resources for API endpoints.

Injecting a shared `httpx.AsyncClient` into a service that is then passed to a scheduler will result in a `TypeError: can't pickle...` on application startup, preventing the scheduler from storing the job.

## 2. Solution: The Dual-Mode Service Pattern

The solution is to design the service to operate in two distinct modes, allowing it to be both picklable for background jobs and high-performance for API requests. The `ESIClient` is the canonical example.

### Mode 1: API Request (High-Performance)

-   **Context**: Used within a standard FastAPI endpoint.
-   **Instantiation**: The service is instantiated by a dependency provider (e.g., `get_esi_client`) which injects shared, long-lived `httpx` and `redis` clients from the application state (`app.state`).
-   **Benefit**: Maximum performance by reusing existing connections across many API requests.

### Mode 2: Background Job (Picklable)

-   **Context**: Used by a service that will be passed to `apscheduler` (e.g., `ContractAggregationService`).
-   **Instantiation**: The service is initialized with **only** picklable objects, such as the `Settings` configuration. The `http_client` and `redis_client` arguments are left as `None`. This makes the service instance itself picklable.
-   **Execution**: The service must implement the **async context manager** protocol (`__aenter__`, `__aexit__`). Inside the background job's execution logic, the service is used in an `async with` block.
    -   This triggers the `__aenter__` method, which creates **temporary, on-demand** clients for the duration of the job.
    -   The `__aexit__` method ensures these clients are properly closed afterward, preventing resource leaks.

### 3. Implementation Example (`ESIClient`)

```python
# In esi_client_class.py

class ESIClient:
    def __init__(
        self,
        settings: Settings,
        http_client: Optional[httpx.AsyncClient] = None, # Optional for pickling
        redis_client: Optional[aioredis.Redis] = None,   # Optional for pickling
    ):
        self.settings = settings
        self._http_client = http_client
        self._redis_client = redis_client
        self._managed_http_client: Optional[httpx.AsyncClient] = None
        self._managed_redis_client: Optional[aioredis.Redis] = None

    # ... properties to get the correct client ...

    async def __aenter__(self):
        """Initializes clients if they were not provided during instantiation."""
        if not self._http_client:
            self._managed_http_client = httpx.AsyncClient(...)
        if not self._redis_client:
            self._managed_redis_client = aioredis.from_url(...)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes clients that were created by the context manager."""
        if self._managed_http_client:
            await self._managed_http_client.aclose()
        if self._managed_redis_client:
            await self._managed_redis_client.close()
```

This pattern provides the best of both worlds: high performance for API endpoints and safe, picklable services for background processing.
