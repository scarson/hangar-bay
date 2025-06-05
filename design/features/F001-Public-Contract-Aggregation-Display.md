# Feature Spec: Public Contract Aggregation & Display

**Feature ID:** F001
**Creation Date:** 2025-06-05
**Last Updated:** 2025-06-05
**Status:** Draft

---
**Instructions for Use:**
*   This template provides a structured format for defining individual features.
*   **Required** sections MUST be completed for every feature by filling in feature-specific details.
*   Evaluate each **Optional** section for its applicability to the current feature. If applicable, include and complete it. If not, it can be omitted or marked as "N/A".
*   Replace bracketed placeholders `[like this]` with feature-specific information.
*   The goal is to provide clear, concise, and comprehensive information to guide development and testing.
---

## 1. Feature Overview (Required)
*   This feature covers the core functionality of regularly fetching public item exchange and auction contracts from specified EVE Online regions, filtering these contracts to identify those primarily offering ships, and displaying key contract details to users.
*   It forms the foundational data pipeline for Hangar Bay.

## 2. User Stories (Required)
*   Story 1: As a Hangar Bay system, I want to periodically fetch all public contracts from configured EVE Online regions, so that I have up-to-date contract data.
*   Story 2: As a Hangar Bay system, I want to filter fetched contracts to identify those primarily containing ships, so that the platform focuses on its core offering.
*   Story 3: As a user, I want to see a list of available public ship contracts with key details (ship type, name, quantity, price, contract type, location, issuer, expiration), so I can quickly scan for interesting offers.
*   [FURTHER_DETAIL_REQUIRED: Additional user stories for different views or interactions with the aggregated data.]

## 3. Acceptance Criteria (Required)
*   **Story 1 Criteria:**
    *   Criterion 1.1: The system successfully fetches public contracts from all configured EVE regions via the ESI API (`GET /v1/contracts/public/{region_id}/`).
    *   Criterion 1.2: Fetching respects ESI cache timers and ETag headers.
    *   Criterion 1.3: Errors during ESI fetching are logged, and appropriate retry mechanisms are in place [NEEDS_DISCUSSION: Define retry strategy].
    *   Criterion 1.4: The system can handle paginated ESI responses for contracts.
*   **Story 2 Criteria:**
    *   Criterion 2.1: A clear definition of what constitutes a "ship contract" is established and implemented [NEEDS_DECISION: How to identify ship contracts? Based on item types within? Single item contracts only? Threshold for non-ship items? Must fetch items via `GET /v1/contracts/public/items/{contract_id}/`].
    *   Criterion 2.2: The system fetches contract items for potentially relevant contracts to determine if they are ship contracts.
    *   Criterion 2.3: Non-ship contracts are filtered out or marked appropriately.
*   **Story 3 Criteria:**
    *   Criterion 3.1: Key contract details (ship type, name, quantity, price, contract type, location, issuer, expiration date) are extracted and stored in the database [NEEDS_DETAIL: Finalize specific DB fields].
    *   Criterion 3.2: Ship type details (name, category) are resolved using ESI `universe/types` and cached.
    *   Criterion 3.3: An API endpoint exists to provide a list of aggregated ship contracts with basic details.

