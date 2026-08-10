<!-- ABOUTME: Handoff after Wave 5's sweep, backend-read 10/10, backend-write 9/18, and both of Sam's -->
<!-- ABOUTME: open decisions implemented and merged. Queue: backend-write 9, frontend 30, reward-per-jump. -->

# Handoff — Wave 5 mid-campaign, both decisions closed (written 2026-08-10)

**Supersedes** [`2026-08-09-coverage-wave-5-continued-handoff.md`](2026-08-09-coverage-wave-5-continued-handoff.md).
Its §3 process rules are RESTATED here (§3) because they are binding and must travel. Its §2.1
sweep instruction is DONE and MUST NOT be re-run — the sweep's results live in the coverage report.

## 0. Headline state

| | |
|---|---|
| `origin/dev` tip | `31b6187` (PR #178 merge) |
| Open PRs | **none** |
| Baselines | backend **799** · frontend eslint/tsc clean, vitest **416 ×2**, e2e **146** |
| Worktree | `.claude/worktrees/coverage-wave-5-da9c1c`, provisioned (`.venv`, `node_modules`, `app/backend/src/.env`) |
| Sam's queue | **the alerting gap (§5)** · C-11's third hazard · production DB allow rule `198.37.143.189/32` (ENV-8) · the dev→main release · design decisions D-a–D-k |

## 1. What shipped this session

Six PRs, all merged. Pointers, not narrative:

- **PR #173** — the Wave 5 sweep + backend-read nice-to-haves **10/10**. Backend 733 → 753.
- **PR #174** — backend-write nice-to-haves **9 of 18**. Backend 753 → 772.
- **PR #175 / #176 / #179** — handoff and its syncs.
- **PR #177** — Decision 2, the label-table drift guard (`Routine`). Backend → 773.
- **PR #178** — Decision 1, the per-field malformed-date policy (`Review`, Sam-merged). Backend → **799**.

**The campaign's source of truth is the wave table** in
[`2026-08-09-f008-remediation-test-coverage-review.md`](../../test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md)
§Remediation status. That file now also carries: §Wave 5 sweep (row-by-row strike evidence), §Wave 5
backend-read (per-row mutant table), **§Wave 5 — the two decisions Sam took** and **§Wave 5 — what
ten review rounds cost and bought**. Read those before touching a row.

**Four pitfalls entries were added or hardened** and are the durable form of this session's lessons —
see §6. Do not re-derive them from this handoff; the pitfalls file is where they live.

## 2. The queue

1. **Backend-write's remaining 9 rows** (§2.1).
2. **Frontend-logic register** — 13 rows, two partial (§2.2).
3. **Frontend-components register** — 17 rows (18 minus the merged duplicate, §2.2).
4. **Reward-per-jump spec + plan** — untouched across two sessions now. Groundwork is the courier
   spike ([`2026-08-01-courier-route-jumps-spike.md`](../specs/2026-08-01-courier-route-jumps-spike.md),
   161 ESI calls / 8.4 s cold) and F008 spec §15.2 (the ESI `/route/` GET→POST shape change,
   entangled with the open ESI-4 pinning decision). **Deliver spec + plan for Sam's review BEFORE
   implementing** — the route-graph data source is an architectural decision, not a coding one.

### 2.1 Backend-write, the 9 rows still open

| Row | What it needs | Notes |
|---|---|---|
| N-6 | Lock released when the locked body RAISES; `aclose()` on all paths | The freshness-swallow test asserts release after a *swallowed* failure, which is not the same thing. `aclose` is asserted nowhere |
| N-7 | `_select_known_station_systems` chunk boundary + a batch mixing a known station with one needing a fetch | `UPDATE_ID_CHUNK_SIZE` is module-level and monkeypatchable — use it, do not write 1000-row fixtures |
| N-8 | **Production change**: hoist `batch_size = 500` and `BATCH_SIZE = 500` (both in `_process_contracts`) to module level, then a TEST-11 boundary test | The row's own prescription. The only production edit left in this register; TDD applies |
| N-9 | Chunk crossing for the `incomplete_contract_ids` and `non_ship_completed` UPDATE loops | Two separate loops that could each stop after chunk one; the existing boundary test covers neither |
| N-12 | Matcher `.distinct()` (two included items of the same watched type in one contract), multi-user fan-out, one-user-two-watches | Without `.distinct()` `matched` double-counts while `created` stays right — assert BOTH numbers |
| N-13 | `_prune` sub-branches: expired-but-present, completed-but-present, `created_at == cutoff` strict-`<` boundary | The existing test uses an ABSENT contract row, a different arm |
| N-14 | `run_matching` happy path end-to-end (commit lands, success `log_key_event` carries matches/created/pruned) | Every current `run_matching` test stubs `_match_and_notify`/`_prune` or holds the lock |
| N-17 | a7c clean downgrade asserts the two indexes were dropped, via `pg_indexes` | Currently caught only accidentally, by the `finally` re-upgrade crashing on a duplicate name |
| N-18 | Failure BEFORE the region fetch records `failure` with 0/0 counters | `esi_client.__aenter__` or the session factory raising |

**N-14 has a new prerequisite this session created.** `run_matching` tests that assert an OUTCOME
must bind `AsyncSessionLocal` to the test database AND request the `db_session` fixture (which is
what creates the schema). Without both, the run dies on `relation "..." does not exist`, records a
failure, and an outcome-is-failure assertion passes for a reason unrelated to the test. See §4.

### 2.2 Frontend registers — what the sweep already settled

Do **not** re-derive these; the sweep verified each against the suite:

- **frontend-logic N-13 is PARTIAL.** Both `useDebouncedValue` halves are closed (Wave 4's
  `lib/useDebouncedValue.test.ts:67,97`). Only `raiseApiError` non-401 leaving `['auth','me']`
  untouched remains — `lib/api/client.test.ts` throws a 400 but never asserts the cache was left alone.
- **frontend-logic N-9 is PARTIAL.** `columns.test.ts:25` is still the self-referential assertion
  (expected set derived from `columnsFor`, so both sides move together — this is now **TEST-27**).
  The per-segment membership SNAPSHOT is the remaining work.
- **frontend-logic N-11 and frontend-components N-11 are ONE gap** (`columns.tsx:141-143`, the
  `EXPIRES_COLUMN` `text-warn` fork). One test closes both. Components is therefore **17 rows**.
- **frontend-logic N-1's premise is wrong.** `hasOfferedItemFilters` is NOT a dead export —
  `FilterRail.tsx:48` calls it inside `hasActiveFilters`. The row means "missing consumer test"
  (Routine), not "delete production code" (would need Sam).
- **frontend-logic N-6 (`formatIsk(0)` → `'0'`) is a LIVE row.** Live ESI sampling during review
  found 16/16 couriers carrying `price=0`.

### 2.3 Fixture regions — the allocation is exhausted after one more

99999977 and 99999978 are claimed. **Next free is 99999979, the LAST id** in the plan's
99999960–99999979 allocation. The next wave to need one must either extend the allocation or reuse
deliberately, and MUST say which in its PR.

## 3. Process rules — BINDING, carried forward

### Merge authority

Agents merge `Routine` PRs themselves. Every PR body carries `## Merge classification`:
`Routine` / `Review — <domain trigger>` / `Escalate — <concern>`. Domain triggers:
schema/migrations, public API contract, auth/secrets, data-integrity paths. `Review`-classified
PRs are **held for Sam, never agent-merged** — PR #178 was the worked example this session.

Merge ONLY through the mechanical gate — the check's output must gate the merge, never
`check; merge`, never `--auto` (no branch has required checks, so `--auto` merges mid-CI):

```bash
gh pr checks <n> | grep -vE "pass|skipping" && echo BLOCKED || gh pr merge <n> --merge --delete-branch
```

Always `--merge`. Never `--squash`, never `--rebase` — per-commit history is permanent and
bisect-visible, so Conventional Commits applies to **every commit**, not just the PR title.

Conflicts: rebase in the worktree, `git push --force-with-lease`. Codegen conflicts
(`openapi.json` / `schema.d.ts`) are REGENERATED (`pdm run export-openapi` →
`npm run generate:api`), never hand-merged.

### Codex adversarial review

`codex exec -m gpt-5.6-sol -c model_reasoning_effort='"high"'`, backgrounded, prompt via
**heredoc** (`- <<'EOF'`) — never a double-quoted string (backticks execute). Open every prompt by
declaring `.private-journal/` and `.serena/` out-of-scope agent tooling, or codex stops with
NEEDS_CONTEXT. **Re-run on every rework.** Trivial reworks (comment-only, constant tunes) may skip
with the skip recorded in the PR body, per the OD5 precedent.

**Frame findings as: "name a plausible EDIT to this code that these tests would not catch."**
The old framing — "name a wrong implementation that passes" — cannot terminate. The rule behind it
is TEST-25's evidence test: *a mutant is evidence only if it carries no information that could only
have come from the test suite.*

**The edit framing alone is NOT sufficient to terminate. Two further rules, learned on PR #178's
ten rounds, MUST be in the prompt:**

1. **Split findings into two categories and say only one blocks.** `(a)` a new test failing to
   constrain what it CLAIMS — blocks merge. `(b)` adjacent production behavior the rows never
   claimed to cover — does not block, list separately. **Bound each row's claim** to its register
   row plus the test's own docstring, and tell the reviewer not to promote a (b) to an (a) by
   reading a docstring expansively. Without this, survivor tables drift into unbounded scope and
   the review widens forever while looking productive.
2. **State that an empty list is the DESIRED outcome.** Verbatim: *"do not manufacture a category
   (a) finding to avoid an empty list; an empty list is the expected and desired outcome of a
   converging review, and reporting one falsely is worse than missing one."* A reviewer with an
   implicit incentive to justify its invocation keeps producing findings — the same
   non-termination the old framing had, reached by a different route.
3. On a long-running review, **demand an explicit CONVERGED / NOT CONVERGED verdict** and, if not
   converged, require the reviewer to justify why its finding falls INSIDE the authorized claim
   rather than beside it.

Also tell codex: **do not run `npm test` from `app/frontend/web`** — but see §4, the sandbox
failure is broader than that one command. And **do not pipe `codex exec` through `tail`**: the pipe
buffers the whole output until exit, so progress is invisible for the entire run. Redirect to a
file and read the file.

### Test discipline

TDD for production code (watch RED first, and confirm the RED is for the RIGHT reason — see §4).
Mutation-verify load-bearing tests (**TEST-12**, whose harness mechanics were hardened this session
and MUST be read before writing a harness). Session-scoped fixtures need footprint-free consumers
with `finally` restoration (TEST-23). Never weaken an assertion to fix a flake (TEST-2). Alembic
downgrade tests name explicit target revisions.

- **Backend**: `.venv\Scripts\pytest.exe` from `app/backend`; `DATABASE_URL_TESTS` and the rest come
  from `app/backend/src/.env` (gitignored — §4). `python -m pdm run lint`.
- **Frontend**: ALL FIVE lanes green before any completion claim — `npx eslint .` · `npx tsc -b` ·
  `npm run test` · `npm run test:future-clock` · `npm run e2e`.

## 4. Seams and environment facts a fresh agent will hit

Carried forward and still true:

- **`app/backend/src/.env` is gitignored and does NOT exist in a fresh worktree.** Backend tests
  fail at import with a pydantic `DATABASE_URL`/`CACHE_URL` validation error until it is copied from
  a provisioned worktree. First thing that breaks in a new worktree.
- **`routeTree.gen.ts` churns on every frontend build.** `git checkout --` it before staging; never
  commit it. Same for `package-lock.json` unless a dependency change is deliberate.
- **`gh pr merge --delete-branch` prints `fatal: 'dev' is already used by worktree`.** That is its
  local post-merge checkout failing because the main worktree holds `dev`. **The merge itself
  succeeds** — verify with `gh pr view <n> --json state`, don't retry. Seen every merge this session.
- **Editing a PR body from Windows mangles unless routed through a file.** `gh pr view ... > f.md`,
  edit, `gh pr edit --body-file f.md`. Note `/tmp` in Git Bash and `/tmp` in Windows Python are
  DIFFERENT directories — write the file to an explicit Windows path when Python will read it back.
- **`e2e/` is typechecked** (`tsconfig.e2e.json`); **`fast-check` is a devDependency** for
  property-based tests.
- **`npx tsx` cannot resolve the project's `.tsx` modules.** To probe runtime values, write a
  throwaway `__probe.test.ts`, have it `writeFileSync` its output, run vitest, read, delete.
- **Treat register prose as evidence, not ground truth.** Three rows have been wrong across this
  campaign. And the same applies to REVIEWER prose — see §6.
- **D-a still looms over search tests.** Concretely: the two courier NULL-placement cases in
  `test_contract_filters.py` reach the joined path via `search`. A correlated-EXISTS search rewrite
  would leave them passing while silently testing the SIMPLE path. Named in their docstring.

New this session:

- **The codex sandbox crash is NOT specific to `npm test`.** `CreateProcessAsUserW failed: 1920`
  fired on a plain `pwsh -Command` carrying multiple statements with nested quotes. The trigger is
  the command SHAPE. Codex retries, so it costs a call rather than a round.
- **`still_listed_by_esi` is an exact `>=` against the region watermark with NO tolerance.** Fixture
  rows meant to be co-listed MUST share an IDENTICAL `last_seen_at`, because ingestion stamps one
  run's whole batch with one value. A helper calling `datetime.now()` per row delists every row but
  the last.
- **A mock you assert `assert_not_awaited` on must be ARMED with a working return first.** An
  unarmed `MagicMock` attribute raises `AttributeError` on that method, and even resolved could
  never be awaited — so the assertion would hold for a reason unrelated to the guard (TEST-15).
- **A test asserting `run_aggregation`'s OUTCOME needs BOTH** an `AsyncSessionLocal` bind to
  `TEST_DATABASE_URL` **and** the `db_session` fixture (which creates the schema). With neither or
  only one, the run dies on `relation "contracts" does not exist` and records a failure — so an
  outcome-is-failure assertion passes for an unrelated reason. Mine did, until it was checked.
  **Corollary: when a TDD test goes GREEN immediately, or RED on the first try, verify the REASON
  before believing it.**
- **Sync tests in an `asyncio`-`pytestmark`ed module emit a PytestWarning.** Test output must be
  pristine, so make them `async def` even with nothing to await.

## 5. Open for Sam

**NEW and unresolved — there is no alert rule.** PR #178 bounds the damage of a malformed ESI date
and makes a wholesale rejection record `failure` instead of `success`. It does **not** make anyone
AWARE. `/ready` reports `last_ingest_outcome` and `data_stale` but deliberately returns 200
(observability-spec §2.5), the frontend has no staleness surface at all, and no alert rule on
`hangar_bay_last_ingest_success_timestamp` or the new
`hangar_bay_ingest_contracts_skipped_total{reason="malformed_date"}` exists in this repo. Alerting
lives in Grafana Cloud, outside version control. This was the larger half of the original finding
and it is untouched.

Carried forward, unchanged: **C-11's third mocked-behavior hazard** (options in the coverage
report's Wave 3 residual section — Wave 3 stands at 10 of 11 until one is chosen), the production DB
allow rule `198.37.143.189/32` (ENV-8), the dev→main release, and design decisions D-a–D-k.

## 6. What this session put in the pitfalls file, and why it matters more than this doc

Read [`docs/pitfalls/testing-pitfalls.md`](../../pitfalls/testing-pitfalls.md) — **TEST-26, TEST-27,
TEST-28 are new, and TEST-12 was hardened.** Summarised only enough to decide whether to read them:

- **TEST-26** — testing the INSERT path is not testing the path production uses, when the writer is
  an upsert. A `preserve_on_null` mutant survived 796 of 798 tests.
- **TEST-27** — an expectation DERIVED from the thing it constrains agrees with every value that
  thing can take. **This bit twice in one day, in the same shape, hours apart**: the sweep flagged
  it in someone else's test at breakfast; it was written into a new test by dinner. Recognizing the
  pattern confers no immunity.
- **TEST-28** — one behavior reached by two control-flow routes gets instrumented on one of them.
  Covers the metric-label projection case (`counter.labels(x)._value` is a projection; a mutant
  incrementing a different label is invisible to it).
- **TEST-12 hardening** — the harness itself is the part that fails: an unresolvable snapshot path
  leaves the mutant ON DISK when the restore raises; a mutation that INTRODUCES a symbol needs an
  assertion the symbol landed, or a broken mutant fails every case with `NameError` and reads as a
  kill; and `git checkout -- <file>` restores from HEAD and discards uncommitted work.

**One methodology lesson has no pitfalls home and lives here:** across three PRs the adversarial
reviewer produced ~19 findings, of which **two were wrong** — and one wrong one (a claim about which
fields ESI sends on which contract type) was written into a persistent artifact as fact before a
later round sampled the live API and falsified it. The mutant behind a finding was always
reproduced before fixing; the DOMAIN PREMISE behind a finding was not. **Reviewer prose is evidence,
not ground truth, on exactly the terms this project already sets for register prose — and an
empirical claim about upstream payloads must be SAMPLED, not reasoned about from a schema
description.** ESI's field descriptions state intent; its payloads carry zero placeholders where the
description implies absence.

## 7. Continuation prompt (paste-ready)

> Hangar Bay: read `docs/superpowers/handoffs/2026-08-10-coverage-wave-5-decisions-handoff.md`
> first — its §3 process rules are binding. State: `origin/dev` at `31b6187`, **ZERO open PRs**,
> backend **799**, frontend eslint/tsc clean + vitest 416×2 + e2e 146. Wave 5's sweep is DONE and
> MUST NOT be re-run; its results are in the coverage report's §Wave 5 sweep. Both of Sam's open
> decisions shipped (PRs #177, #178).
>
> Queue: **backend-write's remaining 9 rows** — §2.1 names each and what it needs; **N-8 is the only
> production edit** (hoist two function-local `500` literals, TDD). Then **frontend-logic 13** and
> **frontend-components 17** — §2.2 records what the sweep already settled, including that
> frontend-logic N-11 and frontend-components N-11 are ONE gap, that `hasOfferedItemFilters` is live
> code rather than a dead export, and that `formatIsk(0)` is a live row. Then the **reward-per-jump
> spec + plan**, delivered for Sam's review BEFORE implementing — the route-graph data source is an
> architectural decision.
>
> Process rules that are binding, not optional: Routine PRs are agent-merged ONLY through the
> mechanical gate (`gh pr checks <n> | grep -vE "pass|skipping" && echo BLOCKED || gh pr merge <n>
> --merge --delete-branch`); `Review`-classified PRs are held for Sam and never agent-merged; always
> `--merge`, never `--squash`/`--rebase`, Conventional Commits on every commit. Codex adversarial
> review before merge and **re-run on every non-trivial rework**: `codex exec -m gpt-5.6-sol -c
> model_reasoning_effort='"high"'`, backgrounded, prompt via heredoc, declaring `.private-journal/`
> and `.serena/` out of scope. Frame findings as **"name a plausible EDIT to this code that these
> tests would not catch"** — and include BOTH termination rules from §3, because the framing alone
> does not converge: split findings into (a) fails-to-constrain-what-it-claims, which blocks, versus
> (b) adjacent-and-never-claimed, which does not, bounding each claim to its register row plus the
> test's docstring; and state explicitly that an empty list is the DESIRED outcome and a manufactured
> finding is worse than a missed one. Do not pipe `codex exec` through `tail`. TDD with RED watched
> first — and verify the RED is for the RIGHT reason. Mutation-verify load-bearing tests. Five
> frontend lanes green before any completion claim.
>
> Read `docs/pitfalls/testing-pitfalls.md` **TEST-12 (hardened), TEST-15, TEST-18, TEST-24, TEST-25,
> TEST-26, TEST-27, TEST-28** before writing tests — 26/27/28 and the TEST-12 hardening were all paid
> for on 2026-08-09/10. Work from `.claude/worktrees/coverage-wave-5-da9c1c` (provisioned). §4 has
> the environment gotchas; the ones that bite first are the gitignored `app/backend/src/.env`,
> `routeTree.gen.ts` churn, the exact-`>=` watermark that requires co-listed fixture rows to share
> ONE `last_seen_at`, arming a mock before asserting `assert_not_awaited` on it, and the fact that a
> `run_aggregation` outcome test needs BOTH an `AsyncSessionLocal` bind and the `db_session` fixture
> or it passes for the wrong reason. Fixture regions are claimed through 99999978; **99999979 is the
> last free id in the allocation** — say which way you go if you need one.
>
> Only Sam decides: **the alerting gap** (there is still no alert rule on ingest freshness or the new
> skip counter — §5), C-11's third hazard, the production DB allow rule, the dev→main release, and
> D-a–D-k.

## Appendix — adversarial review of this handoff

**Round 1 — naive fresh agent (3 applied).** Spelled out that the sweep is done and must not be
re-run (a fresh agent reading a coverage queue naturally starts sweeping); added the explicit
row-lists to §2.1 rather than pointing at the register; expanded the merge gate inline instead of
referencing it.

**Round 2 — recency-bias audit (2 applied).** The session's last hours were PR #178's review rounds,
so earlier material was under-weighted: restored the sweep's frontend findings to §2.2 in full
(they were established at breakfast and are the single largest saving for the next wave), and the
fixture-region exhaustion note, which was decided mid-session and referenced nowhere since.

**Round 3 — seam auditor (2 applied).** Two seams: N-14's new prerequisite (the `AsyncSessionLocal`
+ `db_session` pairing discovered while testing run outcomes directly blocks N-14, which is a
`run_matching` end-to-end test — the same shape), and D-a's now-concrete dependent (the two courier
NULL-placement cases), which was previously stated as a general worry.

