# Hangar Bay - Performance Specification

## 1. Introduction & Philosophy

*   **1.1. Importance of Performance:**
    *   User experience impact: responsiveness, perceived speed.
    *   Efficiency of ESI API interactions.
    *   Scalability with growing data and user load.
*   **1.2. Guiding Principles:**
    *   **Measure, Don't Guess:** Prioritize profiling and identifying actual bottlenecks before optimizing.
    *   **Optimize Critical Paths:** Focus efforts on user-facing critical paths and high-frequency operations.
    *   **Balance:** Strive for optimal performance without undue complexity or premature optimization.
    *   **Continuous Improvement:** Performance is an ongoing concern, to be monitored and refined.
*   **1.3. AI Coding Assistant Role:**
    *   This document guides the AI in generating performant code by default.
    *   AI should proactively consider performance implications based on these guidelines.
    *   AI should assist in identifying potential performance issues and suggesting optimizations.

## 2. Performance Targets & Metrics

*(Specific values are placeholders and should be refined based on testing and requirements.)*

*   **2.1. API Response Times (Backend - FastAPI):**
    *   **P95 (95th percentile):** < 200ms for most read operations under typical load.
    *   **P99 (99th percentile):** < 500ms for most read operations under typical load.
    *   Write operations: Target < 500ms, acknowledging potential DB/ESI write latencies.
    *   *AI Guidance:* When generating API endpoints, consider query complexity, data processing, and potential for caching to meet these targets.
*   **2.2. Frontend Load & Interaction Times (Angular):**
    *   **First Contentful Paint (FCP):** < 1.8 seconds.
    *   **Largest Contentful Paint (LCP):** < 2.5 seconds.
    *   **Time to Interactive (TTI):** < 5 seconds.
    *   **Interaction to Next Paint (INP):** < 200ms for most interactions.
    *   *AI Guidance:* When generating components and pages, consider lazy loading, bundle sizes, change detection strategy, and efficient rendering.
*   **2.3. Resource Utilization:**
    *   **Backend Service (FastAPI):** Define acceptable CPU and memory usage under typical load.
    *   **Frontend Bundle Sizes:** Main bundle < 500KB, lazy-loaded modules < 200KB.
    *   *AI Guidance:* Promote code splitting, tree shaking, and efficient library use.
*   **2.4. Database Query Performance (PostgreSQL):**
    *   Most common queries: < 50ms.
    *   Complex analytical queries (if any): < 1s.
    *   *AI Guidance:* Ensure generated SQLAlchemy queries are efficient, use appropriate indexing, and avoid N+1 problems.
*   **2.5. ESI Interaction Latency:**
    *   Acknowledge ESI API has its own latency. Hangar Bay's performance focus is on minimizing *additional* latency introduced by its own processing and optimizing how it handles ESI responses.

## 3. Performance Design Principles & Patterns

### 3.1. Backend (FastAPI, Python, Valkey, PostgreSQL)

*   **Asynchronous Operations:**
    *   **AI Implementation Pattern:** Always use `async def` for FastAPI route handlers and service methods involving I/O (ESI calls, database queries). Utilize `await` for these operations.
    *   Example: `async def get_esi_data(): response = await http_client.get(...)`
*   **Efficient Data Serialization/Deserialization:**
    *   Use Pydantic models for request/response validation and serialization.
    *   *AI Guidance:* Ensure Pydantic models are well-defined and used consistently.
*   **Caching (Valkey):**
    *   **Strategy:** Cache frequently accessed, slowly changing ESI data and computationally expensive results. Use cache-aside pattern.
    *   **Key Naming:** Consistent and clear cache key naming conventions.
    *   **Invalidation:** Implement appropriate TTLs and consider event-based invalidation if necessary.
    *   **AI Implementation Pattern:**
        *   Check cache before ESI/DB call: `cached_data = await valkey_client.get(cache_key)`
        *   Store in cache after fetching: `await valkey_client.set(cache_key, data, ex=TTL_SECONDS)`
*   **Database Query Optimization (SQLAlchemy):**
    *   **Indexing:** Ensure all columns used in `WHERE` clauses, `JOIN` conditions, and `ORDER BY` are indexed.
        *   *AI Guidance:* When defining SQLAlchemy models, AI should suggest potential indexes based on anticipated query patterns.
    *   **Avoid N+1 Queries:** Use `selectinload` or `joinedload` for eager loading of relationships.
        *   **AI Implementation Pattern:** `stmt = select(models.Contract).options(selectinload(models.Contract.items))`
    *   **Connection Pooling:** Ensure FastAPI is configured to use SQLAlchemy's connection pooling effectively.
    *   **Efficient Queries:** Use specific columns (`select(Model.col1, Model.col2)`) instead of `select(Model)` if not all columns are needed.
*   **Background Tasks (FastAPI `BackgroundTasks`):
    *   For operations that don't need to be completed before returning a response (e.g., sending notifications, non-critical logging).
    *   *AI Guidance:* Identify opportunities for background tasks to improve endpoint responsiveness.

### 3.2. Frontend (Angular)

*   **Change Detection Strategy:**
    *   **AI Implementation Pattern:** Default to `ChangeDetectionStrategy.OnPush` for components to minimize change detection cycles. Trigger manually with `markForCheck()` when necessary.
