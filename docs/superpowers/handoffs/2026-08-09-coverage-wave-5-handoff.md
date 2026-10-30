<!-- ABOUTME: Handoff after coverage waves 3-4 shipped (PRs #169/#170/#171). Wave 5 (60 nice-to-haves) -->
<!-- ABOUTME: is the queue, then the reward-per-jump spec+plan. Carries merge authority + the review protocol. -->

# Handoff — coverage Wave 5 is the queue (written 2026-08-09)

**Supersedes** [`2026-08-09-coverage-campaign-handoff.md`](2026-08-09-coverage-campaign-handoff.md).
Its §3 process rules are RESTATED here (§3) because they are binding and must travel; its §2 queue
is now history — waves 3 and 4 are merged. Its §4 seams remain accurate and are not repeated
except where this session changed them.

## 0. Headline state

| | |
|---|---|
| `origin/dev` tip | `13dd67a` (PR #171 merge) |
| Open PRs | **none** |
| Baselines | backend **733** · frontend eslint/tsc clean, vitest **416 ×2 lanes**, e2e **146** · lint clean |
| Worktree | `.claude/worktrees/hangar-bay-coverage-handoff-6f067d`, fully provisioned (backend `.venv`, frontend `node_modules`, `app/backend/src/.env`) |
| Sam's queue | C-11's third hazard (§5) · production DB allow rule `198.37.143.189/32` (ENV-8) · the dev→main release · bug-hunt design decisions D-a–D-k |

## 1. What shipped this session

Three PRs, all agent-merged on verified-green CI. Pointers, not narrative:

- **PR #169** — coverage Wave 3, backend write-path correctness (11 rows) + O2's partition pin.
  Backend 705 → 733.
- **PR #170** — Wave 4 part 1: frontend-logic register 28/28, all three queued e2e pins
  (O1a/O1b/null-price), components C1–C4. **Plus a typecheck lane for `e2e/` that had never
  existed** (§4).
- **PR #171** — Wave 4 part 2: components C5–C10. vitest 388 → 416, e2e 144 → 146.

**The campaign's source of truth is the wave table** in
[`2026-08-09-f008-remediation-test-coverage-review.md`](../../test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md)
§Remediation status. It is current as of this handoff. The four per-file registers beside it are
the work orders.

**New pitfalls** (all committed): **TEST-24**, **TEST-25** + its corollary, and a hardening of
**TEST-12**. §6 explains why each exists — read them before writing Wave 5 tests, they were all
paid for this session.

## 2. The queue

1. **Coverage Wave 5** — the 60 nice-to-haves. **Sweep before writing anything** (§2.1).
2. **Reward-per-jump spec + plan** — synthesis, not research. Groundwork is the courier spike
   ([`2026-08-01-courier-route-jumps-spike.md`](../specs/2026-08-01-courier-route-jumps-spike.md),
   161 ESI calls / 8.4 s cold) and F008 spec §15.2 (the ESI `/route/` GET→POST shape change,
   entangled with the open ESI-4 pinning decision). **Deliver spec + plan for Sam's review BEFORE
   implementing** — the route-graph data source is an architectural decision, not a coding one.

### 2.1 Wave 5's first task is a sweep, not a test

Waves 3–4 closed several nice-to-haves incidentally. Re-testing them is the main way this wave
wastes effort. The wave table's Wave 5 row names the ones already known-closed (backend-write
N-10 and half of N-11; frontend-logic N-9 is now PARTIAL — the exact mutant it names is killed,
only its per-segment membership snapshot remains). **Verify each against the current suite, then
strike it and record the strike.** Intentional skips go in the report's Remediation status, not
into a silent drop.

Row counts by register: backend-read 10 · backend-write 19 · frontend-logic 13 ·
frontend-components 18 = 60.

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

Always `--merge`. Never `--squash`, never `--rebase` — per-commit history is permanent and
bisect-visible, so Conventional Commits applies to **every commit**, not just the PR title.

Conflicts: rebase in the worktree, `git push --force-with-lease`. Codegen conflicts
(`openapi.json` / `schema.d.ts`) are REGENERATED (`pdm run export-openapi` →
`npm run generate:api`), never hand-merged.

### Codex adversarial review

Meaningful PRs get a review before merge:
`codex exec -m gpt-5.6-sol -c model_reasoning_effort='"high"'`, backgrounded, prompt via
**heredoc** (`- <<'EOF'`) — never a double-quoted string (backticks execute). Open every prompt
by declaring `.private-journal/` and `.serena/` out-of-scope agent tooling, or codex stops with
NEEDS_CONTEXT. **Re-run on every rework.** Trivial reworks (comment-only, constant tunes) may
skip with the skip recorded in the PR body, per the OD5 precedent.

**Frame findings as: "name a plausible EDIT to this code that these tests would not catch."**
This is the single most valuable process change of this session and it MUST carry forward. The
old framing — "name a wrong implementation that passes" — cannot terminate: for any finite test
there is an implementation checking exactly the positions the fixtures vary, so the reviewer can
always produce another. On PR #170 that consumed four rounds and produced zero defects. With the
edit framing, PR #171's rounds produced three findings, all real, all fixed in one commit each.
The rule behind it is TEST-25's evidence test (§6).

Also tell codex, in the prompt: **do not run `npm test` from `app/frontend/web`** — its Windows
sandbox dies on that with a `CreateProcessAsUserW ... 1920` spawn error and the round is lost.
Give it the lane results instead; it will rely on them.

### Test discipline

TDD for production code (watch RED first). Mutation-verify load-bearing tests (TEST-12) — and
read the hardened §revert mechanics first, this session left a mutant in the tree. Session-scoped
fixtures need footprint-free consumers with `finally` restoration (TEST-23). Never weaken an
assertion to fix a flake (TEST-2). Alembic downgrade tests name explicit target revisions.

- **Backend**: `.venv\Scripts\pytest.exe` from `app/backend`; `DATABASE_URL_TESTS` and the rest
  come from `app/backend/src/.env` (gitignored — §4). `python -m pdm run lint`.
- **Frontend**: ALL FIVE lanes green before any completion claim — `npx eslint .` · `npx tsc -b` ·
  `npm run test` · `npm run test:future-clock` · `npm run e2e`.
- Fixture regions claimed through **99999976**; next free **99999977** (unchanged this session —
  no new fixture regions were claimed).

## 4. Seams and environment facts a fresh agent will hit

- **`e2e/` is now typechecked.** `tsconfig.e2e.json` exists and is referenced from
  `tsconfig.json`; before PR #170 `tsc -b` covered only `src`, so the whole fixture lane had no
  type lane. Consequence for Wave 5: `tsc -b` now fails on e2e type errors it used to ignore, and
  it catches spec mistakes (wrong helper arity, nullable arithmetic) that vitest runs green.
- **`fast-check` is a devDependency** (added PR #170) for the property-based `sameSearch` test.
  Available for any Wave 5 predicate that warrants it.
- **`app/backend/src/.env` is gitignored and does NOT exist in a fresh worktree.** Backend tests
  fail at import with a pydantic `DATABASE_URL`/`CACHE_URL` validation error until it is copied
  from a provisioned worktree. This is the first thing that breaks in a new worktree.
- **`routeTree.gen.ts` churns on every frontend build.** `git checkout --` it before staging;
  never commit it. Same for `package-lock.json` unless a dependency change is deliberate.
- **`gh pr merge --delete-branch` prints `fatal: 'dev' is already used by worktree`.** That is
  its local post-merge checkout failing because the main worktree holds `dev`. **The merge itself
  succeeds** — verify with `gh pr view <n> --json state`, don't retry.
- **Editing a PR body from Windows mangles or silently no-ops.** `gh pr view --json body -q .body`
  piped through Python transcodes to mojibake, and `print()` of non-ASCII dies on cp1252. Route
  through a file (`gh pr view ... > f.md`, edit, `gh pr edit --body-file f.md`) and prefix Python
  with `PYTHONIOENCODING=utf-8`. Two body edits silently did nothing before this was diagnosed.
- **`npx tsx` cannot resolve the project's `.tsx` modules.** To probe runtime values from source,
  write a throwaway `__probe.test.ts`, have it `writeFileSync` its output, run vitest, read the
  file, delete the probe.
- **The backend register has an erratum.** `subagent-backend-write-findings.md` C-9 says the a7c
  downgrade drops indexes BEFORE the narrowing rewrite. It does the reverse, which is the correct
  inverse of the upgrade. Recorded in the coverage report's Wave 3 erratum section; the test pins
  what the migration actually emits. **Treat register prose as evidence, not as ground truth** —
  two rows were wrong this session (this one, and the two frontend `DEFAULT_DIRECTION` rows that
  turned out to be parser-unreachable).
- **D-a still looms over search tests.** If Sam takes the offered-only EXISTS semantics decision,
  `_needs_item_join` and the search predicate change. Keep any new search tests behavior-level,
  not plan-shape-level.

## 5. Open for Sam (nothing blocks Wave 5)

**C-11's third mocked-behavior hazard.** `test_plain_upsert_still_merges_on_dialects_without_conflict_support`
asserts `db.merge` is *called* against a hand-rolled recording session, not that merge-based
upsert semantics work. The real fallback (`db_upsert.py:68–79`) runs only on a dialect that is
neither PostgreSQL nor SQLite, and the project has none — so no test can close it. Options are
written up in the coverage report's **Wave 3 residual** section: (a) delete the fallback and its
test, (b) rename the test to say it pins dispatch not semantics, (c) accept the residual. Wave 3
stays at "10 of 11" until one is chosen; whoever chooses should flip that row.

## 6. Why the new pitfalls exist (read before writing Wave 5 tests)

- **TEST-24** — a fixture holding ONE distinct value cannot tell a set-returning query from its
  base case. Found via the ingestion cache's recursive-CTE walks: every repair test stored items
  of exactly one category, so `LIMIT 1` — a cache that repairs only the lowest-numbered category
  forever — passed the entire suite.
- **TEST-25** — a correct assertion at the wrong OBSERVATION POINT constrains nothing. Three
  instances this session, each caught only by mutation: a debounce test that varied two inputs at
  once so the effect re-ran for the wrong reason; a query-freeze test that counted `fetch` calls,
  blind because a reverted query key is served from cache with no request; and its fix, which
  echoed a COUNT and was blind to a same-length substitution. Its **corollary** covers when to
  stop adding examples and change the kind of test instead, and its **evidence rule** is what
  makes review terminate: *a mutant is evidence only if it carries no information that could only
  have come from the test suite.*
- **TEST-12 hardening** — put the mutation restore in a `finally`, and check `git status` after
  every mutation run. A harness here restored on its last line, a `print` hit a console-encoding
  error first, and a `max-lg:hidden` mutant was left in `columns.tsx`. Committing at that moment
  would have shipped a deliberate mutation as production code under a message saying it was
  reverted.

One more pattern, not yet a pitfall because one instance isn't enough: **when a register row
names a workaround that exists because of the gap, the workaround's removability is a free check
on whether you closed the row.** C5 named `sorting.spec.ts`'s raw-locator workaround; I closed
the metadata half only, and the fact that the workaround still had to stay was the tell I walked
past. (Here it must stay regardless — it asserts `aria-sort` on a `display:none` header, which is
legitimately viewport-agnostic — but the question was worth asking.)

## 7. Continuation prompt (paste-ready)

> Hangar Bay: read `docs/superpowers/handoffs/2026-08-09-coverage-wave-5-handoff.md` first — its
> §3 process rules are binding (Routine PRs are agent-merged on a mechanically-gated green check;
> codex adversarial review before merge, framed as "name a plausible EDIT these tests would not
> catch"; TDD + mutation verification; five frontend lanes). State: `origin/dev` at `13dd67a`,
> ZERO open PRs, backend 733 / frontend 416×2 + 146 e2e all green. Waves 1–4 of the coverage
> campaign are merged.
>
> Your queue: **coverage Wave 5** — the 60 nice-to-have rows across the four registers beside
> `docs/test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md`. **Start with a
> sweep, not a test**: waves 3–4 closed several of these incidentally and the wave table's Wave 5
> row names the known-closed ones — verify, strike, and record the strike. Record intentional
> skips in the report's Remediation status. Update the wave table in the same PR. Then the
> **reward-per-jump spec + plan** (from the 2026-08-01 courier spike + F008 §15.2) — deliver for
> Sam's review BEFORE implementing; the route-graph data source is an architectural decision.
>
> Read `docs/pitfalls/testing-pitfalls.md` TEST-12, TEST-24 and TEST-25 before writing tests —
> all three were paid for last session. Work from
> `.claude/worktrees/hangar-bay-coverage-handoff-6f067d` (provisioned). Environment gotchas are in
> the handoff's §4; the ones that will bite first are `app/backend/src/.env` being gitignored,
> `routeTree.gen.ts` churn, and telling codex not to run `npm test` from `app/frontend/web`.
> Only Sam decides: C-11's third hazard, the production DB allow rule, the dev→main release,
> design decisions D-a–D-k.

## Appendix — adversarial review of this handoff

**Round 1 — naive fresh agent (3 applied).** Added the register row-counts per file (a fresh
agent cannot otherwise size Wave 5), spelled out that the wave table is the source of truth
rather than this doc, and expanded the merge-gate one-liner inline instead of referencing it.

**Round 2 — recency-bias audit (2 applied).** The session's last hours were Wave 4 part 2, so the
mid-session material was under-weighted: added the `e2e/` typecheck lane as a *consequence* for
future work (not just an achievement), and the `fast-check` availability note.

**Round 3 — seam auditor (2 applied).** The register-erratum seam generalized from one row to the
rule "treat register prose as evidence, not ground truth", since two rows were wrong this session
in different registers. Kept the D-a seam from the superseded handoff because it is still live and
Wave 5 touches search rows.

**Round 4 — operational guardrails auditor (4 applied).** The Windows-specific failures existed
only in the transcript: the codex sandbox `npm test` crash, the PR-body encoding mangling, the
`gh pr merge` false-alarm error, and the `npx tsx` limitation. All four cost real time to
diagnose and all four will recur.

**Round 5 — loss-averse audit (2 applied).** The workaround-removability heuristic (§6, not yet a
pitfall) and the explicit statement that fixture regions were NOT advanced this session — a fresh
agent would otherwise have to verify the high-water mark themselves.

**Round 6 — review-protocol fidelity audit (session-specific; 2 applied).** Chosen because this
session's defining event was discovering that an adversarial review framing can fail to
terminate, and that discovery is worthless if the next session reverts to the old prompt. Verified
§3's review section against what actually ran: added the concrete round-count contrast (four
rounds / zero defects under the old framing vs three findings / three fixes under the new one) so
the rule carries its own evidence, and cross-linked it to TEST-25's evidence rule so the two are
not maintained independently.

**Round 7 — "would Wave 5 actually start correctly?" (session-specific; 1 applied).** Chosen
because Wave 5's first action differs from every prior wave's — it is a sweep, not authoring —
and a fresh agent reading a queue naturally starts writing tests. Promoted the sweep from a
sentence in the queue to its own §2.1 with the strike-and-record instruction, and put it in the
continuation prompt in bold.

**Round 8 — top-to-bottom coherence pass (0 findings).** Full clean pass after rounds 1–7.
