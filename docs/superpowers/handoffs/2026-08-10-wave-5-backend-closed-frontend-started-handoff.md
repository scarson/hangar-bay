<!-- ABOUTME: Handoff after backend-write closed 18/18 and merged, the reward-per-jump spec+plan -->
<!-- ABOUTME: went to Sam for decision, and frontend-logic reached 10/13 in an open PR. -->

# Handoff — backend-write closed, frontend-logic started (written 2026-08-10)

**Supersedes** [`2026-08-10-coverage-wave-5-decisions-handoff.md`](2026-08-10-coverage-wave-5-decisions-handoff.md).
Its §3 process rules are RESTATED here (§4) because they are binding and must travel. Its §2.1
backend-write queue is **DONE** and MUST NOT be re-run.

## 0. Headline state

| | |
|---|---|
| `origin/dev` tip | `b4a67b9` (PR #182 merge) |
| Open PRs | **#183** — frontend-logic 10/13, all lanes green, adversarial review in flight |
| Baselines | backend **822** · vitest **445 ×2 lanes** · e2e **146** (7 skipped: live-smoke) · eslint + `tsc -b` clean |
| Worktree | `.claude/worktrees/coverage-wave-5-da9c1c`, on `test/frontend-logic-register` |
| Sam's queue | **Decision 1 on reward-per-jump (§3)** · the alerting gap · C-11's third hazard · production DB allow rule `198.37.143.189/32` (ENV-8) · the dev→main release · D-a–D-k |

## 1. What shipped

- **PR #182** (merged `b4a67b9`) — backend-write register **18/18**. Backend 799 → 822.
- **PR #183** (open) — frontend-logic **10/13** plus one production fix. vitest 416 → 445.
- **Reward-per-jump spec + plan** — committed, awaiting Sam. See §3.
- **Three pitfalls updates** (§5) — the durable form of this session's lessons.

**The campaign's source of truth is the wave table** in
[`2026-08-09-f008-remediation-test-coverage-review.md`](../../test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md)
§Remediation status. It is current as of this handoff.

## 2. The queue

1. **Frontend-logic's last 3 rows** (§2.1).
2. **Frontend-components — 17 rows.** Register at
   [`subagent-frontend-components-findings.md`](../../test-coverage-reports/subagent-frontend-components-findings.md)
   §Nice-to-have. **N18 ("no mobile live-smoke project") is a `playwright.config.ts` lane change,
   not a test** — the sweep flagged it out of scope for a test-only wave and it stays flagged for Sam.
3. **Reward-per-jump implementation** — blocked on Sam's Decision 1 (§3).

### 2.1 Frontend-logic, the 3 rows still open

| Row | What it needs |
|---|---|
| N-9 | The `sortableFieldsFor` per-segment membership SNAPSHOT. `columns.test.ts:25` derives its expected set from `columnsFor`, so both sides move together — this is **TEST-27**, and it is the row's entire remaining content. Replace with hand-written per-segment literals |
| N-10 | Blueprint cell: a single copy with one null figure renders a blank cell at list level (`columns.tsx:199-200`) |
| N-11 | `EXPIRES_COLUMN`'s `text-warn` fork on an expired row (`columns.tsx:141-143`). **ONE gap shared with frontend-components N-11** — one test closes both, so close it WITH the components register rather than here |

### 2.2 What the recon already settled — do not re-derive

Verified against source, not register prose (three rows have been wrong across this campaign):

- **`isItemLessSelection([])` is TRUE**, because `[].every()` is vacuously true. `parseContractSearch`
  never produces an empty array, so the test builds it by overriding a real parse. Closed in #183.
- **`hasOfferedItemFilters` is live code**, called by `FilterRail.tsx:48` inside `hasActiveFilters` —
  not the dead export the row suspected. Closed in #183.
- **`formatIsk(0)` is a live row** — live ESI sampling found 16/16 couriers carrying `price=0`.
  Closed in #183.

## 3. Reward-per-jump — waiting on Sam, and the one thing to read first

**Artifacts:** [`specs/2026-08-10-reward-per-jump-spec.md`](../specs/2026-08-10-reward-per-jump-spec.md)
(asks four questions, recommends an answer to each) and
[`plans/2026-08-10-reward-per-jump.md`](../plans/2026-08-10-reward-per-jump.md) (Phase 0 executable
now; Phases 1–4 deferred pending Decision 1).

**Decision 1 is the architectural one:** buy jump counts from ESI's `/route/`, or vendor an
adjacency graph and search it ourselves? The spec argues AGAINST the 2026-08-01 courier spike's
recommendation, because the spike priced the alternative against reproducing CCP's `secure`
semantics — and a survey done *after* the spike established that `secure` is an *upper bound*
(45 jumps where a fully high-sec 34-jump route exists). The two findings sit adjacent and
unreconciled in F008 §15.2. Once matching ESI stops being the goal, the metric is a filtered BFS.

**Two caveats are Sam's:** licensing (the spike found no Fuzzwork license page; vendoring is a
distribution decision) and that nobody has actually fetched the edge list. Phase 0 front-loads both
plus a ranking-inversion measurement whose threshold is fixed in advance so it can overturn the
recommendation rather than ratify it.

