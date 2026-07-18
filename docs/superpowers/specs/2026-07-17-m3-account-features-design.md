<!-- ABOUTME: M3 design spec — F005 Saved Searches, F006 Watchlists, F007 Alerts/Notifications on the zero-scope SSO identity. -->
<!-- ABOUTME: Binds the scope question, data model, matcher job, API surface, frontend integration, and testing strategy; reasoning chain in Appendix A. -->

# M3 — Account Features (F005 / F006 / F007) — Design Spec

**Date:** 2026-07-17 (autonomous session; Sam authorized "build as much as you can" with the M3 direction)
**Status:** Approved for planning under Sam's delegated session authority; items needing Sam's eyeball are marked `[REVIEW]`.
**Feature authority:** [design/features/F005-Saved-Searches.md](../../../design/features/F005-Saved-Searches.md), [F006-Watchlists.md](../../../design/features/F006-Watchlists.md), [F007-Alerts-Notifications.md](../../../design/features/F007-Alerts-Notifications.md) — this spec refines all three against the verified 2026-07-17 codebase state and binds their open choices.
**Verified-facts provenance:** 5-lane recon at `docs/audits/m3-recon/` (backend data/auth, API patterns, scheduler/ingestion, test infra, frontend structure), run against `origin/dev` tip `a7b0f26`.

## 1. Decisions register

### The headline decision: M3 is a ZERO-SCOPE milestone

**F005, F006, and F007 are all buildable on the existing zero-scope SSO identity. M3 requests NO ESI scope.** The M2 docs' working assumption ("M3 = first ESI scope + token-using caller") conflated two different backlogs:

- The account features (this milestone): per-user preference data in Hangar Bay's own DB, matched against *locally aggregated public* contract data. F005 touches no ESI at all; F006 resolves type names via the existing **public** `/v3/universe/types/` + `/v1/universe/groups/` endpoints (Valkey-cached, version-pinned per ESI-1); F007 matches watchlists against the local `contracts`/`contract_items` tables.
- The scope-bearing backlog (structure-name resolution, refresh-token exercising, per-user session invalidation on refresh failure, refresh-400 discrimination, refresh concurrency): all remain deferred to the milestone that requests the first scope. Recorded in the M2 design §2.7/§4.3/Appendix B and the `TODO(M3)` markers in `services/auth_service.py` — those markers' *scope-gated* items stay parked (see §8); only the first-login upsert race rides along (§9).

Consequences: no EVE app consent change, no refresh-token flow goes live, no new secret material. The features degrade gracefully for anonymous users (server-side 401s; frontend renders sign-in prompts).

### Other bound decisions

- **User-row resolution is mandatory on every M3 route.** New dependency `get_current_user` resolves the session to a live `users` row and verifies `character_id` matches; miss ⇒ destroy session + 401 (§4.1). This closes the missing-user-row / reassigned-id hazard (recon: sessions survive dev DB wipes; `users.id` is a volatile autoincrement).
- **Data model:** three new tables `saved_searches`, `watchlist_items`, `notifications` FK'd to `users.id` with `ondelete="CASCADE"`; one new column `users.watchlist_alerts_enabled` (§4.2). Schema rides `Base.metadata.create_all` (dev + tests + CI); Alembic revival stays out of scope, same as M2.
- **Matcher:** a second APScheduler job (own id, own Valkey lock key, own interval setting, default 900 s) running a set-based match of enabled users' watchlists against **outstanding** contracts (`date_expired > now()`, `date_completed IS NULL`) — never `status`, which is always `"unknown"` in the public feed (§4.4).
- **De-duplication is a DB constraint, not app logic:** notifications carry `(user_id, contract_id, watch_type_id)` under a partial unique index; the matcher inserts with `ON CONFLICT DO NOTHING`. Re-notification on further price drops is deferred (F007 marks it "may", §8).
- **API:** all under `/me/*`, bare-mounted (PROXY-1), auth-gated, ownership-scoped, with explicit `ErrorDetail` declarations for 401/404/409 (§4.5). Uniform **404** for both not-found and not-owned (anti-enumeration). Saved-search/watchlist lists are plain arrays with per-user caps; notifications are paginated via the existing `PaginatedResponse[T]`.
- **Frontend ships no new modal/dialog/toast primitives.** Save-search naming, delete confirmation, and watchlist edits are inline disclosures/two-step buttons; the notification bell links to a `/notifications` page instead of opening a dropdown panel (§5). `[REVIEW]` — this is the main UX-shape call made without Sam.
- **PR shape: one campaign branch, one implementation PR, classified `Review — database schema + per-user data authorization`.** The Domain triggers (new schema; authorization-scoping code) make auto-merge unavailable, so the work lands as a single well-commit-structured PR for Sam's return, adversarially reviewed pre-open (§7).

