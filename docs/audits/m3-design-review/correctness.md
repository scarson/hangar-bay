# M3 Design Review — Technical Correctness + Architecture Lens

ABOUTME: Adversarial correctness review of the M3 account-features design spec against the verified 2026-07-17 codebase.
ABOUTME: Attacks get_current_user semantics, the matcher query/dedup/prune, caps races, the ESI DI path, schema lifecycle, and PROXY-1/FASTAPI-1 compliance.

**Spec reviewed:** `docs/superpowers/specs/2026-07-17-m3-account-features-design.md`
**Verdict:** sound-with-fixes. The load-bearing architecture holds up against source: date-gated matching, DB-constraint dedup via a partial unique index, the `get_current_user` `character_id` check, the request-context ESI lookup path, and the `SavedSearchParameters` JSON round-trip all check out against the actual code. Findings are one major (a false acceptance-criterion guarantee) plus several minor correctness-of-meaning / edge issues. No blocker.

---

## What I attacked and found SOUND (refuted findings, recorded so they aren't re-litigated)

- **`get_current_user` + `get_db` + the global exception handler.** The dependency only SELECTs through `db` and issues the session `DEL` directly against Redis, so there is no half-written DB transaction to worry about — `get_db` (db.py:30-43) has nothing to commit on the 401 path, and its `except Exception: rollback` is a no-op over a read. The `HTTPException(401)` is dispatched by FastAPI's built-in HTTPException handler, **not** the `@app.exception_handler(Exception)` 500 handler at main.py:81 (Starlette resolves the most-specific handler; the existing `/me` route already 401s this way today). The re-read of the sid from `request.cookies` to build the `session:{sid}` key for the `DEL` is correct — the payload doesn't carry its own sid. **Sound.**
- **The `character_id` equality check.** `session["character_id"]` is a validated plain int (session.py:42) and `User.character_id` (BigInteger) loads as a Python int; `!=` is well-defined. This genuinely closes the dev-wipe id-reassignment silent-cross-contamination case the recon flagged (backend-data-auth.md §5). **Sound and necessary.**
- **The request-context ESI lookup path the spec "hand-waves."** `core/dependencies.py:39` already exposes `get_esi_client`, which constructs `ESIClient(settings, http_client=<shared>, redis_client=<shared>)`. The `http_client`/`redis_client` properties (esi_client_class.py:40-60) return the injected client, so `get_universe_type`/`get_universe_group` work in a route **without** `async with` (the CM is only needed when clients are *not* injected). `_get_esi_object` (esi_client_class.py:192-253) returns the raw ESI response dict, which for `/v3/universe/types/{id}/` contains `published` and `group_id` — so the "resolve name + published + category_id==6" validation is fully implementable. The str-vs-bytes `decode_responses` split doesn't bite: `json.loads` accepts both, and `redis.set(key, response.content)` accepts bytes on the str-mode app client. **Viable — the spec should just name `get_esi_client` explicitly so the plan doesn't reinvent it.**
- **`SavedSearchParameters` JSON round-trip.** The frontend `ContractSearch` (filters.ts:20-32) is exactly `{search?, min_price?, max_price?, region_ids?, is_bpc?, ships_only, page, size, sort_by, sort_direction}`. Minus `page` that is the 9 fields the spec lists, and `extra="forbid"` correctly rejects the wire-side `is_ship_contract`/ME/TE names. `parseContractSearch` (filters.ts:69-87) tolerates `null` for every optional (null→undefined) and the str-enum values round-trip through `json.dumps`. **Sound.**
- **Scheduler pickling / lock / engine-per-run.** `WatchlistMatcherService(settings)` holding only `Settings` (a pydantic BaseSettings, picklable) mirrors `ContractAggregationService` exactly (background_aggregation.py:63-79); a separate lock key + own `create_async_engine` per run + Lua compare-and-delete release is a faithful copy of the aggregation shape (background_aggregation.py:81-122). **Sound.**
- **PROXY-1 / FASTAPI-1.** All routes are `/me/*` bare-mounted (no `/api/v1`), collection routes keep trailing slashes, and `GET /me/notifications/` uses `Annotated[..., Query()]` for `is_read/page/size`. **Compliant.**
- **`Base.metadata.create_all` schema lifecycle + FK `ondelete=CASCADE`.** `create_all` emits `ON DELETE CASCADE` FKs on Postgres (dev + tests use Postgres; `DATABASE_URL_TESTS` is a `PostgresDsn`), so the partial unique index and the cascade both materialize in the test DB. New `account.py` models register via `models/__init__.py`, which is imported transitively when `main.py:27` does `from .models import contracts`. **Sound** (assuming account.py is added to `models/__init__.py`, which the spec commits to).

---

## Findings

### 1. [MAJOR] Per-user caps are TOCTOU-racy, but acceptance criterion #2 promises they are "DB-constraint-backed" and enforced "under concurrent access"

**Section:** §3.5 / §4.5 (caps) and §10 acceptance criterion #2; Appendix A "plain lists + caps."

