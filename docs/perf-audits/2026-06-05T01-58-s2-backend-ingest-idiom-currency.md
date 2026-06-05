# Backend Ingest — Framework-Idiom Currency Audit

**Lane:** framework-idiom currency (static-only)
**Date:** 2026-06-05
**Index relied on:** `version-indexes/python.md`, `covered_through: "Python 3.13 / Django 5.0 / SQLAlchemy 2.0 / pandas 2.x / NumPy 2.0"` (built 2026-06-03).
**Profile packs consulted:** `profile-packs/python/async-asyncio.md`, `profile-packs/python/orm-database.md`.

**Currency-coverage caveat:** the version index covers SQLAlchemy 2.0 and asyncio (CPython) well. It does **not** carry a redis-py entry, an httpx entry, an APScheduler entry, or asyncpg-specific fast paths. Findings about those libraries are therefore grounded in the profile packs' general idiom guidance (which repeatedly says "verify against the currency brief for your version") and library API history, not the index. There is no live currency brief in this run, so redis-py / httpx / asyncpg version-specific claims are marked **Heuristic** or **LOW** and flagged for manual currency check, per instructions.

Scope: `esi_client_class.py`, `background_aggregation.py`, `db_upsert.py`, `http_client.py`, `scheduler.py`.

---

### [MAJOR impact] Per-call Redis client created via `from_url` where a pooled shared client is the fast path
**Location:** `services/background_aggregation.py:67` (`_concurrency_lock`); also `esi_client_class.py:71` (managed client in `__aenter__`).
**Problem:** `_concurrency_lock` calls `aioredis.from_url(str(self.settings.CACHE_URL))` on every invocation, then `await redis_client.close()` in `finally` (line 87). `redis.asyncio.from_url` builds a brand-new client backed by a fresh `ConnectionPool`; with no shared pool, each aggregation run pays a full TCP connect + (if configured) AUTH/HELLO handshake to acquire the lock, then tears the pool down. The orm-database pack's recurring theme is "**pool reuse** — a mis-sized or zero-lifetime pool pays TCP + auth overhead on every request" (`orm-database.md:6`, and the connection-pool entry at `:8`); the async pack states the same for clients: "constructing … inside a coroutine … each call allocates a new connection pool, pays TCP (and TLS) handshake cost on every request … The correct pattern is one long-lived client shared across the application lifetime" (`async-asyncio.md:15-21`). The codebase already has a shared cache dependency (`get_cache`, imported at `background_aggregation.py:12` but unused) — the constructor comment at `:45-46` notes the cache client was deliberately removed from the service. So the fast path (inject the pooled client) exists and was discarded.
**Impact:** Current idiom = 1 new pool + connect/handshake per aggregation run for the lock set/delete (2 commands). Fast path = reuse the app's shared pooled `redis.asyncio.Redis`, amortising connect cost to ~zero. Frequency is per-run (interval job, `scheduler.py:39`), so per-occurrence cost is bounded — this is MAJOR not CRITICAL because n = a couple of commands per run, not per-request. Note the ESI client's managed-mode Redis (`esi_client_class.py:71`) is also per-context-manager, but its lifetime spans a whole run, so it is far less wasteful than the lock client.
**Confidence:** Heuristic (idiom grounded in profile packs; redis-py not in the index — flag for manual currency check on redis-py 6.2 pool semantics).
**Effort:** Contained — pass the shared `get_cache` client into the service (the wiring was previously present and removed) and drop the on-demand `from_url`; touches the constructor, the lock manager, and `get_aggregation_service`.
**Verification plan:** Log/trace Redis connection establishment per run (e.g. `CLIENT LIST` count or a connect counter) before/after; confirm lock correctness is preserved (still `set nx=True ex=…` then `delete`).

---

### [MINOR impact] Deprecated `.close()` close idiom on `redis.asyncio.Redis` instead of `.aclose()`
**Location:** `esi_client_class.py:81` (`await self._managed_redis_client.close()`); `services/background_aggregation.py:87` (`await redis_client.close()`).
**Problem:** On the modern unified `redis.asyncio` client (redis-py ≥5.0.1), the async-correct close coroutine is `aclose()`; the bare `close()` name was kept as a deprecated alias that emits a `DeprecationWarning` and is scheduled for removal. The prompt's own framing ("is `aioredis.from_url(...).close()` the current close idiom?") points here: under redis-py 6.2 it is the *legacy* spelling, not the current one. This is the current-idiom mismatch the lane targets, but the cost is correctness/forward-compat, not throughput — closing happens once per run.
**Impact:** No measurable per-run perf delta; flagged as currency drift (deprecated API surface) that will break on a future redis-py major. Negligible aggregate cost.
**Confidence:** LOW (ungrounded — redis-py is not in the index `covered_through`; the `aclose()` deprecation timeline is from library API history, not a brief). Flag for manual currency check against redis-py 6.2 release notes.
**Effort:** Localized — two one-line renames.
**Verification plan:** Run the close path under `-W error::DeprecationWarning` on redis-py 6.2; confirm `close()` warns and `aclose()` does not.

