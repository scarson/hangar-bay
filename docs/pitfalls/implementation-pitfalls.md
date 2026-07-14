# Hangar Bay — Implementation Pitfalls & Review Findings

> **Purpose:** Document implementation traps, design flaws, and corrected decisions that would cause production failures, security vulnerabilities, or data correctness bugs if shipped. This document is the primary code review reference for the Hangar Bay codebase.
>
> **What to implement and why.** Read before starting any task; add entries when a bug's root cause is a reusable trap, not a one-off typo. Each entry follows: **ID — the flaw — why it matters — the fix (do instead) — where it bit us.**
>
> **Relationship to testing-pitfalls.md:** This document specifies *what* to implement and *why*. `docs/pitfalls/testing-pitfalls.md` specifies *how to verify* those implementations work correctly. They are complementary — cross-references are noted inline.
>
> **Last validated against codebase:** 2026-07-12 (replace when you audit against the current code)

---

## How to Use This Document

This document serves three audiences. Start here, then go directly to the section you need.

**If you're implementing code:** Go to the domain section matching your work area. Each entry has a clear *Flaw → Why It Matters → Fix → Where It Bit Us* structure. Follow the Fix. The provenance teaches the generalizable principle so you'll catch the next instance of this pattern.

**If you're reviewing code:** Go to your domain section's **Review Checklist** at the end. Each item is a pass/fail check derived from the pitfalls above it. If a checklist item fails, read the referenced pitfall for context.

**If you're maintaining this document:** Every pitfall discovered during implementation, review, or debugging MUST be added here. See the maintenance sections at the end of this file (Appendix C). Partial updates cause drift.

---

## Table of Contents

