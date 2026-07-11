# Frontend Rebuild — Milestone 1: Public Contract Browsing

**Date:** 2026-07-11 (amended same day after adversarial review)
**Status:** Approved design; spec amended per adversarial review findings
**Supersedes:** the Angular frontend (`app/frontend/angular/`) and Angular-specific design docs (`design/angular/`)

## Context

Hangar Bay's backend is a working FastAPI application: ESI contract ingestion, PostgreSQL +
Valkey, a scheduler, observability, tests, and migrations. The frontend, last touched mid-2025,
is an abandoned Angular skeleton — one half-built contracts feature with several `.bak` files.
The Angular effort is being scrapped entirely and the frontend restarted on a stack that
present-day AI agents handle well. Design-system work and UI implementation will be driven by
the `/impeccable` skill after the foundation in this spec is scaffolded.

An adversarial review (2026-07-11) verified this spec's claims against the code by generating
the real OpenAPI schema, exercising the API with a test client, and running the proposed
codegen. Its findings are incorporated throughout; the largest consequence is the
"Backend enablement fixes" section below.

## Goals

- Replace the Angular app with a React SPA foundation at `app/frontend/web/`.
- Deliver the public browsing experience: contract list with search/filter/sort/pagination
  (F002 subset — see "Deferred F002/F003 criteria") and contract detail view (F003), against
  the existing backend API plus the surgical enablement fixes listed below.
- Keep the API layer and data-fetching hooks cleanly separated from components so they could be
  extracted into a package shared with a future React Native app.

## Non-goals (later milestones)

- EVE SSO authentication (F004) and everything downstream of it: saved searches (F005),
  watchlists (F006), alerts (F007).
- SSR/SEO work, PWA packaging, mobile apps.
- Backend **feature** work: new endpoints, new filter capabilities, schema additions. Only the
  bugfixes in "Backend enablement fixes" are in scope.
- i18n wiring. M1 ships hardcoded English strings. This consciously suspends
  `design/specifications/i18n-spec.md`'s externalized-strings mandate for this milestone;
  i18n is revisited before any feature milestone builds on M1 (and the i18n spec's
  Angular-specific guidance gets rewritten for React then).
- Global client-state management (no store until a milestone needs one).

## Stack decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | React 19 + TypeScript (strict) | Deepest agent training coverage; best fit for /impeccable; best hedge for a future React Native app |
| Build | Vite | Plain SPA; FastAPI is already the server, so no meta-framework |
| Styling | Tailwind CSS v4 | Utility-first with tokens as CSS variables; /impeccable builds the design system on this foundation |
| Routing | TanStack Router, **file-based** via the official Vite plugin, routes in `src/routes/` | Typed, first-class URL search params — F002's filter state lives in the URL (shareable links, working back button). File-based is the plugin default and the best-documented path |
| Server state | TanStack Query | Caching, retries, loading/error states; hooks are mobile-shareable |
| API types | Generated via `openapi-typescript` + `openapi-fetch` | Types stay mechanically in sync with Pydantic schemas — eliminates type drift. openapi-fetch's default form/explode serialization of array params (`region_ids=1&region_ids=2`) matches FastAPI's repeated-param parsing |
| Unit tests | Vitest + React Testing Library | Replaces test-spec.md's Angular-era Karma/Jasmine mandate — that doc gets updated this milestone (see Documentation updates) |
| Lint/format | ESLint (flat config) + Prettier + `eslint-plugin-jsx-a11y` | Matches backend's lint/format discipline; a11y lint from day one |
| Dependencies | Exact-pinned versions in `package.json` (no `^`/`~`) | Carries over CONTRIBUTING.md's existing frontend pinning policy |

## Backend enablement fixes (in scope)

The adversarial review found the existing API is not fully consumable by a browser client.
These are contract-preserving **bugfixes** (not features), each with an HTTP-level regression
test — the current backend tests only exercise filters at the service layer, which is how these
went unnoticed:

1. **Multi-value ID filters are unusable from a browser.** `region_ids`/`system_ids`/
   `station_ids`/`type_ids` are bare `Optional[List[int]]` fields in the `Depends(ContractFilters)`
   model (`app/backend/src/fastapi_app/api/contracts.py:28`), so FastAPI binds them to the GET
   **request body**, not query params. Repeated query params (`?region_ids=1&region_ids=2`) are
   silently ignored (200 OK, unfiltered), and browsers cannot send a GET body at all.
   **Fix:** annotate the four fields (or the whole dependency) with `Query()` so they become
   repeated query params; regenerate frontend types.
