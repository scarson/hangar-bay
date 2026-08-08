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

## D12 — The search-text PII scrub is closed at the engine, not only at the log site

*(Numbered D12 on 2026-08-08. It was written as a second D11 during the overnight build, colliding with the sort-visibility entry below; both external references — the 2026-08-07 handoff's PR #140 row and the 2026-08-08 handoff's spot-check item — mean the sort-visibility entry, so that one keeps D11 and this one moves.)*

**Background.** Task B10 replaced the raw search string with its length in all four `search_terms` payloads and its commit claimed the text "never lands in a log line". Review found the claim false: the failure site logs `error_message=str(e)` in the same record, and the exception a contract search realistically fails with is a SQLAlchemy `StatementError` — statement timeout, dropped connection, deadlock — whose `str()` appends `[SQL: ...]\n[parameters: {...}]`. The failing statement is the one carrying the `ILIKE '%<search text>%'` bind, so `error_message` re-published the exact string `search_terms` had just withheld. `create_async_engine` in `db.py` set no `hide_parameters`, so the default `False` applied. The shipped test could not see any of this: it injected `RuntimeError("simulated db failure")`, whose `str()` carries no parameters.

**Alternatives considered.**
1. **Narrow the claim** — retitle the test to "the `search_terms` payloads", record the residual under Discoveries, and defer. Rejected: the residual is a live PII leak on a path that fires under ordinary production operation — no statement timeout is configured, but `db.py` sets `pool_pre_ping=True` precisely because managed-PG restarts and pooler idle-kills happen on this deployment, and a connection dropped mid-statement raises exactly this error class — and the same value escapes past this service anyway — `main.py`'s `generic_exception_handler` logs `str(exc)` and the traceback for the re-raised exception. Deferring would leave a known leak behind an honest label.
2. **Scrub `error_message` at the log site only.** Rejected as insufficient alone: it fixes one of the three places the value surfaces and leaves the global handler and the traceback untouched.
3. **`hide_parameters=True` on the application engine only.** Correct and complete for engine-raised errors, but it makes the invariant depend entirely on one engine-construction kwarg, and the service-level test that carries the invariant's name would have to inject an already-hidden error to pass — which is circular.
4. **Chosen: both.** `hide_parameters=True` on the engine stops SQLAlchemy rendering bind values into any error it raises, closing the service log, the global handler, and the traceback at the source; `_error_without_bound_parameters` at the log site renders through the same flag regardless of which engine produced the exception. CLAUDE.md's defense-in-depth rule governs over DRY here — the two layers fail independently, and the service-level test can then inject a genuinely unscrubbed `StatementError` and assert against the whole record.

**Cost accepted.** Bind values no longer appear in production error messages or in `echo=True` dev SQL logs. The values on this path are contract/region ids and user text; the structured `search_terms` dimensions remain, and the driver's own diagnosis (`canceling statement due to statement timeout`) still reaches `error_message` — only the parameter block is replaced with SQLAlchemy's `[SQL parameters hidden due to hide_parameters=True]` placeholder.

**Reversibility: trivial** — one kwarg and one helper call; the pitfalls entries (SQLA-4, TEST-21) survive either way because the trap is the reasoning, not the switch.

---

## D11 — Sort visibility is enforced in the parser; the All count hides when it cannot be known

**Background.** Codex's PR-C review found three P1s in one family: a sort could outlive the segment whose columns disclosed it (via deep links, saved-search apply, and Clear filters — the click-handler reset covered only segment buttons), the courier DEFAULT sort (`date_issued`) had no courier header at all, and the All control summed lifted item-less counts into a number describing a view All does not restore.

