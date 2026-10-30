<!-- ABOUTME: Implementation plan for courier reward-per-jump; every phase past 0 is blocked on Sam's -->
<!-- ABOUTME: jump-count data-source decision, and Phase 0 exists to confirm or falsify the recommendation. -->

# Reward per Jump Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan
> task-by-task. **Do not start Phase 1 or later** until the spec's Decision 1 is answered — see
> the blocking note below.

**Goal:** Give the F008 courier tab an honest ISK-per-jump figure: a jump count for every courier
whose endpoints can be resolved, the reward divided by it, and a per-row statement of which
security tier the route actually achieved.

**Architecture:** Courier endpoints are a small, heavily-repeating set of station pairs (115 Forge
couriers collapse to 39 distinct system pairs), so jump counts are a bounded lookup, not a
pathfinding service. Endpoint→system resolution already exists in `background_aggregation.py` and
already covers both ends. What this plan adds is the jump count between two systems, a cache for
it keyed by system pair, denormalized `jumps` / `reward_per_jump` columns the list can sort on,
and the courier-tab surfaces that read them.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · Alembic · Valkey · React 19 + TanStack
Router/Query · pytest · vitest + Playwright

---

## ⛔ Blocking status

**Phase 0 is partially complete: Task 0.1 is done; Task 0.2 awaits access to its required live
snapshot. Phases 1–4 remain blocked on Sam's data-source and licensing decision.**