---

### [MINOR impact] Hand-rolled retry/backoff loop instead of httpx transport-level retries
**Location:** `esi_client_class.py:106-126` (the `for attempt in range(max_retries)` loop with `asyncio.sleep(backoff_factor * (2 ** attempt))`).
**Problem:** The retry logic is hand-coded: a manual attempt loop, manual exponential backoff via `asyncio.sleep`, and manual exception capture for `ReadTimeout`/`ConnectError`. The async pack notes that backoff/retry is a place where transport-level mechanisms exist and per-call hand-rolled loops are the anti-idiom (connection/retry handling belongs on the long-lived client/transport, `async-asyncio.md:15-24` and the timeout-hygiene entry `:69-76`). httpx ships `httpx.HTTPTransport`/`AsyncHTTPTransport(retries=N)` for connection-level retry, which would replace the connect-error half of this loop at the transport layer where the shared client lives. Note the 5xx-retry half (lines 109-115) is application-level policy httpx's transport retries do **not** cover (they retry connection failures, not response status), so this cannot be fully delegated — that is why this is MINOR and partly a style boundary.
**Impact:** Per-call within pagination loops; per-occurrence cost is the Python overhead of the manual loop, which is negligible versus the network I/O it guards. The currency issue is idiom drift, not hot-path cost. Bounded — does not move aggregate throughput.
**Confidence:** LOW (httpx not in the index; transport-retry behaviour from library API history — flag for manual currency check on httpx 0.28).
**Effort:** Contained — configure `transport=AsyncHTTPTransport(retries=…)` on the shared client in `http_client.py` and `esi_client_class.py:65`; keep the 5xx/status-retry logic application-side. Per calibration this is borderline style-only; included only because it co-locates retry policy off the long-lived client.
**Verification plan:** Argument-based — confirm connect-failure retries still occur via transport; confirm 5xx retry behaviour is unchanged. No benchmark warranted given negligible cost.

---

## Idioms checked and found current (no finding)

- **SQLAlchemy 2.0 bulk-upsert idiom** (`db_upsert.py:31-56`): uses `pg_insert(table).values(values).on_conflict_do_update(index_elements=…, set_=…)` and `await db.execute(stmt)` — this is exactly the 2.0-current upsert path the index endorses ("`insert().on_conflict_do_update()` (SQLAlchemy) … eliminates the read-then-write round-trip", `orm-database.md:27`; bulk-write entry confirms `execute(insert(), [dicts])` is the 2.0 path superseding `bulk_insert_mappings`). No idiom drift here.
- **Manual batch sizing** (`background_aggregation.py:243-251` contracts `batch_size=500`; `:284-289` items `BATCH_SIZE=50`): the lane asks whether explicit batch sizing is even needed in 2.0 given `insertmanyvalues` + asyncpg executemany. The index says `insertmanyvalues` is automatic and tuned by `insertmanyvalues_page_size` (default 1000) (`version-indexes/python.md:64`, `orm-database.md:27`). The single-statement `on_conflict_do_update().values([many])` path used here is *not* the `executemany`/`insertmanyvalues` path — it is one multi-row VALUES INSERT — so the 500/50 manual chunking is the relevant guard against the PostgreSQL ~65 535 bound-parameter limit (`orm-database.md:27`). With ~22 columns/contract, 500×22 ≈ 11k params (safe); the item batch of 50 is very conservative but correctness-safe. This is **bounded-small-n** and per calibration is **not reported** as a finding — the batch sizes are defensible, not an idiom error. (The item batch of 50 being small is a tuning nit, not a currency issue.)
- **httpx shared-client pattern** (`http_client.py:7-29`): app-lifetime client created once and closed at shutdown via `aclose()` — this is the correct current idiom (`async-asyncio.md:15-21`). No HTTP/2 enabled and no explicit `Limits(...)`, but those are tuning choices outside the currency lane (and the async pack defers limit tuning to the currency brief, `:23-24`), so no finding.
- **`asyncio.sleep` backoff / `asyncio.timeout`**: timeouts are set at the httpx client level (`http_client.py:19`, `esi_client_class.py:68`), which is an accepted current idiom per `async-asyncio.md:69-72`; no `wait_for` misuse present.
- **`import redis.asyncio as aioredis` alias** (`esi_client_class.py:9`, `background_aggregation.py:8`): this is the modern unified client (aioredis-merged-into-redis-py), correctly imported. The alias name `aioredis` is cosmetic only — no finding.

---

## Suspected Bugs (for follow-up)

- **N+1 ESI fetch + per-engine churn (architecture, not idiom-currency):** `background_aggregation.py:256-261` issues one sequential `await get_contract_items(...)` per contract, and `run_aggregation` builds and `dispose()`s a fresh `create_async_engine` every run (`:118`, `:172`). These are throughput concerns but fall under fan-out/concurrency and pool-lifetime architecture, not framework-idiom currency — flagged for the appropriate lane, not chased here.
- **`get_cache` imported but unused** (`background_aggregation.py:12`): dead import; correlates with the MAJOR finding above (the pooled client path was removed).
