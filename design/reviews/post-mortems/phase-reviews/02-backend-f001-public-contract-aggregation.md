<!-- AI_NOTE: This template is for creating Phase Review summaries for the Hangar Bay project. It helps consolidate learnings, track decisions, and guide future phases. Cascade should use this template as a basis and fill in the specifics for each completed phase, focusing on analyzing the 'why and how' to maximize learning and continuous improvement. -->

# Phase 02: Backend F001 Public Contract Aggregation - Post-Mortem Review

**Date of Review:** 2025-06-10
**Phase Duration:** 2025-06-10 to 2025-06-10
**Lead Developer(s)/AI Pair:** USER & Cascade
**RelatedPreMortemReview:** [Link to Pre-Mortem Document for this Phase or N/A]
**PreviousPhaseReview:** [Link to Phase 01 Post-Mortem or N/A]
**NextPhaseReview:** [Link to Next Phase Review Document or N/A]

## 1. Phase Objectives, Outcomes, and Strategic Alignment

*   **1.1. Stated Objectives:**
    *   Finalize and implement the Phase 2 backend for the F001 Public Contract Aggregation feature.
    *   Configure ESI client with robust error handling and caching.
    *   Define and migrate SQLAlchemy data models for contracts, items, and market groups.
    *   Implement a background service to aggregate data automatically.
    *   Manage all service lifecycles within the FastAPI application.
*   **1.2. Achieved Outcomes:**
    *   All stated objectives were met. The ESI client, data models, background aggregation service, and scheduler were fully implemented and integrated.
    *   The database schema was successfully migrated after a series of troubleshooting steps.
    *   After a final round of bug fixes, the application is confirmed to be stable, with the background job running reliably and the server managing its lifecycle gracefully.
*   **1.3. Deviations/Scope Changes:**
    *   The data model for `EsiMarketGroupCache` was modified to use the generic `sqlalchemy.JSON` type instead of the PostgreSQL-specific `JSONB` type. This was an unplanned change triggered by compatibility issues with the SQLite database used for local development.
*   **1.4. Alignment with Strategic Goals:**
    *   This phase successfully built the core data aggregation pipeline for the project, which is a foundational requirement for providing contract-related features to users. It directly enables the primary value proposition of the Hangar Bay application.

## 2. Key Features & Infrastructure: Design vs. Implementation

*   **2.1. Major Deliverables (with verified file paths):**
    *   **Data Aggregation Service:** The core business logic, including ESI API interaction and data processing. (`app/backend/src/fastapi_app/services/background_aggregation.py`)
    *   **Database Upsert Service:** A generic service for handling idempotent database write operations (i.e., `INSERT` on new, `UPDATE` on existing). (`app/backend/src/fastapi_app/services/db_upsert.py`)
    *   **Scheduled Job Trigger:** The entry point for the APScheduler to run the aggregation. (`app/backend/src/fastapi_app/services/scheduled_jobs.py`)
    *   **Scheduler Configuration:** The setup and lifecycle management for APScheduler. (`app/backend/src/fastapi_app/core/scheduler.py`)
    *   **Data Models:** The SQLAlchemy model for the `contracts` table. (`app/backend/src/fastapi_app/models/contracts.py`)
    *   **Alembic Migration:** The database migration script to create the `contracts` table. (`app/backend/alembic/versions/`)
*   **2.2. Design vs. Implementation - Key Variances & Rationale:**
    *   **Feature/Component A:** Data Model for Market Group Cache
        *   **Variance:** The `raw_esi_response` column in the `EsiMarketGroupCache` model was changed from `postgresql.JSONB` to the generic `JSON` type.
        *   **Rationale:** The initial migration failed because the development database is SQLite, which does not support the `JSONB` type. To allow the application to run in both development (SQLite) and production (PostgreSQL) without complex conditional logic in the models, the more compatible generic `JSON` type was chosen.
        *   **Impact (Neutral):** This ensures development environment parity but forgoes potential performance benefits and advanced JSON query capabilities of the native `JSONB` type in PostgreSQL. This is considered acceptable technical debt for now.

