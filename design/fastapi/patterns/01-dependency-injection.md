# Pattern: Dependency Management in Hybrid Contexts

**Last Updated:** 2025-06-12
**Related Design Log Entry:** [2025-06-12 08:29:39-05:00: Architectural Pattern for Dependency Management in Hybrid Contexts](..\..\meta\design-log.md#2025-06-12-082939-0500-architectural-pattern-for-dependency-management-in-hybrid-contexts)

## 1. Context & Objective

The Hangar Bay backend operates in two primary execution contexts:

1.  **Synchronous API Requests:** Handled by FastAPI's request-response lifecycle.
2.  **Asynchronous Background Jobs:** Managed by APScheduler, often running in separate processes.

A critical `PicklingError` during background job execution highlighted the need for a distinct dependency management strategy that caters to both contexts, especially for non-picklable resources like cache (`aioredis.Redis`) or database (`AsyncSession`) clients.

The objective of this pattern is to define a clear, robust, and non-negotiable approach for managing dependencies to ensure application stability and prevent `PicklingError` issues.

## 2. The Dual Pattern

### 2.1. FastAPI Request-Response Context (Default Pattern)

*   **Pattern Name:** Standard FastAPI Dependency Injection.
*   **Mechanism:**
    *   Utilize FastAPI's built-in dependency injection system (`Depends`).
    *   Dependency provider functions (e.g., `get_db` in `core/dependencies.py`, `get_cache` in `core/dependencies.py`) are responsible for creating, yielding, and properly closing/releasing resources.
    *   FastAPI manages the lifecycle of these resources, making them available for the duration of a request.
*   **When to Use:** This is the **default and preferred** method for all standard API endpoints (e.g., functions decorated with `@router.get`, `@router.post`, etc.) and any components that are solely part of the FastAPI request-response lifecycle.
*   **Example Snippet (Conceptual):**
    ```python
    # In an API route
    from fastapi import APIRouter, Depends
    from sqlalchemy.ext.asyncio import AsyncSession
    from ..core.dependencies import get_db

    router = APIRouter()

    @router.get("/items/")
    async def read_items(db: AsyncSession = Depends(get_db)):
        # Use the db session
        pass
    ```

### 2.2. APScheduler Background Job Context (Exception Pattern)

*   **Pattern Name:** Dynamic Resource Instantiation.
*   **Problem Solved:** Objects passed to background jobs running in separate processes (the default for `ProcessPoolExecutor` in APScheduler) *must* be serializable (picklable). Live resource clients (e.g., `aioredis.Redis`, `httpx.AsyncClient`, `AsyncSession`) are generally **not picklable**.
*   **Mechanism:**
    1.  **Picklable Inputs Only:** Services or classes intended for use in background jobs (e.g., `ContractAggregationService`, `ESIClient`) **must not** accept live, non-picklable resource clients in their `__init__` methods.
    2.  **Configuration via `Settings`:** Instead, these components should be initialized with picklable configuration. The primary and preferred way to do this is by passing the Pydantic `Settings` object (from `core.config.settings`).
    3.  **On-Demand Creation:** Within the specific method that is executed as the background job (or methods called by it), the required non-picklable resource is created, used, and properly closed/cleaned up *dynamically within that method's scope*.
*   **When to Use:** This pattern is **mandatory** for any service or function that will be:
    *   Called directly by APScheduler as a job.
    *   Instantiated or used by code that runs within an APScheduler job in a separate process.
*   **Rationale:** This ensures that no non-picklable objects are attempted to be passed across process boundaries, thus preventing `PicklingError`.
*   **Example Snippet (`ESIClient` needing `httpx.AsyncClient` and `aioredis.Redis`):

    ```python
    # In core.esi_client_class.py (simplified)
    from ..core.config import Settings
    import httpx
    import redis.asyncio as aioredis

    class ESIClient:
        def __init__(self, settings: Settings):
            self.settings = settings
            # DO NOT initialize self.http_client or self.redis_client here

        async def get_public_contracts(self, region_id: int):
            # Dynamic instantiation of httpx client
            async with httpx.AsyncClient(base_url=self.settings.ESI_BASE_URL, headers=self.settings.ESI_HEADERS) as client:
                # ... logic using client ...
                response = await client.get(f"/latest/contracts/public/{region_id}/")
                # ... process response ...
                return response.json()

        async def get_cached_data(self, key: str):
            # Dynamic instantiation of Redis client
            redis = await aioredis.from_url(str(self.settings.CACHE_URL))
            try:
                cached = await redis.get(key)
                return cached
            finally:
                await redis.close()
    ```

## 3. Decision Flow & Implications

*   **Critical Question:** When designing or refactoring any service or utility: "Will this code, or any instance of this class, ever be executed as part of a background job running in a separate process?"
    *   **If YES:** The "Dynamic Resource Instantiation" pattern (2.2) **must** be followed for handling non-picklable resources.
    *   **If NO:** The standard FastAPI Dependency Injection pattern (2.1) should be used.
*   **Architectural Rigidity:** This dual-pattern approach is a firm architectural decision. Adherence is critical to prevent regressions and ensure the stability of background processing.
*   **Avoiding Anti-Patterns:** Never attempt to pass a non-picklable object (like a Redis client obtained from `Depends(get_cache)`) as an argument to a service that will be used in a background job.

## 4. Benefits

*   **Prevents `PicklingError`:** Directly addresses the root cause of serialization failures in background jobs.
*   **Clear Separation of Concerns:** Distinguishes between resource management in short-lived API requests vs. potentially long-running background tasks.
*   **Improved Testability:** Services designed with dynamic resource instantiation can be easier to test in isolation, as their resource dependencies are managed internally or can be mocked via settings.
*   **Architectural Stability:** Provides a non-negotiable rule, reducing architectural drift and refactoring churn related to dependency management.
