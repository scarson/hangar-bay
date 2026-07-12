# Handoff — M1 + /impeccable design phase complete (2026-07-12)

> **Superseded (later on 2026-07-12)** by
> [`2026-07-12-e2e-docs-m2-kickoff-handoff.md`](./2026-07-12-e2e-docs-m2-kickoff-handoff.md) —
> priority-queue items 2–4 below (re-ingest/sanity, Playwright E2E, docs sweep) are done;
> the Runbook's `preview_start` note is stale (launch.json now lives at the MAIN repo's
> `.claude/launch.json`, pointing into this worktree).

## Headline state

- **Branch:** `claude/hangar-bay-frontend-rebuild-2e4fe7`, worktree at
  `.claude/worktrees/hangar-bay-frontend-rebuild-2e4fe7`. Tip `d16d145` + this handoff commit,
  **pushed**. Working tree clean.
- **PR:** [#22](https://github.com/scarson/hangar-bay/pull/22) against `main` — contains BOTH
  the M1 rebuild and the design phase (see the PR's design-phase comment). **Unmerged; merge is
  Sam's decision.**
- **Suites at tip:** frontend 47 tests + ESLint + strict `tsc -b`/Vite build green
  (`app/frontend/web`); backend 53 tests green (`app/backend`, needs `DATABASE_URL_TESTS`
  Postgres). Both independently re-run by the closing review gate.
- **Dev environment: DOWN.** The Claude Desktop restart killed the backend uvicorn, the Vite
  preview server, and the dev database content is stale/empty AND predates the
  `is_blueprint_copy`/enrichment-concurrency commits — re-ingest before any live verification
  (see Runbook below). Postgres + Valkey Docker containers were healthy at last check
  (`hangar_bay_postgres`, `hangar_bay_valkey`).

## What shipped this session (artifact pointers, newest last)

M1 milestone (plan with full per-phase execution record:
`docs/plans/2026-07-11-frontend-rebuild-m1-plan.md`; spec:
`docs/superpowers/specs/2026-07-11-frontend-rebuild-milestone-1-design.md`):
scaffold + backend enablement fixes + acceptance + Angular teardown + docs, commits
`598dd22..88cc75f`.

Design phase (no standalone plan doc — it ran via the impeccable craft flow; state lives in
`PRODUCT.md`, `DESIGN.md`, the commits below, and PR #22's design-phase comment):

| Commit | What |
|---|---|
| `f510c65` | `is_ship_contract` API filter param + PRODUCT.md + live config |
| `afdd015` | Item type→group→category enrichment; ship-flagging (F001 completion) |
| `aceda5a` | DESIGN.md — token map and visual-system rules |
| `84fcacf` | ESI object-endpoint fix (list-shaped ETag helper flattened dicts) |
| `733e398` | Sticky ship flags across 304 re-ingestion (upsert supplied-cols); hull-first labels |
| `ba9aaf8` | Design-review frontend findings (recovered from interrupted workflow fixer) |
| `d16d145` | Design-review completion: backend hardening (lock fencing, chunked UPDATEs, bounded-concurrency enrichment, object-GET retry, ENRICHMENT_INCOMPLETE status, `is_blueprint_copy` mapping) + frontend stragglers (history-back BackLink, sticky thead, live region, Filters Button) — full 23-finding ledger in the commit body |

Review provenance: five-lens audit (deep a11y / design-bans via Fable / states+responsive /
frontend code / backend enablers) → 23 actionable findings → all applied → independent Fable
closing gate **approved** (verdict + 4 nits recorded below, since the gate report itself is
ephemeral chat).

## Closing-gate nits (on record here; none block)

1. Live region reads "1 contracts match your filters" — no singular form
   (`ContractsPage.tsx` status region; its test pins the plural).
2. Price Min/Max inputs render mono-14px instead of the 13px `.text-data` step (`text-sm` from
   Input base wins font-size after the @utility reordering) — 1px cosmetic drift.
3. Aggregation lock has fencing but no TTL watchdog/refresh: two overlapping runs are possible
   if a run outlives 1800s (idempotent upserts → wasted work, not corruption).
4. Theoretical: the out-of-range-page redirect effect wouldn't re-fire when hand-editing the
   URL between two distinct out-of-range pages with identical pageCount (unreachable via UI).

## Deferred / not-started (each with unblock condition + authoritative pointer)

- **Playwright E2E** — the M1 spec's Testing section defers E2E "to the end of the /impeccable
  implementation phase." That phase is now over ⇒ **this is due and unowned.** Unblock: none —
  pickable now. Authority: spec §Testing
  (`docs/superpowers/specs/2026-07-11-frontend-rebuild-milestone-1-design.md`).
- **`start_location_system_id` ingestion gap** — same class as the fixed region/ship-flag gaps;
  needed before any milestone exposes system filters. Authority: M1 plan §Discoveries.
- **Spec-doc Angular residue** — accessibility/observability/security-spec +
  `design/features/*.md` + the feature template still carry Angular-as-current guidance.
  Authority: M1 plan §Discoveries (feature-spec bullet added by the spec-sweep agent).
- **Docs odds-and-ends** (milestone-gate nits, pre-existing): web README promissory closing
  line; CONTRIBUTING "SQLite for testing" claims vs the real Postgres requirement; backend test
  file headers claiming "in-memory SQLite"; README's empty "Implementation Status" heading and
  Angular-era screenshot (a fresh screenshot is now worth taking — the UI exists).
- **Backend hygiene (pre-existing, out of all scopes so far):** debug `print()` noise in
  config/aggregation modules; flake8 red (C901 on the ETag helper, E261 comments) — pytest is
  the enforced gate today; two divergent Settings classes.
- **M2: EVE SSO (F004)** — next milestone; per repo conventions expect brainstorm → spec →
  adversarial spec review → /writing-plans-enhanced → plan-review-cycle → execution. Includes
  backend OAuth work and the client-state conversation. Authority: M1 spec §Process step 5.
- **i18n** — explicitly deferred by M1 spec Non-goals; revisit before feature milestones.
- **Frontend CI** — a11y build-fail wiring waits on CI existing at all.

## Operational guardrails accumulated (durable homes noted)

- Dev-loop reload/lock/ingestion discipline → `docs/pitfalls/implementation-pitfalls.md` ENV-3
  (new this session). ENV-1/ENV-2 cover env-file format and wipe-on-restart.
- Ask questions in plain session text, never AskUserQuestion → user memory.
- Have plan reviewers EXECUTE scaffolding steps (toolchain drift) → user memory + proven again
  this session by the ESI seam bug (dict-returning mocks hid what only a live run caught).
- Background workflows die with the desktop app; recover via journal.jsonl + working tree, and
  prefer committing recovered fixer work before continuing (this session: `ba9aaf8`).
- Commit trailer convention: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## Priority queue (suggested)

1. Sam: merge decision on PR #22 (everything else can proceed on the branch either way).
2. Re-ingest + live sanity pass (Runbook) — verify BPC badges now appear on real data
   (first dataset ever to carry `is_blueprint_copy`) and ships-only default view.
3. Playwright E2E (due per spec; the app + states are stable now).
4. Docs residue sweep (spec Angular residue + README/CONTRIBUTING odds-and-ends + screenshot).
5. M2 EVE SSO brainstorm/spec.

## Runbook (fresh session, cold machine)

```bash
cd /Users/sam/Code/hangar-bay/.claude/worktrees/hangar-bay-frontend-rebuild-2e4fe7
docker compose -f app/backend/docker/compose.yml -f app/backend/docker/compose.dependencies.yml up -d --wait postgres_db valkey_cache
export PATH="$HOME/.local/bin:$PATH"      # pdm lives here (uv tool install)
docker exec hangar_bay_valkey valkey-cli DEL "hangar-bay:aggregation:lock"
(cd app/backend && pdm run dev)            # tracked background task; wipes+re-ingests on boot
# wait for: curl -s "localhost:8000/contracts/?is_ship_contract=true&size=1" → total > 0
# frontend: preview_start name=hangar-bay-web (.claude/launch.json) → localhost:5173
```

Backend env lives at `app/backend/src/.env` (already present; `AGGREGATION_REGION_IDS` must be
a JSON list). Test DB: `hangar_bay_test` via `DATABASE_URL_TESTS` (already in .env).

## Adversarial review of this handoff

- Round 1 — naive fresh agent: 2 findings applied (runbook added; PR-contents clarified).
- Round 2 — recency bias: 3 findings applied (Playwright deferral surfaced from the M1 spec;
  pre-existing backend hygiene items; Angular-era screenshot note).
- Round 3 — seam auditor: 2 findings applied (dev-DB-predates-BPC-mapping seam; interrupted
  workflow recovery attribution ba9aaf8/d16d145).
- Round 4 — guardrails auditor: 1 finding applied (ENV-3 pitfall written instead of living here).
- Round 5 — loss-averse: 1 finding applied (gate nits transcribed — they existed only in chat).
- Round 6 — dead-environment auditor (session-specific: this session ended with every live
  process killed by an app restart, and the next agent inherits ONLY disk state): 2 findings
  applied (explicit "environment DOWN" headline; stale-DB warning tied to the exact commits the
  data predates).
- Round 7 — self-consistency re-pass after fixes (holistic top-to-bottom read): 1 finding
  applied (a garbled commit-SHA table cell, corrected to `aceda5a` from the session record).
- Final full pass: zero material findings.
