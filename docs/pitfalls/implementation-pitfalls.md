# Implementation Pitfalls

What to implement and why. Read before starting any task; add entries when a bug's root
cause is a reusable trap, not a one-off typo. Each entry: **ID — trap — why it happens —
what to do instead — where it bit us.**

## FASTAPI-1 — `Depends(Model)` sends list fields to the GET request body

A Pydantic model used via `Depends(Model)` binds scalar fields to query params but any
non-scalar field (e.g. `Optional[List[int]]`) to the **request body** — silently. Repeated
query params are ignored (200 OK, unfiltered), and browsers cannot send a GET body at all.
**Do instead:** declare query-param models as `Annotated[Model, Query()]` (FastAPI ≥ 0.115).
**Bit us:** `region_ids`/`system_ids`/`station_ids`/`type_ids` in `ContractFilters` were
unusable from any browser client (found by 2026-07-11 adversarial spec review).

## SQLA-1 — Paginating a joined query paginates joined rows, not parent entities

`offset/limit` applied to a query that joins a one-to-many child table operates on the
duplicated joined rows; de-duplicating afterwards (`.unique()`) yields short pages, and
parents can be skipped or duplicated across page boundaries while the distinct count query
disagrees. **Do instead:** paginate over distinct parent IDs (grouped subquery with
aggregate-based ordering), then load the page's entities and restore the ID order.
**Bit us:** `get_contracts` pagination under `search`/`is_bpc`/`type_ids`/`ship_name` sort.

## FASTAPI-2 — Declared-but-unimplemented filter params ship dead controls

A filter param that the schema accepts but the service never applies looks functional to
every layer above it (API docs, generated clients, UI). **Do instead:** before exposing any
filter in a client, verify the service layer actually applies it. Mark known-inert params in
the schema description. **Bit us:** `min_me`/`max_me`/`min_te`/`max_te` are accepted and
silently ignored (`contract_service.py` — ME/TE data not in the model).

## PROXY-1 — FastAPI trailing-slash 307 escapes a prefix-rewriting proxy

The backend mounts routes bare (e.g. `/contracts/`) and the dev proxy adds/strips `/api/v1`.
Requesting `/contracts` (no slash) triggers a 307 whose `Location` lacks the proxy prefix,
so the redirect escapes to the SPA origin and fails. **Do instead:** clients call schema
paths verbatim, including trailing slashes; the openapi-fetch client's `baseUrl` owns the
`/api/v1` prefix.

## ENV-1 — pydantic-settings JSON-decodes complex env fields before validators run

A `List[int]` settings field only accepts a JSON list (`AGGREGATION_REGION_IDS=[10000002]`).
A bare int or comma-separated string crashes at startup even if a field validator claims to
handle it — pydantic-settings JSON-decodes complex types first. Also note: the backend loads
env from `app/backend/src/.env` (not next to `.env.example`), requires `ESI_USER_AGENT`, and
there are two divergent Settings classes (`fastapi_app/config.py` and
`fastapi_app/core/config.py`) — setup docs must satisfy both.

## ENV-2 — Backend restart wipes and re-ingests all data

`main.py` drops and recreates all tables on every startup and immediately re-runs
aggregation (dev limit: 100 contracts from configured regions). Real data appears minutes
after boot, not instantly. Don't diagnose an empty contract list as a frontend bug until
ingestion has had time to run.
