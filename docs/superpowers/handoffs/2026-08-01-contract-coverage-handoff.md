<!-- ABOUTME: Session-close handoff for 2026-08-01 — the contract-coverage gap analysis, the decision it -->
<!-- ABOUTME: leaves open, everything that shipped alongside it, and what a fresh session should do next. -->

# Handoff — contract-coverage gap analysis (2026-08-01, session close)

**Read this first, then `docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md`.**

**State at close:** `dev` @ `869cc6d`, green. **18 PRs merged today** (#98–#115). One PR open: [#116](https://github.com/scarson/hangar-bay/pull/116). Production untouched and healthy — still `7a95118`, `db: ok`, `cache: ok`, last ingest succeeded, `data_stale: false`. Production deploys from `main`; nothing today went past `dev`.

## 1. The decision waiting on Sam

**Should we build the type-aware "all contracts" view?** The analysis recommends yes. Nothing in this session presumes the answer: no feature spec was written, no ingestion schema was changed to support it.

The case, in one paragraph: we ingest, enrich, and store the entire Forge public-contract corpus — **~34,000 live contracts — and display 411 of them** (1.2%). The hidden 98.8% is a real market, not noise: **49% of contracts contain a blueprint copy**, and the largest clusters are abyssal/mutated modules and capital-component blueprints — item classes that *cannot* trade on the regular market, so contracts are their only venue. The competitive field is empty: EVE Workbench has **no contract features at all** (verified by extracting all 62 of its routes and grepping its shipped JS), the only living public-contract browser (Adam4EVE) is maintenance-mode with a 2021 copyright and returns database errors on ~half of requests, and **nobody in the ecosystem handles courier contracts**.

If the answer is yes, the next step is an **F008 feature spec** for the type-aware browse view. `design/features/feature-index.md` has no F008 placeholder yet. Two existing spec conflicts must be reconciled *in* that spec, not around it:
- F002 says the market-group/category filter is MVP scope; the M1 design doc says it is deferred for lack of a backing API. Never reconciled.
- Courier handling has **no written policy anywhere** — its exclusion from item fetching is an implementation artifact, not a decision.

Sequencing lives in the analysis §6. Phase 1 (defect fixes) is **done**. Phases 2–4 are not started.

## 2. In-flight at close — check these before assuming anything

| Item | Owner | State |
|---|---|---|
| [PR #116](https://github.com/scarson/hangar-bay/pull/116) — location→system resolution | agent, authorised to self-merge on green | Was green, then conflicted when #115 merged. Agent is rebasing; **must** keep #115's removal of `status`/`date_completed` *and* its own `start_location_system_id`, and must **regenerate** `openapi.json`/`schema.d.ts` rather than hand-merge them |
| ESI spec-drift monitor | agent, `claude/esi-spec-monitor` | Building. `Routine` |
| Future-clock vitest lane | agent, `claude/timebomb-verify` | Building, authorised to self-merge on green |

All three may touch `.github/workflows/` or the pitfalls files. **Verify their PRs merged and `dev` is green before starting new work.**

## 3. What shipped today

**The deliverable.** `docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md` (the ask) and `2026-08-01-mcp-surface-research.md` (a companion, only relevant when the MCP question comes up — its conclusion is that an MCP surface is the right "final form" but is downstream of M5's trust work, not parallel to it).

**Defect fixes**, all verified against production or the ESI spec: the `is_bpc=false` filter (matched zero rows), courier contracts rendering as "Exchange", a courier serialization 500 (one null `start_location_id` failed an entire 50-row page), `collateral` filterable/sortable but never returned, watchlist alerts outliving purchase by up to two weeks, and `status`/`date_completed` being served despite never holding data.

**Test-suite integrity**, which turned out to be the session's biggest surprise — two suites were passing without testing anything:
- Every frontend fixture's `date_expired` had drifted into the past, so the whole component and E2E suite rendered "Expired" throughout. Nothing failed because **no assertion anywhere read a countdown**.
- Five backend tests replayed VCR cassettes that had **never recorded ESI**. All nine interactions were `http://test/...` — the app talking to itself. The marker had been applied to a file of internal-endpoint tests, so re-recording the cassettes (the obvious fix) would have preserved the defect. Cassettes deleted; a collection guard (`tests/marker_guards.py`) now aborts the run if any test pairs `pytest.mark.vcr` with an app-client fixture.
- A sixth test asserted inside `if data["items"]:` while seeding no fixture, so the block never executed in any run since it was written.

**Local environment**, both genuinely broken and now fixed: Postgres was a **repo bug**, not stale data (`7dce47f` bumped the image pin to 18 without moving the volume mount, and PG 18 rejects the pre-18 path even on an empty volume — pitfall ENV-9); `alloy` was **orphaned**, created from a since-deleted worktree so its bind-mount sources vanished (pitfall ENV-10). Both restored and verified.

## 4. Corrections made to this session's own output

Recorded because a future reader will otherwise trust the superseded version.

**Abyssal modules are in scope.** The analysis originally said their roll statistics aren't in public ESI and scoped them out. **Wrong** — verified against the spec: the public contract-items payload returns `item_id`, and `GET /dogma/dynamic/items/{type_id}/{item_id}` is public and unauthenticated, returning `source_type_id`, `mutator_type_id`, and the rolled `dogma_attributes`. That is MutaMarket's entire data model, reachable with the pipeline we already have. Since abyssals are the largest non-ship cluster, this moved them *into* the display phase. See §4.5 of the analysis.

**The four "dead" columns stay.** Dropping `raw_quantity`/`is_singleton` was approved, then reversed when Sam said character/corp contract ingestion is likely to matter. All four permanently-NULL columns (`status`, `date_completed`, `raw_quantity`, `is_singleton`) are **exactly** what `/characters/{id}/contracts` and `/corporations/{id}/contracts` and their `/items` sub-routes return. They are dead only under *public* ingestion. See §4.2 "Keep them, don't drop them".

**The Polygon.io "35+ tool anti-pattern"** cited in the MCP doc is stale — it renamed to Massive and rebuilt to 3 tools. Corrected in place.

## 5. Deferred work — each with its unblock condition

| Item | Unblock condition | Where the unblocker lands |
|---|---|---|
| Ingest `runs` / ME / TE | Bundle into Plan B rather than landing standalone — it touches the ingestion path Plan B is redesigning | `docs/superpowers/handoffs/2026-07-27-plan-b-handoff.md` |
| Ingest `buyout`, `days_to_complete`, `item_id` | Needed by the type-aware view; do it with the taxonomy work | Analysis §4.2, §6 phase 2 |
| Persist item `category_id`/`group_id` | The enabling step for every category filter F002 promised. **Market groups will not substitute** — measured ~87% NULL on non-ship items, worst exactly where the volume is | Analysis §4.1 |
| Resolve the 0.2% structure tail | Only after #116 lands. EVE Ref publishes tokenless structure data. **Trap:** that endpoint returns `solar_system_id`, not `system_id` — copying the station path unchanged writes NULL while appearing to work | PR #116's follow-up note |
| 69 of 70 regions return nothing | Design choice, not a bug with one right answer: hide uncovered regions, label them, or show an explanatory empty state | Analysis §4.3 |
| `min_runs`/`max_runs`, ME/TE remain inert | Depends on the `runs`/ME/TE ingestion above. Params deliberately left in place; removing them is a breaking change nobody approved | `schemas/contracts.py` NOTE blocks |
| Character/corp contract ingestion | Sam's stated direction. Starting inventory: those routes also return `acceptor_id`, `assignee_id`, `availability`, `date_accepted` (no columns exist), and their bids routes return `bidder_id`, which the public route omits. Needs per-user ESI tokens → token-lifecycle and privacy questions the public pipeline doesn't have | Analysis §4.2 |
| `esi_live` marker + `pytest-vcr` have zero users | Deliberately kept — the ESI-recording strategy is legitimate and the collection guard makes misuse impossible. Removing would foreclose a real direction for no saving | `app/backend/pyproject.toml` |

## 6. Operational guardrails established today

These cost real time to learn. They are in durable places; this is the index.

- **`gh pr merge --auto` is NOT a CI gate in this repo.** No branch has required status checks (`dev` has no protection; the one ruleset targets the default branch with `deletion`/`non_fast_forward`/`pull_request` only). `--auto` merges immediately, mid-run. Verify checks yourself, then merge explicitly. → `docs/git-strategy.md` §Mechanics.
- **A clean merge is not evidence of correctness.** Twice today a branch that merged *without conflict* would have silently deleted work that landed while it waited. Read a held branch's diff as **"what would merging this DELETE?"** → `docs/git-strategy.md`.
- **Sequential IDs collide across parallel agents.** `ESI-2` and `TEST-17` were each claimed by two agents for different traps, and git auto-merged the file into **two `TEST-17` entries with no conflict**. Allocate against `origin/dev`, run a duplicate-ID census after any merge, and grep the source tree when renumbering — **pitfall IDs are cited from code comments**. → `docs/git-strategy.md` §Shared sequential identifiers.
- **Never start long-lived containers from a worktree.** Their bind-mount paths die with the worktree, and the container only fails at its *next* restart — weeks later, unattributable. → pitfall ENV-10.
- **Do not read the repo-root `.env`.** A plain `wc -c` on it hung past 120s; it is 1Password-managed and can stall on a prompt. The cost is a dead session, not just a hygiene violation. Use `app/backend/.env.example` for local values.
- **Generating a 1P-backed env file without seeing values:** template of `op://` references → `op inject -o <path>`, verify with key names and value *lengths* only. Parentheses in a 1Password item title break `op://` parsing — use the item UUID.
- **A passing mutation test is a finding.** One migration round-trip test's mutation came back **green**, proving the test's own docstring claim false — a round-trip assertion is structurally blind to whatever the return trip erases.
- **Fresh worktrees lack `app/backend/src/.env`** and need `pdm install`; the shared test DB means parallel agents must use scratch Postgres containers on distinct ports.

## 7. Priority queue for a fresh session

1. **Verify the three in-flight items landed** (§2) and `dev` is green. Do not build on an unmerged assumption.
2. **Get Sam's decision on §1.** Everything below assumes yes.
3. **Write the F008 feature spec** — brainstorm first per CLAUDE.md skill routing; reconcile the two spec conflicts named in §1.
4. **Phase 2 of the analysis §6** — ingestion fields + taxonomy, bundled with Plan B where they overlap.
5. **Phase 3** — the type-aware browse view.
6. Appraisal remains parked per `2026-07-26-m5-direction-options.md`; §3.2 of the analysis is its display contract when it lands.

## 8. Continuation prompt (paste-ready)

> Pick up the Hangar Bay contract-coverage work. Read `docs/superpowers/handoffs/2026-08-01-contract-coverage-handoff.md` first, then `docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md` (§1 findings, §4 the internal gap, §6 the recommendation, and the appendix which records a claim the document got wrong and how).
>
> Before anything else: confirm PR #116 merged, confirm the ESI spec-drift monitor and future-clock vitest lane PRs landed, and confirm `dev` CI is green. Then check with Sam whether he has decided on the §1 question — whether to build the type-aware "all contracts" view. If yes, the next deliverable is an F008 feature spec (use the brainstorming skill first per CLAUDE.md), reconciling the F002-vs-M1 market-group conflict and the total absence of any courier policy.
>
> Do not re-derive the ESI schema facts — they are spec-verified and recorded in analysis §4.2/§4.5. Do not re-propose dropping the four permanently-NULL columns; that was approved, then reversed on Sam's character/corp-ingestion signal, and the reasoning is in §4.2.

## Appendix — adversarial review of this handoff

**Round 1 — naive fresh agent (4 findings applied).** Added the "1.2% of ~34,000" figure inline rather than assuming the reader opens the analysis; spelled out what F008 is and that no placeholder exists; named the two spec conflicts explicitly instead of "the known conflicts"; stated that production deploys from `main`, so "prod unchanged" reads as expected rather than alarming.

**Round 2 — recency bias (3 findings applied).** The morning's work was nearly lost behind the evening's env fixes. Restored: the EVE Workbench route-extraction evidence (the load-bearing competitive finding), the ecosystem survey's conclusion that nobody handles couriers, and the MCP doc's actual status. Early-session material was under-represented on first draft.

**Round 3 — seams (3 findings applied).** Documented the #115→#116 conflict *and* the specific resolution hazard (generated files must be regenerated, not hand-merged); flagged that all three in-flight agents may touch the same workflow/pitfall files; recorded the Plan B overlap as a routing instruction rather than a note, since that is where the `runs`/ME/TE work must go.

**Round 4 — operational guardrails (2 findings applied).** §6 existed only as scattered prose; converted to an index pointing at durable homes. Added the fresh-worktree and scratch-DB mechanics, which cost two agents time today and appear in no pitfall.

**Round 5 — loss-averse (4 findings applied).** Recovered from transcript only: the `solar_system_id`-vs-`system_id` trap for the structure follow-up; the deliberate decision to keep `esi_live`/`pytest-vcr` despite zero users; the `op inject` recipe including the parenthesis parsing failure; and the green-mutation finding, which is a methodology lesson with no other home.

**Round 6 — "corrections auditor" (session-specific, 3 findings applied).** Chosen because this session's defining characteristic is that it **reversed several of its own published conclusions** — abyssal scope, the column drop, the Polygon example. The failure mode is a future reader finding the superseded version and trusting it. Created §4 specifically to make every reversal discoverable from the handoff, and added the "do not re-propose the column drop" instruction to the continuation prompt, since that decision was approved-then-reversed and is exactly what a fresh agent would helpfully re-suggest.

**Round 7 — holistic read (1 finding applied).** Read top-to-bottom cold. The document opened with session narrative rather than the decision; reordered so §1 is the pending decision, because that is the only thing that blocks everything else.

Final pass through rounds 1–7 produced zero further material findings.
