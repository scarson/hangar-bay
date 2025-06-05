# Hangar Bay - Design Decision Log

This document records major design discussion points, considerations, and decisions made throughout the Hangar Bay project, in generally chronological order.

## Initial Phase: Understanding Requirements & ESI (Approx. 2025-06-04 20:00:00-05:00)

*   **Project Goal:** Design a secure e-commerce application for EVE Online ships ("Hangar Bay").
*   **Core Constraint:** Security is paramount due to the EVE Online player base's nature.
*   **Initial Research:** Reviewed EVE Online basics, economy, ships, and the ESI API.
    *   Key finding: ESI API is RESTful, uses SSO, and has cache timers.
    *   ESI Swagger specification reviewed for available endpoints.
*   **Transaction Model Discussion:**
    *   **Consideration:** Can Hangar Bay facilitate transactions directly via ESI?
    *   **ESI Finding:** ESI does *not* allow creating contracts via API.
    *   **Options Considered:**
        1.  Listing platform (manual in-game transactions, Hangar Bay verifies ownership via SSO + asset API).
        2.  Aggregator of public in-game contracts (Hangar Bay displays public contracts, users accept in-game).
    *   **Decision (Memory: d14b4bed): Hangar Bay will be an aggregator of public in-game contracts.**
        *   **Reasoning:** Leverages EVE's existing secure contract system, reducing Hangar Bay's direct involvement in sensitive transaction parts.

## Tech Stack & Core Features Refinement (Approx. 2025-06-04 23:00:00-05:00)

*   **EVE SSO for Value-Add Features:**
    *   **Initial thought:** SSO optional for MVP if just browsing public contracts.
    *   **User Feedback/Decision:** SSO to be a core requirement to enable features like saved searches, watchlists, and configurable alerts. This significantly enhances user value.
*   **Backend Framework Discussion:**
    *   **Options Considered:** Python (FastAPI, Flask) vs. Go.
    *   **FastAPI Pros:** Rapid development, async support, auto-docs, Python ecosystem.
    *   **Go Pros:** Raw performance, concurrency model, static typing.
    *   **Decision: Tentatively Python with FastAPI.**
        *   **Reasoning:** Good balance of performance (especially for I/O bound ESI calls with async) and development speed. User familiarity with C# makes Python's learning curve manageable, and FastAPI's type hints are helpful.
*   **ASGI Server for FastAPI:**
    *   **Initial Spec:** Uvicorn.
    *   **Discussion:** Uvicorn (direct), Hypercorn, Gunicorn with Uvicorn workers.
    *   **Decision: Uvicorn for development, Gunicorn with Uvicorn workers for production.**
        *   **Reasoning:** Gunicorn provides robust process management for production, leveraging Uvicorn's speed.
*   **Database:**
    *   **Options Considered:** PostgreSQL, SQLite for dev.
    *   **Decision: SQLite for development, PostgreSQL for production.**
        *   **Reasoning:** SQLite for ease of local dev, PostgreSQL for production robustness. An ORM (e.g., SQLAlchemy) will be used, designing schemas for PostgreSQL capabilities. No dev-to-prod data migration needed; prod schema populated fresh.
*   **Caching Layer:**
    *   **Options Considered:** Redis vs. Valkey (Redis fork).
    *   **Research:** Valkey is community-driven (Linux Foundation), API compatible with Redis 7.2.4 for core needs, open BSD license.
    *   **Decision: Valkey.**
        *   **Reasoning:** Sufficient for caching needs, aligns with open-source preference, good client library compatibility.
*   **Frontend Framework:**
    *   **Options Considered:** React, Vue.js, Angular.
    *   **Decision: Angular.**
        *   **Reasoning:** User interest in learning Angular, comprehensive framework, TypeScript for static typing (potential security/robustness benefits).
*   **Deployment:**
    *   **Decision: Application must be containerized (Docker).**
        *   **Reasoning:** Consistency across environments, hosting provider agnosticism, CI/CD integration.

## Specification Documents (Approx. 2025-06-05 00:30:00-05:00)

*   **`design-spec.txt`:** Main design document.
*   **`security-spec.md`:** Created for detailed security guidelines.
    *   **Initial Content:** TLS 1.2/1.3, Perfect Forward Secrecy, PQC aspiration, Encryption at Rest placeholder.
*   **`test-spec.md`:** Created for testing strategy.
*   **`design-log.md`:** This document, for chronological decision tracking.
*   **`observability-spec.md`:** Created for logging, metrics, tracing (distinct from security-specific logs).

*(This log will be updated as more decisions are made. Remember to include approximate ISO 8601 timestamps in the format 'YYYY-MM-DD HH:MM:SSZ' (U.S. Central Time) for new major decision sections.)*
