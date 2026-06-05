## Execution Cost Map
> Architectural awareness, NOT an optimization to-do list. Not every region here is a problem; some are inherent and fine.

Slice: ESI ingestion / background aggregation, scheduled every 900 s. The dominant
time-shaping fact of an ingestion run is the **count and serialization of external ESI
round-trips**, because every round-trip is a network-latency-bound wait and the code
issues them one-at-a-time (`await` in a `for` loop). Below, each region multiplies how
*often* it happens across a run by the *unit cost* of the operation.

### Run-level round-trip arithmetic (the time budget)
For R regions, P pages/region, N total contracts, M item-bearing contracts, and
ceil(unique_ids/1000) name chunks, one run serially issues roughly:

- contract pages: **sum(P) over regions** GET round-trips (`get_public_contracts`, `all_pages=True`)
- id→name: **ceil(unique_ids / 1000)** POST round-trips
- contract items: **M** GET round-trips, one per item-bearing contract
- DB upserts: **ceil(N/500)** contract statements + **ceil(total_items/50)** item statements

With N in the thousands–tens of thousands and most contracts item-bearing,
**M dominates the round-trip total by one to two orders of magnitude** over every other
category combined. The item-fetch loop is the run's wall-clock budget.

### Likely time-concentration regions

- **Per-contract item fetch loop (`background_aggregation.py:256-280`)** — basis: one
  `await self.esi_client.get_contract_items(...)` per item-bearing contract (`type in
  {item_exchange, auction}`), awaited sequentially inside a Python `for`. Each call is a
  full ESI HTTP round-trip (request + network + response + JSON parse) via
  `get_esi_data_with_etag_caching`. At M = thousands–tens of thousands, this is M serial
  latency waits; at e.g. 100 ms/round-trip and M=10k that is ~1000 s of pure serialized
  wait — larger than the 900 s interval. This single loop almost certainly holds the
  overwhelming majority of run wall-time. — confidence: **High** — also worth the
  `concurrency` lane's attention (independent awaits chained sequentially; a TaskGroup /
  bounded `asyncio.gather` is the structural lever, subject to ESI rate limits).

- **Contract page fetch across regions (`background_aggregation.py:129-133` →
  `esi_client_class.py:182-185, 95-180`)** — basis: `get_public_contracts` runs per region
  in a serial `for region_id`, and *within* each region the `while True` pagination loop
  issues one GET per page serially until `X-Pages` is exhausted. So sum(P) round-trips,
  fully serialized both across regions and across pages. Each page also JSON-parses a
  full-page array and, on cache-miss, writes two Redis keys. Secondary to item fetch in
  magnitude (pages number in the tens–low hundreds vs. M in thousands) but it is the
  run's first serial latency block and the sole producer of N. — confidence: **High** —
  also worth the `concurrency` lane's attention (regions are independent and parallelizable).

- **Per-page ETag/JSON/Redis handling inside `get_esi_data_with_etag_caching`
  (`esi_client_class.py:100-167`)** — basis: every page of every call (contracts, items,
  and the 304 path) does a Redis GET for the cached ETag, then on a 200 a `response.json()`
  full-array parse plus two Redis SETs, or on a 304 a Redis GET of `data_key` plus
  `json.loads`. This is invoked once per page per ESI call, so it scales with
  (sum(P) + M + name-chunks) — i.e. it rides on top of the item-fetch count. Unit cost is
  modest (local Redis + CPython JSON), but the frequency is the same order as the dominant
  round-trip count, making serialization/Redis a real second-order contributor. The 304
  cache-hit path still costs a Redis round-trip + a JSON decode per call — it cuts the
  *network egress* to ESI but not the per-call Python/Redis overhead. — confidence: **Medium**
  — map-only (inherent to the caching design; `serialization` lane could deepen if `json`
  parse of large pages proves hot).

- **In-memory accumulation: `all_contracts_data` and `all_items`
  (`background_aggregation.py:127, 255-276`)** — basis: the run materializes *all* contracts
  across all regions into one list, then builds a parallel `contract_values` list of dicts
  (`:215-241`), then accumulates *all* item rows into `all_items` before any item upsert.
  At tens of thousands of contracts each fanning out to multiple item rows, peak resident
  memory holds the full run in RAM simultaneously (raw ESI dicts + transformed dicts + item
  dicts). Not a wall-time hotspot per se, but a memory-pressure region that scales linearly
  with N and could induce allocator/GC cost at the high end. — confidence: **Medium** —
  map-only (also of interest to the `memory` lane).

- **ID resolution batching (`background_aggregation.py:188-211` →
  `esi_client_class.py:192-216`)** — basis: a single set-union over all contracts builds the
  unique-id set (CPython set ops, O(N)), then `resolve_ids_to_names` issues
  ceil(unique_ids/1000) serial POSTs, each with a `response.json()` parse and a dict build.
  Already well-batched (1000/chunk) so round-trip count is small (typically single digits);
  the O(N) set construction and the per-result dict population are linear-but-cheap. Minor
  relative to item fetch. — confidence: **High** — map-only (this is the *good* shape; named
  here to show it is *not* where time concentrates).

- **DB upserts: contracts batch-500, items batch-50 (`background_aggregation.py:243-289` →
  `db_upsert.py`)** — basis: ceil(N/500) `INSERT ... ON CONFLICT DO UPDATE` statements for
  contracts and ceil(total_items/50) for items, each an `await db.execute` round-trip to
  Postgres over asyncpg, all serialized on one session. The item batch size of **50** means
  for tens of thousands of item rows this is hundreds–thousands of separate DB statements —
  a notable count, though each is local-network/in-DB and far cheaper than an ESI WAN
  round-trip. The small item batch (50 vs. 500 for contracts) multiplies statement count
  10x relative to a 500-row batch. — confidence: **Medium** — map-only (batch-size asymmetry
  is the only structural note; `data-access` lane could deepen).

- **Per-run engine create/dispose (`background_aggregation.py:114-123, 169-173`)** — basis:
  each run calls `create_async_engine` and `engine.dispose()` once, plus the ESIClient
  context manager builds a fresh `httpx.AsyncClient` + Redis client per run
  (`esi_client_class.py:62-81`). One-time per 900 s run, so negligible against the
  thousands of round-trips it wraps; flagged only for completeness. — confidence: **High**
  — map-only.

### Notes for architecture
- The **network round-trip total is the run's time budget**, and within it the
  per-contract item-fetch count (M) is the single term that scales with data volume and is
  fully serialized. Everything else (pages, name chunks, DB statements) is either small in
  count or cheap in unit cost by comparison. If a run ever risks exceeding the 900 s
  interval, the item-fetch loop is mathematically where the budget is spent.
- The shape is "independent awaits issued one at a time": both the region loop and the
  item loop iterate independent ESI resources but `await` each in turn, so the run's
  latency is the *sum* of per-call latencies rather than the *max*. This is the defining
  architectural characteristic of the slice's cost profile — surfaced here descriptively;
  any change would need to respect ESI rate-limiting / error-budget headers.
- ETag caching (304 path) reduces ESI egress and JSON-parse cost on unchanged resources but
  does **not** reduce the *number* of serial round-trips or the per-call Redis/Python
  overhead — a 304 still costs a full request issue + a Redis read + a decode. So caching
  shifts where time goes (less ESI WAN, same call count) rather than collapsing the budget.
- Memory peak and DB-statement count both scale linearly with N because the run is
  whole-batch (accumulate-all-then-flush) rather than streaming per-region or per-page;
  this couples peak RAM and Postgres write-statement count to the largest run.
