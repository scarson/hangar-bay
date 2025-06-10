---
ReviewID: PREMORTEM-20250610-002
Date: 2025-06-10
Subject: Phase 02 Backend F001 Public Contract Aggregation
RelatedTasks:
  - plans/implementation/phase-02-backend-f001-public-contract-aggregation/02.1-esi-client-public.md
  - plans/implementation/phase-02-backend-f001-public-contract-aggregation/02.2-data-models-f001.md
  - plans/implementation/phase-02-backend-f001-public-contract-aggregation/02.3-background-aggregation-service.md
  - plans/implementation/phase-02-backend-f001-public--contract-aggregation/02.4-api-endpoints-f001.md
Participants: USER, Cascade
ReviewRounds: 3 (2x "Outside the Box" + 1x Formal Pre-Mortem)
PreviousPreMortemReview: N/A
NextPreMortemReview: [Phase 03 Pre-Mortem](./phase-03-frontend-core-infra-pre-mortem.md)
---

## 0. Human Note to Human Reviewer
This Phase 02 pre-mortem review was conducted after the Phase 03 and represents a significant evolution of the review process. It uses a template that is based on the Phase 03 pre-mortem review template, but significantly enhanced with innovations from the more recent pre-mortems and a prompt for improvements based on the prompt "You correctly noted that "A document's true value, especially for learning, comes from its clarity, detail, and the explicit connections it draws between problems and solutions. While the current pre-mortem captures the what, I can enhance it to better explain the why and how, making it a more powerful learning tool for my future self and for the team.'", so the template update should take into consideration how to guide Cascade to include that type of information in future pre-mortem reviews."

## 1. Pre-Mortem Review Summary

This document summarizes the results of a multi-stage pre-mortem review of the Phase 02 backend implementation plans for the F001 public contract aggregation feature. The review process involved several iterative loops, including "outside-the-box" creative thinking and a formal pre-mortem analysis, guided by the "Sources of Inspiration" framework. The primary objective was to proactively identify and mitigate potential failures, risks, and scalability challenges before development. The desired end-state is a highly resilient, scalable, maintainable, and operationally robust backend system.

## 2. Imagining Failure: Key Risks Identified

*(This section synthesizes potential problems identified across all review loops for each task.)*

*   **Task 02.1: ESI API Client**
    *   **Risk 1 (Stalled Aggregation):** An excessively long ESI rate limit reset period (`X-Esi-Error-Limit-Reset`) could cause the aggregation service to stall for extended periods, creating significant data staleness.
    *   **Risk 2 (Performance Degradation):** Frequent unavailability of the Valkey cache, while handled gracefully, would revert the system to making uncached ESI calls, dramatically increasing load on ESI and slowing down aggregation.
    *   **Risk 3 (Data Parsing Failures):** Unexpected changes in the ESI API's data structure (e.g., missing fields, new enum values) could cause parsing errors that crash the client or lead to incomplete data ingestion.
    *   **Risk 4 (Resource Leaks):** Improper lifecycle management of the shared `httpx.AsyncClient` could lead to resource leaks or connection exhaustion under sustained load.

*   **Task 02.2: Data Models & Database**
    *   **Risk 1 (Schema Drift):** The local database schema could diverge from the ESI source of truth over time, leading to data integrity issues or constraint violations when ESI introduces breaking changes.
    *   **Risk 2 (Brittle Data Handling):** The data mapping logic could fail on unexpected `null` values from ESI for fields defined as non-nullable in the database, crashing the upsert process.
    *   **Risk 3 (Migration Failures):** Poorly tested or managed Alembic migrations could cause deployment failures, data corruption, or application downtime.
    *   **Risk 4 (Scalability Bottleneck):** Database indexes designed for initial data volumes may become inefficient at a 10x scale, leading to slow API queries and aggregation performance degradation.
    *   **Risk 5 (Unmanaged Data Growth):** Without a long-term archival or pruning strategy, the `contracts` table could grow indefinitely, impacting storage costs and query performance (The "Data's Lifecycle" problem).