**Defect.** Uniqueness (`UniqueConstraint(user_id, name)` / `(user_id, type_id)`) is genuinely DB-backed and race-safe. The **caps are not** — the only mechanism described is a count-then-insert (`MAX_SAVED_SEARCHES_PER_USER`, `MAX_WATCHLIST_ITEMS_PER_USER`), which is exactly the check-then-act TOCTOU the spec itself rejects for dedup in §3.3(b). Acceptance criterion #2 reads: "All new routes … enforce caps and uniqueness under concurrent access (DB-constraint-backed)." That conjoined claim is false for caps: there is no DB constraint that bounds row *count* per user, and nothing in Postgres will stop it under `READ COMMITTED` (the asyncpg default).

**Failure scenario.** User at 99 saved searches fires two concurrent `POST /me/saved-searches/` with distinct names. Both transactions `SELECT count(*) → 99`, both pass the `< 100` gate, both insert distinct names → the unique constraint doesn't fire (names differ) → user ends at **101**. The cap is silently exceeded. Same for watchlist items at 199 → 201.

**Why it matters here.** The effect is benign (a soft limit overshoots by a few rows), but the spec elevates cap enforcement to a signed-off *done-condition* and asserts a guarantee the build cannot deliver. Sam would approve a false invariant. Given the project's explicit anti-TOCTOU stance (§3.3), holding caps to a weaker standard silently is the kind of last-5% gap CLAUDE.md says not to hand-wave.

**Proposed fix.** Either (a) downgrade the claim — state caps are best-effort/soft and drop "DB-constraint-backed" from criterion #2's cap clause; or (b) if a hard cap is actually wanted, make it atomic (an `INSERT ... WHERE (SELECT count(*) ... ) < :cap` guarded insert, a per-user advisory lock, or a `SERIALIZABLE` retry). Pick (a) unless Sam wants a hard cap; the tests in §6 ("caps: 400 at limit") must not claim concurrency-safety they don't exercise.

---

### 2. [MINOR] `ON CONFLICT DO NOTHING` against a **partial** unique index fails if the insert names `index_elements` without the partial predicate

**Section:** §4.4 step 4 ("`INSERT … ON CONFLICT DO NOTHING` on the partial unique index"); Appendix A "Why dedup lives in a partial unique index."

**Defect.** Postgres index inference for `ON CONFLICT (cols)` will **not** match a *partial* unique index unless the statement also supplies the index predicate. In SQLAlchemy that means `insert(Notification).on_conflict_do_nothing(index_elements=[...], index_where=text("type = 'watchlist_match'"))`. If the implementer writes the natural `index_elements=["user_id","contract_id","watch_type_id"]` **without** `index_where`, Postgres raises `there is no unique or exclusion constraint matching the ON CONFLICT specification` — a hard 500 in the matcher's core write path, every run.

**Failure scenario.** Matcher run inserts a batch with `on_conflict_do_nothing(index_elements=[...])` (no predicate) → first insert of the run raises `InvalidColumnReference` → the run aborts, no notifications are ever written, and (because `scheduled_jobs` swallows/logs) it fails silently on a schedule.

**Proposed fix.** The plan must specify the insert form explicitly: either bare `on_conflict_do_nothing()` (no target — safe here because the table has only that partial index plus the never-conflicting PK) **or** `on_conflict_do_nothing(index_elements=[...], index_where=text("type = 'watchlist_match'"))`. Add a matcher test that asserts the second run inserts zero (already planned as "idempotency") — that test will catch a wrong inference form.

---

### 3. [MINOR] `ESIRequestFailedError → 502` conflates an invalid `type_id` (ESI 404) with ESI-down (5xx)

**Section:** §4.5 (`POST /me/watchlist-items/` … "502 on `ESIRequestFailedError`").

**Defect.** `_get_esi_object` raises `ESIRequestFailedError(status_code=404, …)` for a nonexistent `type_id` (it retries only 5xx/network, then `raise_for_status()` on the 4xx — esi_client_class.py:209-243). The spec maps *all* `ESIRequestFailedError` to 502. So a client POSTing a bogus/garbage `type_id` gets **502 "ESI unavailable"** (a server-fault, retryable signal) for what is actually a 400-class bad request.

**Failure scenario.** `POST /me/watchlist-items/ {"type_id": 999999999}` → ESI 404 → `ESIRequestFailedError` → 502. A well-behaved client retries the 502 (server fault) forever; the real problem is the input.

**Why it's only minor.** The blessed F006 flow supplies `type_id` from wire data that is known-valid, so this is reachable mainly via direct API use. Still a wrong status contract on the declared error surface.

**Proposed fix.** Discriminate on `ESIRequestFailedError.status_code`: 404 (and other 4xx) → 400/404 "unknown or invalid type"; 5xx/network → 502. This mirrors the discrimination the M2 refresh TODO already calls out as the right pattern.

---

### 4. [MINOR] The prune-vs-dedup safety proof rests on an imprecise external-data assumption; a contract outstanding longer than `NOTIFICATION_RETENTION_DAYS` gets re-notified