**Read this before touching the spec:** an independent review found five factual errors in its
reasoning, all now fixed and marked in place. The load-bearing one — **we send
`X-Compatibility-Date: 2026-07-21`, so `GET /route/` already 404s for us** — was already recorded
in pitfall ESI-4's "Where It Stands". See §5.

## 4. Process rules — BINDING, carried forward

### Merge authority

Agents merge `Routine` PRs themselves. Every PR body carries `## Merge classification`:
`Routine` / `Review — <domain trigger>` / `Escalate — <concern>`. Domain triggers:
schema/migrations, public API contract, auth/secrets, data-integrity paths. `Review`-classified PRs
are **held for Sam, never agent-merged**.

Merge ONLY through the mechanical gate — the check's output must gate the merge, never
`check; merge`, never `--auto`:

```bash
gh pr checks <n> | grep -vE "pass|skipping" && echo BLOCKED || gh pr merge <n> --merge --delete-branch
```

Always `--merge`. Never `--squash`, never `--rebase` — per-commit history is permanent and
bisect-visible, so Conventional Commits applies to **every commit**.

### Codex adversarial review

`codex exec -m gpt-5.6-sol -c model_reasoning_effort='"high"'`, backgrounded, prompt via
**heredoc**, redirected to a log (never piped through `tail` — the pipe buffers until exit).
**Re-run on every non-trivial rework.**

**Declare EVERY untracked path out of scope, not just `.private-journal/` and `.serena/`.** This
cost a whole wasted round on 2026-08-10: codex stopped with `NEEDS_CONTEXT` over ordinary scratch
files, citing the repo's own "STOP and ask about uncommitted changes" rule. Name the scratch files,
say they are the review's own artifacts, and state that their presence is not a reason to withhold
a verdict.

**Frame findings as: "name a plausible EDIT to this code that these tests would not catch."** Plus
both termination rules, because the framing alone does not converge:

1. **Split findings into (a) fails-to-constrain-what-it-claims, which blocks, versus (b)
   adjacent-and-never-claimed, which does not.** Bound each claim to its register row plus the
   test's own docstring, and tell the reviewer not to promote a (b) into an (a) by reading a
   docstring expansively.
2. **State that an empty list is the DESIRED outcome**, verbatim: *"do not manufacture a category
   (a) finding to avoid an empty list; an empty list is the expected and desired outcome of a
   converging review, and reporting one falsely is worse than missing one."*
3. On a long review, demand an explicit **CONVERGED / NOT CONVERGED** verdict.

**Scoping a re-review to the delta works and terminates.** Round 4 on PR #182 was pointed only at
the two fixes plus one named regression risk, and converged with an empty list.

