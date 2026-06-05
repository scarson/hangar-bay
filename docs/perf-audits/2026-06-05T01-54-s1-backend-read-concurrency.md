# Performance Audit — Concurrency & Parallelization (backend read path)

Scope: `GET /contracts/` read path on a single asyncio event loop (FastAPI 0.115 async routes, SQLAlchemy[asyncio] 2.0 + asyncpg, redis.asyncio, httpx). Static-only; structural arguments. No fabricated numbers.

Dimension: concurrency & parallelization only. Both directions run:
- (a) EXPLOIT — serial work over independent items / missing pipelining.
- (b) DEFEND — blocking-in-async, lock contention, oversized critical sections, pool exhaustion, event-loop stalls.

---

### [MAJOR impact] Connection pool defaults (5+10) cap concurrent in-flight queries per worker; surplus requests serialize on `pool_timeout`
**Location:** `app/backend/src/fastapi_app/db.py:12-18` (`create_async_engine`, no pool args)

**Problem:** `create_async_engine` is called with `echo` and `future` only — no `pool_size`, `max_overflow`, or `pool_timeout`. SQLAlchemy's async engine uses `AsyncAdaptedQueuePool` with the default `pool_size=5` and `max_overflow=10`, i.e. a hard ceiling of 15 concurrent checked-out connections per process. Every `GET /contracts/` checks out one connection from `get_db()` (`db.py:49`) and holds it for the *duration of the whole handler* — which spans **two** sequential awaits (count query at `contract_service.py:134`, then the data query at `contract_service.py:175`) plus the per-request logging and pydantic validation in between. On an IO-bound async service the whole point is to keep hundreds of requests in flight on one loop; here, once 15 requests are mid-query, request #16 blocks inside the pool checkout waiting up to the default `pool_timeout` (30s) for a connection to free, then raises `TimeoutError` if none does. The event loop is not parked (the wait is async), but effective query concurrency is clamped far below what a single asyncpg-backed loop can sustain.

**Impact:** Under N concurrent `GET /contracts/` requests with N > 15, the excess queue on connection checkout regardless of how fast Postgres answers; tail latency degrades sharply and at sustained overload requests fail with pool-timeout 500s. This is the dominant concurrency ceiling on the read path and it is invisible at low load (the calibration "realistic load" of many concurrent users is exactly where it bites).

**Confidence:** Strong-static (pool defaults are documented SQLAlchemy behavior; the absence of overrides is verified in source and via grep across the package — no `pool_size`/`max_overflow`/`pool_timeout` anywhere).

**Effort:** Localized — add `pool_size`, `max_overflow`, and `pool_timeout` (and ideally `pool_pre_ping`) to the single `create_async_engine` call, sized to expected per-worker concurrency and the Postgres `max_connections` budget (pool_size × workers must stay under the server limit).

**Verification plan:** Structural: each request holds exactly one connection for two round-trips; concurrent-request count above `pool_size + max_overflow` must wait on checkout. Correctness guard: pool sizing changes capacity, not results — pin behavior by asserting the same response body/ordering for a single request before and after, and load-test at N = 2×(pool_size+max_overflow) to confirm the checkout-wait wall moves rather than the data changing. Cross-check pool_size × worker_count ≤ Postgres `max_connections` to avoid pushing the bottleneck onto the server.

---

### [MAJOR impact] Per-request synchronous structlog rendering + blocking `sys.stdout` write inside the async handler parks the event loop for every concurrent request
**Location:** `app/backend/src/fastapi_app/core/logging.py:58-90` (sync `StreamHandler(sys.stdout)`, JSONRenderer); emitted from `contract_service.py:49` (`logger.info` per request), `:139` and `:190` (`log_key_event`), plus the `RequestIDMiddleware` context binds at `logging.py:41-42`.

**Problem:** Logging is configured with a stdlib `logging.StreamHandler(sys.stdout)` and structlog's `JSONRenderer`. Both the JSON serialization and the `write()` to stdout are **synchronous and run on the event-loop thread**. The `/contracts/` path emits at least two structured records per request (the "Starting contract search" info at `contract_service.py:49` and one `log_key_event` at `:139`/`:190`), each carrying a dict of search terms that must be JSON-encoded inline. Per the async-asyncio lens ("logging to a blocking file handler ... with no async adapter") and the web-frameworks lens ("per-request log serialization on a hot route"), every such call blocks the single loop for the encode+write duration, stalling *all* other concurrently-waiting coroutines for that slice. When stdout is a pipe to a slow/backpressured collector (container log driver, sidecar), the `write` can block on a full pipe buffer — turning a structured log line into a multi-millisecond loop stall multiplied across every concurrent request.

