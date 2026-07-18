# M3 Design Review — Lens: Testability + Pitfalls Compliance + Operational Safety

ABOUTME: Adversarial review of the M3 account-features design spec against the verified codebase, pitfalls docs, and recon.
ABOUTME: Findings are grounded in source; each gives a concrete failure scenario. Read-only review; only this file was written.

Spec under review: `docs/superpowers/specs/2026-07-17-m3-account-features-design.md`
Reviewed against: `app/backend/src/fastapi_app/**`, `docs/audits/m3-recon/**`, `docs/pitfalls/{implementation,testing}-pitfalls.md`, `design/features/F005..F007`.

---

## Verifications that HELD (claims I tried to refute and could not)

Recording these so the plan author knows they were checked, not skipped.

- **pytest-httpx interceptability of the watchlist-add ESI call (spec §3.2/§6): CONFIRMED SOUND.** The request-path `ESIClient` is built by `get_esi_client` (`core/dependencies.py:39-50`), which injects `app.state.http_client` (`get_http_client`). In `auth_client` that client is `httpx.AsyncClient(base_url="http://sso.test")`, and pytest-httpx patches httpx's async transport globally, so `esi_client.get_universe_type()` → `_get_esi_object()` → `self.http_client.get("/v3/universe/types/{id}/")` is fully interceptable. The managed-client branch (`__aenter__`) is only taken when no client is injected — never in a request. Test authors must register **two** responses per happy-path add (type `/v3/universe/types/{id}/` then group `/v1/universe/groups/{gid}/`), and note pytest-httpx's `assert_all_requests_were_expected` will fail any unmocked add.
- **FakeRedis surface vs `get_current_user` (spec §4.1): SUFFICIENT.** The dependency needs `getex` (TTL-slide read via `get_current_session`→`read_session`) and `delete` (session destruction) — both present in `tests/fake_redis.py`. The session-deletion assertion (`assert client.fake_redis.exists("session:{sid}") == 0`) is expressible.
- **Notifications is a single-table paginated query, so SQLA-1 (joined-row pagination) does NOT bite it.** The matcher's join is internal and unpaginated. Good.

---

## Findings

### 1. [MAJOR] Partial-index `ON CONFLICT` requires the WHERE predicate restated — matcher fails entirely if omitted

Spec §3.3/§4.4-step-4/Appendix A say dedup is "`INSERT … ON CONFLICT DO NOTHING` against the partial unique index `(user_id, contract_id, watch_type_id) WHERE type='watchlist_match'`." PostgreSQL requires that when the arbiter is a **partial** index, the `ON CONFLICT` inference clause restate the index predicate: `... ON CONFLICT (user_id, contract_id, watch_type_id) WHERE type = 'watchlist_match' DO NOTHING`. Omitting the `WHERE` yields `there is no unique or exclusion constraint matching the ON CONFLICT specification` at execution time.

- **Grounding:** the codebase has **no precedent** for a partial-index conflict target — `services/db_upsert.py:39-47` only ever does `on_conflict_do_update(index_elements=primary_key_cols)` with no `index_where=`. An implementer copying that shape will produce a statement Postgres rejects.
- **Failure scenario:** matcher runs, finds ≥1 match, executes the naive `on_conflict_do_nothing(index_elements=[user_id, contract_id, watch_type_id])` → Postgres raises on every run → the whole matcher errors out and inserts zero notifications forever. The §6 "idempotency (second run creates zero)" test *would* catch it **only if** the first run is asserted to actually create rows (a run that raises creates zero on both passes and could read as "idempotent"). 
- **Fix:** design should mandate the `index_where` / restated predicate in the ON CONFLICT clause (SQLAlchemy `on_conflict_do_nothing(index_elements=[...], index_where=(Notification.type == "watchlist_match"))`), and §6 must assert the **first** matcher run creates N>0 rows before asserting the second creates 0. Add this as an implementation-pitfall entry.

### 2. [MAJOR] Bulk notification INSERT has no stated chunk size vs the asyncpg 32767 bind-param cap