**Decisions.**
1. **Sort reconciliation moved into `parseContractSearch`** (the same pure-parser home as the item-less ships-only normalization), so every route into a view gets the identical rule: a sort no active-segment header can disclose falls back to `date_issued`, or `date_expired` where the set lacks an Issued column (courier). The courier Deadline column also gained its missing `sortField` — the API sorted on `days_to_complete` with no header disclosing it, one more instance of the same defect.
2. **The All control renders without a numeral while an item-less segment is active.** The envelope's item-bearing counts were computed without ships-only, and All's destination restores it — a population those numbers cannot describe. No numeral beats a wrong one. Follow-up if the numeral is wanted: serve Criterion 1.8's mirror (ships-respecting item-bearing counts) on item-less-segment requests.
3. **A segment-reconciled sort persists through Clear filters.** Sort is not a filter and Clear has always preserved it; by the time it persists it was visibly disclosed (header + aria-sort) on the segment that set it. The alternative — tracking whether a sort was user-chosen vs parser-derived — is hidden state for a marginal nicety.

**Reversibility: cheap** (all client-side; the wire is untouched).

**Codex review:** it raised all three; dispositions on PR #140.

---

## D10 — PR-A codex finding on name NULL-overwrite: deferred as a pre-existing, self-healing defect class

**Background.** Codex's PR-A review flagged as P1: a transient `/universe/names` failure yields a partial name map, every upsert row still supplies `end_location_name=None`, and `bulk_upsert` copies supplied columns on conflict — blanking previously-resolved courier destinations for the re-sighted batch.

**Verification.** Confirmed real — and confirmed **pre-existing**: `start_location_name`, `issuer_name`, and `issuer_corporation_name` have carried the identical exposure since M1. It also self-heals: names re-resolve on every sighting, so the blank window lasts exactly as long as the ESI names outage.

**Alternatives.** (1) Fix now via coalesce-on-conflict semantics in `bulk_upsert` — correct, but changes shared upsert infrastructure consumed by every writer, at the gate of a schema-classified PR, for a defect class production has lived with for months. (2) Per-row key omission — impossible under the uniform-keys invariant. (3) **Defer (chosen):** land PR-A with the exposure unchanged in kind (one more nullable display column), file the coalesce fix as its own reviewed change covering all four name columns.

**Decision.** Defer with a spawned follow-up task; severity treated as parity-with-existing (P2), not P1, because F008 adds no new failure *mechanism*. **Reversibility: cheap** — the follow-up is independent of everything in this build.

**Codex reviewed:** it raised it; the fix lands separately with its own review. Also from the same review: the taxonomy cache gained a DB-observed retry for **group** names (P1-2, accepted and shipped in the gate commit), the category-repair test now uses a fresh service across runs (P2-3), the group-less-type NULL case is pinned (P2-4), and B7's readiness check was re-scoped to live contracts with its own query (P2-5, plan amendment).

---

## D9 — Codex round-2 outcomes: 13 findings accepted, one rebutted (migration-file ABOUTME headers)

**Background.** The cross-model plan review (codex, gpt-5.6-sol, high) returned 13 P1 + 2 P2 findings. All were verified against source before acting; 14 were accepted and are folded into the plan (PR-B/C boundary, item-surface gate scope, coverage denominator + cache-completeness + threshold-test arithmetic, taxonomy-cache retry path, category-less-payload completion bug, All-count arithmetic, item-less deep-link normalization, buyout sort fixtures, columns-module extraction, non-enum type folding, conditional DISTINCT).

**The rebuttal.** Finding 13 said the plan's migration scaffold violates the repo's ABOUTME-header rule for created files. Declined: every existing Alembic revision follows `script.py.mako`'s docstring-first shape with no ABOUTME header, migrations are template-generated scaffolds, and CLAUDE.md's own consistency rule ("match the style of surrounding code") governs a file family with five uniform precedents. Adding a header to one migration would make it the odd file out in its own directory. **Reversibility: trivial** — if Sam prefers ABOUTME on migrations, it's a two-line addition and a template edit.

**Also amended by this round:** D1 gains the two-condition coverage signal (denominator over ALL live item-bearing contracts, plus name-cache completeness) and the whole-surface gate scope; D2's conditional-DISTINCT wording is now binding over the plan's earlier "unconditional is harmless" line; D6's PR train is now A → B (which includes the frontend type adaptation and the renderer-module extraction, or frontend CI breaks on the regenerated types) → C (segments/columns/coverage states) → D.

---

## D8 — Range families under §3.1: straddling mixed-child contracts match both single-bound branches

