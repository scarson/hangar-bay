<!-- ABOUTME: Decision log for the F008 overnight build (2026-08-06/07) — background, alternatives, -->
<!-- ABOUTME: decision, and reversibility for every consequential call made without Sam in the loop. -->

# F008 build — decision log

**Companion to:** [`2026-08-06-f008-type-aware-contract-browsing.md`](2026-08-06-f008-type-aware-contract-browsing.md) (the implementation plan).
**Why this exists:** Sam authorized autonomous decision-making for this build on the condition that consequential decisions are logged for post-hoc review — background, alternatives considered, the decision, and how reversible it is. Entries are appended as decisions are made; none are edited after the fact except to record outcomes.

Reversibility scale: **cheap** (config or single-PR revert), **moderate** (touches persisted schema or wire contract, revert needs a migration or client regen), **one-way** (data loss or external contract others now depend on).

---

## D1 — Step-4 gating: data-driven coverage signal, not a Settings flag, not a held release

**Background.** F008 §7.1 requires the plan to name the mechanism by which the item-level surface (taxonomy filters, blueprint columns, composition summaries) waits for the ~80-minute production resweep that populates the new item columns. The spec offers three shapes: merged-to-dev-but-held-from-release, a flag, or a separate release train.

**Alternatives considered.**
1. *Hold from the release PR* — rejected: this repo's releases are whole-of-`dev` publication PRs; holding a slice means cherry-pick surgery on the release path, which the git strategy has no machinery for.
2. *Settings feature flag (default off, flipped by Sam after verifying the resweep)* — workable, but recon showed no flag mechanism exists anywhere in the repo, the SPA has no channel to read backend config, and CI's `openapi-drift` job re-exports the schema under a fixed env — any flag that changes route registration or response shape makes the committed schema flag-dependent and breaks CI. A data-level flag survives those constraints but still needs a human to flip it, and goes stale as a mechanism after the one use.
3. *Observed-coverage signal (chosen)* — the taxonomy endpoint (`GET /contracts/taxonomy`) computes `coverage: "partial" | "complete"` from observed reality: the share of live, item-bearing, `COMPLETED` contracts stamped at the current `ENRICHMENT_VERSION` (threshold ≥ 0.99, measured against the recently-seen population per §7.1's denominator warning). The frontend shows the item-level controls only when `coverage == "complete"` and renders an honest "still indexing" note otherwise.

**Decision.** Alternative 3. It is the same philosophy Criterion 7.4 already mandates for region coverage ("observed reality, not configured intent"), it needs no human flip, it keeps the exported OpenAPI schema constant, and it self-heals: any *future* `ENRICHMENT_VERSION` bump automatically degrades the surface to "partial" during its resweep and restores it after — the gate keeps working forever instead of being one-shot scaffolding.

**Reversibility: cheap.** The threshold and the signal computation are server-side implementation details behind a stable wire field; swapping to a flag later changes no schema.

**Codex review:** yes — included in the plan-review-cycle scope.

---

## D2 — Exact-count strategy: one grouped count statement replaces the flat count; no Valkey cache in v1

**Background.** The perf audit (`docs/perf-audits/2026-08-02-contract-list-watermark-subquery.md` §9) explicitly defers "exact counts at corpus scale" to this plan. F008 makes the unfiltered list primary (count ≈ 1.6 s on production post-PR-#130) *and* adds `segment_counts`, which naively is a second corpus-scale aggregate per request (≈ 3.2 s sequential).

**Alternatives considered.**
1. *Keep `_count_distinct_contracts` + add a separate grouped query* (the shape §17.5 says is "correct and expected") — two corpus-scale aggregates per request; roughly doubles the worst path the smoke test already failed on once.
2. *Approximate counts above a threshold* — rejected for v1: the UI promises "N contracts match" in a polite live region the smoke test parses; approximate totals change product behavior and deserve their own decision with Sam.
3. *Valkey-cached counts keyed by filter hash* — recon showed zero cache infrastructure on the request path (no helper, no key convention, no invalidation signal beyond `INGEST_LAST_RUN_KEY`), and DEPLOY-3 makes eviction routine. Building that machinery tonight adds a failure surface to the hottest path for a benefit the merged query already delivers.
4. *One grouped statement (chosen)* — `GROUP BY Contract.type` with two aggregates per type: `count(DISTINCT contract_id)` and `count(DISTINCT contract_id) FILTER (WHERE is_ship_contract)`. Python then derives: `segment_counts` per Criterion 1.8 (item-bearing segments read the ships-only-respecting aggregate while `ships_only` is active; item-less segments read the lifted one), zero-fills absent types over the enum (SQL emits no row for an absent group), and derives `total` by summing the selected types' appropriate aggregates. The flat count query disappears from the list path entirely — one corpus aggregate per request, same as today.

**Decision.** Alternative 4, with a pinned equivalence property test: for a matrix of filter combinations, the grouped-derived `total` must equal the old `_count_distinct_contracts` result computed side-by-side. `_count_distinct_contracts` itself is retained for the `unknown_system_excluded` residual path. The DISTINCT is applied only when the item join is active (absorbing perf-audit §9's "drop the DISTINCT wrapper" follow-up into the new shape).

**Reversibility: cheap.** Pure query-shape change behind an unchanged (extended) response contract.

**Codex review:** yes — this is the riskiest query rewrite in the plan.

---

## D3 — Coverage envelope sourced via a loose-index-scan CTE, not `SELECT DISTINCT` and not ingestion-written state

**Background.** Criterion 7.3/7.4 and §17.7 require the list envelope to report which regions are actually ingested, from observed reality. The naive `SELECT DISTINCT start_location_region_id` measures **602 ms** on production (perf audit §4 — Postgres 18's btree skip scan does not engage here). That cost per list request is unacceptable on the path PR #130 just fought down.

**Alternatives considered.**
1. *`SELECT DISTINCT` per request* — 602 ms, rejected on measurement.
2. *Ingestion writes observed regions to a side table / Valkey key* — a second source of truth with the exact failure modes that killed the watermark-table design two reviews ago (perf audit §8): a write-side signal can advance when nothing was actually restamped, and Valkey state evicts (DEPLOY-3).
3. *Loose index scan (chosen)* — the classic recursive-CTE emulation over `ix_contracts_region_last_seen`'s leading column: O(#regions × index depth) probes, sub-millisecond at any plausible region count, no new state, no writer. `as_of` rides the same CTE as the max watermark across observed regions.

**Decision.** Alternative 3, implemented as a `text()` SQL fragment with a comment explaining why it isn't a plain DISTINCT, plus a test seeding multiple regions and asserting the observed set (and that a configured-but-empty region is absent — the exact drift case 7.4 exists for).

**Reversibility: cheap.**

---

## D4 — `SavedSearchParameters` widens to accept the newly functional params; `extra="forbid"` stays

**Background.** F008 §14: the saved-search blob deliberately rejects the inert ME/TE params (two pinning tests assert the 422), and Criterion 2.5 makes them real. The plan must decide widen-or-hold explicitly; the third pin (`additionalProperties is False` at `test_saved_searches.py:168`) and the rejected `page`/`is_ship_contract` cases constrain the shape.

**Alternatives considered.**
1. *Hold saved searches at the current nine params* — defensible (smaller change) but leaves the flagship new filters unsaveable, and the docstring's FASTAPI-2 rationale evaporates the moment the params work — the model would be rejecting *functional* filters on the strength of a stale comment.
2. *Widen (chosen)* — add `contract_type`, `category_id`, `group_id`, `min_runs`/`max_runs`, `min_me`/`max_me`/`min_te`/`max_te` with the same bounds as `ContractFilters`; keep `extra="forbid"`; keep rejecting `page` and the wire-only `is_ship_contract` (the blob keeps `ships_only`); update the two 422 pins to a still-rejected key and the docstring to name what is *now* rejected and why.

**Decision.** Alternative 2 — completeness over shortcut, and the enum coupling (`sort_by: SortableContractFields`) already widens the blob implicitly when the sort enum gains members, so holding the rest would be incoherent.

**Reversibility: moderate.** Saved blobs re-validate on read, so a later narrowing would break stored searches — narrowing later is the expensive direction, which is why the widened set copies `ContractFilters` bounds exactly rather than inventing looser ones.

---

## D5 — Index set for the new columns: btree on the five filterable item columns + the two new sortable contract columns; no expression index for `reward_per_volume`

**Background.** §11 requires the plan to specify taxonomy indexes; house precedent indexes every filterable item column (`is_blueprint_copy`, even the dead `raw_quantity`) and every sortable contract column (`price`, `date_issued`, `collateral`, `volume`).

**Decision.** `contract_items`: btree on `category_id`, `group_id`, `runs`, `material_efficiency`, `time_efficiency` (matching the raw_quantity precedent; these back correlated-EXISTS filters at corpus scale). `contracts`: btree on `buyout`, `days_to_complete` (new sortable fields, matching the existing sortable-column pattern). **No index on `item_id`** (write-only until the abyssal follow-on — YAGNI) and **no expression index for `reward_per_volume`** (computed `reward / NULLIF(volume, 0)`; sorts flow through the grouped-aggregate pagination path where a plain expression index would not be used as-is; measure first if it ever shows up hot).

**Alternatives considered.** Minimal set (category/group only) — rejected because ME/TE filters are the feature's headline fix and an unindexed corpus-scale EXISTS probe is the next latency incident; full set incl. item_id — rejected as pure write amplification for a column nothing reads.

**Reversibility: cheap** (indexes add/drop independently; each is one migration line).

---

## D6 — PR train: four sequential PRs, honest classifications, codex-reviewed, self-merged under Sam's grant

**Background.** §7.1's single-writer constraints (one migration, one `ENRICHMENT_VERSION` bump, codegen regenerated-never-merged, `ContractTable.tsx` restructured once) force ordering; Sam granted merge authority conditioned on codex review per PR.

**Decision.**
- **PR-A** — migration + models + ingestion writes + taxonomy cache + manifest/snapshot + `ENRICHMENT_VERSION` bump (last commit inside the PR). Classification: `Review — database schema` (merged by agent under Sam's 2026-08-06 grant, post-codex).
- **PR-B** — API contract: response-model split, new filters/sorts, grouped counts, coverage envelope, taxonomy endpoint, PII log fix, SavedSearch widening, regenerated `openapi.json`/`schema.d.ts`. Classification: `Review — public API contract` (same merge basis).
- **PR-C** — frontend contract-level surface: cell-renderer refactor first, then segments, auction/courier columns, coverage-honest empty states, `last_seen_at`. Classification: `Routine`.
- **PR-D** — frontend item-level surface behind the D1 coverage gate: taxonomy cascading filter, ME/TE/runs controls, BPC columns, composition, want-to-buy split. Classification: `Routine`.

Strictly sequential (each builds on the previous merge); workflow parallelism is used *within* a PR only where files are disjoint, and backend test runs are serialized on this worktree's scratch DB (`hangar_bay_test_f008`).

**Alternatives considered.** One monolithic PR — rejected: §7.1 explicitly requires step 4 to be independently shippable, and review quality collapses at that diff size. Parallel PR development — rejected: codegen conflicts (§7.1) and the migration chain make it a DEPLOY-5 factory.

**Reversibility: cheap** (process decision).

---

## D7 — `min_me` handoff question resolved by construction

**Background.** Handoff queue item 6 asked whether the four inert ME/TE params should hard-error now or fold into F008's item-level migration. **Decision:** folded — F008 makes them functional (Criterion 2.5), which supersedes the hard-error option; no separate change needed. **Reversibility:** n/a (the question dissolves).