| § | Section | You're working on... | Entries | Checklist |
|---|---------|---------------------|---------|-----------|
| 1 | [API & Request Binding](#section-1-api--request-binding) | FastAPI request/query binding, filter params, dev-proxy routing | FASTAPI-1, FASTAPI-2, PROXY-1 | §1.C |
| 2 | [Data & Persistence](#section-2-data--persistence) | SQLAlchemy queries, pagination over joins | SQLA-1 | §2.C |
| 3 | [Environment & Dev Loop](#section-3-environment--dev-loop) | Settings/env loading, startup ingestion, dev-server hygiene | ENV-1, ENV-2, ENV-3, ENV-4, ENV-5, ENV-6 | §3.C |
| 4 | [External Integrations (ESI)](#section-4-external-integrations-esi) | Calling EVE's ESI API — route versions, deprecations, upstream status | ESI-1 | §4.C |
| — | [Orchestration](#orchestration) | Parallel subagent dispatch and output persistence | ORCH-1 | §Orchestration.C |
| A | [Historical Changelog](#appendix-a-historical-changelog) | Provenance, validation dates, review process meta-observations | — | — |
| B | [Unified Summary Table](#appendix-b-unified-summary-table) | All pitfalls at a glance, with severity and status | — | — |
| C | [Document Maintenance Guide](#appendix-c-document-maintenance-guide) | How to add, update, and supersede entries | — | — |

---

# Section 1: API & Request Binding

> **Reader context:** I'm building or reviewing FastAPI request handling — query-parameter binding, filter models, and how the SPA/dev-proxy reaches backend routes.
>
> These traps share a theme: a filter or route can look correct at every layer above HTTP (schema, generated client, service) while being silently unreachable or inert over the wire.

---

### FASTAPI-1: `Depends(Model)` sends list fields to the GET request body

**The Flaw:** A Pydantic model used via `Depends(Model)` binds scalar fields to query params but any non-scalar field (e.g. `Optional[List[int]]`) to the **request body** — silently.

**Why It Matters:** Repeated query params are ignored (200 OK, unfiltered), and browsers cannot send a GET body at all — so the filter is unreachable from any browser client while every server-side layer still looks healthy.

**The Fix:** Declare query-param models as `Annotated[Model, Query()]` (FastAPI ≥ 0.115).

**Where It Bit Us:** `region_ids`/`system_ids`/`station_ids`/`type_ids` in `ContractFilters` were unusable from any browser client (found by 2026-07-11 adversarial spec review). See testing-pitfalls.md TEST-1.

---

### FASTAPI-2: Declared-but-unimplemented filter params ship dead controls

**The Flaw:** A filter param that the schema accepts but the service never applies looks functional to every layer above it (API docs, generated clients, UI).

**The Fix:** Before exposing any filter in a client, verify the service layer actually applies it. Mark known-inert params in the schema description.

**Where It Bit Us:** `min_me`/`max_me`/`min_te`/`max_te` are accepted and silently ignored (`contract_service.py` — ME/TE data not in the model).

---

### PROXY-1: FastAPI trailing-slash 307 escapes a prefix-rewriting proxy

**The Flaw:** The backend mounts routes bare (e.g. `/contracts/`) and the dev proxy adds/strips `/api/v1`. Requesting `/contracts` (no slash) triggers a 307 whose `Location` lacks the proxy prefix, so the redirect escapes to the SPA origin and fails.

**The Fix:** Clients call schema paths verbatim, including trailing slashes; the openapi-fetch client's `baseUrl` owns the `/api/v1` prefix.

---

### §1.C — Review Checklist

- [ ] **Query-param models use `Annotated[Model, Query()]`, not `Depends(Model)`** — confirm non-scalar fields (e.g. `List[int]`) bind to query params, not the GET body (FASTAPI-1)
- [ ] **Every filter param the schema accepts is actually applied by the service layer** — known-inert params are explicitly marked in the schema description (FASTAPI-2)
- [ ] **Clients call schema paths verbatim, including trailing slashes** — the openapi-fetch `baseUrl` owns the `/api/v1` prefix; no bare-path request 307-escapes the proxy (PROXY-1)

---

# Section 2: Data & Persistence

> **Reader context:** I'm writing or reviewing SQLAlchemy queries — especially anything that paginates, sorts, or joins one-to-many relationships.

---

### SQLA-1: Paginating a joined query paginates joined rows, not parent entities

**The Flaw:** `offset/limit` applied to a query that joins a one-to-many child table operates on the duplicated joined rows.

**Why It Matters:** De-duplicating afterwards (`.unique()`) yields short pages, and parents can be skipped or duplicated across page boundaries while the distinct count query disagrees.

**The Fix:** Paginate over distinct parent IDs (grouped subquery with aggregate-based ordering), then load the page's entities and restore the ID order.

**Where It Bit Us:** `get_contracts` pagination under `search`/`is_bpc`/`type_ids`/`ship_name` sort. See testing-pitfalls.md TEST-4.

---

### §2.C — Review Checklist

- [ ] **Pagination over a one-to-many join paginates distinct parent IDs, not duplicated joined rows** — grouped subquery with aggregate-based ordering; page entities re-loaded and restored to the ID order (SQLA-1)

---

# Section 3: Environment & Dev Loop

> **Reader context:** I'm configuring settings/env, or debugging why the backend has no data / behaves oddly in the dev loop.
>
> Several of these are not shipped-code bugs but dev-loop traps that repeatedly cost debugging sessions — an empty database that *looks* like a frontend or data bug is almost always one of these.

---

### ENV-1: pydantic-settings JSON-decodes complex env fields before validators run

**The Flaw:** A `List[int]` settings field only accepts a JSON list (`AGGREGATION_REGION_IDS=[10000002]`). A bare int or comma-separated string crashes at startup even if a field validator claims to handle it — pydantic-settings JSON-decodes complex types first.

**Also note:** the backend loads env from `app/backend/src/.env` (not next to `.env.example`) and requires `ESI_USER_AGENT`. (Prior to the M2 settings consolidation there were two divergent Settings classes — `fastapi_app/config.py` and `fastapi_app/core/config.py` — that setup docs had to satisfy both; M2 consolidated them into the single `core/config.py` Settings, so this is now a single-class concern. See ENV-4 for the consolidated class's `extra="ignore"` requirement.)

---

### ENV-2: Backend restart wipes and re-ingests all data

**The Flaw:** `main.py` drops and recreates all tables on every startup and immediately re-runs aggregation (dev limit: 100 contracts from configured regions). Real data appears minutes after boot, not instantly.

**The Lesson:** Don't diagnose an empty contract list as a frontend bug until ingestion has had time to run.

---

### ENV-3: uvicorn --reload + startup ingestion + the Valkey lock interact badly in dev

**The Flaw:** Every backend source edit triggers a reload, which drops/recreates all tables (ENV-2) and starts a fresh aggregation run; killing a run mid-flight (reload, pkill, app restart) can strand the Valkey lock so the NEXT startup run logs "already running" and silently skips — leaving an empty database that looks like a data bug.

**The Fix:** Finish all backend edits first, then run one clean cycle: `docker exec hangar_bay_valkey valkey-cli DEL "hangar-bay:aggregation:lock"`, `touch app/backend/src/fastapi_app/main.py`, then hand off the backend until ingestion completes (first run ~2-7 min; ESI ETag/TTL caches in Valkey make repeats much faster). The lock is TTL-bounded (30 min) and fencing-tokened since `d16d145`, so production self-heals; this is purely a dev-loop trap.

**Also:** run dev servers as tracked background tasks with visible logs — a detached server logging to `/dev/null` cost a debugging session when stale logs from a dead process were mistaken for live state.

---

### ENV-4: pydantic-settings rejects unknown .env keys unless extra="ignore"

**The Flaw:** The consolidated `Settings` reads the whole `app/backend/src/.env` file. Without `extra="ignore"` in `model_config`, any key present in `.env` that is NOT a declared field aborts construction at import — crashing boot.

**Why It Matters:** During M2, adding `TOKEN_CIPHER_KEYS` to `.env` before the field existed on the class crashed the baseline app at startup. Unknown ENV VARS are ignored (pydantic-settings only reads env vars matching fields), but unknown `.env`-FILE keys are not — this trap is `.env`-file-specific.

**The Fix:** Keep `extra="ignore"` on the consolidated `Settings.model_config` (`core/config.py`). New config always adds the field AND documents it in `.env.example`.

**Where It Bit Us:** M2 settings consolidation (2026-07-12).

---

### ENV-5: The backend venv/CI pin Python 3.12 until the FastAPI 0.115 hold lifts

> **SUPERSEDED (2026-07-13):** Hold lifted — no longer applicable. The FastAPI-current / Python-3.14 chore migrated the backend to FastAPI 0.139 / Starlette 1.3.1 and moved the venv and both CI `python-version` pins to 3.14. FastAPI 0.139 precomputes `Dependant.is_coroutine_callable` at route registration and no longer calls the 3.14-deprecated `asyncio.iscoroutinefunction`, so the 16 DeprecationWarnings are gone at the source (never a filter mask). The spike that "broke 19 tests" traced to `prometheus-fastapi-instrumentator` 7.1.0, whose middleware crashes in `_get_route_name` against Starlette 0.52.x despite its `starlette<1.0` pin; reaching current Starlette required bumping it to 8.0.2 (`starlette>=1.0`). The pydantic-relock context below stays true; original content preserved for history.

**The Flaw:** The default machine `python3` is CPython 3.14. The pydantic stack is relocked with cp314 wheels (pydantic 2.13 / pydantic-core 2.46), so 3.14 installs and passes — but FastAPI is deliberately held at 0.115 (`fastapi>=0.115.12,<0.116` in pyproject): its internals call `asyncio.iscoroutinefunction`, which 3.14 deprecates, emitting a DeprecationWarning block in every test run and violating the pristine-test-output gate. The unheld resolve (FastAPI 0.139 / Starlette 0.52) broke 19 tests on first contact — a real migration, not a version bump.

**The Fix:** Keep the backend venv and CI on Python 3.12 (`actions/setup-python` + `setup-pdm` with `python-version: '3.12'`) until a dedicated FastAPI/Starlette migration lands; then flip the pins to 3.14 and delete this entry. Never mask the warnings with a filter, and do not "fix" application code for other interpreter versions.

**Where It Bit Us:** M2 CI bring-up + the pydantic relock spike (2026-07-12).

---

### ENV-6: F811 cascade when removing debug prints/functions

**The Flaw:** The repo's flake8 config ignores `F401` (unused import) but NOT `F811` (redefinition). Deleting a debug print/function whose sole job consumed a module-level `settings` import leaves that import orphaned — invisible under the F401 ignore — and any same-named function parameter (e.g. a `settings` argument on some other function in the same module) then trips a live `F811` ("redefinition of unused `settings`").

**Why It Matters:** Because F401 is silenced project-wide, an agent removing debug scaffolding gets no signal that the import is now dead; the failure only surfaces as an unrelated-looking F811 on a different function elsewhere in the file, which reads like a pre-existing lint bug rather than a consequence of the deletion just made.

**The Fix:** When deleting a debug print/function, always check whether it was the last consumer of any module-level import it referenced, and drop the now-orphaned import (and any comment that falsified it) in the same edit — don't rely on flake8 to catch it, since F401 is ignored here.

**Where It Bit Us:** M2 Phase 1 settings consolidation, twice (DISC-EXEC-2, 2026-07-12).

---

### §3.C — Review Checklist

- [ ] **Complex settings fields (e.g. `List[int]`) are supplied as JSON** — `AGGREGATION_REGION_IDS=[...]`; env is loaded from `app/backend/src/.env`; `ESI_USER_AGENT` is set; the single consolidated `core/config.py` Settings class is satisfied (ENV-1)
- [ ] **Empty data after a backend (re)start is not diagnosed as a frontend bug** — startup drops/recreates tables and re-ingests; give ingestion time before concluding a data bug (ENV-2)
- [ ] **After backend edits, run one clean cycle** — clear the Valkey aggregation lock, `touch main.py` once, hand off until ingestion completes; run dev servers as tracked background tasks with visible logs (ENV-3)
- [ ] **`Settings.model_config` keeps `extra="ignore"`** — any new config field is also documented in `.env.example` (ENV-4)
- [ ] **Backend venv/CI run Python 3.14** — the FastAPI 0.115 / Python-3.12 hold is resolved (ENV-5, superseded); keep the two CI `python-version` pins in sync and never mask interpreter warnings with a filter (migrate off the deprecated API instead)
- [ ] **Deleting a debug print/function also drops any module-level import it orphaned** — flake8 ignores F401 here so it won't catch it, but F811 will trip on an unrelated function (ENV-6)

---

# Section 4: External Integrations (ESI)

> **Reader context:** I'm adding or changing a call to EVE Online's ESI API — a data route, the SSO/JWT path, or an upstream health check.
>
> ESI removes legacy and unversioned routes on published dates. Code that names a specific version survives these removals; code that leans on `/latest` or legacy meta-routes breaks on the removal date with no change on our side.

---

### ESI-1: Pin explicit ESI route versions; avoid removed legacy/meta routes

**The Flaw:** ESI periodically retires unversioned and legacy routes. The "Spring Cleaning" removal (24 March 2026) dropped `/status.json`, `/swagger.json` (plus `/dev/`, `/_dev/`, `/legacy/`, `/_legacy/` variants), `/diff`, `/versions`, and `/headers`, and began redirecting `/verify` to `https://login.eveonline.com/v2/oauth/verify` (the redirect itself removed 28 April 2026). The `/latest/*` alias is soft-deprecated — its `swagger.json` is frozen and new routes appear only in the OpenAPI specs.

**Why It Matters:** A request built on any of these routes keeps working until the removal date, then fails with no code change on our side — the hardest kind of breakage to anticipate.

**The Fix:**
*   Pin an explicit version prefix on every ESI request (`/v1`, `/v3`, …), matching the `ESIClient` convention (`core/esi_client_class.py`). Never `/latest`.
*   For upstream health, use `/meta/status` (values `OK` / `Degraded` / `Down` / `Recovering`) — never the removed `/status.json`. See `design/specifications/observability-spec.md` §2.5.
*   Validate SSO JWTs offline against JWKS (`services/sso.py`), not by calling `/verify`.
*   Consume ESI data from the OpenAPI specs, not the removed legacy `swagger.json`.

**Where It Stands:** The backend already complies — every data route pins `/v1`/`/v3` and JWTs are validated offline, so Hangar Bay was unaffected by the 24 March 2026 removals. The lone `/latest` usage, the `generate-regions.mjs` build script, was pinned to `/v1`. References: "Spring Cleaning: legacy routes removed 24 March 2026" (https://developers.eveonline.com/blog/spring-cleaning-legacy-routes-removed-24-march-2026) and "A better view on status: improving ESI health monitoring" (https://developers.eveonline.com/blog/a-better-view-on-status-improving-esi-health-monitoring).

### §4.C — Review Checklist

- [ ] **Every ESI request names an explicit version prefix** (`/v1`, `/v3`, …), not `/latest` (ESI-1)
- [ ] **Upstream status checks target `/meta/status`, not the removed `/status.json`** (ESI-1)
- [ ] **SSO JWT validation is offline against JWKS, not a `/verify` round-trip** (ESI-1)

---

## Orchestration

Pitfalls that arise when a session dispatches parallel subagents and consolidates their output. The canonical rules live in `docs/git-strategy.md` → §Multi-agent coordination → Output persistence. This section is the discovery hook for plan writers who arrive here via the `writing-plans-enhanced` (or equivalent) mandated-read path — it does NOT restate the rules in full.

### ORCH-1: Analysis Dispatches Must Persist Findings Before Returning

**Trigger:** Your plan dispatches parallel subagents (bug hunts, audits, phased analysis, parallel investigations) whose findings would be expensive to regenerate if lost.

**What you need to do:** Every such dispatched subagent MUST write its complete report to a persistent file BEFORE returning; the response message is not the sole record.

**Read the full rule:** `docs/git-strategy.md` → §Multi-agent coordination → Output persistence. That section carries the copy-pasteable prompt block (with `<PERSISTENCE_PATH>` substitution), file-path conventions, orchestrator commit cadence, and the cases where the rule doesn't apply.

**Why this is in implementation-pitfalls:** because the plan-writing skill mandates reading this file, and this rule has to be noticed at plan-write time (when the dispatch prompts are being drafted), not at execution time (when it's too late). The failure mode — orchestrator context compacting mid-consolidation and lossily dropping findings — is predictable and preventable if the plan author builds persistence into the dispatch prompts from the start.

### §Orchestration.C — Review Checklist

- [ ] **Dispatch prompts include the mandatory-persistence block** — copy from `docs/git-strategy.md` §Output persistence; substitute `<PERSISTENCE_PATH>` with a durable per-subagent path (ORCH-1)
- [ ] **Plan specifies exact persistence paths, not "write somewhere useful"** — ambiguous paths default to `/tmp` under pressure, which doesn't survive (ORCH-1)
- [ ] **Orchestrator commits subagent artifacts wave-by-wave** — committed files land on the campaign branch before consolidation begins (ORCH-1)

---

# Appendix A: Historical Changelog

## 2026-07-13 — ENV-5 superseded: FastAPI-current / Python-3.14 migration

- Lifted the FastAPI 0.115 hold: migrated the backend to FastAPI 0.139 / Starlette 1.3.1 (+ `prometheus-fastapi-instrumentator` 8.0.2, required for Starlette ≥1.0 — its 7.1.0 middleware crashes against Starlette 0.52.x despite a `starlette<1.0` pin). FastAPI 0.139 precomputes the dependant coroutine flag and no longer calls the 3.14-deprecated `asyncio.iscoroutinefunction`, eliminating the 16 DeprecationWarnings at the source (no filter mask). Flipped the backend venv and both CI `python-version` pins 3.12 → 3.14.
- Marked ENV-5 `SUPERSEDED` (kept its original body + the pydantic-relock context as history); rewrote the §3.C checklist item to the current 3.14 invariant and updated the Appendix B status row.

## 2026-07-12 — M2 additions: ENV-4, ENV-5, ENV-6; ENV-1 two-Settings text retired

- Added ENV-4 (pydantic-settings rejects unknown `.env` keys unless `extra="ignore"`) and ENV-5 (backend venv/CI pin Python 3.12 until the FastAPI 0.115 hold lifts) from the M2 EVE SSO plan (Phase 9, Task 9.2).
- Added ENV-6 (F811 cascade when removing debug prints/functions whose sole job consumed a module-level import) — a trap discovered twice during M2 Phase 1 settings consolidation (DISC-EXEC-2).
- Retired ENV-1's "two divergent Settings classes" claim (its "Also note" paragraph and the §3.C checklist line): M2 Phase 1 consolidated `fastapi_app/config.py` and `fastapi_app/core/config.py` into the single `core/config.py` Settings, so the setup-docs-must-satisfy-both text was false. ENV-1's JSON-decode trap itself is unchanged and remains live.

## 2026-07-12 — Restructured to the pitfalls-docs template

- Migrated this file to the standard template shape: added §How to Use, Table of Contents, per-section Review Checklists, the Orchestration §ORCH-1 universal entry, and Appendices A/B/C (summary table + maintenance framework).
- **Preserved all existing project entries with their IDs and facts:** FASTAPI-1, SQLA-1, FASTAPI-2, PROXY-1, ENV-1, ENV-2, ENV-3. Entries were regrouped into domain sections (API & Request Binding; Data & Persistence; Environment & Dev Loop) and reformatted into the Flaw → Why → Fix → Where-It-Bit-Us shape without dropping content or renumbering.

## 2026-07-12 — Testing infra & dev-loop traps recorded

- ENV-3 hardened with the Valkey-lock clean-cycle procedure after a detached-server / stale-log debugging session.

## 2026-07-11 — Adversarial spec review

- FASTAPI-1 discovered: ID-list `ContractFilters` params were GET-body-bound and unreachable from browser clients.

---

# Appendix B: Unified Summary Table

| ID | Title | Severity | Status | Domain |
|----|-------|----------|--------|--------|
| FASTAPI-1 | `Depends(Model)` sends list fields to the GET body | HIGH | VALIDATED | API & Request Binding |
| FASTAPI-2 | Declared-but-unimplemented filter params ship dead controls | MEDIUM | UNIMPLEMENTED | API & Request Binding |
| PROXY-1 | Trailing-slash 307 escapes a prefix-rewriting proxy | MEDIUM | VALIDATED | API & Request Binding |
| SQLA-1 | Paginating a joined query paginates joined rows | HIGH | VALIDATED | Data & Persistence |
| ENV-1 | pydantic-settings JSON-decodes complex env fields early | MEDIUM | VALIDATED | Environment & Dev Loop |
| ENV-2 | Backend restart wipes and re-ingests all data | LOW | VALIDATED | Environment & Dev Loop |
| ENV-3 | --reload + ingestion + Valkey lock interact badly in dev | MEDIUM | VALIDATED | Environment & Dev Loop |
| ENV-4 | pydantic-settings rejects unknown .env keys unless extra="ignore" | MEDIUM | VALIDATED | Environment & Dev Loop |
| ENV-5 | FastAPI 0.115 / Python-3.12 hold (resolved 2026-07-13: FastAPI 0.139 + Python 3.14) | LOW | SUPERSEDED | Environment & Dev Loop |
| ENV-6 | F811 cascade when removing debug prints/functions | LOW | VALIDATED | Environment & Dev Loop |
| ESI-1 | Pin ESI route versions; avoid removed legacy/meta routes | LOW | VALIDATED | External Integrations (ESI) |
| ORCH-1 | Analysis Dispatches Must Persist Findings | HIGH | VALIDATED | Orchestration |

Severity levels: `CRITICAL` (production data loss / security), `HIGH` (correctness bug under predictable conditions), `MEDIUM` (correctness bug under edge cases), `LOW` (cleanliness / clarity / dev-loop hazard).

Status values: `VALIDATED` (prescribed fix is implemented and tested), `UNIMPLEMENTED` (pitfall documented but fix not yet in code), `SUPERSEDED` (replaced by another entry or no longer applicable).

> **Note:** Severity and status above were inferred from each entry's text during the 2026-07-12 restructure (FASTAPI-2 is marked `UNIMPLEMENTED` because its inert `min/max_me/te` params still ship). Adjust when you next audit against the code.

---

# Appendix C: Document Maintenance Guide

## When to Update This Document

Update this document when any of the following occur:

| Trigger | Action |
|---------|--------|
| Bug hunt finds a generalizable pattern | Add a pitfall to the appropriate domain section |
| Health review flags a cross-cutting issue | Add or strengthen a pitfall |
| Implementation reveals a prescribed fix was wrong | Update the existing pitfall to match reality — the code is the source of truth |
| Code review catches a pitfall already documented here | Strengthen the entry with the new example |
| A pitfall's prescribed fix is implemented | Update the entry's status in Appendix B |
| A feature is removed or an approach abandoned | Mark the pitfall as SUPERSEDED with a note explaining why |
| testing-pitfalls.md adds a new section | Check if a cross-reference should be added here |

**Do NOT update this document for:**

- One-off implementation bugs that don't generalize to a pattern
- Code style preferences or formatting choices
- Performance optimizations without correctness implications

---

## How to Add a Pitfall

### Step 1: Choose the domain section

If the pitfall spans two domains, place it where the reader is most likely to look when they encounter the bug. Add a "See Also" cross-reference in the other section.

### Step 2: Assign the next ID

IDs are sequential within each section's prefix (`FASTAPI-3`, `ENV-4`, etc.). Check the last entry with that prefix and increment. Use a short prefix that matches the domain (2-7 letters, uppercase, descriptive). Existing IDs are load-bearing — they are referenced from handoff docs, CLAUDE.md, and session memory. Never renumber an existing entry.

### Step 3: Write the entry

**For complex findings** (non-obvious failure mode or architectural fix):

```markdown
### PREFIX-N: Title

**The Flaw:** What the code does wrong or what's missing.
**Why It Matters:** The production failure mode — what breaks, for whom, and why it's hard to detect.
**The Fix:** The specific code change or pattern to apply. Include a code example when the fix is non-trivial.
**Where It Bit Us:** The concrete incident and its provenance (date / review), if any.
```

**For simple findings** (one-line pattern substitution, self-evident why):

```markdown
### PREFIX-N: Title
[One paragraph: what's wrong, what to do instead, and why. No code example needed.]
```

**Use the right heuristic:** If an implementing agent could correctly apply the fix from just a one-line description without understanding the failure mode, use the condensed format. If they'd need to understand WHY to apply it correctly, use the full format.

### Step 4: Update the review checklist

Add a checkbox item to the section's review checklist (§X.C) that captures the key check for this pitfall.

### Step 5: Update the Table of Contents

Update the entry list in the TOC table (e.g., `FASTAPI-1, FASTAPI-2` becomes `FASTAPI-1, FASTAPI-2, FASTAPI-3`).

### Step 6: Update the Summary Table

Add a row to Appendix B with the pitfall ID, title, severity, status, and domain.

### Step 7: Check for cross-references

- Does testing-pitfalls.md need a corresponding test guidance entry?
- Does another domain section need a "See Also" pointer?
- Does the same pattern exist elsewhere in the codebase? Grep for other instances.

---

## How to Update an Existing Pitfall

1. **Read the current entry** and understand its intent
2. **Check the code** to see what actually changed
3. **Update the entry** to reflect reality — never preserve a prescription that contradicts the code
4. **Update Appendix B** status if it changed (e.g., `UNIMPLEMENTED` → `VALIDATED`)
5. **Check Appendix A** — add a changelog line noting the update date and reason

---

## How to Mark a Pitfall as Superseded

Do NOT delete pitfall entries. Mark them:

```markdown
### PREFIX-N: Title

> **SUPERSEDED (YYYY-MM-DD):** [Reason — e.g., "Feature removed in Phase 12" or "Replaced by PREFIX-M which covers the broader pattern"]

[Original content preserved below for historical context]
```

Update Appendix B status to `SUPERSEDED`.

---

## Completeness Checklist

**A pitfall update is not complete until ALL of these are done.** Partial updates are how this document drifts — and a drifted document is worse than no document, because it creates false confidence in protections that don't exist.

- [ ] Entry written in the correct domain section with the correct format
- [ ] Entry has the next sequential ID for its prefix (existing IDs never renumbered)
- [ ] TOC entry list updated
- [ ] Appendix B summary table row added/updated
- [ ] Review checklist (§X.C) updated with the corresponding check item
- [ ] Cross-references checked: testing-pitfalls.md, other domain sections, See Also block
- [ ] If the pattern could exist elsewhere in the codebase: grepped for other instances
- [ ] Appendix A changelog updated with date and source

**If you skip any of these steps, the next agent to read this document will not find your pitfall.** The TOC is the routing table — without it, your entry is invisible. The summary table is the audit trail — without it, the next health review won't know your finding was addressed.

---

## Voice and Style Reference

This document uses persuasion principles to ensure agents follow critical practices:

- **Authority** for bright-line rules: "MUST", "Never", "Always", "No exceptions"
- **Implementation intentions** for triggers: "When writing a query-param model, ALWAYS use `Annotated[Model, Query()]`"
- **Social proof via failure modes**: "Without this, the ID-list filters are unreachable from any browser client — every time"
- **Commitment** via checklists: the review checklists at the end of each section

When writing pitfall entries, apply these principles. A pitfall that says "consider using X" will be ignored under pressure. A pitfall that says "MUST use X — without it, Y happens every time" will be followed.

Reference: the `superpowers:writing-skills` skill (or equivalent in your skill library) carries the full persuasion-principles framework if you want to go deeper.