*   **Task 02.3: Background Aggregation Service**
    *   **Risk 1 (Zombie Aggregator):** A silent failure in the concurrency lock release mechanism (e.g., due to a cache error in a `finally` block) could prevent the aggregator from ever running again.
    *   **Risk 2 (Poison Pill Data):** A single malformed contract from ESI could repeatedly crash the processing logic for an entire region, preventing any further updates for that region.
    *   **Risk 3 (Scheduler Failure):** The `APScheduler` could fail silently or stop triggering jobs, halting all data aggregation without obvious errors until data becomes noticeably stale.
    *   **Risk 4 (Database Contention):** Inefficient or overly large batch upsert operations could cause database deadlocks or high CPU/IO load, impacting the performance of the entire application.

*   **Task 02.4: API Endpoints**
    *   **Risk 1 (Denial of Service):** Malicious or poorly formed API requests with specific filter combinations could create unexpectedly slow database queries, consuming server resources and impacting availability.
    *   **Risk 2 (Pagination Performance Collapse):** The standard `OFFSET`-based pagination will become progressively slower as the `contracts` table grows, leading to a poor user experience.
    *   **Risk 3 (Obscured Failures):** The resilient design choice to return `null` for a `ship_name` when its `type_id` is missing from the cache is good, but without clear, specific logging, it becomes an "Operator's Nightmare" to diagnose the root cause of the data gap.
    *   **Risk 4 (Cross-Phase Friction):** A mismatch between the backend API contract (filters, response objects) and the frontend's expectations could cause significant integration delays and rework.

## 3. Root Causes & Likelihood/Impact Assessment

*   **Problem 1: Over-reliance on External Service Stability & Predictability**
    *   **Root Cause(s):** Initial plans not fully accounting for the realities of distributed systems: network latency, dependency failures (Cache, ESI), unpredictable API behavior (rate limits, schema changes), and data inconsistencies.
    *   **Likelihood:** High.
    *   **Impact:** High (Can lead to data staleness, service crashes, and poor reliability).

*   **Problem 2: Fragile Data Processing & State Management**
    *   **Root Cause(s):** Background job logic not sufficiently isolating failures (e.g., "poison pill" data). Critical mechanisms like concurrency locking lacking robust error handling for their own state management (releasing the lock).
    *   **Likelihood:** Medium.
    *   **Impact:** High (A single bad item or a transient cache error can halt all data processing indefinitely, creating a "zombie" service).

*   **Problem 3: Insufficient Planning for Scalability and Long-Term Data Lifecycle**
    *   **Root Cause(s):** Designs prioritizing initial implementation simplicity (e.g., sequential processing, basic pagination) without addressing clear future bottlenecks. Lack of a concrete plan for managing data growth over the system's lifetime.
    *   **Likelihood:** High (Inevitable in a successful application).
    *   **Impact:** High (Leads to costly re-architecting, performance degradation, and increased operational costs).

*   **Problem 4: Lack of Operational Empathy in Design ("Operator's Nightmare")**
    *   **Root Cause(s):** Task plans focusing on the "happy path" without mandating the necessary structured logging and observability for failure modes. Not thinking through how a person on-call would diagnose a problem at 3 AM.
    *   **Likelihood:** High.
    *   **Impact:** High (Turns minor issues into prolonged outages due to difficult and time-consuming debugging).

*   **Problem 5: Configuration Management Complexity**
    *   **Root Cause(s):** The introduction of multiple new configuration parameters (region lists, ship group IDs, scheduler intervals, cache settings) creates risk of misconfiguration during deployment, leading to unexpected behavior that may not be immediately obvious.
    *   **Likelihood:** Medium.
    *   **Impact:** Medium (Can cause the aggregator to fetch the wrong data, or not run at all, but is typically fixable with a configuration change once identified).

## 4. Assumptions and Dependencies

This system design and its mitigations rely on the following core assumptions and external dependencies:

*   **ESI API Stability & Contract:** Assumes the EVE Swagger Interface (ESI) for public contracts will remain largely stable in terms of endpoint availability, data structures, and rate limiting behavior. Significant unannounced changes could break the client or data models.
*   **Valkey Cache Availability & Performance:** Assumes the Valkey cache service is reliably available and performs within expected latency for ETag caching and concurrency locking.
*   **Database Availability & Performance:** Assumes the PostgreSQL database is reliably available and performs within expected latency for reads and batch upserts.
*   **Infrastructure Stability:** Assumes the underlying hosting environment (network, compute, storage) is stable.
*   **Correctness of Configuration:** Assumes critical environment variables (ESI URLs, region lists, ship group IDs, database credentials, cache connection strings, scheduler intervals) are correctly configured at deployment. Misconfiguration is a significant operational risk.
*   **FastAPI & SQLAlchemy Ecosystem Compatibility:** Assumes continued compatibility and stability between the major versions of FastAPI, SQLAlchemy, Pydantic, `httpx`, and `APScheduler` used in the project.
*   **Frontend Data Requirements:** Assumes the current understanding of data required by the frontend for F001 (as reflected in API schemas) is accurate and won't drastically change without corresponding backend API updates.

## 5. Implications for Testing Strategy

This pre-mortem directly informs the testing strategy required to validate our mitigations and ensure system robustness.

