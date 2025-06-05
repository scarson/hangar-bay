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

## Feature Specification Management (Approx. 2025-06-05 01:46:46-05:00)

*   **Approach:** To facilitate focused development and clear requirements for the Windsurf coding assistant, individual features will be detailed in separate markdown files.
*   **Location:** These feature specifications will reside in the `design/features/` directory.
*   **Template:** A standardized template, `design/features/00-feature-spec-template.md`, has been created to ensure consistency and comprehensiveness across all feature specs.
    *   The template includes sections for overview, user stories, acceptance criteria, scope, data models, API interactions, workflow, UI/UX, error handling, security, performance, dependencies, and notes.
    *   It distinguishes between **Required** and **Optional** sections, with instructions to complete all required sections and evaluate optional ones for applicability.
*   **Process (Memory: e0009aae):** When creating a new feature spec, the `00-feature-spec-template.md` will be referenced. Required sections and applicable optional sections will be copied and filled with feature-specific details.

## Feature Specification Elaboration: F001, F002 & F003 (Approx. 2025-06-05 03:11:17-05:00)

*   **Focus:** Began detailed elaboration of feature specifications, starting with F001 (Public Contract Aggregation & Display), F002 (Ship Browsing & Advanced Search/Filtering), and then F003 (Detailed Ship Contract View).
*   **F001 (Public Contract Aggregation & Display) Initial Decisions:**
    *   **Data Storage:**
        *   `issuer_name`: Store directly (resolved once at ingestion).
        *   `start_location_name`: Resolve on display (via `start_location_id`).
        *   `esi_type_cache`: Store all `dogma_attributes` and `dogma_effects` (using SQLite JSON1 for dev, PostgreSQL JSONB for prod).
    *   **Error Handling:** For DB errors, implement retry with exponential backoff and jitter.
    *   **Configuration:** EVE regions to poll will be admin-configurable.
    *   **Contract Updates:** Handle updates to existing contracts (e.g., auction prices) via targeted re-fetches based on ESI cache timers and internal refresh intervals, not full re-scans.
*   **F002 (Ship Browsing & Advanced Search/Filtering) Initial Decisions:**
    *   **List View:**
        *   Added user story for basic contract details in list view.
        *   Defined initial fields: Ship Type, Quantity, Total Price, Contract Type, Location, Time Remaining, Issuer Name.
        *   Default sort order: Expiration date (soonest first).
    *   **Advanced Filtering:**
        *   Ship attributes (meta level, tech level): Plan to use `dogma_attributes` from `esi_type_cache`.
        *   Ship categories/groups: Source from ESI Market Groups, cache periodically, and expose via API.
*   **F003 (Detailed Ship Contract View) Decisions:**
    *   **Dogma Attributes Display:** A curated list of 'Key Ship Attributes' will be displayed prominently, with an option (e.g., 'All Attributes' toggle/tab) to view all others. Attributes to be grouped logically.
    *   **Handling Multiple Items:** Main focus on primary ship(s). An 'Additional Included Items' section will list other non-primary-ship items (Name and Quantity).
    *   **Image Server:** Use EVE Online's official image server (`https://images.evetech.net/`) for ship renders (e.g., `types/{type_id}/render?size=512`) and icons.
*   **Cross-Feature Consistency & Iterative Refinement:**
    *   Initial decisions for F001 and F002 were made. Subsequently, F003 was elaborated.
    *   Decisions and requirements from F003, along with F002's needs, prompted revisions to F001. F002 was also updated to note potential enhancements based on F001/F003 changes.
    *   **Updates to F001 (driven by F002 & F003):**
        *   Added `market_group_id` to `esi_type_cache` (for F002 category filtering).
        *   Clarified `contracts.title` usage (for F002 keyword search).
        *   Noted dependency on a separate `location_details_cache` (for F002 location name search).
        *   Added `contains_additional_items: BOOLEAN` to the `contracts` table schema (for F003 display of mixed contracts).
        *   Clarified that `esi_type_cache` population must cover all item types in processed contracts, not just primary ship items (for F003).
    *   **Updates to F002 (driven by F001/F003):**
        *   Noted potential use of the `contains_additional_items` flag (from F001, for F003) for UI indicators or filtering in the list view.
    *   **Rationale:** This iterative refinement ensures that feature specifications remain consistent and that dependencies between features are explicitly identified and addressed. This process is crucial for robust design, allowing insights from detailing one feature to inform and improve related features.

*(This log will be updated as more decisions are made. Remember to include approximate ISO 8601 timestamps in the format 'YYYY-MM-DD HH:MM:SSZ' (U.S. Central Time) for new major decision sections.)*