**Impact:** Event-loop stall proportional to (records/request × encode+write cost), paid on the hottest read endpoint and synchronized across all in-flight requests on the worker. Symptom is loop latency that does not improve as concurrency rises — the async-asyncio "hidden blocking that parks the loop" signature.

**Confidence:** Strong-static for the synchronous-handler structure (StreamHandler + sync JSONRenderer, no queue/async adapter). Heuristic for per-occurrence magnitude (depends on payload size and whether stdout is a fast TTY or a backpressured pipe).

**Effort:** Contained — route stdlib logging through a non-blocking sink: a `logging.handlers.QueueHandler` + `QueueListener` (listener owns the blocking `StreamHandler` on a background thread) so the loop thread only enqueues, or move emission off-loop. No call-site changes required if done at handler config in `setup_logging`.

**Verification plan:** Structural: the handler is synchronous and is invoked from within `async def get_contracts`; therefore its encode+write executes on the loop thread. Correctness guard: switching to a `QueueHandler`/`QueueListener` must preserve record content and ordering-per-logger — pin by capturing emitted JSON records before/after for an identical request and asserting field-for-field equality; verify no records are dropped at shutdown (listener `.stop()` flush) so log completeness is unchanged.

---

### [MINOR impact] Redundant blocking `logger.info` on the zero-result early-return path adds a second synchronous render before returning
**Location:** `app/backend/src/fastapi_app/services/contract_service.py:137-152`

**Problem:** On the `total == 0` early-return branch the handler still performs a full `log_key_event` (`:139`) — a second synchronous JSON render+write — in addition to the entry-time `logger.info` at `:49`. This compounds the loop-stall described above specifically on empty-result queries (a common case for narrow filters/search). It is the same root cause as the finding above, scoped to an extra emission on a branch that otherwise does almost no work, so the logging overhead is proportionally the largest share of that request's loop time.

**Impact:** Extra synchronous encode+write on the loop thread per zero-result request; small in isolation but it is pure logging overhead on an otherwise-cheap path, and it scales with the frequency of empty-result searches.

**Confidence:** Strong-static.

**Effort:** Localized — subsumed entirely by the `QueueHandler`/`QueueListener` fix in the finding above; no separate change needed once logging is off-loop. Listed separately only to note the branch.

**Verification plan:** Same off-loop-logging guard as above; confirm the empty-result response body (`PaginatedResponse(total=0, ...)`) is byte-identical before/after.

---

## Considered and explicitly NOT flagged

- **Count query then data query (`contract_service.py:134` → `:175`) are NOT parallelizable.** The `total == 0` check at `:137` gates an early return that skips the data query entirely — a genuine data/control dependency. Issuing both with `asyncio.gather` would run a data query that the count proves unnecessary and, more importantly, both coroutines share the **same `AsyncSession`**, which is not safe for concurrent operations (asyncpg connection state is single-in-flight; concurrent `execute` on one session raises / corrupts state). This would be a correctness regression, not a win. Correctly left sequential.

- **`selectinload(Contract.items)` (`contract_service.py:172`, `contracts.py:50`)** issues a second batched query for items, but it is SQLAlchemy's intended single-extra-query eager load (not N+1) and runs on the same session sequentially by necessity. Not a concurrency finding.

- **`time.time()` (`contract_service.py:46`, `:138`, `:180`, `:212`)** is non-blocking (vDSO clock read); not an event-loop stall. Style only — not reported.

- **No `command_timeout` on asyncpg queries / no `asyncio.timeout()` around `db.execute`.** This is a resilience/pool-protection concern (a slow query pins a pooled connection, worsening the pool-exhaustion finding) more than a throughput concurrency defect; noting it as adjacent to the pool finding rather than as a separate concurrency finding, since on its own it changes failure behavior, not steady-state concurrency.

- **`RequestIDMiddleware` via `BaseHTTPMiddleware` (`logging.py:27-47`)** runs on every request and Starlette's `BaseHTTPMiddleware` carries known per-request overhead (wraps the call in an anyio task group / streaming bridge). It is real per-request cost but it does not park the loop or serialize requests against each other — bounded, cross-cutting, and below the reporting bar for this dimension. Noted, not flagged.

---

## Suspected Bugs (for follow-up)

- **Duplicate `get_db_session_factory` definition** at `db.py:30-34` and `db.py:37-41` (the second shadows the first — identical, so harmless) and **`Base = declarative_base()` defined twice** at `db.py:6` and `db.py:27` (the second rebinds `Base`; models import-order dependent). Not a concurrency issue but a latent correctness/maintenance hazard.
- **`create_db_tables()` drops and recreates all tables on every startup** (`main.py:128-137`, called from `lifespan` at `:45`). Destructive on a shared/prod DB; not in this dimension but flagged for follow-up.