## 3. Technical Learnings & Discoveries

*   **3.1. Key Technical Challenges & Resolutions:**
    *   **Challenge 1:** Resolving a cascading series of Alembic migration failures.
        *   **Resolution/Workaround:** A multi-step troubleshooting process was required:
            1.  **Initial Error (`NameError: name 'Text' is not defined`):** The first failure was due to a missing import for a type used by `JSONB`. This was fixed by adding `from sqlalchemy import Text` to the migration script.
            2.  **Second Error (`OperationalError: table contracts already exists`):** The first failed migration had partially completed. The resolution was to downgrade the database (`alembic downgrade -1`), but this led to an inconsistent state.
            3.  **Third Error (`UnsupportedCompilationError: ...can't render element of type JSONB`):** After resetting the DB, the root cause was identified: SQLite does not support the PostgreSQL-specific `JSONB` type. The model was updated to use generic `JSON`.
            4.  **Fourth Error (`Target database is not up to date`):** After deleting the DB file to regenerate migrations, Alembic became confused. The final correct procedure was established: `alembic upgrade head` to create and sync the DB, then `alembic revision --autogenerate` to create the new migration, and finally `alembic upgrade head` again to apply it.
        *   **Actionable Learning & Future Application (Cascade & Team):**
            *   When using database-specific column types, ensure the development environment (e.g., SQLite) has a compatible fallback or use the generic SQLAlchemy types (`JSON`, `String`, etc.) from the start if cross-dialect compatibility is required.
            *   Alembic state can become confused if migration files and the database schema get out of sync. The reliable recovery pattern is often to bring the database to the latest known good state (`upgrade head`) *before* attempting to generate new revisions.
            *   Always review autogenerated migration scripts. They may contain errors or, as seen, miss tables if Alembic believes they already exist in the target database.

    *   **Challenge 2:** Resolving a persistent `ValueError: Invalid reference` from APScheduler during application startup.
        *   **Resolution/Workaround:** This error was exceptionally difficult to debug because it masked the true underlying exceptions. The resolution involved a multi-stage investigation:
            1.  **Initial State:** The scheduler was configured to run a job using a string reference (`'fastapi_app.services.scheduled_jobs.run_aggregation_job'`). This failed silently within APScheduler, only raising the generic `Invalid reference` error.
            2.  **Debugging Step 1 (Exposing Hidden Errors):** To uncover the real issue, we moved the `ESIClient` class from `services/esi_client.py` to a new `core/esi_client_class.py` file and relocated dependency providers (`get_esi_client`, `get_cache`) to `core/dependencies.py`. This broke a critical circular import chain between the services and core modules.
            3.  **Debugging Step 2 (Targeted Import Simulation):** Even after fixing the circular imports, the `Invalid reference` error persisted. We added a temporary debugging block to the FastAPI `startup_event` to manually import the job function using `importlib` *before* the scheduler was initialized. This diagnostic step surprisingly succeeded, proving the module was technically importable, but it still failed inside APScheduler. This pointed to a subtle runtime context or state issue.
            4.  **Final Resolution (Bypassing String Reference):** The ultimate solution was to abandon the string-based job reference entirely. We modified `core/scheduler.py` to import the `run_aggregation_job` function directly and pass the actual function object to `scheduler.add_job()`. This completely bypassed APScheduler's internal import mechanism and immediately resolved the startup error.
        *   **Actionable Learning & Future Application (Cascade & Team):**
            *   The APScheduler `ValueError: Invalid reference` is a strong indicator of a masked, underlying `ImportError` or a circular dependency. Do not trust the surface-level error.
            *   When debugging such issues, the most effective pattern is to first rule out circular dependencies by carefully mapping the import graph. If that fails, the most reliable solution is to switch from a string-based job reference to a direct function object reference. This provides a more robust and less error-prone way to schedule jobs.
            *   Forcing a manual import with `importlib` can be a useful diagnostic tool to confirm if a module path is valid, even if it doesn't solve the root cause in a complex framework context.

    *   **Challenge 3:** Resolving multiple `TypeError` exceptions in the background job and application lifecycle.
        *   **Resolution/Workaround:** After the scheduler was fixed, the background job began to run but immediately failed with new errors:
            1.  **`TypeError: CacheManager.__init__() takes 1 positional argument but 2 were given`:** The scheduled job was incorrectly instantiating the `CacheManager` by passing a URL to its constructor. The fix was to call the empty constructor (`CacheManager()`) and then call the separate `await cache_manager.initialize(url)` method, matching the class's actual design.
            2.  **`TypeError: close_http_client() takes 0 positional arguments but 1 was given`:** The FastAPI shutdown hook was passing the `app` instance to a `close_http_client` function that was not defined to accept any arguments. The fix was to update the function signature to `async def close_http_client(app: FastAPI)` and add the necessary logic to close the client on the app state.
        *   **Actionable Learning & Future Application (Cascade & Team):**
            *   When a background job or a separate process instantiates classes, it does not share the same application context or dependency injection setup as the main FastAPI app. Dependencies must be created and managed manually and correctly within the job's scope.
            *   Always ensure that FastAPI lifecycle event handlers (`@app.on_event("startup")`, `@app.on_event("shutdown")`) have the correct function signatures. Shutdown handlers often receive the `app` object and must be defined to accept it.

    *   **Challenge 4:** Final bug fixes to achieve application stability.
        *   **Resolution/Workaround:** After resolving the major scheduler issues, the background job began running but exposed several more subtle bugs that were fixed in succession:
            1.  **`KeyError: 'status'`:** The aggregation job failed when processing contract data from ESI because the `status` field was sometimes missing. The fix was to use the safe `.get("status", "outstanding")` method, providing a sensible default that complies with the non-nullable database schema.
            2.  **`TypeError: close_cache()` on shutdown:** During hot-reloading, the application failed with a `TypeError` because the `close_cache` lifecycle function was not defined to accept the `app` argument passed by FastAPI. This was fixed by updating its signature, reinforcing a pattern of errors seen with other lifecycle handlers.
            3.  **`asyncio.exceptions.CancelledError` on shutdown:** This error was observed in the logs but was determined to be normal and expected behavior when Uvicorn's reloader stops the server, not an application bug.
        *   **Actionable Learning & Future Application (Cascade & Team):**
            *   Data from external APIs should never be trusted. Always use defensive coding patterns (e.g., `.get()` for dictionaries) and validate data against the local schema, providing defaults for required fields where appropriate.
            *   The iterative process of fixing a major bug, running the application, and observing the next failure is a powerful, if sometimes tedious, method for uncovering and resolving a chain of nested issues.

    *   **Challenge 5:** Optimizing Database Transactions and Batching for ESI Data Aggregation.
        *   **Initial Approach & Problem:** Early iterations of the aggregation service sometimes committed data to the database too frequently within a larger logical operation (e.g., saving a contract header before all its items were fetched and processed). This approach, while seemingly incremental, risked data inconsistency if subsequent ESI calls or processing steps for the same logical entity (e.g., a contract and all its items) failed.
        *   **Consequences of Fine-Grained Commits:**
            *   **Data Inconsistency:** If an ESI call for contract items failed after the contract header was already committed, the database could be left with a contract record missing its essential item details.
            *   **Orphaned Data:** Partial data for a logical entity could be persisted.
            *   **Complex Rollback Logic:** Managing rollbacks across multiple small, already-committed transactions for a single logical unit of work would be significantly more complex.
        *   **Resolution/Refined Strategy:** The strategy was refined to prioritize atomicity for logical units of work:
            1.  **Define Logical Units of Work:** A "logical unit of work" was clearly defined (e.g., fetching one public contract *and all* its associated items).
            2.  **Single Database Transaction per Unit:** All database operations (inserts, updates) for a single logical unit of work are now performed within a single database transaction.
            3.  **Commit on Full Success:** The transaction is committed *only if all* ESI calls for that unit succeed and all associated data processing is successful.
            4.  **Rollback on Any Failure:** If *any* ESI call within that unit fails, or any processing error occurs, the entire transaction for that unit is rolled back. This ensures the database is not left with partial or inconsistent data for that specific contract. The error is logged, and the unit can be retried (leveraging ESI ETags to minimize redundant data transfer).
        *   **Actionable Learning & Future Application (Cascade & Team):**
            *   **Prioritize Data Integrity:** It's preferable to re-fetch data for a logical unit (especially when ESI ETags can prevent actual re-downloading of unchanged data) than to risk committing incomplete or inconsistent data.
            *   **Atomic Operations for Logical Units:** Treat operations that fetch and process a complete, self-contained entity from an external API (like a contract and its items) as atomic. All related database changes should succeed or fail together within a single transaction.
            *   **ESI Cost vs. DB Transaction Cost:** Recognize the asymmetry: ESI calls are expensive (network, rate limits), while local database transactions are cheap. Design transaction boundaries to ensure a complete, consistent state is achieved for each "expensive" set of ESI operations.

    *   **Challenge 6:** Resolving `PicklingError` in background jobs due to non-picklable dependencies.
        *   **Problem:** After resolving the scheduler startup issues, the background aggregation job began failing with a `PicklingError`. The root cause was that `APScheduler`, when running jobs in a separate process, needs to "pickle" (serialize) the job and its arguments. The application was attempting to pass live, non-picklable objects—specifically the `aioredis.Redis` client instance—from the main application's dependency injection system into the scheduled job's context.
        *   **Debugging Methodology: Pinpointing the Non-Picklable Object with ID Logging:**
            Before arriving at the architectural solution, a methodical debugging process was used to precisely identify which object was causing the `PicklingError`. Standard tracebacks were insufficient as they only pointed to the pickling library itself, not the problematic object.

            1.  **Hypothesis:** The error occurs when `APScheduler` tries to serialize the job's context. This context includes the `ContractAggregationService` instance and any arguments passed to its method. The non-picklable object is likely a live resource client (e.g., Redis, DB session) held by one of these.
            2.  **Technique: Object ID Comparison:** The Python `id()` function provides a unique memory address for an object. By logging the `id()` of suspected objects at various points in the application lifecycle, we could trace their identity and prove whether the *exact same instance* was being passed from the main application thread to the background job context.
            3.  **Implementation:**
                *   **In `main.py` (App Startup):** Logged the `id()` of the `redis_client` immediately after its creation.
                *   **In Dependency Providers:** Logged the `id()` of the `redis_client` being passed into service constructors (`get_esi_client`, `get_aggregation_service`).
                *   **In Service Constructors:** Logged the `id()` of the `redis_client` received and stored in `self.redis_client` within `ESIClient` and `ContractAggregationService`.
            4.  **Analysis of Logs:** The logs showed conclusively that the `id()` of the Redis client was identical across all these points. This proved that the live, non-picklable Redis client instance created at application startup was the *exact same instance* being held by the `ContractAggregationService` when `APScheduler` attempted to pickle it for the background job. This confirmed the root cause of the `PicklingError`.

        *   **Resolution/Architectural Refactor:** With the root cause confirmed, a critical architectural pattern was established to resolve this and prevent future occurrences. The solution ensures that any component intended to be used within a scheduled job is fully picklable.
            1.  **Decouple from Live Instances:** Services like `ESIClient` and `ContractAggregationService` were refactored. Instead of accepting a live `redis_client` instance in their `__init__` methods, they now only accept the picklable `Settings` object.
            2.  **Dynamic Resource Instantiation:** Within the methods of these services that require a Redis connection, a new client is created dynamically *inside the method's scope*. For example: `client = await aioredis.from_url(str(self.settings.CACHE_URL))`. This ensures the live, non-picklable client object only exists within the context of the running job process and is never passed across process boundaries.
            3.  **System-Wide Update:** This pattern was propagated throughout the application. All dependency providers (`get_esi_client`, `get_aggregation_service`) and service instantiations (`main.py`) were updated to no longer pass the `cache` or `redis_client` instances to these services.
        *   **Illustrative Example (The Fix):**
            ```python
            # IN: app/backend/src/fastapi_app/core/scheduler.py

            # BEFORE: Passing a live, unpickleable client to the job's args via Depends()
            # This fails because the resolved dependency contains an httpx.AsyncClient.
            scheduler.add_job(
                aggregate_contracts,
                "interval",
                minutes=60,
                args=[Depends(get_esi_client)],
            )

            # AFTER: Passing a simple, pickleable Settings object
            scheduler.add_job(
                aggregate_contracts,
                "interval",
                minutes=60,
                args=[app.state.settings], # This works!
            )

            # And inside the job function, clients are created on-demand:
            async def aggregate_contracts(settings: Settings):
                esi_client = EsiClient(settings)
                db_upsert_service = DbUpsertService(settings)
                # ... rest of the job logic
            ```
        *   **Actionable Learning & Future Application (Cascade & Team):**
            *   Any object passed to a background job running in a separate process (like with the default `APScheduler` configuration) *must* be picklable. This includes all arguments and the state of the object whose method is being called.
            *   Live resource connections (database, cache, etc.) are generally not picklable.
            *   The established pattern—passing configuration (like a `Settings` object) and creating resources dynamically within the job's execution context—is the standard architectural solution for this problem. This pattern must be followed for all future background job implementations.