Spec §4.4-step-4 says notifications are inserted "batched" but names no batch size and no test crossing a batch boundary. The aggregation service already paid for this exact lesson: `background_aggregation.py:39-43` caps id-list UPDATEs at `UPDATE_ID_CHUNK_SIZE=1000` because "asyncpg caps a statement at 32767 bind parameters … blows that ceiling and rolls back the entire aggregation transaction."

- **Failure scenario:** a `Notification` row binds ~7 columns (user_id, type, message, contract_id, watch_type_id, price, is_read). A single-statement bulk insert of >~4680 matched rows (plausible at production scale: many users × a popular ship appearing across many outstanding contracts) exceeds 32767 params → asyncpg raises → the matcher transaction rolls back → **zero** notifications that cycle, repeating every interval until match volume drops.
- **Fix:** specify a chunk size (mirror `UPDATE_ID_CHUNK_SIZE`) and add a §6 test that arranges a match set spanning >1 batch and asserts all notifications land (the writer-side analog of TEST-4). This is a §4 bounded-growth item the design currently misses.

### 3. [MAJOR] Unread-badge `total` must be asserted to respect the `is_read=false` filter

Spec §5 badge = `GET /me/notifications/?is_read=false&size=1` reading `total`. §6 lists a generic "is_read filter" test and a TEST-4 "total matches" assertion, but does not explicitly require that `total` be computed **after** the `is_read` filter is applied.

- **Grounding:** the existing paginated count builds a filtered count subquery (`contract_service.py:132-139`). A new endpoint author who counts the unfiltered table (or forgets to thread `is_read` into the count query) produces a `total` = all rows.
- **Failure scenario:** user has 50 read + 3 unread notifications. Badge query returns `total=53` → the bell shows "53" instead of "3", permanently, and clears to a wrong number after mark-read. 
- **Fix:** §6 must include an explicit assertion: with mixed read/unread fixtures, `total` under `is_read=false` equals the unread count (not the row count). Cheap and it pins the badge contract.

### 4. [MINOR] TEST-8 (dual `role="status"`) is unaddressed for the three new list pages

Spec §6 frontend/E2E covers vitest-axe and the polite-live-region, but never mentions TEST-8. The recon (`backend-test-infra.md` §7) explicitly flags TEST-8 as biting "any new M3 list view." All three new pages (`/saved-searches`, `/watchlist`, `/notifications`) are list views that, if they follow `ContractTable`'s pattern (a loading skeleton `role="status"` coexisting with the always-mounted results live region `role="status"`), reproduce the strict-mode collision.

- **Failure scenario:** a Playwright/RTL spec for `/notifications` polls `getByRole('status')` to read the results region while the skeleton is still mounted → "strict mode violation: multiple elements match role=status" → intermittent failure, which under pressure gets "fixed" by `.first()` (a TEST-2 erosion).
- **Fix:** design should state the synchronization contract for the new lists (wait for skeleton unmount / `waitForDataRendered` before asserting the results region), or give the loading skeleton a distinct role so the two never collide.

### 5. [MINOR] Prune-window test has no injectable clock — "clock-injected created_at" is not achievable as written

Spec §6 says the prune-window test uses "clock-injected `created_at`." But `notifications.created_at` is `server_default func.now()` (DB clock, §4.2), and the prune (`DELETE … WHERE created_at < now() - NOTIFICATION_RETENTION_DAYS`, §4.4-step-5) also uses the DB clock. The `FakeRedis(clock=…)` injection seam (the one clock-injection precedent in the suite) governs **Redis** TTLs, not Postgres timestamps — it does nothing here.

- **Failure scenario:** to test the retention boundary deterministically (a row exactly at the edge kept/deleted), you cannot inject a clock; you must backdate `created_at` on insert AND the cutoff is computed against the live DB `now()`, so the boundary drifts with wall-clock. The boundary case (§6 as written) is untestable.
- **Fix:** either compute the prune cutoff in Python from an injectable `now` on `WatchlistMatcherService` (so a test passes a fixed `now`), or have §6 arrange rows with explicit backdated `created_at` and test the coarse (well past / well within) cases only, dropping the "clock-injected" language. testing-pitfalls §7 wants an injected clock — the service should expose one.

