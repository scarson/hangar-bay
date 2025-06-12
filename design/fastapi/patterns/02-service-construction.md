# Pattern: Service Construction - Configuration over Live Resources

**Last Updated:** 2025-06-12
**Related Design Log Entry:** [2025-06-12 08:31:00-05:00: Service Architecture: Self-Contained vs. Injected Resources](..\..\meta\design-log.md#2025-06-12-083100-0500-service-architecture-self-contained-vs-injected-resources)

## 1. Context & Objective

To establish a consistent, robust, and maintainable approach for instantiating service-layer classes (e.g., `ESIClient`, `ContractAggregationService`) within the Hangar Bay backend. This pattern aims to prevent cyclical refactoring (e.g., confusion over whether to pass full `Settings` objects vs. individual pre-instantiated resources like database sessions) and ensure services are designed for flexibility, testability, and compatibility with different execution contexts (API requests vs. background jobs).

## 2. The Pattern: Initialize with Configuration, Acquire Resources On-Demand

### 2.1. Core Principle: Services are Self-Sufficient Units

A service is viewed as a component responsible for a specific domain of business logic. It should be self-sufficient in terms of acquiring the resources it needs, guided by configuration.

### 2.2. Initialization with Configuration (Primarily `Settings`)

*   **Decision:** Service classes **must** be initialized with *configuration* rather than live, stateful resource instances (e.g., an active database session or a connected cache client).
*   **Primary Configuration Object:** The main piece of configuration to be passed to a service's `__init__` method is the global Pydantic `Settings` object (from `core.config.settings`).
*   **Rationale:**
    *   **Decoupling:** Separates the service's business logic from the complexities of resource lifecycle management. The service doesn't need to know *how* a database session or cache client is created and managed globally, only *that* it needs one and has the configuration to obtain it.
    *   **Flexibility & Testability:** Makes it significantly easier to instantiate services in test environments. A mock or test-specific `Settings` object can be passed, or specific settings can be overridden, without needing to mock complex live resource objects.
    *   **Pickle Safety (Crucial for Background Jobs):** The Pydantic `Settings` object is picklable. As detailed in the "Dependency Management in Hybrid Contexts" pattern, passing picklable configuration is essential for services that might be used in background jobs executed by APScheduler in separate processes.
    *   **Reduced Constructor Complexity:** Service constructors remain simple, primarily taking `settings` and potentially other picklable, configuration-like parameters or other service instances (if a service composes another).

*   **Canonical Instantiation Pattern:**
    ```python
    from ..core.config import settings
    from ..services.my_service import MyService
    from ..core.esi_client_class import ESIClient # Example of another service

    # In main.py or a dependency provider
    esi_client = ESIClient(settings=settings)
    my_service = MyService(settings=settings, esi_client=esi_client)
    ```

### 2.3. Resource Acquisition: On-Demand and Context-Aware

*   **Decision:** Services acquire the live resources they need (like database sessions or cache clients) *at the point of use* within their methods, adapting to the execution context.
*   **Two Contexts for Acquisition:**
    1.  **API Request Context (via FastAPI DI):**
        *   If a service method is called as part of a standard FastAPI API endpoint, it can (and often should) accept live resources (e.g., `db: AsyncSession = Depends(get_db)`) as *method parameters*. These are provided by FastAPI's dependency injection system.
        *   The service itself is still instantiated only with `Settings`.
        ```python
        # In services.my_service.py
        from ..core.config import Settings
        from sqlalchemy.ext.asyncio import AsyncSession

        class MyService:
            def __init__(self, settings: Settings, ...):
                self.settings = settings
                ...

            async def do_something_with_db(self, item_id: int, db: AsyncSession):
                # db session is passed in by FastAPI DI
                result = await db.execute(...)
                return result.scalar_one_or_none()
        ```

    2.  **Background Job Context (Dynamic Instantiation):**
        *   If a service method (or the service instance itself) is part of a background job running in a separate process, it **must** instantiate its own non-picklable resources dynamically using the `Settings` object it holds. This is detailed in the "Dependency Management in Hybrid Contexts" pattern.
        ```python
        # In services.contract_aggregation.py (simplified)
        from ..core.config import Settings
        import redis.asyncio as aioredis

        class ContractAggregationService:
            def __init__(self, settings: Settings, ...):
                self.settings = settings
                ...

            async def _acquire_lock(self, lock_key: str) -> bool:
                redis = await aioredis.from_url(str(self.settings.CACHE_URL))
                try:
                    # ... use redis ...
                    return True
                finally:
                    await redis.close()
        ```

## 3. Anti-Patterns to Avoid

*   **Anti-Pattern 1: Injecting Live Resources into Constructor:**
    ```python
    # AVOID THIS IN SERVICE CONSTRUCTOR
    # def __init__(self, settings: Settings, db: AsyncSession, cache: RedisClient):
    #     self.settings = settings
    #     self.db = db # Problematic: ties service to a specific session/client instance
    #     self.cache = cache # Problematic: non-picklable, inflexible
    ```
    This makes the service hard to test, non-picklable if `db` or `cache` are live clients, and inflexible regarding resource lifecycle.

*   **Anti-Pattern 2: Global Service Instances with Embedded Live Resources:** Creating global singleton instances of services that hold live, non-picklable resources. This will lead to issues with background jobs and testing.

## 4. Benefits

*   **Architectural Stability:** Provides a clear, consistent, and long-term answer to how services are constructed and how they obtain resources, preventing refactoring churn.
*   **Enhanced Testability:** Services are easier to unit test by mocking `Settings` or providing test-specific configurations.
*   **Pickle Safety:** Ensures services are compatible with background processing frameworks like APScheduler.
*   **Decoupling:** Service logic is decoupled from global resource lifecycle management.
*   **Flexibility:** Services can adapt their resource acquisition strategy based on the execution context.