*   **Lazy Loading:**
    *   **AI Implementation Pattern:** Use lazy loading for Angular modules to reduce initial bundle size.
    *   Example (routing): `{ path: 'feature', loadChildren: () => import('./feature/feature.module').then(m => m.FeatureModule) }`
*   **Tree Shaking & Bundle Optimization:**
    *   Ensure Angular CLI build optimizations are enabled.
    *   Import only necessary functions/modules from libraries.
*   **Virtual Scrolling (`@angular/cdk/scrolling`):
    *   **AI Implementation Pattern:** For long lists of items, use `cdk-virtual-scroll-viewport` to render only visible items.
*   **`trackBy` for `*ngFor`:**
    *   **AI Implementation Pattern:** Always use a `trackBy` function with `*ngFor` to improve rendering performance for lists, especially when items are reordered or modified.
    *   Example: `<div *ngFor="let item of items; trackBy: trackById">{{ item.name }}</div>`
                   `trackById(index: number, item: Item): string { return item.id; }`
*   **Optimizing Angular Material Components:**
    *   Be mindful of the performance characteristics of complex Material components.
*   **Efficient State Management (e.g., NgRx, Akita, or services with BehaviorSubjects):
    *   Minimize data duplication and ensure efficient data flow.
    *   Use selectors to derive and memoize data.
*   **Debouncing/Throttling User Inputs:**
    *   For inputs that trigger API calls (e.g., search boxes), use `debounceTime` or `throttleTime` with RxJS.

### 3.3. Data Handling (General)

*   **Pagination:**
    *   Implement for all API endpoints returning lists of data.
    *   Use on the frontend to display large datasets.
    *   *AI Guidance:* Default to paginated responses for list endpoints.
*   **HTTP Compression:**
    *   Ensure server (Uvicorn/Gunicorn) is configured for Gzip/Brotli compression.
*   **Data Minimization:**
    *   Fetch and transmit only the data necessary for a given view or operation.

## 4. Performance Testing & Profiling

(Refer to `test-spec.md` for general testing types and CI/CD integration)

*   **4.1. Tools:**
    *   **Backend:**
        *   Load Testing: `locust`
        *   Benchmarking: `pytest-benchmark`
        *   Profiling: Python's `cProfile`, `py-spy`
    *   **Frontend:**
        *   Browser DevTools (Lighthouse, Performance tab, Network tab)
        *   WebPageTest
    *   **Database (PostgreSQL):**
        *   `EXPLAIN ANALYZE <query>`
*   **4.2. Methodologies:**
    *   **Load Testing:** Simulate concurrent users to identify bottlenecks under stress.
    *   **Stress Testing:** Push the system beyond normal operating conditions.
    *   **Soak Testing:** Evaluate stability over extended periods.
    *   **Profiling:** Identify hot spots in code (CPU and memory).
    *   **Benchmarking:** Measure performance of specific functions/components before and after changes.
*   **4.3. AI Coding Assistant Role in Testing:**
    *   *AI Guidance:* AI can generate boilerplate for `locust` test scripts or `pytest-benchmark` tests.
    *   AI can be prompted to analyze code snippets for potential performance issues that warrant profiling.

## 5. Monitoring & Alerting

(Refer to `observability-spec.md` for detailed monitoring setup)

*   **5.1. Key Performance Indicators (KPIs) to Monitor:**
    *   API response times (P95, P99, error rates).
    *   Frontend load times (FCP, LCP, TTI).
    *   System resource usage (CPU, memory, disk I/O).
    *   Database query latencies.
    *   Cache hit/miss ratios.
*   **5.2. Alerting:**
    *   Set up alerts for significant deviations from performance targets or sudden spikes in error rates.

## 6. Common Anti-Patterns & Pitfalls

*   **Backend:**
    *   Synchronous blocking calls in `async` code.
    *   Fetching excessive data from the database ("SELECT *").
    *   Inefficient loops or algorithms for data processing.
    *   Lack of database indexing for queried fields.
    *   Over-caching or under-caching; incorrect cache TTLs.
*   **Frontend:**
    *   No `trackBy` in `*ngFor`.
    *   Not using `OnPush` change detection where appropriate.
    *   Large initial bundles due to lack of lazy loading.
    *   Subscribing to Observables without unsubscribing (memory leaks).
    *   Frequent, un-debounced API calls from user interactions.
*   **AI Guidance:** AI should be explicitly instructed to avoid these anti-patterns.

## 7. AI Implementation Guidance Summary

*   **AI Actionable Checklist (General):**
    *   [ ] When generating backend endpoints, apply async patterns, consider caching, and optimize database queries.
    *   [ ] When generating Angular components, use `OnPush`, `trackBy`, consider lazy loading, and optimize for bundle size.
    *   [ ] For list data, implement pagination by default.
    *   [ ] Proactively identify and avoid common performance anti-patterns.
    *   [ ] Suggest areas where performance testing or profiling would be beneficial.

## 8. Cross-References

*   `design-spec.md`: For overall application design and UI/UX responsiveness goals.
*   `test-spec.md`: For performance testing methodologies and integration into the test suite.
*   `observability-spec.md`: For details on performance monitoring tools and practices.
*   Individual Feature Specifications: May contain feature-specific performance requirements.