*   **Resilience & Failure Mode Testing:**
    *   **Cache Unavailability:** Integration tests must simulate Valkey being unavailable to verify that the ESI client gracefully degrades (makes uncached calls) and that the aggregation service aborts safely (if it can't acquire a lock).
    *   **"Poison Pill" Injection:** Create test fixtures with malformed contract data (e.g., unexpected nulls, incorrect data types) and verify the aggregation service logs the error for that specific contract but continues processing the rest of the region.
    *   **ESI Rate Limiting:** Use `pytest-httpx` to simulate ESI `420` error responses and verify that the client correctly waits for the duration specified in the `X-Esi-Error-Limit-Reset` header.
    *   **Concurrency Lock:** Write a test that attempts to trigger the aggregation job while it is already running to confirm the lock prevents concurrent execution.

*   **Data & Schema Validation Testing:**
    *   **Schema Drift:** Create tests that pass an ESI response with extra, unexpected fields to the data mapping logic to ensure it doesn't crash.
    *   **Data Integrity:** Include tests that use a variety of contract types (item exchange, auction, courier) to ensure the data models and upsert logic are robust.

*   **Performance & Scalability Testing:**
    *   **API Load Testing:** Use a tool like Locust to load test the `/api/v1/contracts/ships` endpoint, particularly with filters and high page numbers, to identify potential query bottlenecks.
    *   **Aggregation Benchmarking:** Measure the duration of the aggregation job with a representative data load to establish a performance baseline.

*   **Configuration Testing:**
    *   Test the application's startup behavior with invalid or missing environment variables to ensure it fails fast with clear error messages.

## 6. Monitoring and Observability Requirements

To ensure operational stability and rapid troubleshooting, the following monitoring and observability capabilities are essential:

*   **Key Metrics to Track:**
    *   **Aggregation Service:**
        *   Job execution duration (overall, per region).
        *   Number of contracts processed/upserted per run.
        *   Number of `EsiTypeCache` entries refreshed/created per run.
        *   ESI API call count and error rate (distinguishing 4xx, 5xx, rate limit errors like 420).
        *   Cache hit/miss ratio for ETag caching.
        *   Concurrency lock acquisition success/failure/wait time.
        *   Number of "poison pill" contracts skipped (logged with contract ID).
        *   Scheduler job success/failure count.
    *   **API Endpoints (`/api/v1/contracts/ships`):**
        *   Request latency (p50, p90, p99).
        *   Request rate (requests per second/minute).
        *   Error rate (distinguishing 4xx and 5xx responses).
        *   Database query time specifically for API requests (if measurable).
    *   **System-Level (via Infrastructure Monitoring):**
        *   CPU, memory, disk I/O, network traffic for the application and database instances.
        *   Cache connection status, memory usage, and eviction rates.
        *   Database connection pool usage and error rates.

*   **Critical Alerts (Examples - Thresholds TBD):**
    *   Aggregation job fails N consecutive times.
    *   Aggregation job duration exceeds X minutes/hours.
    *   ESI API error rate (excluding 404s on optional data) exceeds Y% over Z minutes.
    *   Valkey cache service becomes unavailable or reports high error rates.
    *   API endpoint p99 latency exceeds A milliseconds for B minutes.
    *   API endpoint 5xx error rate exceeds C% over D minutes.
    *   Database connection errors or high query latency detected by the application.
    *   Concurrency lock cannot be acquired/released after multiple retries.
    *   Critical errors logged by the application (e.g., unhandled exceptions, configuration errors at startup).

*   **Structured Logging:**
    *   All log entries should be structured (e.g., JSON) and include a timestamp, log level, service name, correlation ID (if applicable), and relevant context (e.g., region_id, contract_id, endpoint, user_id if future auth is added).
    *   Ensure logs provide clear diagnostic information for all identified failure modes (e.g., specific error from ESI, reason for skipping a contract, cache connection failure details).

## 7. Key Decisions & Changes Resulting from this Review

*The following actionable changes were made to the Phase 02 task files to mitigate the identified risks:*

*   **For Task 02.1 (ESI Client):**
    *   **Actions:** Added notes to consider a max wait threshold for rate limits, actively monitor cache client health, and implement robust validation for incoming ESI response structures.
    *   **Mitigates:** Risk 1 (Stalled Aggregation), Risk 2 (Performance Degradation), Risk 3 (Data Parsing Failures).

*   **For Task 02.2 (Data Models):**
    *   **Actions:** Added notes emphasizing the need to handle unexpected `null` values gracefully, plan for ESI schema evolution, and periodically review database index performance at scale. Reinforced the importance of a long-term data archival/pruning strategy.
    *   **Mitigates:** Risk 1 (Schema Drift), Risk 2 (Brittle Data Handling), Risk 4 (Scalability Bottleneck), Risk 5 (Unmanaged Data Growth).

*   **For Task 02.3 (Background Service):**
    *   **Actions:** Strengthened concurrency lock release logic; added "poison pill" handling to isolate failures; added notes on monitoring scheduler health, tuning database batch sizes, and managing log volume.
    *   **Mitigates:** Risk 1 (Zombie Aggregator), Risk 2 (Poison Pill Data), Risk 3 (Scheduler Failure), Risk 4 (Database Contention).

*   **For Task 02.4 (API Endpoints):**
    *   **Actions:** Added notes for clear logging on data gaps; included future considerations for keyset pagination and query complexity limits; stressed frontend coordination.
    *   **Mitigates:** Risk 1 (DoS), Risk 2 (Pagination Performance Collapse), Risk 3 (Obscured Failures), Risk 4 (Cross-Phase Friction).

## 8. Broader Lessons Learned / Insights Gained

*   **Frameworks Fuel Insight:** The "Sources of Inspiration" framework (Operator's Nightmare, Data's Lifecycle, 10x Scalability, etc.) is a highly effective tool for moving beyond surface-level reviews to uncover deeper, systemic risks.
*   **Resilience is Granular:** True resilience requires handling failures at a granular level—isolating a single bad contract, retrying a failed cache connection, or logging a single missing data point—not just catching top-level exceptions.
*   **Design for Observation:** A system's maintainability is directly proportional to its observability. Planning for structured logging and operational insight must be a first-class citizen in the design process, not an afterthought.

## 9. Impact on Cascade's Understanding & Future Actions

*   **Deepened Understanding:** This process has solidified my understanding of the complex interplay between the different backend components and their dependencies, and the critical importance of designing for failure.
*   **Proactive Framework Application:** I will more proactively apply the "Sources of Inspiration" framework when generating or reviewing future task plans to identify these classes of risk earlier.
*   **Emphasis on Non-Functional Requirements:** I will place a stronger emphasis on non-functional requirements like scalability, resilience, and observability as core deliverables of any implementation plan.