### Test discipline

TDD for production code (watch RED first, and confirm the RED is for the RIGHT reason).
Mutation-verify load-bearing tests (**TEST-12**). Session-scoped fixtures need footprint-free
consumers with `finally` restoration (TEST-23). Never weaken an assertion to fix a flake (TEST-2).

- **Backend**: `.venv\Scripts\pytest.exe` from `app/backend`; `python -m pdm run lint`.
- **Frontend**: ALL FIVE lanes green before any completion claim — `npx eslint .` · `npx tsc -b` ·
  `npm run test` · `npm run test:future-clock` · `npm run e2e`.

## 5. What this session put in the pitfalls file

Read [`docs/pitfalls/testing-pitfalls.md`](../../pitfalls/testing-pitfalls.md) and
[`implementation-pitfalls.md`](../../pitfalls/implementation-pitfalls.md). Summarised only enough
to decide whether to read them:

- **TEST-11 hardened** — a boundary test asserting only "every row landed" does NOT constrain the
  chunking, and the regression it misses is the worse one. Five such tests survived de-chunking
  here. Assert statement counts or write sizes; and guard the CONSTANT separately, since a test
  that monkeypatches the size to 2 constrains the loop and never the value.
- **"How to Use This Document" gained a reading rule** — read an entry's `Where It Stands` before
  acting on its `The Flaw`. An entry is named for the flaw, so its opening paragraph keeps
  describing the broken state in the present tense after the fix lands. Reading the top and
  stopping can return the exact opposite of what is true.
- **JS-1 (new, implementation)** — `Number('   ')` is 0, not NaN, so a whitespace-only value passes
  a junk filter as a legitimate zero. Fixed in `filters.ts::toNumber` by trimming before the
  emptiness check.

**One methodology lesson has no pitfalls home and lives here.** Across four adversarial passes on
PR #182 the reviewer produced nine category-(a) findings; **every one was correct**. That is a
different ratio from the previous session's (~19 findings, two wrong) and the reason is worth
naming: this session's findings were about *test-to-claim fit*, which the reviewer can check
mechanically against the code, while the previous session's wrong ones were *domain premises* about
upstream payloads, which it cannot. **Reviewer prose about your own code is strong evidence;
reviewer prose about the outside world still needs sampling.** The same asymmetry cut the other way
in the spec review — its five findings about our own source were all right, and the one I had to
verify hardest (`X-Compatibility-Date`) took a single grep.

## 6. Seams and environment facts a fresh agent will hit

Carried forward and still true: the gitignored `app/backend/src/.env`; `routeTree.gen.ts` churn
(`git checkout --` before staging, never commit); `gh pr merge --delete-branch` printing
`fatal: 'dev' is already used by worktree` while **the merge itself succeeds** (verify with
`gh pr view <n> --json state`); `e2e/` is typechecked; `npx tsx` cannot resolve the project's
`.tsx` modules; register prose is evidence, not ground truth.

New this session:

- **The full backend suite takes ~2m15s, over the Bash tool's 2-minute default.** It gets killed at
  exit 143 if run plainly. Redirect to a log and background it, or pass an explicit longer timeout.
- **`cat >> file <<'EOF'` in the Bash tool breaks on apostrophes inside the heredoc body**, despite
  the quoted delimiter. Write the fragment with the Write tool and `cat` it on instead.
- **Create the PR before writing its number into any document.** Predicting from the last merged
  number is wrong whenever anything landed in between; `#181` cost a correction commit when the PR
  came back `#182`.
- **A monitor watching a codex log cannot use a bare substring for anything.** This bit three times
  in one session, each differently. (a) Grepping the WHOLE log for the verdict matched the prompt's
  own echo of the word, reporting `NOT CONVERGED` for a run that had stopped at `NEEDS_CONTEXT`
  and reviewed nothing. (b) Grepping for the end marker `tokens used` matched **the diff under
  review** — the log contains every file codex reads, so a handoff doc describing the end marker
  matched it, and the monitor fired while the review was still running. (c) The verdict then came
  back empty, because the tail held no verdict at all. **Use process liveness as the completion
  signal and a line-anchored pattern for the verdict** (`grep -nx`, `grep -oE '^\*\*...'`), never a
  substring — and never trust a monitor result you have not confirmed by reading the file.