## 2. Corrections to the feature specs (verified against the 2026-07-17 codebase)

These override F005/F006/F007 text where they conflict:

1. **There is no `esi_type_cache` table** (F006 §6.1/§16 assumes one). Type→name/category resolution exists only as the ESI client's Valkey-cached object fetches (`esi-object:{path}`, 24 h TTL) plus per-contract denormalized `ContractItem.type_name`/`category`. F006's "check against esi_type_cache" becomes: resolve via `ESIClient.get_universe_type`/`get_universe_group` at watchlist-add time and **denormalize `type_name` onto the watchlist row**.
2. **`Contract.status` is unusable** — the public feed carries no status; ingestion stores `"unknown"` and never deletes rows. "Current contract" = `date_expired > now() AND date_completed IS NULL`. F007's matcher must date-gate.
3. **`users.id` is the FK target and it is volatile in dev** (autoincrement, reassigned after every wipe+relogin). The F005/F006 models' bare "FK to users.id" is insufficient without the §4.1 resolution dependency.
4. **Celery (F007 §14/§16) is not the house scheduler** — APScheduler is. The matcher is an APScheduler interval job mirroring the aggregation job's shape.
5. **The saved-search payload is not free-form** (F005 stores "the filter state from F002"). The concrete contract is the frontend's `ContractSearch` shape minus `page`, validated server-side by a dedicated Pydantic model that **rejects** unknown keys — which also excludes the four inert ME/TE params (FASTAPI-2) by construction.
6. **i18n:** all three specs carry extensive i18n guidance; frontend i18n is deferred house-wide (M1 precedent). Notification messages are stored pre-rendered English; `message_key`/`message_params` columns are NOT built (§8).
7. **Email notifications, saved-search alerts, WebSockets:** already out of scope per F007; confirmed deferred.

## 3. Approaches considered (per axis)