The spec [`2026-08-10-reward-per-jump-spec.md`](../specs/2026-08-10-reward-per-jump-spec.md) asks
Sam four questions. Decision 1 — **do jump counts come from ESI's `/route/` endpoint, or from an
adjacency graph we vendor and search ourselves?** — changes which tasks exist, not just how they
are written. This plan is written for the spec's recommendation (**vendor and search ourselves**)
and carries an explicit delta in [Appendix A](#appendix-a--what-changes-if-sam-chooses-esi-route)
for the alternative.

Phase 0 deliberately front-loads the two things that could falsify that recommendation, so
discovering a problem costs one phase rather than the whole wave.

---

## Living Document Contract

This plan is a living document. Every executing agent MUST update it as
execution progresses, not only at completion.

- **On phase claim:** before flipping your own banner, the executor MUST
  check the preceding phase's banner against git reality — a ✅ SHIPPED
  banner's recorded SHA reachable on the default branch, a 🚧 banner live
  per the stale-claim signals below. If a banner does not match reality,
  correct it first. A plan's accuracy is checked by the next agent to
  arrive, not by the one who left it; this is the only read-back the
  contract has. Then flip your own banner to 🚧 IN PROGRESS
  with a claim timestamp (ISO 8601 UTC) and the active branch name. The
  banner MUST NOT include an expected-completion estimate — agents cannot
  reliably estimate their own wall-clock, and a fabricated duration
  becomes a stale anchor that misleads future readers. Followers
  encountering a 🚧 banner determine liveness by observable signals (PR
  existence, recent branch commits), not by arithmetic on expected times.
- **On phase ship:** the executor MUST update that phase's **Execution
  Status** banner with the shipped commit SHA(s) and date. If a PR is
  open, the PR number and URL MUST appear in the Execution Status table.
  Recorded SHAs stay resolvable because this project merges with
  `--merge` and preserves per-commit history.
- **On phase defer:** the executor MUST update the banner with ⏸ status
  AND a prose description of the unblock condition + a link to the
  likely-unblocker artifact (plan page, task, or PR whose own Execution
  Status banner will signal completion). Prose + link is durable across
  paraphrases and scope edits; exact-string coordination between agents
  is not.
- **On PR merge:** the executor MUST record the merge SHA in the banner
  + the Execution Status table.
- **On deviation from the written plan** (scope edits, structural
  refactors, dropped tasks, reordered phases): the executor MUST
  inline-document the deviation in the affected task AND summarize it
  in the Execution Status section's "Deviations" subsection.
  Deviation state MUST NOT live only in PR notes or status reports.
- **On discovery** (pre-existing drift surfaced during execution, new
  bugs found, architectural issues noted): the executor MUST record it
  in the Execution Status section's "Discoveries" subsection with
  pointers to the files/lines affected. Follow-up dispatches read this
  subsection to avoid duplicate discovery work.

**Layout invariant.** The status table is the first content under
`## Execution Status`. Deviations and Discoveries are subsections
*below* it and MUST NOT be placed above it — the table is what a reader
needs in the first screen, and it stops being that the moment a growing
narrative sits on top of it. Entries in both subsections are a one-line
summary plus a pointer to where the detail lives (the affected task, the
file:line); they are not the place to tell the story.

The plan SHOULD reflect reality at the end of every session that touches
it. Anything worth putting in a status report to the user is worth
putting in the plan.

Rationale: `/writing-plans-enhanced` Step 5. Writing at ship time is
cheap; reconstruction by downstream readers is expensive, compounds
across dispatches, and fails silently when state is split across PR
notes and commit messages.

---

## Execution Status
<!-- The status table stays directly below this heading. New content goes in the
     Deviations / Discoveries subsections below it — never above the table. -->

| Phase | Status | Ship SHA(s) | Notes |
|---|---|---|---|
| 0 — Falsify or confirm the data source | ⏸ Partially complete | — (phase incomplete) | Task 0.1 complete in [edge-list findings PR #185](https://github.com/scarson/hangar-bay/pull/185), source `733e7b1`, merge `793b16f`; [Task 0.2 ranking measurement](#task-02-measure-whether-the-denominator-choice-actually-reorders-anything) awaits the required live snapshot |
| 1 — Route graph and jump counts | ⬜ Not started | — | blocked on Decision 1 |
| 2 — Ingestion wiring and denormalization | ⬜ Not started | — | blocked on Phase 1 |
| 3 — API surface | ⬜ Not started | — | blocked on Phase 2 |
| 4 — Courier tab | ⬜ Not started | — | blocked on Phase 3 |

**Overall:** 0/5 phases shipped. Phase 0 has 1/2 tasks complete; Task 0.2 is deferred pending
access to its required live snapshot. Phases 1–4 remain blocked on the spec's Decision 1.

### Deviations
- _None yet._

### Discoveries
- 2026-09-05: [Task 0.1's edge-list findings](#task-01-obtain-and-check-the-adjacency-edge-list) were already merged; the plan's unstarted status did not reflect that evidence.
- 2026-09-05: [Task 0.2's live-population access prerequisite](#task-02-measure-whether-the-denominator-choice-actually-reorders-anything) remains unmet; the public list response does not establish the required frozen courier population.

---

## Read before any task in this plan

Every task below assumes these have been read once, at the start of the session:

- [`docs/pitfalls/implementation-pitfalls.md`](../../pitfalls/implementation-pitfalls.md) — in
  particular **ESI-3** (ESI omits fields rather than sending falsy ones, so absence is never zero),
  **ESI-4** — **read its "Where It Stands" paragraph specifically, not just the flaw statement.**
  It is marked Resolved, records that Hangar Bay pins `ESI_COMPATIBILITY_DATE` to `2026-07-21`, and
  states the consequence this plan turns on: `/route/` is a hard cutover at `2025-09-30`, and *any
  future work that calls it must use the POST form*. The opening paragraph still describes the
  historical header-less state, which is what makes reading only the top of the entry misleading,
  **SQLA-2** (the chunked upsert and its partial-index `ON CONFLICT`), and **FASTAPI-1** (a GET
  filter model takes `Annotated[Model, Query()]`, never a bare `Depends`).
- [`docs/pitfalls/testing-pitfalls.md`](../../pitfalls/testing-pitfalls.md) — in particular
  **TEST-11** (a chunked writer needs a test crossing one chunk boundary), **TEST-18** (reconcile
  fixtures against the WRITER, never the model), **TEST-24** (a fixture holding one distinct value
  cannot tell a set-returning query from its base case), and **TEST-26** (testing the INSERT path
  is not testing the upsert path production uses).
- The spec's §1 "Already settled" — three of the original spike's nine work items are **already
  done in the code** and MUST NOT be redone.

---

## Phase 0 — Falsify or confirm the data source

**Execution Status:** ⏸ DEFERRED — Task 0.1 completed 2026-08-10; Task 0.2 is deferred
pending [access to the required live snapshot](#task-02-measure-whether-the-denominator-choice-actually-reorders-anything).

Phase 0 answers two questions that decide whether the spec's recommendation survives. It writes no
production code and ships no feature. **Its output is evidence for Sam, not an implementation.**

Run it before asking Sam to decide, or alongside; either way its findings go into the spec's
Decision 1 section before that decision is taken.

### Task 0.1: Obtain and check the adjacency edge list

**Execution Status:** ✅ DONE — 2026-08-10, [edge-list findings PR #185](https://github.com/scarson/hangar-bay/pull/185).
Source commit `733e7b1eb6e20f834b2bd6c8dc72cdb1beb92b0b`; merge commit
`793b16f9815882e7844968e7f18a6bb8033723e5`, both reachable from `origin/dev` at the 2026-09-05
status check. The [spec appendix's fetched edge-list findings](../specs/2026-08-10-reward-per-jump-spec.md#phase-0-task-01--the-edge-list-actually-fetched-2026-08-10)
record the measurements, security coverage, and unresolved licensing position. No data was vendored.

**Files:**
- Create: `app/backend/tools/route_graph/` (scratch — nothing here ships in this task)

The spec's §2 rests on a measurement I did not make: that Fuzzwork's
`dump/latest/csv/mapSolarSystemJumps.csv` is a 937 KB, 13,978-row directed edge list, and that a
minimal ID-pair form is ~51 KB gzipped.

**Step 1:** Fetch the file. Record its actual size, row count, and column headers.

**Step 2:** Load it into an adjacency dict and count connected components. **Expected: four** —
main New Eden (~5,228 systems), Pochven (27, gate-isolated), and two Jove pockets (7 and 6). If
the count is not four, STOP and report: either the file is not what the spike measured or the map
has changed, and both invalidate the sizing.

**Step 3:** Establish where per-system security status comes from and record it the same way
(size, row count, and specifically **whether it covers every system id appearing in the edge
list** — a security source with gaps silently reclassifies the missing systems). Candidates, in
the order worth trying: Fuzzwork's `mapSolarSystems.csv` (same dump, so one provenance story
rather than two), the CCP SDE's solar-system dataset, and — only as a last resort —
`GET /universe/systems/{id}`, which is 8,490 calls and was already rejected on those grounds as
the spike's Option C. Both options need this — see the spec's §2, "Option A needs per-system
security data anyway."

**Step 4:** Record the licensing position of whatever source is used, including the absence of one.
The spike explicitly could not find a Fuzzwork license page. **Do NOT vendor anything into the
repository in this task.** Vendoring is a distribution decision and it is Sam's.

**Deliverable:** a findings note appended to the spec's appendix. No commit to `app/backend/src/`.

**Do NOT:** write the BFS yet, add a dependency, or commit the data file.

### Task 0.2: Measure whether the denominator choice actually reorders anything

**Execution Status:** ⏸ DEFERRED — access to the required live snapshot is unavailable.

The 2026-09-05 access check found no available Render API key or production database connection
in the process or expected root/backend environment files. A public contract-list request returned
HTTP 200 but lacked coverage metadata and `end_location_system_id`; it did not establish support
for the requested courier filter, the courier population, or runtime `AGGREGATION_REGION_IDS`.
Paginating that changing listing does not satisfy the single-instant snapshot requirement.

**Unblock condition:** obtain a read-only, consistent export of the live courier population across
every runtime-configured `AGGREGATION_REGION_IDS` region, with contract IDs, rewards, both endpoint
system IDs, eligibility fields, extraction time, and the deployed configured region list. Freeze
that population once for both rankings and apply the exclusions in Step 1. The held production
database allow rule `198.37.143.189/32` remains unchanged. No ranking measurements are recorded.

**Files:**
- Create: `app/backend/tools/route_graph/inversion_count.py` (scratch)

The spec argues that ESI's `secure` upper bound matters *because the error is length-correlated
and the metric is a ranking*. That is an argument, not a measurement. This task measures it.

**Step 1:** Take the live courier population for **every region the deployment currently
ingests** (`AGGREGATION_REGION_IDS`), in ONE snapshot taken at a single instant and written to a
file, so both rankings are computed over identical input. Include only couriers with both endpoints
resolvable to systems.

Exclusions, stated so two runs cannot disagree: drop couriers with no `reward` (the ratio is
undefined, not zero), drop same-system couriers (zero jumps, ratio undefined), and drop pairs with
no all-high-sec route — the last is a *finding to report separately*, with its count, not a row to
score. Rank descending by reward-per-jump; break ties by `contract_id` ascending so the ordering is
total.

**Step 2:** Compute reward-per-jump twice — once with ESI's `secure` count, once with the true
shortest all-high-sec count from Task 0.1's graph.

**Step 3:** Report: the number of ranking inversions between the two orderings, the top-10 overlap,
and the maximum single-contract ratio difference.

**Step 4:** State the verdict against a threshold fixed BEFORE the numbers are seen, so the
result cannot be rationalized either way. **If fewer than 10% of ranked pairs are inverted AND the
top-10 overlap is 9 or 10, the spec's recommendation is wrong and Option A wins on simplicity** —
say so, in those words, rather than defending the recommendation. Report the three figures
regardless of which side of the line they fall on. A Phase 0 that cannot overturn the thing it was
written to test is theatre.

The threshold is a judgement call, not a derived constant; it is written down in advance precisely
because a threshold chosen after seeing the data is not a threshold.

**Deliverable:** the numbers, appended to the spec's Decision 1 section.

**After completing Phase 0:**

Review the batch once, from a perspective the individual tasks did not apply. Run further rounds
only while the previous round produced material findings; stop when one produces none. A round run
to reach a count, after findings have stopped, manufactures them — and a manufactured finding is
the same defect as a suppressed one.

---

## Phase 1 — Route graph and jump counts

**Execution Status:** ⏸ DEFERRED pending Sam's answer to the spec's Decision 1 (whether jump
counts are computed from a vendored adjacency graph or fetched from ESI's `/route/` endpoint), and
pending Phase 0's two findings, which may change that answer. See
[the spec's §2](../specs/2026-08-10-reward-per-jump-spec.md) — its Decision 1 section is where the
answer will be recorded. A follow-up dispatch verifies by reading that section, not by grepping.

*Written for the recommended option. If Sam chooses ESI, replace this phase with
[Appendix A](#appendix-a--what-changes-if-sam-chooses-esi-route).*

### Task 1.1: Vendor the graph data

**Files:**
- Create: `app/backend/src/fastapi_app/data/solar_system_jumps.csv.gz` and
  `app/backend/src/fastapi_app/data/solar_system_security.csv.gz` — **use these exact paths and
  names even if Task 0.1 sourced the data differently**; if Task 0.1 found a single joined file is
  better, collapse to `app/backend/src/fastapi_app/data/solar_systems.csv.gz` and say so in the
  Deviations subsection. Do not invent a third layout.
- Create: `app/backend/src/fastapi_app/data/README.md` — provenance, source URL, fetch date,
  licensing position, and the refresh procedure
- Create: `app/backend/src/fastapi_app/services/route_graph.py`
- Test: `app/backend/src/fastapi_app/tests/services/test_route_graph.py`

**Read Task 0.1's findings note before starting.** It carries the actual row counts, the component
enumeration, and the security-source decision this task builds on.

**Tasks 1.1 → 1.2 → 1.3 → 1.4 all modify `route_graph.py` and its one test file. They are strictly
sequential and MUST NOT be parallelized across agents.**

**BEFORE starting work:**
1. Invoke `superpowers:test-driven-development`
2. Read `docs/pitfalls/testing-pitfalls.md`

Follow TDD: write failing test → implement → verify green. Cover the error paths and edge cases as
you write the tests — that is part of writing them, not a separate audit afterwards.

**Step 1: Write the failing tests.** Two: one over a *known* piece of EVE geography rather than
over the loader's own output (TEST-27 — an expectation derived from the thing it constrains agrees
with every value that thing can take), and one proving the two vendored files agree with each
other.

The second matters because Task 0.1 checked the SOURCE files, and what ships is a transformed
artifact. A security file truncated or mis-parsed during that transformation leaves systems with no
security value, every one of which then silently fails the high-sec predicate — corrupting
`high_sec_jumps_between` and the tier for whole regions while the adjacency test stays green:

```python
def test_every_system_in_the_graph_has_a_security_value():
    graph = load_solar_system_graph()
    missing = {system for system in graph if security_of(system) is None}
    assert missing == set(), f"{len(missing)} systems have no security status"
```


```python
def test_the_graph_carries_a_known_new_eden_adjacency():
    graph = load_solar_system_graph()
    # Jita (30000142) neighbours Perimeter (30000144) — a hand-checked fact about
    # the map, not a value read back out of the file under test.
    assert 30000144 in graph[30000142]
    assert 30000142 in graph[30000144]  # the edge list is directed; both rows must exist
```

**Step 2: Run it and watch it fail** for the right reason — `load_solar_system_graph` undefined,
not a missing data file. Run:
`cd app/backend && ./.venv/Scripts/pytest.exe src/fastapi_app/tests/services/test_route_graph.py -q`

**Step 3: Implement** the loader. Load once at module import into a module-level dict; the file is
static and the parse cost must not be paid per call.

**Step 4: Run and confirm green.**

**Step 5: Commit.** `feat(api): vendor the solar-system adjacency graph`

**Do NOT:** add a runtime download, a refresh job, or a cache-invalidation mechanism. The file is
static and its refresh procedure is a documented human step, per the README this task writes.

### Task 1.2: Shortest-path jump counts

**Files:**
- Modify: `app/backend/src/fastapi_app/services/route_graph.py`
- Test: `app/backend/src/fastapi_app/tests/services/test_route_graph.py`

**BEFORE starting work:** as Task 1.1.

**Step 1: Write the failing tests.** Four cases, and the fourth is the one a naive implementation
gets wrong:

```python
def test_the_same_system_is_zero_jumps():
    assert jumps_between(30000142, 30000142) == 0

def test_an_adjacent_system_is_one_jump():
    assert jumps_between(30000142, 30000144) == 1

def test_jita_to_amarr_is_eleven_jumps():
    # The spike measured this against live ESI: 11 under `shortest`.
    assert jumps_between(30000142, 30002187) == 11

def test_a_system_in_another_component_is_unreachable():
    # Pochven is gate-isolated (filament entry only), so there is no route.
    # None is the honest answer and it is NOT the same as 0.
    assert jumps_between(30000142, A_POCHVEN_SYSTEM_ID) is None
```

`A_POCHVEN_SYSTEM_ID` is a module constant this task defines. **Take its value from Task 0.1's
component analysis** — that step already enumerates the four components, so the Pochven member ids
are in hand. Do NOT guess an id from memory; a wrong id makes this test pass for the wrong reason
(an id absent from the graph is also unreachable). Assert the id is present in the graph before
asserting it is unreachable, so the test cannot pass vacuously (TEST-15).

**Step 2: Run and watch them fail.** Confirm the failure is `jumps_between` undefined.

**Step 3: Implement** breadth-first search over the adjacency dict, returning `None` when the
frontier exhausts without reaching the destination.

**Step 4: Run and confirm green.**

**Step 5: Mutation-verify** (TEST-12). Replace the BFS body with `return 1` and confirm the
Jita→Amarr and unreachable tests both go red while the adjacency test stays green. Take the
snapshot BESIDE the file being mutated, guard the mutation target with an `assert <target> in
text`, put the restore in a `finally`, and check `git status` afterwards — an unexpected `M` on a
source file is a stop-everything signal.

**Step 6: Commit.** `feat(api): compute solar-system jump counts by breadth-first search`

### Task 1.3: High-security-only jump counts

**Files:**
- Modify: `app/backend/src/fastapi_app/services/route_graph.py`
- Test: `app/backend/src/fastapi_app/tests/services/test_route_graph.py`

**BEFORE starting work:** as Task 1.1.

The metric the courier tab defaults to. This is the same BFS over a subgraph filtered to systems
at security ≥ `HIGH_SEC_MINIMUM`.

**Step 1: Write the failing tests:**

```python
def test_the_high_sec_route_is_the_shortest_one_that_never_leaves_high_sec():
    # The spike found ESI returns 45 for this pair while a fully high-sec 34-jump
    # route exists. Ours must find the 34 — that divergence is the whole reason
    # this function exists rather than a stored ESI `secure` count.
    assert high_sec_jumps_between(30000142, 30002187) == 34

def test_a_destination_with_no_high_sec_route_is_unreachable_rather_than_long():
    # Jita -> 1DQ1-A (30004759): ESI's `secure` returns an 81-jump route still
    # crossing 23 low/null systems. The honest answer is that no high-sec route
    # exists. Confirm the id against Task 0.1's data before relying on it; if it
    # does not match, use any null-sec system the graph carries and say which.
    assert high_sec_jumps_between(30000142, 30004759) is None
    # Not vacuous: the same pair IS reachable without the security constraint.
    assert jumps_between(30000142, 30004759) is not None

def test_the_security_cutoff_sits_where_eve_displays_it():
    # Ahbazon is 0.421, which EVE displays as 0.4 and treats as low-sec.
    assert is_high_sec(0.45) is True
    assert is_high_sec(0.421) is False
```

**Step 2: Run and watch them fail.**

**Step 3: Implement.** `HIGH_SEC_MINIMUM = 0.45` as a **named module constant, never a literal at
the comparison site** — the spec flags the cutoff as something worth being able to find and
reconsider.

**Step 4: Run and confirm green.**

**Step 5: Mutation-verify** that changing `HIGH_SEC_MINIMUM` to `0.4` fails
`test_the_security_cutoff_sits_where_eve_displays_it` while the plain-BFS tests stay green.

**Step 6: Commit.** `feat(api): compute shortest all-high-sec jump counts`

### Task 1.4: Prove the graph against CCP's own answer

**Files:**
- Create: `app/backend/src/fastapi_app/tests/services/test_route_graph_matches_esi.py`

**BEFORE starting work:** as Task 1.1.

This is the task that converts "we wrote a BFS" into evidence, and it is the spec's stated reason
for preferring our own graph over buying counts.

**This task needs an ESI seam that does not exist under the vendored-graph option.** `ESIClient`
has no route method, and at the pinned compatibility date `2026-07-21` the route endpoint is
`POST /route/{origin_system_id}/{destination_system_id}` returning `{"route": [...]}` — the legacy
`GET` returning a bare array is already a 404 for us, so the list-shaped helper the spike described
does not apply. Write the smallest thing that answers the question:

**Step 1:** Add a route call to `ESIClient` sufficient for this comparison — POST shape, object
response, `preference: Shorter`. Do NOT build the caching, the fan-out, or the other two
preferences; nothing in the shipped feature calls this under Option B, and it exists to check the
graph.

**Step 2:** Write the comparison over **the full set of distinct system pairs in the live courier
population for the ingested regions** — not a hand-picked sample. Record the pair count in the test
output. Fewer than 20 pairs means the snapshot is wrong; stop and find out why rather than
proceeding with a weak check.

**Step 3: Keep it out of the default lane, mechanically.** The `esi_live` marker declared in
`pyproject.toml` is a *label*; nothing in the pytest configuration deselects it, so a marked test
runs in ordinary CI and makes real network calls. Add an explicit opt-in — a `--esi-live` flag
whose absence skips, or a `-m "not esi_live"` default in `addopts` — and state in the test's
docstring exactly how to run it. Verify by running the default lane and confirming the test reports
as skipped, not passed (a passing test here means the guard does not work).

**Step 4:** Run it against live ESI. **Any disagreement STOPS this plan** — report it rather than
adjusting the expectation. A graph that disagrees with CCP on shortest-path is wrong in a way the
high-sec count would inherit silently.

**Step 5: Commit.** `test(api): pin our jump counts against ESI's own shortest routes`

**Never use the `vcr` marker here.** Per TEST-14 it replays a cassette and never reaches the code
under test, which would make this comparison assert against a recording of itself.

**After completing Phase 1:**

Review the batch once, from a perspective the individual tasks did not apply. Run further rounds
only while the previous round produced material findings; stop when one produces none.

---

## Phase 2 — Ingestion wiring and denormalization

**Execution Status:** ⏸ DEFERRED pending Phase 1 shipping (a working `jumps_between` /
`high_sec_jumps_between` pair, whichever data source Decision 1 selects). See Phase 1's Execution
Status banner above.

### Task 2.1: Schema

**Files:**
- Modify: `app/backend/src/fastapi_app/models/contracts.py`
- Create: one migration under `app/backend/src/alembic/versions/`
- Test: `app/backend/src/fastapi_app/tests/test_migrations.py`

Add to `Contract`: `jumps` (nullable int), `reward_per_jump` (nullable float), and
`route_security_tier` (nullable str — the per-row disclosure F008 §15.2 requires). All nullable:
~9–10% of couriers can never have a jump count because an endpoint is a player structure, and that
is structural.

**What `jumps` means, stated here because every later task depends on it and "the default is
high-security-preferred" does not by itself say.** `jumps` is the count for the route the contract
would actually be flown on, and `route_security_tier` says which route that was. The three cases
are exhaustive and MUST be implemented exactly as written:

| Case | `jumps` | `route_security_tier` |
|---|---|---|
| An all-high-sec route exists | the **high-sec** count | `'high_sec'` |
| No high-sec route exists, but a route does | the **shortest** count | `'crosses_low_sec'` |
| No route at all, **or** an endpoint is unresolvable | `NULL` | `NULL` |

**The last row folds two different situations together, and the UI copy must respect that.** An
endpoint that could not be resolved to a system (the player-owned-structure case) and a resolved
pair with no gate route between them (EVE's map has four disconnected components — Pochven and two
Jove pockets) both store NULL. v1 does NOT distinguish them: the jumps cell reads the same for
both, and the copy stays generic ("no route available") rather than naming the structure cause,
which would be a confident falsehood for the second. A `route_unknown_reason` column is **deferred,
not rejected** — add it when a surface actually needs to tell the two apart.

The middle row is the case that would otherwise be silently invented by whoever implements it
first. Falling back to the shortest count is deliberate: a null-sec delivery is a real courier
contract with a real jump count, and storing NULL for it would hide it from the ranking entirely
rather than disclose its risk — which is the opposite of what the per-row disclosure is for.

`route_security_tier` takes exactly those two non-NULL values, `'high_sec'` and
`'crosses_low_sec'`. **Do NOT add a third tier for null-sec**: distinguishing low from null needs a
second threshold nobody has chosen, and the disclosure's job is "did this leave high-sec," which
two values answer. If a third tier is later wanted, that is a decision, not an implementation
detail.

Index `reward_per_jump` — the courier tab sorts on it.

**Migration rules this repo already enforces**, visible in the two prior migrations: a downgrade
that could lose data states its refusal rather than failing incidentally; `SET lock_timeout` and
`LOCK TABLE ... IN ACCESS EXCLUSIVE MODE` precede any guard so the check and the alteration cannot
be split by a concurrent writer; and the guard must render correctly under `alembic downgrade
--sql`. A downgrade here only drops columns, so no refusal guard is needed — but say so in the
migration docstring rather than leaving the reader to infer it.

**Test:** extend the migration suite with a clean-downgrade test asserting the columns are gone,
reading `information_schema.columns`, and asserting their PRESENCE first (TEST-15 — an empty result
from a query that never could have matched is not evidence of absence). Restore head in a
`finally`: `blank_migrated_sync_connection` is **session-scoped** (TEST-23), one database shared by
every consumer.

**Commit:** `feat(api): store courier jump counts and reward per jump`

### Task 2.2: Stamp jumps during ingestion

**Files:**
- Modify: `app/backend/src/fastapi_app/services/background_aggregation.py`
- Test: `app/backend/src/fastapi_app/tests/services/test_background_aggregation.py`

**BEFORE starting work:** as Task 1.1.

`_build_one_contract_row` already stamps `start_location_system_id` and `end_location_system_id`
from the `station_to_system` map. Add the jump count and the ratio alongside them.

**Step 1: Write the failing tests.** Five, and each names a distinct failure:

```python
async def test_a_high_sec_courier_stores_the_high_sec_count_and_says_so(db_session):
    """Task 2.1's first row: jumps is the high-sec count, tier is 'high_sec'."""
async def test_a_courier_with_no_high_sec_route_falls_back_to_the_shortest_count(db_session):
    """Task 2.1's MIDDLE row, and the one an implementer will otherwise invent.
    jumps is the shortest count and the tier says 'crosses_low_sec' — NOT NULL, which
    would hide a real contract from the ranking instead of disclosing its risk."""
async def test_a_courier_with_an_unresolvable_endpoint_stores_null_jumps_and_null_tier(db_session): ...
async def test_a_same_system_courier_stores_zero_jumps_and_a_null_ratio(db_session):
    """Zero jumps is a measurement; reward/0 is undefined, not infinity."""
async def test_a_courier_ESI_sent_no_reward_for_stores_a_null_ratio(db_session):
    """ESI marks `reward` optional, so the NUMERATOR can be absent as easily as the
    denominator (TEST-22 — reconcile the writer against the spec's `required` array,
    not against payloads the author has happened to see). A jump count still stores;
    only the ratio is NULL."""
async def test_a_non_courier_contract_carries_the_keys_with_null_values(db_session):
    """"Never gets a jump count" means NULL values, never absent keys.

    bulk_upsert derives the updated column set from values[0], so a batch whose first
    row omits these three keys writes none of them for ANY row in that batch — an
    order-dependent data loss that appears only when a non-courier sorts first. Every
    row carries all three keys; couriers fill them."""

async def test_a_mixed_batch_led_by_a_non_courier_still_stores_the_couriers_jumps(db_session):
    """The batch-order hazard above, exercised: a non-courier FIRST and a courier
    second, in one _process_contracts call."""
async def test_a_re_sighted_courier_whose_route_CHANGED_updates_all_three_columns(db_session):
    """The upsert's ON CONFLICT arm is the path production uses — every contract is
    re-fetched each run, so a fresh insert exercises the arm that runs once in a
    contract's life and skips the one that runs hourly (TEST-26).

    The second sighting must carry a DIFFERENT destination, so the three derived
    columns have to change. Re-writing identical values passes even when jumps,
    reward_per_jump and route_security_tier are absent from the conflict update
    entirely — the stale-derived-data bug this test exists to catch.

    Assert all three move together: a contract whose route changed but whose stored
    tier still describes the old one is worse than no tier at all."""
```

**Step 2–4:** RED for the right reason, implement, GREEN. **When a TDD test goes GREEN
immediately, or RED on the first try, verify the REASON before believing it.**

**Step 5: Mutation-verify** three things separately, because they fail differently: remove the
divide-by-zero guard (the same-system test must go red, the others green); make the tier always
`'high_sec'` (only the fall-back test goes red); and make the fall-back store NULL instead of the
shortest count (again only the fall-back test). A single mutation covering all three would not
show that each is independently constrained.

**Step 6: Commit.** `feat(api): stamp jump counts and reward per jump during ingestion`

**Do NOT** add `jumps` to `NAME_COLUMNS_PRESERVED_ON_NULL`. A NULL jump count means the route is
not resolvable *this run*, and that is a fact about the contract, not a degraded lookup to be
papered over — the same reasoning that keeps `date_completed` out of that set (TEST-26's entry
records what happened when a column was added to it for plausible-sounding reasons).

### Task 2.3: Cache the pair→jumps lookup

**Files:**
- Modify: `app/backend/src/fastapi_app/services/background_aggregation.py`
- Test: `app/backend/src/fastapi_app/tests/services/test_background_aggregation.py`

**BEFORE starting work:** as Task 1.1.

Under the vendored-graph option this is an in-process memo per run, not a table: BFS over ~8,490
nodes is cheap, but recomputing the same pair once per contract is waste with no upside.

**Test:** result equality cannot see a memo at all — the same answer comes back either way
(TEST-25: pick an observable that DIFFERS under the mutation). Count the route computations
instead: wrap the jump function, feed **two distinct pairs each appearing on two contracts**, and
assert exactly two computations for four contracts. Two distinct pairs, not one, because with a
single pair a memo and a per-contract cache are indistinguishable (TEST-24).

**Decide and state the key normalization.** Jumps are symmetric, so `(A, B)` and `(B, A)` are the
same question. Normalize the key to a sorted tuple and add a case proving a reversed pair reuses
the memo — or, if you deliberately do not normalize, say why in the docstring. Leaving it
unstated is how two callers get different answers for one route.

**Commit:** `perf(api): memoize jump counts per system pair within a run`

**After completing Phase 2:** review the batch once, per the rule above.

---

## Phase 3 — API surface

**Execution Status:** ⏸ DEFERRED pending Phase 2 shipping (jump counts persisted on contract
rows). See Phase 2's Execution Status banner above.

### Task 3.1: Expose the fields and the sorts

**Files:**
- Modify: `app/backend/src/fastapi_app/schemas/contracts.py`
- Modify: `app/backend/src/fastapi_app/services/contract_service.py`
- Test: `app/backend/src/fastapi_app/tests/api/test_contract_filters.py`

**BEFORE starting work:** as Task 1.1.

Add `jumps`, `reward_per_jump` and `route_security_tier` to the contract response schema, and
`reward_per_jump` to `SortableContractFields` beside the existing `reward_per_volume`.

**The NULL-placement decision is the spec's Decision 4(a) and is not the executor's to re-open:**
unknown-jump rows sort **last under ascending and descending alike**. That deliberately breaks sort
symmetry, and it is the point — the alternative puts ~10% of couriers in the "best value" position
under one direction.

**Test:** both directions, asserting the full ordered id list rather than a digest of it (TEST-25 —
every lossy observable admits a wrong implementation that is wrong in exactly the way the digest is
blind to). Include at least one NULL-jump row and assert it is last in **both** directions; a
fixture with NULLs at only one end cannot tell the intended asymmetry from ordinary NULL handling.

Add an HTTP-level test that sends the sort as a real query param (TEST-1 — a filter can work
perfectly at the service layer while being unreachable over HTTP).

**Do NOT commit at the end of this task.** Task 3.2 regenerates the client from this schema
change, and the generated files must land in the SAME commit as the change that caused them.
Tasks 3.1 and 3.2 share one commit boundary, taken at the end of 3.2.

### Task 3.2: Regenerate the client chain

**Files:**
- Modify: `app/frontend/web/openapi.json` (generated)
- Modify: `app/frontend/web/src/lib/api/schema.d.ts` (generated)

Run, in this order, from the stated directories:

```bash
cd app/backend && python -m pdm run export-openapi
```

```bash
cd app/frontend/web && npm run generate:api
```

(`python -m pdm` rather than a bare `pdm` — on this project's Windows setup PDM is reachable only
through the module form, which is also how `python -m pdm run lint` is invoked.)

Commit both regenerated files **in the same commit as the schema change that caused them**. Never
hand-edit either; they are generated and are exempt from the comment rules.

**Commit — this is the single commit for Tasks 3.1 and 3.2 together**, carrying the schema
change, the service change, the tests, and both regenerated files:

`feat(api): expose jumps and reward per jump, sortable`

**After completing Phase 3:** review the batch once, per the rule above.

---

## Phase 4 — Courier tab

**Execution Status:** ⏸ DEFERRED pending Phase 3 shipping (the fields present in the generated
typed client). See Phase 3's Execution Status banner above.

### Task 4.1: The jumps and ISK/jump cells

**Files:**
- Modify: `app/frontend/web/src/features/contracts/columns.tsx`
- Modify: `app/frontend/web/src/features/contracts/format.ts`
- Test: `app/frontend/web/src/features/contracts/format.test.ts`,
  `app/frontend/web/src/features/contracts/columns.test.ts`

**BEFORE starting work:** as Task 1.1.

The display rules are the spec's Decision 4(b) and are settled: **unknown reads `'—'`, genuinely
zero reads `'0'`**, and reward-per-jump for a zero-jump contract is `'—'` rather than an infinity.
This mirrors `formatVolume`, where `formatVolume(0)` is `'0'` and absent is `'—'`.

**The formatter takes the SERVER's `reward_per_jump`, it does not recompute from reward and
jumps.** Phase 3 exposes the authoritative value and the list sorts on it; a client-side division
can disagree with the column the rows are ordered by, which is the worst kind of disagreement
because it looks like a sorting bug. This mirrors `formatRewardPerVolume`, which consumes the
server-derived figure for the same reason.

```typescript
it('distinguishes a zero-jump route from an unresolvable one', () => {
  expect(formatJumps(0)).toBe('0')
  expect(formatJumps(null)).toBe('—')
})

it('renders no rate where the server derived none', () => {
  // A zero-jump contract has an undefined ratio, so the backend sends null —
  // the frontend must not divide by zero on its own and invent an Infinity.
  expect(formatRewardPerJump(null)).toBe('—')
})
```

**Commit:** `feat(web): render courier jumps and ISK per jump`

### Task 4.2: Per-row security-tier disclosure

**Files:**
- Modify: `app/frontend/web/src/features/contracts/columns.tsx`
- Test: `app/frontend/web/src/features/contracts/components/pages.test.tsx`

**Task 4.1 and Task 4.2 both modify `columns.tsx`. Run them in order, in one agent — do NOT
dispatch them in parallel.**

Per-row disclosure is how F008 §15.2's honesty requirement is met, and it replaces a user-facing
preference picker — **do NOT build a picker.**

The wire values are Task 2.1's two: `'high_sec'` and `'crosses_low_sec'`. Render them as
**"High-sec"** and **"Leaves high-sec"** respectively, and render a NULL tier as nothing at all
rather than as a third label — an unresolvable route has no tier to disclose, and inventing
"Unknown" here would put it in the same visual family as a measured one.

**Never label anything "Safe"** — the spike found ESI's `secure` returning routes through 23
low/null systems, and the same word would be a straightforward lie under either data source.
**Do NOT** restyle, reorder, or re-title the existing courier columns while adding these; the tier
is an addition to the row, not a redesign of it.

**Commit:** `feat(web): disclose which security tier each courier route achieved`

### Task 4.3: E2E

**Files:**
- Modify: `app/frontend/web/e2e/fixtures/contracts.ts`
- Create: `app/frontend/web/e2e/reward-per-jump.spec.ts`

Fixture dates MUST be built from the clock (`expiryInDays()` / `daysFromNow()`), never hardcoded —
TEST-17 records a fixture literal that turned `dev` CI red on a calendar boundary, on a branch
whose diff could not explain it. Selectors are role/label only, no CSS or test-ids. Playwright
`retries` stay at **0**.

Every fixture-lane spec MUST intercept `GET /me` (TEST-9), even though this one does not touch
auth.

**BEFORE marking this task complete:**

If any test assertion races, flakes, or fails nondeterministically, the fix is deterministic
synchronization — NOT assertion removal or weakening. If synchronization cannot make the assertion
pass reliably, STOP and raise it. Do not ship a weaker test. Weakened assertions rationalized as
"CI stability fixes" are the exact pattern this rule prevents (TEST-2).

**Commit:** `test(e2e): cover the courier reward-per-jump surface`

**BEFORE marking Phase 4 complete — all five frontend lanes green, from `app/frontend/web`:**

```bash
npx eslint . && npx tsc -b && npm run test && npm run test:future-clock && npm run e2e
```

`routeTree.gen.ts` churns on every build — `git checkout --` it before staging, and never commit
it. Same for `package-lock.json` unless a dependency change is deliberate.

**After completing Phase 4:** review the batch once, per the rule above.

---

## Appendix A — what changes if Sam chooses ESI `/route/`

Phases 3–4 are unchanged; they consume stored values and do not care where those came from.
**Phase 2 is NOT unchanged** — Task 2.3's in-process memo is specific to the local-graph option, and
under Option A it is replaced by the durable `system_route_jumps` table below plus an asynchronous
acquisition step, which also changes the interface Task 2.2 calls. Re-read Phase 2 against A.1–A.6
before executing it. Phase 1 is replaced entirely:

- **A.1** — **The POST shape, not the legacy GET.** This project sends
  `X-Compatibility-Date: 2026-07-21` on every ESI request (`core/config.py`), which is above the
  `2025-09-30` cutover, so `GET /route/` already 404s for us. The endpoint is
  `POST /route/{origin_system_id}/{destination_system_id}` with a JSON body
  (`preference: Shorter | Safer | LessSecure`) returning an OBJECT `{"route": [...]}`. The spike's
  "we need a list-shaped helper" note applied to the legacy GET and no longer applies; `_get_esi_object`
  handles an object response. **Never send `security_penalty`** — it is measurably non-monotonic.
- **A.2** — `ESIClient.get_route(origin, destination, preference)` with a long Valkey TTL. The POST
  shape is documented `not-cached` with no ETag, so OUR cache is the only cache; route geography is
  static, which is what makes that safe.
- **A.3** — A `system_route_jumps` table keyed `(origin, destination, preference)`, read back
  before fetching. This is the same durable-cache trick `_select_known_station_systems` already
  plays for stations, and it is what makes steady state cost zero requests.
- **A.4** — **Add `GET /route/` to the ESI drift-monitor manifest.** Non-optional per F008 §15.2:
  without it, the day CCP raises the compatibility floor is the day couriers 404 in production.
- **A.5** — Decision 2 becomes live: handle both the legacy `GET` and the newer `POST` shape, or
  pin below `2025-09-30`. The spec recommends handling both.
- **A.6** — Per-system security data is **still required**, because F008 §15.2 requires "does a
  high-sec route exist?" to be answered from the returned system list rather than from the flag.
  Task 0.1's Step 3 covers this either way.

Under this option, the stored high-sec count is an **upper bound**, and that must be stated in the
UI copy and in the field's schema description rather than left implicit.

## Appendix B — explicitly out of scope

- **"Jumps from my location."** Permanently out of this line of work per F008 §15.2. The vendored
  graph would make it possible; that is a consequence to note, not a reason to build it.
- **A user-facing route-preference picker.** Demoted to optional refinement by the survey recorded
  in F008 §15.2; per-row disclosure is the mechanism instead.
- **`security_penalty`.** Measurably non-monotonic (0 → 45 jumps, 5–20 → 11, 25+ → 45). Pin to
  default, never expose. Moot under the vendored-graph option.
- **Storing an `insecure` / prefer-low-sec count.** The spec's Decision 3 rejects it: no surface
  asks the question, and a stored column nothing reads drifts out of meaning.