2. **Pagination is broken when item-level filters/sorts are active** (`search`, `type_ids`,
   `is_bpc`, `min/max_runs`, `sort_by=ship_name`): the service outer-joins `contract_items`
   and applies `offset/limit` to the joined (duplicated) rows before de-duplicating
   (`app/backend/src/fastapi_app/services/contract_service.py:167–177`), while the count query
   counts distinct contracts. Pages come up short, and contracts can be skipped or duplicated
   across page boundaries. `search` and the BPC toggle are in M1's minimum UI, so this is
   user-visible immediately. **Fix:** paginate over distinct contract IDs (subquery) before
   joining items. Frontend QA must not paper over short/duplicated pages as a frontend bug.
3. **OpenAPI export script** for codegen: a small `pdm` script in `app/backend` that dumps
   `app.openapi()` to JSON using safe dummy env values (importing the app requires env setup —
   see "Backend dev prerequisites"). `npm run generate:api` in the frontend consumes that file.
   Codegen against the real schema is verified working (including
   `PaginatedResponse_ContractSchema_`).

**Known-broken, do not expose:** `min_me`/`max_me`/`min_te`/`max_te` are declared in
`ContractFilters` but never applied by the service (the underlying data isn't in the model —
`contract_service.py:121`). The FilterBar must not surface ME/TE controls in any milestone
until the backend actually implements them.

## Architecture

```
app/frontend/web/
  src/
    lib/api/              # generated OpenAPI types + thin typed client (mobile-shareable)
    routes/               # TanStack Router file-based routes: /contracts (list), /contracts/$contractId (detail)
    features/contracts/
      hooks/              # TanStack Query hooks: useContracts(filters), useContract(id)
      components/         # ContractTable, FilterBar, ContractDetail, ...
    components/           # design-system primitives — owned by /impeccable
  vite.config.ts          # dev proxy: /api/v1/* -> http://localhost:8000/* (prefix stripped)
```

- **URL search params are the single source of truth** for filter, sort, and pagination state.
  TanStack Router validates/types them; components never hold shadow copies of filter state.
- **TanStack Query owns all server state.** Components consume `useContracts(filters)` /
  `useContract(id)`; no fetch calls outside `lib/api` + hooks.
- **Dev proxy** mirrors the old Angular `proxy.conf.json` contract: the SPA calls relative
  `/api/v1/...` paths; Vite proxies to FastAPI on `:8000`, stripping the `/api/v1` prefix.
  The backend mounts its routers bare (e.g. `/contracts`) and expects the deployment layer to
  own the public prefix (see comment at `app/backend/src/fastapi_app/main.py:165`).
- **Client path invariant:** the openapi-fetch client is created with `baseUrl: "/api/v1"` and
  all calls use the schema paths **verbatim, including trailing slashes** (the list route is
  `/contracts/`; hitting `/contracts` triggers a 307 whose Location drops the proxy prefix and
  escapes to the SPA origin).

## Backend API surface (existing + enablement fixes)

Paths below are as the SPA sees them (`/api/v1` prefix added by proxy; backend serves them bare):

