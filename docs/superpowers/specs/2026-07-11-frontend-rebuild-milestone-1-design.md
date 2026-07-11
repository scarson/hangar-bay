# Frontend Rebuild — Milestone 1: Public Contract Browsing

**Date:** 2026-07-11
**Status:** Approved (design approved in session; spec pending user review)
**Supersedes:** the Angular frontend (`app/frontend/angular/`) and Angular-specific design docs (`design/angular/`)

## Context

Hangar Bay's backend is a working FastAPI application: ESI contract ingestion, PostgreSQL +
Valkey, a scheduler, observability, tests, and migrations. The frontend, last touched mid-2025,
is an abandoned Angular skeleton — one half-built contracts feature with several `.bak` files.
The Angular effort is being scrapped entirely and the frontend restarted on a stack that
present-day AI agents handle well. Design-system work and UI implementation will be driven by
the `/impeccable` skill after the foundation in this spec is scaffolded.

## Goals

- Replace the Angular app with a React SPA foundation at `app/frontend/web/`.
- Deliver the public browsing experience: contract list with search/filter/sort/pagination
  (F002) and contract detail view (F003), against the existing backend API — no backend changes.
- Keep the API layer and data-fetching hooks cleanly separated from components so they could be
  extracted into a package shared with a future React Native app.

## Non-goals (later milestones)

- EVE SSO authentication (F004) and everything downstream of it: saved searches (F005),
  watchlists (F006), alerts (F007).
- SSR/SEO work, PWA packaging, mobile apps.
- Backend changes of any kind.
- Global client-state management (no store until a milestone needs one).

## Stack decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | React 19 + TypeScript (strict) | Deepest agent training coverage; best fit for /impeccable; best hedge for a future React Native app |
| Build | Vite | Plain SPA; FastAPI is already the server, so no meta-framework |
| Styling | Tailwind CSS v4 | Utility-first with tokens as CSS variables; /impeccable builds the design system on this foundation |
| Routing | TanStack Router | Typed, first-class URL search params — F002's filter state lives in the URL (shareable links, working back button) |
| Server state | TanStack Query | Caching, retries, loading/error states; hooks are mobile-shareable |
| API types | Generated via `openapi-typescript` + `openapi-fetch` | FastAPI publishes the OpenAPI schema; `npm run generate:api` keeps frontend types mechanically in sync with Pydantic schemas — eliminates type drift |
| Unit tests | Vitest + React Testing Library | Aligned with `design/specifications/test-spec.md`; Playwright deferred until there is real UI to smoke-test |
| Lint/format | ESLint (flat config) + Prettier | Matches backend's lint/format discipline |

## Architecture

```
app/frontend/web/
  src/
    lib/api/              # generated OpenAPI types + thin typed client (mobile-shareable)
    features/contracts/
      hooks/              # TanStack Query hooks: useContracts(filters), useContract(id)
      components/         # ContractTable, FilterBar, ContractDetail, ...
      routes              # /contracts (list), /contracts/$id (detail)
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

## Backend API surface (existing, consumed as-is)

Paths below are as the SPA sees them (`/api/v1` prefix added by proxy; backend serves them bare):

- `GET /api/v1/contracts/` → `PaginatedResponse[ContractSchema]`
  (`total`, `page`, `size`, `items`). Filters (query params, per `ContractFilters`):
  - `search` (text), `min_price`/`max_price`, `min_collateral`/`max_collateral`,
    `min_runs`/`max_runs`, `min_me`/`max_me`, `min_te`/`max_te` (BPC attributes),
    `region_ids`/`system_ids`/`station_ids`/`type_ids` (multi-value), `is_bpc`,
    `page` (≥1), `size` (1–100, default 50),
    `sort_by` ∈ {date_issued, date_expired, price, collateral, ship_name, volume},
    `sort_direction` ∈ {asc, desc}.
- `GET /api/v1/contracts/{contract_id}` → `ContractSchema` with nested `items:
  ContractItemSchema[]` (type names, quantities, BPC flags, market group).

The milestone 1 UI must expose search, price range, region/system filters, BPC toggle, sorting,
and pagination at minimum; remaining filters (collateral, runs, ME/TE, station, type-ID) are
exposed as the FilterBar design matures under /impeccable. The generated client covers the full
surface either way.

## Error handling & UX states

- Query-level error boundaries with a retry affordance; no blank screens on failure.
- Skeleton loading states for list and detail; explicit empty state for zero-result filters.
- Visual/interaction specifics of these states are designed during the /impeccable phase; the
  scaffold guarantees the mechanical hooks (error/loading/empty branches) exist from day one.

## Testing

- Vitest + RTL: filter/search-param serialization round-trips, query hooks (mocked client),
  component states (loading/error/empty/populated).
- The generated API client itself is not unit-tested (machine-generated); its correctness is
  covered by hook tests against recorded response shapes.
- E2E (Playwright) deferred to the end of the /impeccable implementation phase.

## Teardown

In this milestone, delete:
- `app/frontend/angular/` (git history preserves it)
- `design/angular/` (Angular-specific guidance; framework-agnostic specs in
  `design/specifications/` and `design/features/` remain authoritative)

Update `README.md` and `CONTRIBUTING.md` frontend sections (stack, setup, commands) at the end
of the milestone.

## Process

1. ~~Design approved in session~~ ✔
2. User reviews this spec.
3. Implementation plan (writing-plans) for the scaffold: Vite app, Tailwind v4, TanStack
   Router/Query, generated API client, dev proxy, lint/format/test wiring, one working
   end-to-end contract fetch rendering real data.
4. `/impeccable` drives the design system and the full F002/F003 interface build on top.
5. Milestone 2 (separate spec): EVE SSO (F004) — includes the backend OAuth work and the
   client-state conversation.