### 6. [MINOR] Watchlist list ordering `type_name ASC` has no tiebreaker (TEST-3)

Spec §4.5 orders `GET /me/watchlist-items/` by `type_name ASC`. Unlike notifications (`created_at DESC, id DESC` — has an `id` tiebreaker) and saved-searches (`name ASC`, backed by the `UniqueConstraint(user_id, name)` so no ties), `type_name` is **not** unique — EVE has distinct `type_id`s sharing a name, and `type_name` is a denormalized `String(255)`.

- **Failure scenario:** a user watches two type_ids with identical names; the ordered GET returns them in planner/heap order, which varies across executions → a TEST-3 ordering test flakes, and the UI row order is unstable between requests.
- **Fix:** order by `type_name ASC, type_id ASC` (or `, id`). One-line change; make it part of the design so tests get a stable tiebreaker.

### 7. [MINOR] Watchlist-add validation order is unspecified; cap and duplicate checks should precede the ESI lookup

Spec §4.5 lists 400-cap, 409-duplicate, and 502-ESI outcomes for `POST /me/watchlist-items/` but does not fix the order of cap-check vs ESI-resolve vs insert.

- **Grounding:** `_get_esi_object` caches into `app.state.redis` (FakeRedis, fresh per test), so an add that reaches ESI needs its type+group responses registered.
- **Failure scenario (test cost + correctness):** if the cap is checked **after** the ESI lookup, the `MAX_WATCHLIST_ITEMS_PER_USER=200` cap test must register ~200 distinct type+group mock pairs (or pre-seed the esi-object cache) just to drive the 201st add to 400 — and a capped user wastefully hits ESI on every doomed add. If the duplicate is only caught at INSERT (the design's deliberate IntegrityError→409, which is correct), the dup test still fires one ESI lookup first — acceptable, but the cap should short-circuit before ESI.
- **Fix:** design should state: cap-count check first (no ESI), then ESI resolve/validate, then insert with IntegrityError→409. This keeps the cap test cheap and avoids burning an ESI call on a rejected add.

### 8. [MINOR] `PUT /me/watchlist-items/{id}` "explicit-null clears" needs the null-vs-absent test pinned

Spec §4.5 says PUT accepts `max_price`/`notes` where "explicit-null clears." The absent-field-vs-JSON-null distinction (does omitting `max_price` preserve or clear?) is a classic partial-update footgun and is not disclosed in §6.

- **Failure scenario:** a client sends `{"notes": "x"}` intending to keep the existing `max_price`; if the handler treats absent as null (full-replace PUT semantics), the price silently clears — or vice versa, an explicit `{"max_price": null}` fails to clear because the schema drops nulls. Either way a user's data is wrong with no error.
- **Fix:** §6 must test both `max_price: null` (clears to NULL) and `max_price: 5.00` (sets), and the design must state whether an omitted field preserves or clears (recommend: PUT replaces the mutable fields, so document that omission clears, or switch to explicit optional-with-sentinel semantics).

### 9. [MINOR] Dedup TOCTOU is claimed as "structurally impossible" but only tested sequentially

Spec §3.3/Appendix A lean hard on concurrent double-notification being impossible via the partial unique index, but §6's only dedup test is a **sequential** re-run ("second run creates zero"). testing-pitfalls §5 explicitly wants two concurrent callers through the critical section for "use once"/idempotency claims.

- **Reality check:** the function-scoped `db_session` is a single begin()-wrapped, rolled-back transaction — it cannot express two truly-concurrent inserters, and the aggregation suite doesn't either. So a full concurrency test is hard here.
- **Failure scenario the sequential test misses:** if the partial index is mis-declared (e.g. wrong column set, or the `contract_id`/`watch_type_id` NULLability lets `(user_id, NULL, NULL)` rows never conflict — Postgres treats NULLs as distinct in unique indexes), sequential idempotency could still pass for populated rows while the guarantee is hollow for any NULL-bearing path.
- **Fix:** at minimum, add a test that inserts two rows with the *same* `(user_id, contract_id, watch_type_id)` via two separate `db.execute` INSERT statements within one test and asserts exactly one survives (exercises the real constraint, not a Python pre-check), and assert the index is `WHERE type='watchlist_match'` so it can't bind other notification types. Note in the design that the matcher always populates both nullable dedup columns (the guarantee evaporates if either is NULL).

### 10. [NIT] `_get_esi_object` retries 3× with real `asyncio.sleep` — the 502 error-path test is slow and makes 3 requests, not 1

`esi_client_class.py:213-234`: on 5xx the object fetch retries 3 times with `0.5·2^attempt` backoff (0.5s + 1.0s real sleep). The §6 "ESI 5xx ⇒ 502, no row inserted" test therefore pays ~1.5s wall-clock and issues **three** HTTP requests against the registered response.

- **Failure scenario:** a test author registers one 5xx response and asserts `len(httpx_mock.get_requests()) == 1` → fails (3 requests). Or the retry backoff has no injectable seam, so the test is unavoidably slow.
- **Fix:** §6 should note the 5xx path issues 3 attempts (register a repeatable response; don't assert request count == 1). Longer-term, an injectable backoff/clock on the retry loop would let error-path tests run without real sleeps (testing-pitfalls §7).

### 11. [NIT] `_FakeLockRedis` lives inside `test_background_aggregation.py`; the matcher lock tests need it shared

Spec §6 says matcher lock behavior is tested "via the `_FakeLockRedis` pattern." That double (`set(nx,ex)`/`eval`/`close`) is defined privately in `tests/services/test_background_aggregation.py:275-295`; the session `FakeRedis` has no `eval`/Lua (recon §2). To test the matcher's compare-and-delete **release** branch (token mismatch → CAD returns 0), the matcher tests need the same double.

- **Fix:** promote `_FakeLockRedis` to a shared test helper (conftest or `tests/services/_lock_double.py`) rather than copy-pasting, and cover the matcher's release-token-mismatch branch, not just the held-lock skip.

### 12. [NIT] `/me` (no DB) and `/me/*` (DB-checked `get_current_user`) can disagree; the frontend should drop to anonymous on an account-route 401

Spec §4.1 keeps `/me` DB-less (reads the session payload) while every `/me/*` route resolves the row and can 401 + destroy the session. In production users are never deleted, so divergence is a dev-only (id-reassignment) scenario — low impact — but during that window `useCurrentUser` (fed by `/me`) still renders "logged in" while every account page and the badge poll 401.

- **Fix (small):** design should state that a 401 from any `/me/*` route invalidates the `useCurrentUser`/`['currentUser']` cache so the header collapses to the sign-in state, keeping the UI consistent with the server's forced re-login.

---

## Coverage note (out-of-lens, flagged once)

The matcher compares `contracts.price <= watchlist.max_price` where `contracts.price` is the **whole-contract/bundle** price, but a watchlist entry expresses interest in a single ship `type_id`. An `item_exchange` bundling a watched ship with other goods, or a multi-ship contract, matches on the bundle price — which may over- or under-notify. This is a data-model/semantics question (another lens), but §6 should at least pin the intended semantics with a test (e.g. a contract containing the watched ship plus a second item, priced above `max_price`, must/must-not notify) so the behavior is deliberate rather than incidental.

---

## Summary

The spec is unusually pitfall-aware (PROXY-1, FASTAPI-1, TEST-1/3/4/7/9/10, ENV-2/3, SQLA-1 are all named and mostly handled) and the pytest-httpx interceptability claim it stakes its watchlist tests on is genuinely sound. The gaps that would change the built system cluster around three operational/DB mechanics the design under-specifies — the **partial-index ON CONFLICT predicate** (#1), the **bulk-insert bind-param chunking** (#2), and the **filtered unread `total`** (#3) — plus a handful of concrete test-strategy holes (#4–#9). None require re-architecting; all are answerable in the implementation plan.