## 4. Process Learnings & Improvements

*   **4.3. AI Collaboration (USER & Cascade):**
    *   The interactive, step-by-step troubleshooting of the Alembic issues was highly effective. Cascade's ability to interpret errors, propose a solution, execute, and then analyze the subsequent outcome allowed for rapid iteration.
    *   The USER's request to proactively create this post-mortem is a positive process improvement, shifting documentation from a reactive to a proactive task.

*   **4.4. Addressing Cyclical Refactoring and Architectural Drift:**
    *   **Observation:** The series of bugs, culminating in the `PicklingError`, was exacerbated by a pattern of "architectural drift." Previous refactoring efforts were sometimes incomplete or their underlying rationale was lost, leading to cycles of breaking and fixing similar issues (e.g., how the `Settings` object is provided vs. a `get_settings` dependency).
    *   **Improvement:** The resolution of the pickling issue established a firm, documented architectural pattern. To prevent future drift, this post-mortem, along with new entries in the `design-log.md` and a dedicated FastAPI architecture guide, will serve as canonical references. Future development must consult these documents to ensure architectural consistency. This moves us from relying on implicit knowledge to explicit, documented patterns.

## 7. Unresolved Issues & Technical Debt

*   **7.3. Technical Debt Incurred (This Phase):**
    *   **Debt Item 1:** Use of generic `JSON` type instead of `JSONB` for market group data.
        *   **Reason Incurred:** Conscious trade-off to maintain compatibility with the SQLite development environment.
        *   **Future Impact/Risk:** Minor. May result in slightly less performant JSON queries in PostgreSQL. If complex server-side JSON manipulation is required in the future, this may need to be revisited.
        *   **Suggested Priority to Address:** Low.
        *   **Potential Solution/Effort Estimate (Optional):** When the project moves to a dedicated PostgreSQL development environment, change the column type back to `JSONB` and generate a new migration. Effort: Very Low.