**Background.** Spec §3.1 / §16.3 say the mixed-child fixture "must assert it lands in exactly one branch." During plan review (round 1) this turned out to be internally consistent only for the boolean `is_bpc` family, whose false branch is the *negation* of the true branch. Range families (runs/ME/TE) have no negation branch, and §3.1's own existential rule ("at least one offered item satisfies the predicate") means a contract holding ME-5 and ME-15 offered items genuinely matches BOTH `max_me=9` and `min_me=10` — each bound satisfied by a different item.

**Alternatives considered.** (1) Force "exactly one branch" onto ranges — would reject a *correct* implementation and effectively demand contract-level (not item-level) bound evaluation, contradicting §3.1's window rule. (2) Read §3.1's identity as requiring non-straddling fixtures only — loses the most informative fixture. (3) **Chosen:** keep the straddling fixture, assert both-branch membership explicitly as a *feature* of existential semantics, pin same-item range composition via the window test (`min_me=10&max_me=12` excludes the straddler), and compute the three-way identity with the overlap named (`|A| + |B| − |A∩B| + neither == unfiltered`).

**Decision.** Alternative 3 (plan Task B5). The spec sentence is treated as boolean-family-specific rather than amended mid-build; flagged for Sam to fold back into §3.1's wording later.

**Reversibility: cheap** (test-shape decision; no wire or schema impact).

**Codex review:** yes — and codex **objected** (round-2 finding 8): it agrees the spec is internally inconsistent but holds that changing acceptance behavior against a binding spec's literal text needs the spec owner, not a plan-local ruling. Proceeding anyway under Sam's explicit 2026-08-06 decision-making grant, because the alternative (enforcing "exactly one branch" on ranges) would reject implementations that are *correct under the spec's own existential rule* — but this entry is the one flagged most prominently for Sam's morning ratification, and §3.1's wording should be amended once ratified. If Sam overrules, the change is confined to the B5 test fixtures.

**Outcome: RATIFIED by Sam, 2026-08-08.** Spec §3.1 and §16.3 amended in the same change: the identity gains its explicit overlap term (`branch_a + branch_b - both + neither == unfiltered`), "exactly one branch" is scoped to the negation-derived boolean family, and the range-family fixture's three discriminating assertions (both-branch membership, same-item window exclusion, stated-count identity) are now the spec's own text. Codex's objection is resolved the way it asked: by the spec owner.

---

## D13 — The item-level readiness gate is read live, not carried on the list response

**Background.** Task D1 gates the whole item-dependent surface — taxonomy and blueprint controls, the blueprint column, the composition cell, and the deep-link warning — on `GET /contracts/taxonomy`'s `coverage` field. WEB-1 (added by Task C4 four days earlier) says anything *describing the rows* must be derived inside the list query function so it travels with the rows through `keepPreviousData`. The column set and the warning both describe the rows, so the rule appears to apply.

**Alternatives considered.**
1. *Put readiness in the list query key* (`['contracts','list', query, ready]`) — correct by construction, and wrong on cost: taxonomy and the list fire together on a cold load, taxonomy resolves first, the key changes, and the app issues a **second corpus-scale list request** on every cold load. The unfiltered count path is the one PR #130 spent a release fighting down; doubling it to close a seconds-long cosmetic window is a bad trade.
2. *Capture readiness in the query function's closure* (no key change) — free, and correct for every steady state, but wrong exactly when it matters most: on a cold load the taxonomy query has not resolved when the list query function runs, so the first page of a fully-enriched production corpus would render with the item surface closed until the reader navigated. That is the common case, not an edge.
3. *Read the live query in both consumers (chosen)* — `useItemSurfaceReady()` reads the taxonomy cache directly wherever the gate is needed.

**Decision — REVERSED. What shipped is alternative 2 (capture at fetch time), plus the sequencing that removes its one defect.** Two rounds of codex review dismantled alternative 3, and both rounds were right. The reasoning trail is kept below rather than rewritten, because the way this decision failed is more useful than the decision.

**What shipped — three mechanisms, none of which is sufficient alone.**

