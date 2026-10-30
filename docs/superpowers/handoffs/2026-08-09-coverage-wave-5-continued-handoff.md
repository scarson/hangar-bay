<!-- ABOUTME: Handoff after Wave 5's sweep, the backend-read register (10/10) and backend-write 9/18. -->
<!-- ABOUTME: Remaining queue is backend-write 9, frontend-logic 13, frontend-components 17, then reward-per-jump. -->

# Handoff — Wave 5 in progress (written 2026-08-09)

**Supersedes** [`2026-08-09-coverage-wave-5-handoff.md`](2026-08-09-coverage-wave-5-handoff.md).
Its §3 process rules are RESTATED here (§3) because they are binding and must travel. Its §2.1
sweep instruction is DONE — do not re-run it. Its §4 seams remain accurate except where §4 here
corrects them.

## 0. Headline state

| | |
|---|---|
| `origin/dev` tip | `5b519a2` (PR #177 merge) |
| Open PRs | **#178** — the malformed-date policy, `Review — data-integrity path`, HELD FOR SAM |
| Baselines | backend **773** · frontend eslint/tsc clean, vitest **416 ×2**, e2e **146** |
| Worktree | `.claude/worktrees/coverage-wave-5-da9c1c`, provisioned (`.venv`, `node_modules`, `app/backend/src/.env`) |
| Sam's queue | C-11's third hazard · production DB allow rule `198.37.143.189/32` (ENV-8) · the dev→main release · design decisions D-a–D-k · **NEW: two decisions in §5** |

## 1. What shipped this session

- **PR #173** — the Wave 5 sweep + backend-read nice-to-haves **10/10**. Backend 733 → 753.
  Two adversarial-review rounds, four findings, all real, all fixed.
- **PR #174** — backend-write nice-to-haves **9 of 18**. Backend 753 → 772.
  **Thirteen** review findings over FIVE rounds, all real, all fixed; rounds produced
  6 → 3 → 3 → 1 → 0. Merged on the clean round.

**Two of my own tests could not fail, for structural reasons, and both are worth knowing:**

- **A test parametrized over the production constant polices nothing.** The
  preserve-on-null test read `NAME_COLUMNS_PRESERVED_ON_NULL`, so adding `"title"` to
  that set merely added a case that passed — COALESCE lets non-NULL through regardless —
  while `title` silently acquired preserve-on-null semantics. Set membership needs a
  hand-written literal. **This is the same shape as frontend-logic N-9's
  `sortableFieldsFor`, which the sweep had already identified that same day** — the
  pattern is easy to recognize in someone else's test and easy to write in your own.
- **A "nothing changed" assertion on a database that starts empty is vacuous.**
  Comparing row counts gave `0 == 0`, which an implementation that deleted every row also
  satisfies. Seed a sentinel and compare its full state; a truncate-and-reinsert keeps
  the count too.

**Three more that cost real time, from the #178 rounds:**

- **Testing the INSERT path is not testing the path production uses.** Ingestion re-sights
  the whole corpus every run, so the upsert's `ON CONFLICT` arm is where stored data
  actually meets new data — different SQL from a fresh insert. A `preserve_on_null`
  mutant survived the entire 798-test suite except the two cases written for it.
- **A mutation harness whose snapshot path fails to resolve leaves the mutant ON DISK.**
  `/tmp` resolves differently in Git Bash and Windows Python; the `finally` restore raised
  and left the mutation in production code. Snapshot BESIDE the file being mutated, assert
  the snapshot exists before mutating, and grep for the mutant afterwards.
- **`git checkout -- <file>` restores from HEAD and discards uncommitted work.** TEST-12
  says this in writing. It was done anyway while cleaning up a mutant helper, losing three
  uncommitted fixes. Tests written first are the only reason the loss was loud.

Also worth carrying: **a relational assertion is a digest.** `date_expired > date_issued`
held for a mapping that replaced every persisted expiry with one constant. Assert the
value, not a relation between values (TEST-25).

**The campaign's source of truth is still the wave table** in
[`2026-08-09-f008-remediation-test-coverage-review.md`](../../test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md)
§Remediation status, which now also carries a §Wave 5 sweep section and a §Wave 5 backend-read
section with per-row mutant tables. Read those before touching a row — they record which mutants
were killed and which overlaps are legitimate.

## 2. The queue

1. **Land PR #174** if it has not merged. Then **backend-write's remaining 9 rows** (§2.1).
2. **Frontend-logic register** — 13 rows, two of them partial (§2.2).
3. **Frontend-components register** — 17 rows (18 minus the merged duplicate, §2.2).
4. **Reward-per-jump spec + plan** — untouched this session. Groundwork is the courier spike
   ([`2026-08-01-courier-route-jumps-spike.md`](../specs/2026-08-01-courier-route-jumps-spike.md),
   161 ESI calls / 8.4 s cold) and F008 spec §15.2 (the ESI `/route/` GET→POST shape change,
   entangled with the open ESI-4 pinning decision). **Deliver spec + plan for Sam's review BEFORE
   implementing** — the route-graph data source is an architectural decision, not a coding one.

### 2.1 Backend-write, the 9 rows still open

| Row | What it needs | Notes |
|---|---|---|
| N-6 | Lock released when the locked body RAISES; `aclose()` on all paths | The freshness-swallow test asserts release after a *swallowed* failure, which is not the same thing. `aclose` is asserted nowhere |
| N-7 | `_select_known_station_systems` chunk boundary + a batch mixing a known station with one needing a fetch | `UPDATE_ID_CHUNK_SIZE` is module-level and monkeypatchable — use it, do not write 1000-row fixtures |
| N-8 | **Production change**: hoist `batch_size = 500` (`background_aggregation.py:545`) and `BATCH_SIZE = 500` (`:588`) to module level, then a TEST-11 boundary test | The row's own prescription. TDD applies — this is the only production edit in the register |
| N-9 | Chunk crossing for the `incomplete_contract_ids` and `non_ship_completed` UPDATE loops | Two separate loops that could each independently stop after chunk one; the existing boundary test covers neither |
| N-12 | Matcher `.distinct()` (two included items of the same watched type in one contract), multi-user fan-out, one-user-two-watches | Without `.distinct()` `matched` double-counts while `created` stays right — so assert BOTH numbers |
| N-13 | `_prune` sub-branches: expired-but-present, completed-but-present, `created_at == cutoff` strict-`<` boundary | The existing test uses an ABSENT contract row, which is a different arm |
| N-14 | `run_matching` happy path end-to-end (commit lands, success `log_key_event` carries matches/created/pruned) | Every current `run_matching` test stubs `_match_and_notify`/`_prune` or holds the lock |
| N-17 | a7c clean downgrade asserts the two indexes were dropped, via `pg_indexes` | Currently caught only accidentally, by the `finally` re-upgrade crashing on a duplicate name |
| N-18 | Failure BEFORE the region fetch records `failure` with 0/0 counters | `esi_client.__aenter__` or the session factory raising |

### 2.2 Frontend registers — what the sweep already settled

Do **not** re-derive these; the sweep verified them against the suite:

- **frontend-logic N-13 is PARTIAL.** Both `useDebouncedValue` halves are closed (Wave 4's
  `lib/useDebouncedValue.test.ts:67,97`). Only `raiseApiError` non-401 leaving `['auth','me']`
  untouched remains — `lib/api/client.test.ts` throws a 400 but never asserts the cache was left alone.
- **frontend-logic N-9 is PARTIAL.** `columns.test.ts:25` is still the self-referential assertion
  (expected set derived from `columnsFor`, so both sides move together). The per-segment membership
  SNAPSHOT is the remaining work.
- **frontend-logic N-11 and frontend-components N-11 are ONE gap** (`columns.tsx:141-143`,
  the `EXPIRES_COLUMN` `text-warn` fork). One test closes both. Components is therefore **17 rows**.
- **frontend-logic N-1's premise is wrong.** `hasOfferedItemFilters` is NOT a dead export —
  `FilterRail.tsx:48` calls it inside `hasActiveFilters`. The row means "missing consumer test"
  (Routine), not "delete production code" (would need Sam).
- **frontend-logic N-6 (`formatIsk(0)` → `'0'`) is a LIVE row, not theoretical.** Live ESI sampling
  during this session's review found 16/16 couriers carrying `price=0`.

### 2.3 Fixture regions — the allocation is nearly exhausted

99999977 and 99999978 were claimed this session. **Next free is 99999979, the LAST id** in the
plan's 99999960–99999979 allocation. The next wave to need one must either extend the allocation
or reuse deliberately, and should say which in its PR.

## 3. Process rules — BINDING, carried forward

### Merge authority

Agents merge `Routine` PRs themselves. Every PR body carries `## Merge classification`:
`Routine` / `Review — <domain trigger>` / `Escalate — <concern>`. Domain triggers:
schema/migrations, public API contract, auth/secrets, data-integrity paths. `Review`-classified
PRs are **held for Sam, never agent-merged**.

Merge ONLY through the mechanical gate — the check's output must gate the merge, never
`check; merge`, never `--auto` (no branch has required checks, so `--auto` merges mid-CI):

```bash
gh pr checks <n> | grep -vE "pass|skipping" && echo BLOCKED || gh pr merge <n> --merge --delete-branch
```

Always `--merge`. Never `--squash`, never `--rebase`. Conventional Commits on **every** commit.

Codegen conflicts (`openapi.json` / `schema.d.ts`) are REGENERATED, never hand-merged.

### Codex adversarial review

`codex exec -m gpt-5.6-sol -c model_reasoning_effort='"high"'`, backgrounded, prompt via
**heredoc** (`- <<'EOF'`) — never a double-quoted string. Open every prompt by declaring
`.private-journal/` and `.serena/` out-of-scope, or codex stops with NEEDS_CONTEXT.
**Re-run on every rework.** Trivial reworks (comment-only, constant tunes) may skip with the skip
recorded in the PR body (OD5 precedent — used once this session, for a doc-only correction).

**Frame findings as: "name a plausible EDIT to this code that these tests would not catch."**
This continues to earn its keep: it produced 4 real findings across 2 rounds on PR #173, and
terminated both times. The rule behind it is TEST-25's evidence test.

Tell codex **not to run `npm test` from `app/frontend/web`** — but see §4, the real trigger is
broader than that one command.

**Two refinements this session earned, both of which made the review TERMINATE.**

**Split findings into two categories in the prompt, and say only one blocks.** By round 3 the
survivor tables had begun mixing *(a) the new test fails to constrain what it CLAIMS* with
*(b) adjacent production behavior these rows never claimed to cover* — fractional-second
precision, negative dev-limit config, SQLite-only preserve semantics. Category (b) items are
real observations but they are not defects in the rows under review, and leaving them
unseparated makes a converging review look like it is still finding problems. Bound each row's
claim to its register row plus the test's own docstring, and tell codex not to promote a (b) to
an (a) by reading a docstring expansively. Round 4 then classified 1 blocker against 13 adjacent;
round 5 returned an empty (a) and the PR merged. Rounds went **6 → 3 → 3 → 1 → 0**.

**Say explicitly that an empty list is the desired outcome.** Add: *"do not manufacture a
category (a) finding to avoid an empty list; an empty list is the expected and desired outcome of
a converging review, and reporting one falsely is worse than missing one."* A reviewer with an
implicit incentive to justify its invocation will keep producing findings forever, which is the
same non-termination the old "name a wrong implementation" framing had, reached by a different
route.

**And a rule for the mutation harness itself, which lied once here.** A run reported a mutant
killed with every parametrized case failing; the edit that DEFINED the mutant's helper had
silently not applied, so the mutant referenced an undefined name and every case died on a
`NameError` rather than on behavior. Applied correctly, exactly one case failed. **Assert on the
symbols a mutation INTRODUCES, not only on the text it replaces**, and read the per-case
breakdown rather than the summary line — a broken mutant fails everything, which is
indistinguishable from a thorough test at the summary and obvious one line deeper. TEST-12's rule
applies to the harness as much as to the tests: a red run is evidence only if the mutation is the
one you intended.

### Test discipline

TDD for production code (watch RED first). Mutation-verify load-bearing tests (TEST-12) — restore
in a `finally`, check `git status` after every run. Session-scoped fixtures need footprint-free
consumers (TEST-23). Never weaken an assertion to fix a flake (TEST-2).

- **Backend**: `.venv\Scripts\pytest.exe` from `app/backend`; `python -m pdm run lint`.
- **Frontend**: ALL FIVE lanes green before any completion claim — `npx eslint .` · `npx tsc -b` ·
  `npm run test` · `npm run test:future-clock` · `npm run e2e`.

## 4. Seams and environment facts — corrections and additions

Corrections to the previous handoff:

- **The codex sandbox crash is NOT specific to `npm test`.** `CreateProcessAsUserW failed: 1920`
  fired this session on a plain `pwsh -Command` carrying multiple statements with nested quotes
  (`$c = Get-Content 'path'; $c[115..300]; $c[300..470]`). The real trigger is the command SHAPE.
  Codex recovers and retries, so it costs a call rather than a round — but do not assume warning it
  off one command makes the sandbox safe.
- **Do not pipe `codex exec` through `tail`.** The pipe buffers the entire output until exit, so
  progress is invisible for the whole run. Redirect to a file and read the file.

Still accurate, and all still bite:

- `app/backend/src/.env` is gitignored and absent from a fresh worktree; copy it from a provisioned
  one or backend tests fail at import with a pydantic validation error.
- `routeTree.gen.ts` churns on every frontend build. `git checkout --` it before staging.
- `gh pr merge --delete-branch` prints `fatal: 'dev' is already used by worktree`. **The merge
  succeeds** — verify with `gh pr view <n> --json state`, do not retry. Confirmed again this session.
- Editing a PR body from Windows mangles unless routed through a file
  (`gh pr view ... > f.md`, edit, `gh pr edit --body-file f.md`). The file route worked cleanly twice.
- `e2e/` is typechecked (`tsconfig.e2e.json`); `fast-check` is available as a devDependency.
- **D-a still looms over search tests**, and now has a concrete dependent: the two courier
  NULL-placement cases in `test_contract_filters.py` reach the joined path via `search`. If a
  correlated-EXISTS search rewrite lands, they keep passing while silently testing the SIMPLE path.
  Named in their docstring.

New, learned this session:

- **`still_listed_by_esi` is an exact `>=` against the region watermark with NO tolerance.** Fixture
  rows meant to be co-listed must share an IDENTICAL `last_seen_at`, because ingestion stamps one
  run's whole batch with one value. A helper calling `datetime.now()` per row delists every row but
  the last — it cost a debugging cycle here.
- **A mock you assert `assert_not_awaited` on must be ARMED with a working return first.** An
  unarmed `MagicMock` attribute raises `AttributeError` on that method, and even resolved it could
  never be awaited, so the assertion would hold for a reason unrelated to the guard (TEST-15).
- **Sync tests in an `asyncio`-`pytestmark`ed module emit a PytestWarning.** Test output must be
  pristine, so make them `async def` even with nothing to await.

## 5. Open for Sam

**Both decisions from the first brief are now IMPLEMENTED.** The two items below that used
to be open are resolved; what remains for Sam is the merge decision on #178 and the
alerting gap.

- **Decision 1 — malformed-date blast radius: DONE, awaiting merge.** PR **#178**, held
  because it changes the ingestion write path. A malformed REQUIRED date skips that
  contract (counted on `hangar_bay_ingest_contracts_skipped_total{reason="malformed_date"}`,
  logged with contract id and field); a malformed OPTIONAL date stores NULL; and a run
  that fetched contracts but stored NONE records `failure` rather than freshening the
  staleness clock over an empty write. Backend 775 → 798, ten review rounds, fourteen
  findings, all real, ending CONVERGED.
- **Decision 2 — the `"a contract"` label: DONE and MERGED** (PR #177). The fallback was
  not dead code, it was the symptom of the last hand-listed copy of a partition
  `ITEM_BEARING_CONTRACT_TYPES` derives. `set(_SHIP_TYPE_LABELS)` is now asserted equal to
  it, so a sixth `ContractType` fails a test naming the type missing its label.
- **STILL OPEN and Sam's alone: there is no alert rule.** The metric exists and the
  success gauge already did; whether to alert on either lives in Grafana Cloud, outside
  this repo. #178 bounds the damage of a malformed date and makes a wholesale rejection
  record `failure` — it does not make anyone AWARE. That was the larger half of the
  original finding and it is untouched.

### Previously open, unchanged

Carried forward, unchanged: **C-11's third mocked-behavior hazard** (options in the coverage
report's Wave 3 residual section), the production DB allow rule, the dev→main release, and design
decisions D-a–D-k.

**New this session — two decisions:**

1. **A malformed ESI date discards the WHOLE AGGREGATION RUN.** `_parse_esi_datetime` calls
   `fromisoformat` with no guard, from inside the list comprehension that builds rows for the
   entire batch — and `run_aggregation` concatenates every page of every configured region before
   calling `_process_contracts` **once**. So one bad date string anywhere in the corpus discards
   every contract fetched that cycle, not merely one region page. (The first draft of this handoff
   said "one region page"; the review corrected it, and the corrected version is worse.) This is
   the hazard shape a NOT NULL `price` already demonstrated in production (TEST-22 / FASTAPI-3).
   Now pinned as characterization (`test_a_malformed_esi_date_takes_the_whole_batch_down_with_it`)
   so any change is deliberate. Options: abort the run (today), skip the offending contract, or
   persist a NULL date. Two of the three change what the site shows, so this is Sam's call.
2. **backend-write N-11's `"a contract"` fallback label is unreachable** behind the matcher's type
   gate. Either it is defense-in-depth worth a direct unit call, or it is dead and should be
   recorded as such. Not a gap — a decision.

## 6. What I would tell my successor in one paragraph

The sweep is done and its results are in the report — trust them, do not re-derive. The single most
valuable habit this session was **verifying the premise of a claim before acting on it, whoever
made it**. Across two PRs the adversarial reviewer produced ten findings; eight were real and two
were wrong, and one of the wrong ones (about what ESI sends on which contract type) got written
into a persistent artifact as fact before a later round sampled the live API and falsified it.
My own prose was wrong three times — the blast radius of a malformed date, the implicit-coverage
counts (4 and 1, actually 53 and 28, because I read them off a `-k`-filtered run), and the claim
that a set-parametrized test covers a fifth member. Register prose, reviewer prose, and your own
prose are all evidence rather than ground truth.

Two corollaries that actually save time. **When a claim is empirical — about upstream payloads,
about what the writer populates, about what a fixture can reach — sample it** rather than reasoning
from a schema description; ESI's field descriptions state intent, and its payloads carry zero
placeholders where the description implies absence. **And when you catch a bad-test pattern in
someone else's code, expect to write it yourself within the day**: the self-referential set
assertion was identified in the sweep at breakfast and committed in my own test by dinner.

## 7. Continuation prompt (paste-ready)

> Hangar Bay: read `docs/superpowers/handoffs/2026-08-09-coverage-wave-5-continued-handoff.md`
> first — its §3 process rules are binding (Routine PRs are agent-merged on a mechanically-gated
> green check; codex adversarial review framed as "name a plausible EDIT these tests would not
> catch"; TDD + mutation verification; five frontend lanes). State: `origin/dev` at `5b519a2`,
> backend **773**, frontend 416×2 + 146 e2e. Wave 5's sweep is DONE — its results are in the
> coverage report's §Wave 5 sweep; do not re-run it.
>
> Queue: **backend-write's remaining 9 rows** (§2.1 names each and
> what it needs — N-8 is the only production edit, a hoist of two function-local `500` literals).
> Then **frontend-logic 13** and **frontend-components 17** — §2.2 records which rows the sweep
> already narrowed, including that logic N-11 and components N-11 are ONE gap and that
> `hasOfferedItemFilters` is not a dead export. Then the **reward-per-jump spec + plan**, delivered
> for Sam's review BEFORE implementing.
>
> Read `docs/pitfalls/testing-pitfalls.md` TEST-12, TEST-15, TEST-18, TEST-24 and TEST-25 before
> writing tests. Work from `.claude/worktrees/coverage-wave-5-da9c1c` (provisioned). §4 has the
> environment gotchas — the ones that bite first are the gitignored `app/backend/src/.env`,
> `routeTree.gen.ts` churn, the exact-`>=` watermark that requires co-listed fixture rows to share
> one `last_seen_at`, and arming a mock before asserting `assert_not_awaited` on it. Fixture regions
> are claimed through 99999978; **99999979 is the last free id in the allocation**.
>
> Only Sam decides: the malformed-date blast radius, N-11's unreachable fallback label, C-11's third
> hazard, the production DB allow rule, the dev→main release, and D-a–D-k.
