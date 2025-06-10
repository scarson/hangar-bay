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

*   **2.1. Major Deliverables:**
    *   ESI Client Service (`services/esi_client.py`)
    *   SQLAlchemy Data Models (`models/contracts.py`)
    *   Alembic Database Migrations
    *   Database Upsert Utility (`services/db_upsert.py`)
    *   Background Aggregation Service with Redis locking (`services/background_aggregation.py`)
    *   APScheduler Integration (`core/scheduler.py`)
    *   FastAPI Lifecycle Integration (`main.py`)
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

## 4. Process Learnings & Improvements

*   **4.3. AI Collaboration (USER & Cascade):**
    *   The interactive, step-by-step troubleshooting of the Alembic issues was highly effective. Cascade's ability to interpret errors, propose a solution, execute, and then analyze the subsequent outcome allowed for rapid iteration.
    *   The USER's request to proactively create this post-mortem is a positive process improvement, shifting documentation from a reactive to a proactive task.

## 7. Unresolved Issues & Technical Debt

*   **7.3. Technical Debt Incurred (This Phase):**
    *   **Debt Item 1:** Use of generic `JSON` type instead of `JSONB` for market group data.
        *   **Reason Incurred:** Conscious trade-off to maintain compatibility with the SQLite development environment.
        *   **Future Impact/Risk:** Minor. May result in slightly less performant JSON queries in PostgreSQL. If complex server-side JSON manipulation is required in the future, this may need to be revisited.
        *   **Suggested Priority to Address:** Low.
        *   **Potential Solution/Effort Estimate (Optional):** When the project moves to a dedicated PostgreSQL development environment, change the column type back to `JSONB` and generate a new migration. Effort: Very Low.