- **Do not commit to a branch while an adversarial review of that branch is running.** The review
  reads `git diff origin/dev...HEAD`, so a commit lands inside the thing being reviewed. It is also
  what put this handoff's own text into the log that (b) above then matched.
- **`subprocess.run` over `npx vitest` needs `encoding="utf-8", errors="replace"`** — vitest's
  output is not cp1252-decodable and the harness dies mid-run. Its `finally` restore held, which is
  exactly the TEST-12 hardening working.
- **An empty array in a test fixture infers `never[]`**, so a `Parameters<typeof f>[0]` cast that
  the neighbouring tests use stops overlapping and `tsc` rejects it. That is `tsc` doing its job:
  the cast had been hiding a genuinely missing required field. Supply the field; drop the cast.

## 7. Open for Sam

**NEW and unresolved:** **Decision 1 on reward-per-jump** (§3) — nothing is implemented until it is
answered.

Carried forward, unchanged: **the alerting gap** (there is still no alert rule on
`hangar_bay_last_ingest_success_timestamp` or
`hangar_bay_ingest_contracts_skipped_total{reason="malformed_date"}`; alerting lives in Grafana
Cloud, outside version control), **C-11's third mocked-behavior hazard** (Wave 3 stands at 10 of 11
until one option is chosen), the production DB allow rule `198.37.143.189/32` (ENV-8), the dev→main
release, and design decisions D-a–D-k.

One judgment call to ratify or reverse: **backend-write N-11's `"a contract"` fallback** was left by
the sweep as an either/or for Sam (defense-in-depth worth a direct call, or dead code to note as
such). It was resolved as defense-in-depth without waiting, on the grounds that the production
comment beside the branch already says so and testing it changes no behaviour. Had the answer been
"dead code" it would have meant deleting production code, and that would have waited.

## 8. Continuation prompt (paste-ready)