**Round 4 — operational guardrails auditor (3 applied).** The two codex termination rules were the
session's most valuable process output and existed only in prompt text; promoted to §3 as numbered
binding rules and repeated in the continuation prompt. Added the `/tmp`-means-two-things warning to
the PR-body-editing note, since that exact mismatch stranded a mutant on disk.

**Round 5 — loss-averse audit (2 applied).** The "reviewer prose is evidence, not ground truth"
lesson had no pitfalls home and would have died with the transcript — given its own subsection in
§6. Added the corollary that a TDD RED/GREEN must be verified for its REASON, which cost real time
twice.

**Round 6 — "would the next agent trust the wrong thing?" (session-specific; 3 applied).** Chosen
because this session's defining feature was that *carefully written, passing, reviewed tests were
wrong* — and a handoff that reports coverage counts without that caveat invites false confidence.
Verified every count in this doc against a real run rather than against my own earlier messages
(backend 799, not the 798 my last status said — #177 and #178 branched independently off dev and
their tests summed only after both merged). Reframed §6 so the pitfalls file is named as the
authority and this doc explicitly as the summary. Added "confirm the RED is for the right reason"
to §3's TDD line, not just §4, because §3 is what gets read.

**Round 7 — decision-provenance audit (session-specific; 2 applied).** Chosen because two of Sam's
decisions were implemented this session and a future reader will need to know not just WHAT was
decided but what the decision rested on — otherwise the first person to find the skip path will
"fix" it back. Moved the full decision rationale into the coverage report (where the campaign's
record lives) rather than this handoff, and left §5 carrying only what is still OPEN. Made the
alerting gap the FIRST item in Sam's queue in §0, since it is the one thing the merged code does
not address.

**Round 8 — top-to-bottom coherence pass (0 findings).** Full clean pass after rounds 1–7.