- `GET /api/v1/contracts/` → `PaginatedResponse[ContractSchema]`
  (`total`, `page`, `size`, `items`). Query params (per `ContractFilters`):
  - `search` (text, **`min_length=3` — the UI must not send values under 3 chars**; shorter
    input keeps the previous unfiltered/filtered state rather than 422ing),
  - `min_price`/`max_price`, `min_collateral`/`max_collateral`, `min_runs`/`max_runs`,
  - `region_ids`/`system_ids`/`station_ids`/`type_ids` (repeated params, post-fix #1),
  - `is_bpc`, `page` (≥1), `size` (1–100, default 50),
  - `sort_by` ∈ {date_issued, date_expired, price, collateral, ship_name, volume},
    `sort_direction` ∈ {asc, desc},
  - ME/TE params exist but are inert — never expose (see above).
- `GET /api/v1/contracts/{contract_id}` → `ContractSchema` with nested
  `items: ContractItemSchema[]` (type names, quantities, BPC flags, market group); 404 when absent.

**Response-shape gaps the UI must design around** (do not assume these fields exist):
`ContractSchema` has **no `collateral` field** (though it's sortable/filterable — sorting by an
invisible column is acceptable in M1), no region/system IDs or names (only
`start_location_name`), and item-level ME/TE is absent. List responses include nested `items`,
so ship names are derivable for the list view.

## Milestone-1 minimum filter surface

The FilterBar must expose: text search, price range, **region multi-select**, BPC toggle,
sorting, and pagination. The region selector is backed by a small **bundled static region
name→ID map** (EVE region IDs are stable static data; no backend lookup endpoint exists).
Regions without ingested data simply return empty results.

Exposable later as the FilterBar design matures under /impeccable (API supports them post-fix,
but they need name-lookup or entry UX that doesn't exist yet): collateral range, BPC runs
range, system/station filters, type-ID filters.

## Deferred F002/F003 criteria (need backend feature work — later milestones)

`design/features/F002-...md` remains the authoritative product spec, but these of its criteria
have **no backing API** today and are explicitly out of M1:

- Ship type/category filter via dropdown/autocomplete (F002 criteria 3.1, 4.3–4.5) — requires
  the nonexistent `GET /ships/market_groups` endpoint.
- Contract-type filter, auction vs item_exchange (F002 story 7 / criterion 6.1) — no such
  filter param exists.
- `contains_additional_items` indicator/filter (F002 story 9) — no such field in the schema.
- Name-based region/system lookup (F002 story 5) — API takes numeric IDs only; M1 covers
  regions via the bundled static map, systems deferred.

## Error handling & UX states

- Query-level error boundaries with a retry affordance; no blank screens on failure.
- Skeleton loading states for list and detail; explicit empty state for zero-result filters.
- Visual/interaction specifics of these states are designed during the /impeccable phase; the
  scaffold guarantees the mechanical hooks (error/loading/empty branches) exist from day one.

## Testing

- Vitest + RTL: filter/search-param serialization round-trips (including repeated array params
  and the 3-char search gate), query hooks (mocked client), component states
  (loading/error/empty/populated).
- Accessibility: `eslint-plugin-jsx-a11y` at lint time from the scaffold onward, plus axe-core
  assertions (vitest-axe) on the list and detail views once /impeccable builds them. This is
  the M1 posture for accessibility-spec.md's automated-scan mandate; CI build-fail wiring
  arrives when frontend CI exists.
- The generated API client itself is not unit-tested (machine-generated); its correctness is
  covered by hook tests against recorded response shapes.
- Backend enablement fixes each get an HTTP-level regression test (TestClient hitting
  `GET /contracts/` with repeated ID params; pagination correctness under `search`/`is_bpc`).
- E2E (Playwright) deferred to the end of the /impeccable implementation phase.

## Backend dev prerequisites (for the end-to-end acceptance step)

Verified by actually booting the app — the current `.env.example` is insufficient:

- Env file lives at `app/backend/src/.env` (not next to `.env.example`). Required beyond the
  example: `ESI_USER_AGENT` (required by `core/config.py`), `AGGREGATION_REGION_IDS` — which
  must be a **JSON list** (`[10000002]`); a bare int or comma-separated string crashes at
  startup despite validator comments claiming otherwise.
- Valkey/Redis must be running (APScheduler `RedisJobStore`).
- Every backend restart **drops and recreates all tables** (`main.py:128–137`) and immediately
  re-runs aggregation against the configured regions (dev limit 100 contracts) — real data
  appears minutes after boot, not instantly.
- Two divergent Settings classes exist (`fastapi_app/config.py` vs `fastapi_app/core/config.py`)
  with different requirements — setup docs must satisfy both.
- Backend tests require a real Postgres via `DATABASE_URL_TESTS` (`tests/conftest.py:31`).
- These belong in the rewritten CONTRIBUTING.md frontend/dev-setup sections at milestone end.

## Teardown & documentation updates

Delete in this milestone:

- `app/frontend/angular/` (git history preserves it)
- `design/angular/` (Angular-specific guidance)

Update at milestone end:

- `README.md` and `CONTRIBUTING.md` frontend sections (stack, setup incl. backend
  prerequisites above, commands, exact-pin dependency policy).
- `design/specifications/test-spec.md` frontend sections (Karma/Jasmine/Protractor →
  Vitest/RTL/Playwright).
- `design/specifications/accessibility-spec.md` and `i18n-spec.md`: replace Angular-specific
  mandatory guidance with the React equivalents / explicit M1 deferral noted above.

## Process

1. ~~Design approved in session~~ ✔
2. ~~Adversarial review of this spec; findings incorporated~~ ✔ (2026-07-11)
3. Implementation plan (writing-plans-enhanced) covering: backend enablement fixes + regression
   tests, scaffold (Vite app, Tailwind v4, TanStack Router/Query, generated API client, dev
   proxy, lint/format/test wiring), one working end-to-end contract fetch rendering real data,
   teardown + doc updates.
4. `/impeccable` drives the design system and the full M1 interface build on top.
5. Milestone 2 (separate spec): EVE SSO (F004) — includes the backend OAuth work and the
   client-state conversation. Backend feature gaps listed under "Deferred F002/F003 criteria"
   get scheduled across subsequent milestones.
