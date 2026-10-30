<!-- ABOUTME: Session-close handoff for the 2026-08-06/07 F008 overnight build — what shipped to dev, -->
<!-- ABOUTME: what Phase D's executor picks up, the production-activation runbook, and Sam's review queue. -->

# Handoff — F008 overnight build (2026-08-06 → 2026-08-07)

**Read this first.** The authoritative execution state lives in the plan's banners — [`docs/superpowers/plans/2026-08-06-f008-type-aware-contract-browsing.md`](../plans/2026-08-06-f008-type-aware-contract-browsing.md) — and the reasoning behind every consequential call lives in the decision log, [`2026-08-06-f008-decision-log.md`](../plans/2026-08-06-f008-decision-log.md) (D1–D11). This handoff is the narrative index over those two documents, not a replacement for them.

## 0. Things only Sam can do

1. **Rotate `RENDER_API_KEY`** — leaked into a session transcript 2026-08-02; repeated in every handoff until Sam states it is rotated (the 1Password item that materializes the repo-root `.env` needs updating too).
2. **Remove the temporary IP allow rule** `198.37.143.189/32` from `hangar-bay-db` (Connections → allowed source IPs; correct end state: empty list).
3. **Ratify or overrule decision-log D8** (range-filter branch semantics where spec §3.1 conflicts with its own existential rule — codex formally objected to the plan-local ruling; implementation follows the existential reading; if ratified, amend §3.1's wording; if overruled, the change is confined to the B5 test fixtures).
4. **Decide release timing** — see §3.

## 1. What shipped to `dev` (all CI-green, all codex-reviewed pre-merge, merged under Sam's 2026-08-06 grant)

| PR | Merge | Contents |
|---|---|---|
| #137 | `af48b96` | The implementation plan + decision log, after a 4-round review cycle (self ×2, codex cross-model, converged clean) |
| #138 | `8303e15` | **Phase A, data layer:** migration `685dab7d6df5` (10 nullable columns, 7 indexes, `esi_taxonomy_cache`), ingestion writes for every F008 field, end-location resolution with both-role read-back guards, self-healing taxonomy name cache (category AND group levels), completion-predicate widening for requested items, drift-manifest extension, `ENRICHMENT_VERSION` 1→2 |
| #139 | `9e1218e` | **Phase B, API contract (breaking, `feat(api)!`):** `ContractSchema` → `ContractListItemSchema`/`ContractDetailSchema` split per §17; `contract_type` (closed enum) + `category_id`/`group_id` + functional runs/ME/TE filters as offered-only per-family EXISTS; `segment_counts` from one grouped statement (equivalence property-tested); observed-coverage envelope (loose-index-scan CTE); `GET /contracts/taxonomy` with the two-condition readiness signal; three new sorts (`nulls_last`); `SavedSearchParameters` widened; search text scrubbed from all four log sites + `hide_parameters` guard; regenerated client; frontend type adaptation + column-module extraction (Tasks C1/C2 ride this PR — see D9's PR-boundary correction) |
| #140 | `75d95d0` | **Phase C, contract-level surface:** segment tabs with honest counts, per-segment column sets (auction bid/buyout, courier route/rate/deadline), parser-level sort-visibility enforcement (D11), freshness display, coverage-honest empty states incl. the nothing-ingested case, live-region truthfulness; pitfall WEB-1 added |
| #141 | (this PR) | Plan banner closeout + this handoff |

**Test trajectory:** backend 572 → 669; frontend unit 192 → 243 (×2 lanes); Playwright e2e 92 → 112. Roughly 90 subagents implemented and adversarially reviewed the work task-by-task; codex (gpt-5.6-sol, high) reviewed the plan and every PR — its findings and their dispositions are comments on each PR.

## 2. Phase D — deferred, fully unblocked, self-contained pickup

The item-level surface (taxonomy cascading filter, ME/TE/runs controls, BPC columns, composition cells, want-to-buy split) is **⏸ deferred with zero upstream blockers**: every API it consumes is merged. A fresh session executes plan Tasks D1–D5 directly, branching `feat/f008-item-surface` off `dev`. The Phase D banner carries the two executor corrections (eight params for `toSavedSearchParameters`, and the D2 gating note from the B6 review advisory). Nothing about release timing depends on D: its UI activates in production only when the taxonomy readiness signal reports `complete`, whenever it ships (decision-log D1).

## 3. Production activation runbook (when Sam publishes `dev` → `main`)

1. Publish via the normal release PR; time the deploy into the post-ingestion idle window (DEPLOY-4).
2. The migration runs as `preDeployCommand`. The next ordinary run backfills contract-level columns; the `ENRICHMENT_VERSION` bump makes the run after deploy a **one-off ~80-minute full-corpus resweep** — the `Aggregation lock token mismatch on release` warning at its end is EXPECTED then (runbook at the constant). **Do not redeploy mid-resweep.**
3. No manual gate: `GET /contracts/taxonomy` flips to `complete` when the observed corpus is restamped; the item-level UI (once Phase D ships) appears on its own.
4. Verify per plan §Production activation: item-column non-NULL rates measured against recently-seen contracts, and **re-measure the unfiltered count path once on production** — the count query changed shape (D2: one grouped statement); record the number in the perf-audit doc's §9. The live smoke should go green with this release (it was failing on the pre-#130 latency; both fixes are now in).

## 4. Operational guardrails from this session (already in memory files; repeated for the repo record)

- **Topologically re-sort workflow dispatch order from the plan's cross-task notes**, never from section numbering — the C2-before-B10 mis-ordering cost one round-trip; the executing agent correctly refused to take another task's single-writer step (Rule #1 doing its job).
- **A readiness ratio's denominator must include the failure states it exists to detect** (COMPLETED-only measured 1/1 = "complete" while 99 contracts sat failed). Same family: "the next run retries it" is false whenever a skip-predicate suppresses the retry path — trace re-entry before writing self-healing claims.
- **A PR that commits regenerated artifacts must keep every consumer compiling within that same PR** — CI runs per-PR, and the frontend lane type-checks whatever the generated types orphan.
- **Sort fields need a disclosing header in every column set that can host them** — four separate instances of the invisible-sort family surfaced (segment switches, deep links, Clear filters, and a sortable API field with no header at all); the durable fix was parser-level reconciliation.
- **The backend suite serializes on one scratch DB per worktree** (`hangar_bay_test_f008` here); parallel pytest is still the fastest way to fake a failure.

## 5. Local machine state a fresh session should know

- This worktree (`.claude/worktrees/eve-ship-order-requirements-ddb49c`) ends the session on branch `docs/f008-plan-closeout`; `feat/*` phase branches were deleted on merge (locals may linger — reclaimable). `app/backend/src/.env` exists (copied unread from the main checkout); `ESI_USER_AGENT` and `DATABASE_URL_TESTS` still come from process env per test run.
- Scratch DB `hangar_bay_test_f008` exists in the local `hangar_bay_postgres` container — drop when this worktree is reclaimed. The earlier sessions' `hangar_bay_perf` and `hangar_bay_test_watermark` scratch DBs are ALSO still present (see the 2026-08-02 handoff §7).
- Postgres/Valkey containers run from the main checkout (ENV-10 respected). The `hangar-bay-frontend-rebuild-2e4fe7` worktree still must NOT be reclaimed (it bind-mounts those containers).
- A pending task chip: coalesce-on-conflict fix for the four name columns (decision-log D10).

## 6. Priority queue for the next session

1. **Sam's §0 items** — nothing else here needs Sam synchronously.
2. **Phase D execution** (plan Tasks D1–D5) — the one remaining build item; ~one focused session with the established per-task implement/review pattern.
3. **Publish `dev` → `main`** when Sam calls it (§3's runbook governs; it also finally turns the production live-smoke green).
4. **The D10 follow-up chip** (name-column NULL-overwrite) — independent, small, reviewed on its own.
5. **Deferred measurements** (recorded in the plan): the §15.1 market-group NULL-rate re-measure and the B7 `_live_category_ids` EXPLAIN both need production data access, which returns when Sam rotates the key and re-authorizes.

## Appendix — adversarial review of this handoff

**Round 1 — fresh-agent read (3 findings applied):** pointed the Phase D pickup at the banner rather than duplicating its content; added the local-branch/scratch-DB cleanup notes a fresh session would otherwise rediscover; stated explicitly that release timing does not depend on Phase D.
**Round 2 — credential-and-exposure lens (2 findings applied):** §0 keeps both standing credential items with their exact objects and end states (the standing instruction says every handoff until confirmed); the deferred-measurements item names WHY they're blocked (no production access) so nobody burns a session rediscovering it.
**Round 3 — trust-the-numbers lens (2 findings applied):** every merge SHA and test count above was read from the PR/CI records in-session, not recalled; the ~80-minute resweep figure is marked as the spec's measured estimate, with the verification step (§3.4) that replaces trust with measurement.
Final pass produced no further material findings.