```
Hangar Bay: read docs/superpowers/handoffs/2026-08-10-wave-5-backend-closed-frontend-started-handoff.md
first — its §4 process rules are binding. State: origin/dev at b4a67b9, backend 822, vitest 445×2,
e2e 146, eslint/tsc clean. PR #183 is OPEN (frontend-logic 10/13 + one production fix, all five
lanes green) with a codex adversarial review in flight — read _cx.log in the worktree for its
verdict, fix any category (a) findings, re-run codex on non-trivial rework, then merge through the
mechanical gate. The backend-write register is CLOSED 18/18 and MUST NOT be re-run.

Queue: frontend-logic's last 3 rows (§2.1 — N-9 is the sortableFieldsFor per-segment snapshot
replacing a TEST-27 self-referential assertion; N-10 the blueprint cell; N-11 the EXPIRES_COLUMN
text-warn fork, which is ONE gap shared with frontend-components N-11 and should close WITH that
register). Then frontend-components 17 rows — its N18 is a playwright.config.ts lane change, not a
test, and stays flagged for Sam. §2.2 records what recon already settled against source, including
that isItemLessSelection([]) is TRUE and hasOfferedItemFilters is live code.

Reward-per-jump spec + plan are committed and awaiting Sam's Decision 1 — do NOT implement any of
Phases 1-4 until it is answered; Phase 0 is executable now and is written to be able to overturn
the recommendation.

Process rules that are binding: Routine PRs merge ONLY through the mechanical gate (gh pr checks
<n> | grep -vE "pass|skipping" && echo BLOCKED || gh pr merge <n> --merge --delete-branch);
Review-classified PRs are held for Sam; always --merge, never --squash/--rebase; Conventional
Commits on every commit. Codex: backgrounded, heredoc, redirect to a file, never pipe through tail,
and DECLARE EVERY UNTRACKED PATH OUT OF SCOPE — not just .private-journal/ and .serena/ — or it
stops with NEEDS_CONTEXT and reviews nothing. Frame findings as "name a plausible EDIT to this code
that these tests would not catch", and include BOTH termination rules: the (a)/(b) split bounded to
the register row plus the test's docstring, and that an empty list is the DESIRED outcome. Scoping
a re-review to just the delta works and converges. TDD with RED watched first, verified for the
RIGHT reason. Mutation-verify load-bearing tests. Five frontend lanes green before any completion
claim.

Read docs/pitfalls/testing-pitfalls.md — TEST-11 was HARDENED on 2026-08-10 (a boundary test
asserting only "every row landed" does not constrain the chunking; de-chunking is the worse
regression and survives it — assert statement counts or write sizes, and guard the constant
separately) — plus TEST-12, TEST-15, TEST-18, TEST-24, TEST-25, TEST-26, TEST-27, TEST-28. Read the
new "How to Use This Document" rule: an entry's Where It Stands, not its The Flaw, is the current
state — reading the top and stopping returned the exact opposite of the truth this session and cost
a spec rewrite. Implementation-pitfalls JS-1 is new.

Work from .claude/worktrees/coverage-wave-5-da9c1c (provisioned). §6 has the environment gotchas;
the ones that bite first are the full backend suite exceeding the 2-minute Bash default, heredocs
breaking on apostrophes, creating the PR before writing its number anywhere, and monitors that
grep a whole log matching the prompt's own echo of the verdict word.

Only Sam decides: reward-per-jump Decision 1, the alerting gap, C-11's third hazard, the production
DB allow rule, the dev→main release, and D-a–D-k.
```

## Appendix — adversarial review of this handoff

**Round 1 — naive fresh agent (3 applied).** Spelled out that backend-write is closed and must not
be re-run; gave §2.1 the actual row content rather than pointing at the register; expanded the merge
gate inline.

**Round 2 — recency-bias audit (2 applied).** The session's last hour was frontend work, so the
backend review rounds were under-weighted: restored the codex `NEEDS_CONTEXT` guardrail to §4 (it
cost a full wasted round and would otherwise cost the next one too), and the delta-scoping technique
that made round 4 converge.

**Round 3 — seam auditor (2 applied).** Two seams: frontend-logic N-11 is the SAME gap as
frontend-components N-11, so closing it in the logic slice would duplicate work the components
register also claims — §2.1 now says to close it with components. And PR #183 is open with a review
in flight, so the continuation prompt names the log file rather than assuming the next agent
re-runs the review.

**Round 4 — operational guardrails auditor (3 applied).** The untracked-files declaration, the
suite-exceeds-Bash-timeout fact, and the monitor-grep-matches-the-prompt trap all existed only in
the transcript. All three are now in §6 and the first is in §4, since §4 is what gets read.

**Round 5 — loss-averse audit (2 applied).** The N-11 judgment call (resolved without waiting for
Sam) needed to be visible for ratification rather than buried in a commit message — now §7. And the
reviewer-accuracy asymmetry had no pitfalls home and would have died with the transcript — now §5.

**Round 6 — "which reviewer claims can I trust?" (session-specific; 2 applied).** Chosen because
this session's defining feature was that an adversarial reviewer went nine-for-nine on findings
after the previous session recorded two wrong ones — a reversal worth explaining rather than
recording as luck. The distinction that emerged (test-to-claim fit is mechanically checkable;
domain premises about the outside world are not) is now §5's methodology lesson, and it is what
justifies having accepted all nine findings without re-litigating each.

**Round 7 — top-to-bottom coherence pass (1 applied).** Verified every count against a real run
rather than against my own earlier messages: backend is **822**, not the 821 an earlier status said,
because the round-3 rework added the bind-ceiling test after that number was quoted.
