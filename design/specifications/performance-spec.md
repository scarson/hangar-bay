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
*   **2.2. Frontend Load & Interaction Times (React):**
    *   **First Contentful Paint (FCP):** < 1.8 seconds.
    *   **Largest Contentful Paint (LCP):** < 2.5 seconds.
    *   **Time to Interactive (TTI):** < 5 seconds.
    *   **Interaction to Next Paint (INP):** < 200ms for most interactions.
    *   *AI Guidance:* When generating components and pages, consider route-level code splitting, bundle sizes, re-render behavior, and efficient rendering.
*   **2.3. Resource Utilization:**
    *   **Backend Service (FastAPI):** Define acceptable CPU and memory usage under typical load.
    *   **Frontend Bundle Sizes:** Main bundle < 500KB, lazy-loaded route chunks < 200KB.
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

### 3.2. Frontend (React)

*   **Minimizing Re-renders:**
    *   **AI Implementation Pattern:** Keep state minimal and colocated; derive values during render rather than duplicating them in state. Reach for memoization (`React.memo`, `useMemo`, `useCallback`) only where profiling shows a hot re-render path — do not sprinkle it by default.
*   **Route-Level Code Splitting:**
    *   Already active: TanStack Router's Vite plugin runs with `autoCodeSplitting: true` (see `app/frontend/web/vite.config.ts`), so each route file is split into its own lazy-loaded chunk.
    *   **AI Implementation Pattern:** Keep route components and their heavy dependencies inside the route files so the automatic split stays effective; do not re-import route-only dependencies from shared modules.
*   **Tree Shaking & Bundle Optimization:**
    *   The Vite production build (`npm run build`) performs tree-shaking and minification via Rollup and esbuild; no additional build configuration is required.
    *   Import only necessary functions/modules from libraries.
*   **Virtual Scrolling (long lists):**
    *   **Requirement:** For long lists of items, render only the visible window (virtualization). This requirement carries forward from the original Angular design (which prescribed `@angular/cdk/scrolling`); a React virtualization library has NOT been selected — the choice is deferred to the `/impeccable` design phase, when list rendering performance is designed. Do not introduce one ad hoc; the current paginated table (max page size 100) does not need it.
*   **Stable `key` props for lists:**
    *   **AI Implementation Pattern:** Always key rendered list items with a stable domain identifier so React can reconcile reordered or modified lists efficiently; never use the array index for dynamic lists.
    *   Example: `{contracts.map((c) => <ContractRow key={c.contract_id} contract={c} />)}`
*   **Design-System Component Cost:**
    *   Be mindful of the rendering cost of complex design-system components built during the `/impeccable` phase.
*   **Efficient State Management:**
    *   Server state lives in TanStack Query (caching, request deduplication, background refetch); filter/sort/pagination state lives in typed URL search params via TanStack Router. No global client-state store exists (per the Milestone-1 spec, none is added until a milestone needs one).
    *   Minimize data duplication: components must not hold shadow copies of URL or server state.
*   **Debouncing/Throttling User Inputs:**
    *   For text inputs that trigger API calls (e.g., search boxes), debounce before the query fires; TanStack Query deduplicates identical in-flight requests, and keystroke-driven URL updates use `navigate({ replace: true })` so they do not pollute history.

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
    *   Index-based or unstable `key` props on dynamic lists.
    *   Unnecessary re-renders (state lifted higher than needed; unstable object/array/function props defeating memoization).
    *   Large initial bundles from defeating route-level code splitting (e.g., importing route-only heavy dependencies into shared modules).
    *   Effects without cleanup (leaked timers, event listeners, subscriptions — memory leaks).
    *   Frequent, un-debounced API calls from user interactions.
    *   Fetching outside the generated API client + TanStack Query hooks (loses caching/deduplication and duplicates server state).
*   **AI Guidance:** AI should be explicitly instructed to avoid these anti-patterns.

## 7. AI Implementation Guidance Summary

*   **AI Actionable Checklist (General):**
    *   [ ] When generating backend endpoints, apply async patterns, consider caching, and optimize database queries.
    *   [ ] When generating React components, use stable list `key`s, avoid unnecessary re-renders, keep route-level code splitting effective, and optimize for bundle size.
    *   [ ] For list data, implement pagination by default.
    *   [ ] Proactively identify and avoid common performance anti-patterns.
    *   [ ] Suggest areas where performance testing or profiling would be beneficial.

## 8. Cross-References

*   `design-spec.md`: For overall application design and UI/UX responsiveness goals.
*   `test-spec.md`: For performance testing methodologies and integration into the test suite.
*   `observability-spec.md`: For details on performance monitoring tools and practices.
*   Individual Feature Specifications: May contain feature-specific performance requirements.