## 4. Scope (Required)
### 4.1. In Scope
*   Fetching public contracts (item exchange & auction) via ESI API for configured regions.
*   Fetching items for these public contracts from ESI.
*   Identifying/filtering for contracts that are primarily for ships.
*   Storing relevant details of these ship contracts in the application's database.
*   Basic data transformation for consistent storage (e.g., resolving type IDs to names).
*   Adherence to ESI caching, rate limiting, and error handling best practices for these specific ESI calls.
### 4.2. Out of Scope
*   User interface for displaying contracts (covered by F002).
*   Advanced searching and filtering logic beyond basic identification (covered by F002).
*   User authentication (F004).
*   Handling of non-public contracts.
*   Direct interaction with EVE game client for contract acceptance.
*   Detailed market analysis or price history (beyond what's needed for basic display).

## 5. Key Data Structures / Models (Optional, but often Required)
*   **`contracts` table:**
    *   `contract_id`: BIGINT (Primary Key, from ESI)
    *   `contract_type`: VARCHAR (e.g., 'item_exchange', 'auction')
    *   `issuer_id`: INTEGER (Character ID from ESI)
    *   `issuer_name`: VARCHAR (Resolved once during ingestion and stored directly. Character name changes are rare.)
    *   `start_location_id`: BIGINT (Station/Structure ID from ESI)
    *   `start_location_name`: VARCHAR (Resolved on display via `start_location_id`. Location names can change or be dynamic.)
    *   `region_id`: INTEGER
    *   `price`: DECIMAL
    *   `volume`: DOUBLE [NEEDS_CLARIFICATION: From ESI or sum of items? Relevant for ships?]
    *   `date_issued`: TIMESTAMP
    *   `date_expired`: TIMESTAMP
    *   `title`: VARCHAR(255) (From ESI, used for keyword search in F002), if available)
    *   `for_corp`: BOOLEAN
    *   `is_ship_contract`: BOOLEAN (derived by this feature's logic)
    *   `last_esi_check`: TIMESTAMP (Timestamp of when contract items were last fetched/verified)
*   **`contract_items` table:**
    *   `record_id`: BIGINT (Primary Key from ESI, or internal auto-increment if ESI doesn't provide a unique item ID within a contract response)
    *   `contract_id`: BIGINT (Foreign Key to `contracts`)
    *   `type_id`: INTEGER (EVE Online Type ID)
    *   `quantity`: INTEGER
    *   `is_included`: BOOLEAN
    *   `is_blueprint_copy`: BOOLEAN
    *   `material_efficiency`: INTEGER
    *   `runs`: INTEGER
    *   `time_efficiency`: INTEGER
*   **`esi_type_cache` table (for ships and relevant items):**
    *   `type_id`: INTEGER (Primary Key, EVE Online Type ID)
    *   `name`: VARCHAR
    *   `group_id`: INTEGER
    *   `market_group_id`: INTEGER (From ESI type details, for F002 category filtering)
    *   `icon_id`: INTEGER (Optional)
    *   `mass`: DOUBLE (Optional)
    *   `packaged_volume`: DOUBLE (Optional)
    *   `portion_size`: INTEGER (Optional)
    *   `radius`: DOUBLE (Optional)
    *   `volume`: DOUBLE
    *   `capacity`: DOUBLE
    *   `published`: BOOLEAN
    *   `dogma_attributes`: JSONB (Store all attributes. For SQLite in dev, this will be TEXT using JSON1 functions; for PostgreSQL in prod, native JSONB.)
    *   `dogma_effects`: JSONB (Store all effects. For SQLite in dev, this will be TEXT using JSON1 functions; for PostgreSQL in prod, native JSONB.)
    *   `last_esi_check`: TIMESTAMP (Timestamp of when contract items were last fetched/verified from ESI)
*   [FURTHER_DETAIL_REQUIRED: Define relationships, indexing strategy, final decision on name resolution/storage.]

## 6. API Endpoints Involved (Optional)
### 6.1. Consumed ESI API Endpoints
*   **Endpoint 1:** `GET /v1/contracts/public/{region_id}/`
    *   Fields: All fields returned.
    *   Caching: Per ESI headers (typically 300s).
*   **Endpoint 2:** `GET /v1/contracts/public/items/{contract_id}/`
    *   Fields: All fields returned.
    *   Caching: Per ESI headers (typically 3600s).
*   **Endpoint 3:** `GET /v3/universe/types/{type_id}/`
    *   Fields: All fields for caching ship/item details.
    *   Caching: Per ESI headers (often long, ETag vital).
*   **Endpoint 4:** `POST /v1/universe/ids/`
    *   Fields: `id`, `name` (for resolving character, station, system names if not done on frontend).
    *   Caching: Per ESI headers (typically 3600s).
### 6.2. Exposed Hangar Bay API Endpoints
*   **Endpoint 1:** `GET /api/v1/contracts/ships`
    *   Request: Query parameters for pagination (e.g., `page`, `limit`), basic filtering (e.g., `region_id`).
    *   Success Response: JSON array of ship contracts with key details (e.g., `contract_id`, `ship_name`, `price`, `location_name`, `date_expired`). Status 200.
    *   Error Responses: [NEEDS_DETAIL: Define standard error responses for invalid parameters, etc.]

## 7. Workflow / Logic Flow (Optional)
1.  Scheduled task (e.g., Celery beat) triggers contract aggregation for a list of configured EVE regions.
2.  For each region:
    a.  Fetch public contracts page by page using `GET /v1/contracts/public/{region_id}/`.
    b.  For each contract received:
        i.  If contract is new or `last_esi_check` is stale (or contract is of interest based on initial data):
            1.  Fetch its items using `GET /v1/contracts/public/items/{contract_id}/`.
            2.  Determine if it's a ship contract based on defined criteria [NEEDS_DECISION: Logic for ship contract identification].
            3.  If it is a ship contract:
                a.  Extract/transform relevant data.
                b.  Fetch/update ship type details from `GET /v3/universe/types/{type_id}/` for items not in local cache or stale, store in `esi_type_cache`.
                c.  Store/update contract and item details in the Hangar Bay database (`contracts`, `contract_items`).
            4.  Update `last_esi_check` for the contract in the `contracts` table.
3.  Handle ESI errors, rate limits, and caching throughout.

## 8. UI/UX Considerations (Optional)
*   N/A for this backend-focused data aggregation feature. Data provided must support F002 (Browsing/Searching UI).

## 9. Error Handling & Edge Cases (Required)
*   ESI API unavailable/errors: Implement retry logic (e.g., exponential backoff), log errors, potentially mark regions/contracts as temporarily un-pollable or data as stale.
*   ESI rate limiting: Strictly respect error rate limits; gracefully back off.
*   Unexpected ESI data format: Log error, attempt to continue if possible, flag data for review.
*   Database errors during storage: Log error. Implement a retry strategy such as **retry with exponential backoff and jitter** for transient errors (e.g., connection issues, deadlocks). This involves increasing delays between retries and adding randomness to avoid thundering herd. Define max retries and differentiate retryable vs. non-retryable errors. Ensure operations are idempotent. Log all retry attempts and failures. A circuit breaker pattern could be a further enhancement if needed.
*   Large number of contracts/items: Ensure processing is efficient and does not overwhelm resources (memory, CPU, DB connections).
*   [FURTHER_DETAIL_REQUIRED: More specific edge cases related to contract types (auction vs. item_exchange), item types, etc.]

## 10. Security Considerations (Required)
*   Input validation: Data from ESI, while generally trusted, should be validated for expected types/formats before database insertion to prevent issues if ESI schema changes unexpectedly or data is malformed.
*   Resource consumption: Ensure ESI polling strategy doesn't lead to excessive outbound requests (respect cache timers strictly).
*   Database security: Use parameterized queries (typically handled by ORMs like SQLAlchemy) to prevent SQL injection, even with system-generated data.
*   No direct user input for this feature, but the integrity of the data it provides is crucial for user-facing features.
*   Refer to `security-spec.md` for general guidelines on secure coding, data handling, and interaction with external APIs.

## 11. Performance Considerations (Optional)
*   Efficient ESI polling (minimize redundant calls, maximize cache use).
*   Database writes should be optimized (batching if appropriate and if the ORM/DB driver supports it efficiently [NEEDS_DISCUSSION]).
*   Time taken to process all configured regions should be reasonable and not lead to excessive data staleness [NEEDS_DECISION: Define acceptable processing window/data freshness target].
*   Indexing strategy for database tables (`contracts`, `contract_items`, `esi_type_cache`) to support efficient querying by F002 and other features.

## 12. Dependencies (Optional)
*   Database system (e.g., PostgreSQL).
*   Caching layer (e.g., Valkey).
*   Task scheduler (e.g., Celery) for periodic polling.
*   EVE Online ESI API.

## 13. Notes / Open Questions (Optional)
*   **EVE regions to poll**: This will be admin-configurable. For development/prototyping, it can be limited to a few regions, but production will require flexibility.
*   [NEEDS_DISCUSSION: Detailed logic for identifying a "ship contract" – e.g., based on item category ID (e.g., categoryID 6 for Ships), percentage of items that are ships, specific ship group IDs? What if a contract has a ship and many non-ship items?]
*   [NEEDS_DISCUSSION: Strategy for handling contracts with very many items – fetch all items, or cap at a certain number for performance reasons during initial filtering?]
*   **Handling updates to existing contracts (e.g., auction prices)**: Avoid full periodic re-scans of all items for all contracts. Instead, use a targeted re-fetch strategy:
    1.  Poll regional contract list endpoints (`/contracts/public/{region_id}/`) respecting ESI cache timers.
    2.  For each contract from the list:
        a.  If new, fetch its items via `/contracts/public/items/{contract_id}/`.
        b.  If existing and active (not expired): Check if its item data is stale based on the ESI cache timer for its items OR a defined internal refresh interval (e.g., "check active auctions every 15 minutes") by comparing against our internally stored `last_esi_check` timestamp for that contract's items.
        c.  If item data is deemed stale, re-fetch items from `/contracts/public/items/{contract_id}/` (respecting its ESI cache timer and using ETags).
    3.  Update the Hangar Bay database if changes in items (e.g., auction bid price) are detected. This balances data freshness with ESI politeness and processing load.
*   [NEEDS_DECISION: How to resolve and store/display location names (stations, structures)? Store IDs and resolve on display, or resolve during ingestion and store names? Consider frequency of name changes.]
*   [NEEDS_DECISION: Same for issuer names.]
*   [CROSS_FEATURE_NOTE: F002 (Ship Browsing) requires efficient backend keyword searching on location names. While F001 provides `start_location_id`, a separate, periodically updated cache (e.g., `location_details_cache`) mapping `location_id` (stations, structures) to their current `name` will be necessary. This cache would be populated from relevant ESI `/universe/` endpoints and is a dependency for F002's full search functionality.]