### 3.1 Scope framing
- **(a) Zero-scope M3 — CHOSEN.** All three features consume only local DB + public ESI. No consent change, no token custody expansion, no live-unexercised code paths activating. The scope-bearing backlog stays parked with its unblock condition intact ("first feature that needs private ESI data").
- (b) Request the first scope now (M2 docs' assumption) — activates refresh-token flow + its three known TODO gaps for zero feature benefit; every F005–F007 requirement is satisfiable without it. Rejected as YAGNI with real carrying cost.

### 3.2 Watchlist type validation/naming
- **(a) Resolve at add-time via public ESI, denormalize `type_name`, require published ship (category 6) — CHOSEN.** One or two Valkey-cached lookups per add; the row is self-sufficient for display forever after; ship-only validation per F006 §9. ESI outage at add-time surfaces as a clean 502 (rare, retryable, honest).
- (b) Only allow adds from contract context (local `contract_items` carry names) — free lookups but users can't watch ships not currently listed, which is the core use case of a watchlist. Rejected.
- (c) Build a durable type table — infrastructure for M3 needs a milestone doesn't have; the Valkey cache already makes (a) cheap. Rejected (revisit if a future feature needs type browsing).

### 3.3 Matcher write path / de-duplication
- **(a) Set-based SELECT of matches + Python message rendering + bulk `INSERT … ON CONFLICT DO NOTHING` against a partial unique index — CHOSEN.** The DB constraint makes dedup correct under concurrency and re-runs by construction (TOCTOU-free); the matcher is idempotent; message strings stay in Python where they're testable.
- (b) App-level "does a notification exist" check-then-insert — the classic §5 concurrency pitfall (two racing runs double-notify). Rejected.
- (c) A separate match-ledger table + notifications referencing it — cleaner separation but a second table and a join for zero MVP benefit; the notification row IS the ledger. Rejected; revisit if re-notification-after-cooldown lands (§8).

### 3.4 Notifications list shape
- **(a) `PaginatedResponse[NotificationSchema]` + `is_read` filter; unread badge reads `total` from `size=1` query — CHOSEN.** Notifications grow unboundedly (until pruned); pagination is the house envelope; the badge needs no dedicated count endpoint.
- (b) Dedicated `/me/notifications/unread-count` — an endpoint whose payload is a subset of (a)'s envelope. Rejected (YAGNI).

### 3.5 Saved-search/watchlist list shape
- **(a) Plain `list[Schema]` with per-user creation caps (100 saved searches, 200 watchlist items) — CHOSEN.** Bounded by the cap, so pagination is dead weight; caps also satisfy the bounded-growth testing discipline. Cap breach ⇒ 400 with a clear detail string.
- (b) Paginated envelopes everywhere — consistency, but the frontend consumers (dropdown of saved searches; a manage page) want the full set anyway. Rejected.

### 3.6 Frontend write-UI primitives
- **(a) Inline disclosures + two-step destructive buttons + a notifications page — CHOSEN.** Zero new overlay primitives (none exist today — no dialog/toast/popover); everything stays role/label-selectable for the E2E discipline; keyboard/focus behavior is native.
- (b) Build a modal + toast system — the "right" long-term kit, but it's a design-system project stapled to a feature milestone, and every M3 surface has a good non-overlay shape. Rejected for M3; the z-scale tokens (`--z-modal`, `--z-toast`) remain reserved. `[REVIEW]`

### 3.7 Auth gating on the frontend
- **(a) Component-level branch (mirror `HeaderIdentity`): `useCurrentUser()`; pending ⇒ skeleton, anonymous ⇒ sign-in prompt with `next` deep-link — CHOSEN.** Matches the "anonymous is a data state" philosophy; no router-context plumbing; server-side 401s remain the actual enforcement.
- (b) Route-level `beforeLoad` guards — requires wiring a router context + query-cache reads through `createRouter` (touches `main.tsx`/`renderApp.tsx`); more machinery for the same UX. Rejected for M3.

## 4. Backend architecture

New surface, following the house layout:

- `fastapi_app/models/account.py` — `SavedSearch`, `WatchlistItem`, `Notification` (registered in `models/__init__.py`).
- `fastapi_app/models/user.py` — gains `watchlist_alerts_enabled` column.
- `fastapi_app/core/current_user.py` — the `get_current_user` dependency (§4.1).
- `fastapi_app/schemas/account.py` — request/response models incl. `SavedSearchParameters` (§4.5).
- `fastapi_app/services/saved_search_service.py`, `services/watchlist_service.py` — CRUD logic (thin; ownership scoping + caps + IntegrityError→409 mapping).
- `fastapi_app/services/watchlist_matcher.py` — `WatchlistMatcherService` (§4.4).
- `fastapi_app/api/saved_searches.py`, `api/watchlist.py`, `api/notifications.py` — routers, bare-mounted in `main.py` (PROXY-1).
- `core/scheduler.py` — `add_watchlist_matcher_job`; `services/scheduled_jobs.py` — `run_watchlist_matcher_job`.

### 4.1 `get_current_user` — session→row resolution (the M3 auth backbone)

```python
async def get_current_user(
    request: Request,
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_cache),
) -> User:
```

1. `SELECT … FROM users WHERE id = session["user_id"]` (PK lookup).
2. Row absent **or** `row.character_id != session["character_id"]` ⇒ delete the server-side session and raise 401. The session payload does not carry its own sid, so the dependency re-reads the sid from the request cookie (`request.cookies.get(settings.SESSION_COOKIE_NAME)`) to build the `session:{sid}` key for the `DEL`; the stale browser cookie then points at nothing and the next login replaces it. This is the deliberate "force re-login" behavior the M2 design noted for M3.
3. Match ⇒ return the ORM `User`.

The `character_id` equality check is load-bearing: after a dev wipe + different user's login, `users.id` can be *reassigned*; without the check, an old session would silently read/write another character's data. One indexed PK read per authed request is the accepted cost; `/me` itself keeps its M2 no-DB behavior (unchanged surface).

### 4.2 Data model

`SavedSearch` (`saved_searches`):

```
id                 Integer PK autoincrement
user_id            Integer, ForeignKey("users.id", ondelete="CASCADE"), index, not null
name               String(100), not null            (trimmed, non-empty; validated in schema)
search_parameters  JSON, not null                   (validated SavedSearchParameters dump)
created_at / updated_at  DateTime(tz), server_default func.now() (+ onupdate)
UniqueConstraint(user_id, name)
```

`WatchlistItem` (`watchlist_items`):

```
id            Integer PK autoincrement
user_id       Integer, FK users.id ondelete CASCADE, index, not null
type_id       Integer, not null                     (matches ContractItem.type_id width)
type_name     String(255), not null                 (denormalized at add-time from ESI)
max_price     Numeric(20, 2), nullable              (ISK; >= 0.01 when present)
notes         String(500), nullable
created_at / updated_at  (house pattern)
UniqueConstraint(user_id, type_id)
```

`Notification` (`notifications`):

```
id             Integer PK autoincrement
user_id        Integer, FK users.id ondelete CASCADE, index, not null
type           String(50), not null                 ("watchlist_match" only in M3)
message        Text, not null                       (pre-rendered English)
contract_id    BigInteger, nullable                 (deep-link target; NOT an FK — contracts
                                                     rows are upsert-only external data and a
                                                     pruned/wiped contract must not delete the
                                                     user's notification history)
watch_type_id  Integer, nullable                    (the matched watchlist type_id)
price          Numeric(20, 2), nullable             (price at match time)
is_read        Boolean, not null, server_default false
created_at     DateTime(tz), server_default func.now()
Index(user_id, is_read); Index(user_id, created_at)
Partial unique index: (user_id, contract_id, watch_type_id) WHERE type = 'watchlist_match'
```

`User` gains: `watchlist_alerts_enabled  Boolean, not null, server_default true`.

All three models register in `models/__init__.py` (create_all discoverability — recon risk #5) and the matcher's own engine sees them the same way.

### 4.3 Config additions (all with defaults — `_ENV_DEFAULTS` stays untouched)

```
WATCHLIST_MATCH_INTERVAL_SECONDS: int = 900        # 15 min
WATCHLIST_MATCH_LOCK_TTL_SECONDS: int = 900
NOTIFICATION_RETENTION_DAYS: int = 90              # prune window; see §4.4 step 5
MAX_SAVED_SEARCHES_PER_USER: int = 100
MAX_WATCHLIST_ITEMS_PER_USER: int = 200
```

### 4.4 The watchlist matcher job

`WatchlistMatcherService(settings)` — picklable (no live clients at rest), mirroring `ContractAggregationService`:

1. **Lock:** `SET NX EX` on `hangar-bay:watchlist-match:lock` (own key — never the aggregation lock), TTL from settings, uuid fencing token, Lua compare-and-delete release (copy the aggregation shape).
2. **Own engine per run** (`create_async_engine(DATABASE_URL)`), disposed in `finally`.
3. **Match query (set-based):** join `watchlist_items` (users with `watchlist_alerts_enabled`) → `contract_items` on `type_id` with `is_included IS TRUE` → `contracts` where `type IN ('item_exchange','auction')` AND `date_expired > now()` AND `date_completed IS NULL` AND (`max_price IS NULL OR contracts.price <= max_price`). Select the columns needed for rendering (user_id, type_id, type_name, contract_id, price, contract type, start_location_name).
4. **Insert:** render `message` per row in Python (e.g. `"Caracal (Auction) found for 10,500,000 ISK in Jita IV - Moon 4 …"` — reuse the watchlist row's `type_name`, format price with thousands separators), then `INSERT … ON CONFLICT DO NOTHING` on the partial unique index, batched. Count actually-inserted rows via `RETURNING id` for the log line. Matching uses raw `type_id` (recon risk #7: `is_ship_contract`/`category` are best-effort enrichment and can be false-negative; `type_id` is always present).
5. **Prune:** `DELETE FROM notifications WHERE created_at < now() - NOTIFICATION_RETENTION_DAYS` (bounded growth). Safe against dedup resurrection because a notification only re-inserts while its contract is still outstanding, and EVE public contracts live ≤ 4 weeks — far inside the 90-day window.
6. **Structured completion event:** `log_key_event(logger, "watchlist_match_run", success=…, duration_ms=…, matches=…, created=…, pruned=…)` — the matcher is born observable (the aggregation job's missing run-event is a known observability gap; don't replicate it).

Job registration in `main.py` lifespan after the aggregation job: `add_watchlist_matcher_job(scheduler, matcher_service, settings)` with `id="match_watchlists"`, `replace_existing=True`, `misfire_grace_time=300`, first run at `now + 120 s` (offset so boot-time ingestion gets a head start; jobs don't chain — recon risk #4).

### 4.5 API surface (all bare-mounted; collection routes keep trailing slashes)

**`SavedSearchParameters`** (the server-side validation model for `search_parameters`): `model_config = ConfigDict(extra="forbid")`; fields mirror the frontend `ContractSearch` minus `page` — `search: str|None (min_length=3)`, `min_price/max_price: float|None (ge=0)`, `region_ids: list[int]|None (positive)`, `is_bpc: bool|None`, `ships_only: bool = True`, `size: int = 50 (1..100)`, `sort_by: SortableContractFields = date_issued`, `sort_direction: SortDirection = desc`. `extra="forbid"` rejects ME/TE and arbitrary junk at the API boundary (defense in depth per F005 §10 — the blob is re-validated by `parseContractSearch` on the way back out, and by `ContractFilters` if a future server-side consumer evaluates it).

| Route | Behavior |
|---|---|
| `POST /me/saved-searches/` | 201 `SavedSearchSchema`; 400 cap; 409 duplicate name (IntegrityError-mapped, race-safe); 422 invalid params |
| `GET /me/saved-searches/` | 200 `list[SavedSearchSchema]` ordered `name ASC` |
| `PUT /me/saved-searches/{id}` | rename only (`name` required in `SavedSearchUpdate`); 200; 404; 409 |
| `DELETE /me/saved-searches/{id}` | 204; 404 |
| `POST /me/watchlist-items/` | 201 `WatchlistItemSchema`; 400 cap / not-a-published-ship; 409 duplicate type; 502 ESI lookup unavailable |
| `GET /me/watchlist-items/` | 200 `list[WatchlistItemSchema]` ordered `type_name ASC` |
| `PUT /me/watchlist-items/{id}` | `max_price`/`notes` (explicit-null clears); 200; 404 |
| `DELETE /me/watchlist-items/{id}` | 204; 404 |
| `GET /me/notifications/` | 200 `PaginatedResponse[NotificationSchema]`; `is_read: bool|None`, `page`, `size` (Annotated[…, Query()] — FASTAPI-1); ordered `created_at DESC, id DESC` |
| `POST /me/notifications/{id}/mark-read` | 204; 404 |
| `POST /me/notifications/mark-all-read` | 204 (idempotent) |
| `GET /me/notification-settings` | 200 `NotificationSettingsSchema {watchlist_alerts_enabled: bool}` |
| `PUT /me/notification-settings` | 200 (field required) |

Conventions: every route depends on `get_current_user` and scopes queries by `user.id`; every route declares its error bodies (`responses={401: {"model": ErrorDetail}, …}`) so the typed client sees them — closing the `/me` 200-only gap for the new surface; not-found and not-owned are the same 404 (anti-enumeration); watchlist add validates via `get_universe_type` (`published` true) + `get_universe_group` (`category_id == 6`), 400 otherwise, 502 on `ESIRequestFailedError`. The GET-side individual-resource routes from the specs (`GET /me/saved-searches/{id}`, `GET /me/watchlist-items/{id}`) are **not built** — no consumer exists; the list responses carry complete rows. Recorded as a spec deviation (§8).

After the backend lands: `pdm run export-openapi` → `npm run generate:api`, committed together with the schema change.

## 5. Frontend design

New feature folders: `src/features/saved-searches/`, `src/features/watchlists/`, `src/features/notifications/` ({components,hooks} shape). New routes: `/saved-searches`, `/watchlist`, `/notifications` (flat files, named `RouteComponent` pattern). Type aliases added in `lib/api/client.ts` after regen.

- **Query keys:** `['savedSearches','list']`, `['watchlists','list']`, `['notifications','list', params]`, `['notifications','unreadCount']`. Mutations follow the `useLogout` template — `if (!response.ok) throw new ApiError(status)`, invalidate the domain prefix on success only.
- **Auth gating (all three pages):** component-level branch per §3.7 — `isPending` ⇒ skeleton; `null` ⇒ sign-in prompt reusing the `HeaderIdentity` login-link mechanics (`/api/v1/auth/sso/login?next=<encoded current path>`, full navigation, `?sso` stripped).
- **Save Search (F005):** authed-only control in the `ContractsPage` results header (beside the count line, where `search` and `useCurrentUser` are already in scope). Activating it opens an **inline disclosure** — name `Input` + Save/Cancel `Button`s, label-wired, focus moved to the input. On 409, inline error "name already exists". The persisted object is `search` minus `page`.
- **Saved-searches page:** list (name + human-readable criteria summary derived from the params) with per-row Apply (`navigate({ to: '/contracts', search: parseContractSearch(saved.search_parameters) })` — free re-validation of the stored blob), Rename (inline input swap), Delete (two-step: "Delete" ⇒ "Confirm delete?" with timeout-reset).
- **Watchlist add (F006):** on the contract detail page (F003), each included **ship** item row gains an authed-only "Watch" button (type_id + type_name are in the wire data; `category === 'ship'` gates the button; enrichment false-negatives just omit the button — display-tier, not correctness-tier). Optional max-price entry happens on the watchlist page after adding (keeps the detail-page control one-click). 409 ⇒ "already watching" inline notice.
- **Watchlist page:** list rows: type name (+ portrait-style type icon via `https://images.evetech.net/types/{type_id}/render?size=64` — decorative), max price (inline-editable `Input`, ISK formatted via `formatIsk`), notes (inline-editable), Remove (two-step). Empty state per house pattern.
- **Notifications (F007):** header bell inside `HeaderIdentity` (authed only): a `Link` to `/notifications` with an unread-count `Badge`; count query = `GET /me/notifications/?is_read=false&size=1` reading `total`, `refetchInterval: 60_000`, `enabled: !!user`. The `/notifications` page: paginated list (message, relative time via `timeRemaining`-style formatting, link to `/contracts/$contractId` when present), per-row mark-read on click + "Mark all as read" button; unread rows visually distinct (`bg-raised` + brand accent). Settings: a single labeled checkbox ("Watchlist alerts") on the notifications page wired to `/me/notification-settings` — no separate settings page.
- **Accessibility:** all controls role/label-selectable (E2E discipline); count changes announced via the existing polite-live-region pattern; disclosures manage focus; `aria-live` on save/delete feedback.

## 6. Testing strategy (TDD throughout)

**Backend (pytest, HTTP-level per TEST-1):**
- New fixture `authed_user` (the recon-identified gap): insert a real `User` via `db_session` + `flush()`, mint a session with `user_id=user.id` via `sess.create_session`, set the cookie on `auth_client`; returns `(user, auth_client)`. A second `other_user` helper for cross-user isolation tests.
- Per router: happy-path CRUD; 401 anonymous; **cross-user isolation** (A cannot read/rename/delete B's rows — expect 404, and the 404 must be indistinguishable from not-found); 409 duplicate (both name and type_id paths — via real constraint violation, not pre-check); caps (400 at limit); validation (bad `search_parameters` incl. an ME/TE key and an unknown key ⇒ 422; short search; negative price); notifications pagination **crossing page boundaries** (TEST-4) with deterministic `created_at` fixtures (TEST-3); `is_read` filter; mark-read idempotency and ownership.
- `get_current_user`: session-without-row ⇒ 401 AND the Valkey session is deleted (assert via `fake_redis`); row-with-different-character_id ⇒ 401 + session deleted; happy path.
- Watchlist add ESI paths (pytest-httpx on the app's http client seam): published ship ⇒ 201 with denormalized name; non-ship category ⇒ 400; `published: false` ⇒ 400; ESI 5xx ⇒ 502 and **no row inserted** (error-path side-effect check).
- Matcher (service-level, aggregation-test shape): arrange users/watchlists/contracts in `db_session`, call the inner match method directly; assert created notifications' fields and messages; **idempotency** (second run creates zero); price-boundary (`price == max_price` matches; `price > max_price` doesn't); expired/completed contracts excluded; `is_included=False` items excluded; disabled-alerts users excluded; prune window (clock-injected `created_at`); lock behavior via the `_FakeLockRedis` pattern (held lock ⇒ run skips).
- Schema tests mirroring `test_me_schema.py`: new paths present and bare (PROXY-1 sentinel), error responses declared, `SavedSearchParameters` constraints visible in component schemas.

**Frontend (vitest):** hook tests at the fetch seam (TEST-5: URL + method + body asserted); mutation triplets (success/HTTP-error/network-error, invalidation only on success); page tests via `renderApp` with URL-aware stubs — every test decides `/me` explicitly (401 default via `anonymousMe`, or an authed identity); error states exhaust `retry: 1` (TEST-7); bell count render + zero-count (no badge) states; a11y via `vitest-axe` for the three new pages.

**E2E (Playwright fixture lane, retries 0):** new wire fixtures `e2e/fixtures/account.ts` (`makeSavedSearch`, `makeWatchlistItem`, `makeNotification`) + intercept helpers returning captured calls; specs: save-search flow (save button visible only authed; created payload asserted at the wire), apply-saved-search (lands on `/contracts` with the right URL search), watchlist add/remove, notifications page + badge + mark-all-read, anonymous sign-in prompts on all three routes. Every spec intercepts `/me` explicitly (TEST-9); `stubPortraits` covers the new type-render images domain too (extend to `images.evetech.net/types/*`).

## 7. Delivery shape

One campaign branch `claude/m3-account-features` off `origin/dev`; ordered, individually-green conventional commits (models → deps → F005 API → F006 API → F007 backend → codegen → frontend F005 → F006 → F007 → e2e → docs). Single PR to `dev` at the end, body classified **`Review — database schema + per-user data authorization`** (both Domain triggers apply; auto-merge is off the table by policy). Before opening: full local gates (pytest, eslint, tsc, vitest, Playwright fixture lane) + an adversarial code review pass; the PR waits for Sam.

Docs riding along in the same PR: README implementation status, feature-index statuses, F005/F006/F007 "Implemented-with-deviations" notes, pitfalls entries for any new traps discovered during implementation.

## 8. Deferred / out of scope (each with unblock condition)

- **First ESI scope + structure-name resolution + refresh-token exercising + per-user session invalidation + refresh-400 discrimination + refresh concurrency** — unblocked by the first feature needing private ESI data (unchanged from M2; the account features turned out not to be that feature).
- **Re-notification on further price drops / 24 h cooldown** (F007 Criterion 1.3 "may") — unblocked by user demand; requires a match-ledger separate from the pruneable notifications table (§3.3c).
- **Saved-search alerts** (F007 Story 2, already future-tagged), **email/push channels**, **WebSockets** for the bell (polling at 60 s is fine at this scale).
- **Updating a saved search's criteria in place** (F005 explicitly defers; rename-only PUT).
- **`GET /me/saved-searches/{id}` / `GET /me/watchlist-items/{id}`** — spec'd but consumer-less; add when a consumer exists (deviation recorded in §4.5).
- **Modal/toast primitive kit** — unblocked by the first feature that genuinely can't ship as inline UI.
- **Alembic revival** — unchanged from M2; unblocked by a real production deployment plan.
- **Type-ahead ship search for watchlist adds** — unblocked by demand; adds-from-contract-context covers the browsing-driven flow.

## 9. Riding-along improvements (small, each serving files M3 touches)

1. **First-login upsert race fix** (`auth_service.upsert_user` `TODO(M3)`): reimplement as `INSERT … ON CONFLICT (character_id) DO UPDATE` (or IntegrityError-catch + re-select) so the losing concurrent first login uses the winner's row. In scope because M3 is the milestone the TODO named, and the fix is small and testable without a concurrency harness.
2. **`test_auth_flow`'s sessions get real user rows** where the new `authed_user` fixture makes that trivial — only where it reduces duplication; no wholesale rewrite.

## 10. Acceptance criteria (M3 done =)

1. F005 Stories 1–5, F006 Stories 1–5, F007 Stories 1/3/4 criteria met under the §2 corrections, verified by the §6 suites (F007 Story 2 is spec-deferred).
2. All new routes 401 anonymously, 404 across ownership boundaries, and enforce caps and uniqueness under concurrent access (DB-constraint-backed).
3. The matcher runs on schedule, is idempotent, date-gates correctly, logs a structured run event, and never double-notifies.
4. Backend pytest, frontend vitest + eslint + `tsc -b` + Playwright fixture lane: all green locally and in CI.
5. Codegen chain regenerated and committed; new schemas visible to the typed client with declared error bodies.
6. Docs updated (README, feature index, feature specs' deviation notes, pitfalls for new traps); PR opened, classified `Review`, with the adversarial review recorded.

---

## Appendix A — Reasoning chain & alternatives (thinking-documentation discipline)

**Why zero-scope was decidable without Sam.** The handoff framed it as an open question, but it's a facts question, not a preferences question: enumerate each feature's data needs and check them against what exists. F005: reads/writes only Hangar Bay rows. F006: needs "name + is-ship" for a type_id — both available from public, unauthenticated, version-pinned ESI endpoints already wrapped by `ESIClient` with caching. F007: matches rows against rows. Nothing touches a private ESI surface. The M2 assumption came from bundling structure-name resolution (which DOES need a scope) into "M3" as a label, not from the account features themselves. Choosing scopes here would have activated the three known-deficient token paths (refresh 400-discrimination, refresh concurrency, session invalidation) for zero feature value — the strongest kind of YAGNI violation.

**Why `get_current_user` verifies `character_id`, not just row existence.** The dev-wipe scenario isn't only "row missing" — it's "row missing, then a DIFFERENT character logs in and receives the same autoincrement id". A session minted before the wipe then resolves to a live row that belongs to someone else. Existence checks pass; data cross-contaminates silently. The character_id equality check turns both failure shapes into a clean forced re-login. This is cheap (the row is already fetched) and is exactly the "handle a missing user row by forcing re-login" note the M2 design left for M3 — extended to handle the nastier reassignment case the M2 note didn't anticipate.

**Why dedup lives in a partial unique index.** Every app-level alternative is check-then-act across concurrent matcher runs (the lock narrows but doesn't eliminate this — locks have TTLs and operators have retry fingers). `ON CONFLICT DO NOTHING` against a real constraint makes double-notification structurally impossible and makes the matcher idempotent for free, which in turn makes the prune-window interaction analyzable: a notification can only be re-created while its contract is outstanding (≤ 4 weeks in EVE), so a 90-day retention window can never resurrect a dedup key that still matters. The partial index (WHERE type='watchlist_match') keeps the constraint from accidentally binding future notification types with NULL dedup columns.

**Why `contract_id` on notifications is NOT a foreign key.** Contracts are external upsert-only data with no deletion today — but the moment pruning of stale contracts lands (a plausible future), an FK with CASCADE would silently delete users' notification history, and RESTRICT would block the prune. The notification is a historical record of "this matched at this time"; it must outlive the contract row. The deep link degrades to a 404 detail page, which is honest.

**Why inline UI instead of modals.** Three independent pressures align: (1) no overlay primitive exists, and building one properly (focus trap, scroll lock, escape handling, portal, a11y audit) is a mini-project; (2) the E2E discipline (role/label selectors only, retries 0) strongly favors flat, always-in-document UI; (3) every M3 surface has a natural inline shape (name-on-save is a disclosure; delete-confirm is a two-step button; the notification panel is a page). The cost is a little less polish on the bell interaction (navigation instead of a dropdown). If Sam wants the dropdown, it's an additive change later. `[REVIEW]`

**Why the matcher renders messages in Python rather than SQL.** A pure `INSERT … SELECT` with SQL string assembly would be one round trip, but message formatting (thousands separators, contract-type labels, location fallbacks) is exactly the kind of logic that wants unit tests, and the match volumes (dev: ~100 contracts; prod: thousands) make the fetch-then-insert shape irrelevant to performance. Correctness pressure beats a round trip.

**Why plain lists + caps for saved searches/watchlists but pagination for notifications.** The first two are user-curated sets with natural small bounds — the cap IS the product decision (and satisfies the bounded-growth testing discipline); paginating them adds envelope-handling to every consumer for no reachable case. Notifications are machine-generated and unbounded between prunes — the house envelope fits, and its `total` field doubles as the badge count, deleting an endpoint.

**Considered and ruled out, kept visible:** requesting the first ESI scope (activates deficient paths, zero benefit); durable type table (infrastructure without a consumer); Celery (F007's text predates the APScheduler house choice); app-level dedup checks (TOCTOU); a match-ledger table (second table for a "may" requirement); modal/toast kit (design-system project in feature clothing); route-level auth guards (router-context plumbing for equal UX); dedicated unread-count endpoint (subset of the envelope); FK on `notifications.contract_id` (history must outlive external data); storing `message_key`/`message_params` i18n columns (house-wide i18n deferral makes them dead weight now — and the `message` column can be backfilled from structured fields if i18n ever lands).

**What I'm still uncertain about.** (1) The 200-item watchlist cap and 100-search cap are gut numbers — cheap to change, but Sam may have opinions. (2) Whether the bell-as-link (no dropdown) feels too spartan — flagged `[REVIEW]`. (3) The 120 s matcher first-run offset is a heuristic; if boot ingestion takes longer, the first matcher pass just sees last cycle's data (harmless — it self-corrects next interval). (4) Whether `notes` at 500 chars is generous enough. None of these block implementation; all are one-line changes.

**Things the recon caught that would have been design bugs:** matching on `Contract.status` (always `"unknown"` — would have matched nothing or everything); assuming an `esi_type_cache` table exists (F006 as spec'd is unimplementable verbatim); paginating joined watchlist-match queries naively (SQLA-1); minting test sessions with `user_id=1` and no row (every existing auth test does this — fine until FKs exist, then every M3 test would 500); the `ContractSearch`/`ContractFilters` naming mismatch (`ships_only` ⇒ wire `is_ship_contract`) which the saved-search payload must store in exactly one form (chosen: the frontend `ContractSearch` form, since apply-side is the frontend and `parseContractSearch` re-validates).
