<!-- ABOUTME: Handoff for the 2026-08-01 contract-coverage gap analysis session — what shipped, what awaits Sam's -->
<!-- ABOUTME: decision or review, and the verified facts a follow-on planning session needs. -->

# Handoff — contract-coverage gap analysis session (2026-08-01)

**Session goal (Sam's ask):** gap-analyse Hangar Bay against EVE Workbench's market tool and the wider EVE tool ecosystem, because "we should at least display the data for all these other contracts we're ingesting besides plain ships." Later additions: survey other marketplace viewers, research an MCP surface for Hangar Bay's final form, and verify/fix any bugs the analysis surfaced.

**Everything below is either merged to `dev` or open and named. Nothing is half-done in a worktree.**

## 1. The one decision waiting on Sam

**Should we build the type-aware "all contracts" view?** The analysis says yes; no product decision has been taken. Read `docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md` §6 for the recommendation and its sequencing. Nothing in this session presumes the answer — no feature spec was written, no ingestion schema was changed.

The short version of why: we ingest and store **33,817 live contracts and display 411 of them** (1.2%). 49% of the corpus contains a blueprint copy; the biggest non-ship clusters are abyssal/mutated modules and capital-component blueprints. EVE Workbench has **no contract features at all** (verified by extracting all 62 of its Angular routes and grepping its shipped JS). The only living public-contract browser, Adam4EVE, is in maintenance mode with a 2021 copyright and returns database connection errors on roughly half of requests. Nobody in the ecosystem handles courier contracts.

If the answer is yes, the natural next step is an **F008 feature spec** for the type-aware browse view — `design/features/feature-index.md` has no F008 placeholder yet, and two existing spec conflicts need reconciling in it (F002 says the market-group/category filter is MVP scope; the M1 design doc says it's deferred for lack of a backing API. Courier handling has no written policy at all).

## 2. Awaiting Sam's review

**[PR #98](https://github.com/scarson/hangar-bay/pull/98)** — `claude/contract-filter-bugfixes`. Classified `Review — serialization contract / schema changes`, all four checks green, **deliberately not merged**. Fixes four confirmed defects: the `is_bpc=false` filter (matched zero rows), courier contracts rendering as "Exchange", a courier serialization 500 (one null `start_location_id` fails an entire 50-row page, not just its row), and `collateral` being filterable/sortable but absent from every response. Adds pitfalls ESI-2, FASTAPI-3, SQLA-3, TEST-17, TEST-18, TEST-19.

Worth knowing: a codex adversarial review caught a real second-order bug in the first `is_bpc` fix — a per-item predicate made mixed BPC bundles match *both* boolean values, so the two filters' totals summed to more than the corpus. The final fix derives both branches from one negated correlated EXISTS, so they are exact complements by construction.

## 3. Merged this session

| PR | What |
|---|---|
| [#99](https://github.com/scarson/hangar-bay/pull/99) | The gap analysis + MCP surface research docs |
| [#100](https://github.com/scarson/hangar-bay/pull/100) | Developer-license deep-dive folded into the MCP doc |
| [#101](https://github.com/scarson/hangar-bay/pull/101) | ESI client prefers `Cache-Control` over the deprecating `Expires`; also fixed a pre-existing red `dev` |
| [#102](https://github.com/scarson/hangar-bay/pull/102) | Corrections: abyssal data reachability, MCP prior-art staleness, the `--auto` CI-gate trap |

## 4. Verified facts a follow-on session should not re-derive

All checked against primary sources this session; each has cost someone time to establish.

**Abyssal modules are reachable from public ESI.** The gap analysis originally said they weren't and scoped them out. That was wrong, and §4.5 now records the mechanism: the public contract-items payload returns `item_id`, and `GET /dogma/dynamic/items/{type_id}/{item_id}` is public and unauthenticated, returning `source_type_id` (base module), `mutator_type_id` (mutaplasmid), and the rolled `dogma_attributes`. That is MutaMarket's entire data model. Rolled attributes are immutable per `item_id`, so the fetch is once-ever and cacheable forever. EVE Ref also publishes resolved dynamic-item dogma in its twice-hourly public-contract CSV dataset (verified on their docs), which is a viable shortcut worth evaluating against doing our own resolution.

**Two persisted columns can never hold data.** `raw_quantity` and `is_singleton` do not exist on ESI's *public* contract-items route — they appear only on the authenticated character/corporation routes. The complete public item schema is exactly `record_id, type_id, quantity, is_included, item_id, is_blueprint_copy, material_efficiency, time_efficiency, runs`. This is why the `min_runs`/`max_runs` filter (wired to `raw_quantity`) matches nothing. Also: on the public route, `runs` is *omitted* for originals rather than being `-1` as the spec description implies, so the obvious implementation would be wrong.

**`gh pr merge --auto` is not a CI gate in this repo.** No branch has required status checks — `dev` has no protection at all, and the one active ruleset targets the default branch with `deletion`/`non_fast_forward`/`pull_request` only. `--auto` merges immediately, mid-run. An agent hit this today. Now documented in `docs/git-strategy.md` §Mechanics for auto-merge and in both CLAUDE.md and AGENTS.md.

**ESI operational posture.** Token-bucket costs are 2xx = 2, 3xx = 1, 4xx = 5 — conditional requests that 304 are deliberately half-price, so ETag discipline is a rate-limit strategy, not politeness. `Expires` is being deprecated in favour of `Cache-Control` as routes convert to event-driven invalidation; our client now prefers `Cache-Control` (PR #101). **Flag for Plan B:** its scheduling design polls each region at `Expires + ε`. A conversion wouldn't change that header's value, it would remove the signal the scheduler is built on — worth re-checking before implementing that scheduling.

**CCP is now Fenris Creations** (rebranded 2026-05-06), though the Developer License still names CCP hf. throughout. ESI-data redistribution is *silence, not permission* — the license grants distribution "within an Application," reserves all other rights, has no sublicense clause, and CCP has never addressed third-party re-serving in any medium. Established sites do it openly and CCP indexes them. Monetization is hard-prohibited except ISK, voluntary cost-offsetting donations, and non-intrusive ads.

## 5. Known-broken, needs Sam

**Local Postgres is down.** The `docker_postgres_data` volume holds **PG 16** data while compose pins `postgres:18-alpine`, so `hangar_bay_postgres` crash-loops. Backend tests can't use the compose container — agents worked around it with throwaway containers on scratch ports. The data is ephemeral by design (ENV-2 drops it every backend start), so recreating is safe:

```bash
docker rm -f hangar_bay_postgres && docker volume rm docker_postgres_data && docker compose -f app/backend/docker/compose.yml -f app/backend/docker/compose.dependencies.yml up -d --wait postgres_db
```

I could not run this — the sandbox blocks Docker volume operations, including taking a backup first. Also noticed: the local `alloy` container has been exited with code 127 for ~11 days, so local telemetry shipping is dead. Untouched.

**Optional:** adding required status checks to `dev` would make the documented "agents merge their own PR on green CI" rule actually enforceable rather than advisory. That's a repo-settings change affecting everyone's workflow, so it wasn't done unilaterally.

## 6. Defects found but deliberately not fixed

- **`system_ids` filter matches zero rows** — `start_location_system_id` is never populated. Not cheap to fix: ESI carries no system id on contracts, so it needs a second hop. `/v1/universe/stations/` covers 97.1% of sampled start locations; the player-structure tail needs ACL-scoped tokens. Only 160 distinct locations across 7,292 contracts, so a location→system cache table would be tiny. Recommended, not done — the API param was left in place rather than removed.
- **Watchlist notifications outlive purchase.** The matcher filters on expiry plus an always-true `date_completed IS NULL`, and does *not* use the per-region `last_seen_at` watermark the list view uses — so an already-accepted contract keeps generating notifications until its expiry, up to two weeks. The fix changes notification semantics, so it needs a decision.
- **`status` is always the literal `"unknown"`** and `date_completed` always NULL — neither field exists in public ESI data. M5 Workstream D already designs the retirement.
- **69 of 70 regions in the frontend filter can never match** — we ingest The Forge only. Same defect class as the "silent filter no-op" the analysis proposes making a product invariant, and it's live in the shipped UI.

## 7. Documents to read, in order

1. `docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md` — the deliverable. §1 headline findings, §4 the internal gap, §6 the recommendation, and the appendix records the reasoning and a claim this document got wrong.
2. `docs/superpowers/specs/2026-08-01-mcp-surface-research.md` — companion. Only relevant when the MCP question comes up; its conclusion is that an MCP surface is the right "final form" but is downstream of M5's trust work, not parallel to it.
3. `docs/pitfalls/implementation-pitfalls.md` and `testing-pitfalls.md` — six new entries this session.