1. **`enabled`.** The list waits for the taxonomy query to hold an answer of any kind (`!taxonomy.isPending` — an *error* counts, so an unreachable endpoint degrades to not-ready instead of blocking the list forever), bounded by a 5s abort on the request and `retry: false` on that query, so a hung probe cannot hold the app's core view on its skeleton. Without this, what the query function captures is a not-yet rather than an answer.
2. **Captured in the query function.** Readiness is returned with the rows, and every consumer that describes rows — the column set, the label cell's composition-vs-count choice, the incomplete-results notice — reads `data.itemSurfaceReady`. Without this, `keepPreviousData` renders the incoming answer over the outgoing rows.
3. **In the query key.** Without this, a readiness change during a request for a key with no cached data is absorbed: React Query reuses the in-flight promise, so the response lands carrying the value captured *before* the change and nothing remains to correct it. Invalidation cannot fix that — it is the same in-flight promise either way. Keying starts a genuinely new query, and `keepPreviousData` then shows the old rows still described by the old answer, which is exactly right.

`useItemSurfaceRefresh` — the invalidation hook that mechanism 3 replaced — is deleted. `FilterRail` still reads live, and that stays correct: its controls express what the reader may ask for *next*, not what the rows on screen mean.

**The cost that made keying look unaffordable was conditional, and the condition changed.** Alternative 1 was rejected because keying on readiness costs a second corpus-scale list request on every cold load. That is true *only if the list may fetch before readiness is known*. Once mechanism 1 is in place the key never moves from unknown to known, so the cold load costs one request — measured on the live dev backend, not assumed. The rejection was sound when made and stopped being sound two mechanisms later, and nothing in the original entry would have prompted a re-check.

**Why alternative 3 failed, in the order it was taken apart.**

*Round 1 found two factual errors in the original entry.* It claimed the stale window was "the seconds between the flip and the next list fetch" and that the worst rendering was "byte-identical to the legitimate rendering for every non-blueprint row". Neither held. `staleTime` marks data stale without scheduling anything, so with no `refetchInterval` a tab open across an `ENRICHMENT_VERSION` resweep kept reporting the *previous* answer for the whole ~80 minutes — the opposite of D1's "degrades on its own". And the rendering is not indistinguishable: `is_blueprint_copy_contract` has been ingested since M1, so the row shows its **BPC badge beside three empty cells**, which reads as missing data rather than as a non-blueprint.

*Round 2 showed the repairs were insufficient in kind, not merely in degree.* Invalidating on a flip narrows the window; it does not close it, because `keepPreviousData` holds the partial rows on screen for the whole refetch — so the new columns still land on the old rows, which is precisely WEB-1. And the `undefined → first answer` exclusion (added to avoid a cold-load double fetch) leaves a permanent race: a taxonomy response that resolves while the first list request is still in flight produces the same mismatch with no transition to invalidate on.

**The general lesson, which is the reason this entry is worth its length.** "This value describes the corpus rather than the rows" felt like a principled exemption from WEB-1. It is not one. Any value the row rendering consumes is *about the rows* at the moment it is consumed, whatever it is about ontologically — and if it can change independently of them, it will eventually describe them wrongly. The exemption I reached for does not exist; what looked like a narrower rule was just the same rule with a story attached.

**The cost that made alternative 2 look unattractive was mispriced.** It was rejected because "on a cold load the taxonomy has not resolved when the list query function runs, so the first page renders with the surface closed". That is only true if the list is allowed to run first. Sequencing it behind a tiny, cacheable endpoint costs one small round trip in front of the first list request — against a list request measured in seconds — and buys correctness by construction. Alternative 1's cost (a *second* corpus-scale list request on every cold load) was real; this one is not comparable to it, and I treated them as if they were.

**Reversibility: cheap** — the capture and the `enabled` gate are a few lines in `useContracts`.

---

## D7 — `min_me` handoff question resolved by construction

**Background.** Handoff queue item 6 asked whether the four inert ME/TE params should hard-error now or fold into F008's item-level migration. **Decision:** folded — F008 makes them functional (Criterion 2.5), which supersedes the hard-error option; no separate change needed. **Reversibility:** n/a (the question dissolves).