**Section:** §4.4 step 5 and Appendix A "Why dedup lives in a partial unique index" ("EVE public contracts live ≤ 4 weeks — far inside the 90-day window").

**Defect.** The no-resurrection invariant depends on every matched contract's lifetime being shorter than `NOTIFICATION_RETENTION_DAYS` (90d). Two problems: (a) the "≤ 4 weeks" figure is wrong — EVE's contract-availability options go up to **1 month** (~30-31 days), not 28; harmless against 90d but the stated bound is inaccurate; (b) more importantly, `date_expired` is written **verbatim from ESI** (background_aggregation ingestion; recon backend-scheduler §4) and is not validated. A contract whose `date_expired` is far-future (data anomaly, or any future ESI change to durations) stays `date_expired > now()` past the 90-day prune, so its notification is pruned **while it still matches** → the next matcher run re-inserts it → the user is re-notified for a stale contract every retention cycle.

**Failure scenario.** Contract C has `date_expired = now + 200d`. Day 0: user notified. Day 90: prune deletes the notification (created_at < now-90d) while C is still outstanding. Day 90 (next run): `ON CONFLICT` finds no row → re-inserts → duplicate notification. Repeats every 90d.

**Proposed fix.** Make the invariant defensive instead of assumption-based: gate the prune so it never deletes a notification whose target contract is still outstanding (e.g. `DELETE … WHERE created_at < cutoff AND (contract_id IS NULL OR NOT EXISTS (SELECT 1 FROM contracts WHERE contract_id = notifications.contract_id AND date_expired > now() AND date_completed IS NULL))`), or set `NOTIFICATION_RETENTION_DAYS` comfortably above the real max contract lifetime and *state the enforced bound* rather than an assumed one. At minimum, correct "≤ 4 weeks" to "≤ ~1 month" and note it's an unvalidated external assumption.

---

### 5. [MINOR] The match message presents the whole-contract price as if it were the watched ship's price

**Section:** §4.4 step 4 (message example: `"Caracal (Auction) found for 10,500,000 ISK …"`) and the `contracts.price <= max_price` match predicate.

**Defect.** `contracts.price` is the price of the *entire* contract, which may bundle the watched ship with other items (a contract can have many `contract_items`). The matcher matches when the *contract* price ≤ `max_price` and renders a message naming the *ship* at that price. For a multi-item contract, "Caracal found for 20,000,000 ISK" is misleading — the 20M buys the Caracal plus everything else, and a user with `max_price = 15M` gets no notification for a genuinely-cheap Caracal that happens to be bundled up past 15M. For `auction` contracts, `price` is the starting/current bid, not the settle price, so the figure can understate the real cost.

**Failure scenario.** Contract bundles a Caracal + 5 other ships for 20M. User watches Caracal `max_price = 15M`. No notification (20M > 15M) — a false negative for the ship. Conversely a bundle at 12M notifies "Caracal found for 12,000,000 ISK" when 12M is the bundle, not the ship.

**Why it's minor.** This is inherent to contract-vs-item semantics (F006 territory) and the price is at least an upper bound the user pays. But the message wording asserts a per-ship price the system doesn't actually know.

**Proposed fix.** Reword the rendered message to be price-honest — e.g. "Caracal available in a contract priced 12,000,000 ISK" (contract price, not ship price), and consider noting item-count so bundles are visible. Document the bundle/auction semantics as a known F006 limitation so the plan's message tests assert the honest wording.

---

### 6. [NIT] Saving a search while a 1–2 char `search` term is in the box 422s

**Section:** §5 ("The persisted object is `search` minus `page`") + §4.5 `SavedSearchParameters.search` `min_length=3`.

**Defect.** The frontend `ContractSearch` state legitimately holds a 1-2 char `search` (the user is mid-typing; `toApiQuery` gates it out of the live query but `parseContractSearch` keeps it in state — filters.ts:71,97). If "Save search" persists the ContractSearch minus `page`, a short `search` reaches `SavedSearchParameters` (`min_length=3`) → **422**, failing the whole save with an opaque validation error.

**Failure scenario.** User types "ca" into search, clicks Save Search → 422, no saved search created, generic error.

**Proposed fix.** Client-side, drop `search` from the persisted payload when it's below `MIN_SEARCH_LENGTH` (mirror `toApiQuery`'s gate) so the save succeeds and stores the still-useful rest of the filter state; or surface a clear inline "search too short to save" message. One-line frontend change.

---

## Cross-cutting note (not a numbered finding)

The spec is internally consistent on the hard calls the recon flagged as design-bug bait (status unusable → date-gating; no `esi_type_cache` → ESI-at-add-time + denormalize; volatile `users.id` → `get_current_user`; APScheduler not Celery; `ships_only`↔`is_ship_contract` stored in one form). Those are all correctly resolved against source. The residual risk is concentrated in (1) the caps guarantee wording and (2)-(4) three write-path edge behaviors that are cheap to get right if the *plan* names them explicitly — which is the right place to fix them, before implementation.
