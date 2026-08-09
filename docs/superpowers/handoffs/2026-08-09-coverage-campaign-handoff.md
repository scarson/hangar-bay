<!-- ABOUTME: Handoff ending the 2026-08-08/09 marathon session: all follow-ups, the bug-hunt remediation, -->
<!-- ABOUTME: perf quick-wins, and coverage waves 1-2 are MERGED; waves 3-5 + reward-per-jump are the queue. -->

# Handoff — coverage campaign waves 3–5 + reward-per-jump are the queue (written 2026-08-09)

**Supersedes** [`2026-08-08-overnight-campaign-handoff.md`](2026-08-08-overnight-campaign-handoff.md)
§0–§3 (its "PR #156 held" state and docket are history — Sam merged everything). Its §4 seams and
the machine notes it points at (decision-log OD1/OD6) remain accurate and are NOT restated.

## 0. Headline state

| | |
|---|---|
| `origin/dev` tip | `485a611` (PR #166 merge) — this handoff's merge lands just above it |
| Open PRs | **none** — Sam merged #156, #162, #164, #166 personally; every Routine PR (#148–#155, #157–#161, #163, #165, #167) auto-merged on verified-green CI |
| Baselines at handoff | backend **705** green · frontend eslint/tsc clean, vitest 322×2, e2e 140 · lint clean |
| Worktree | `.claude/worktrees/pr-147-handoff-beaace` on the **Windows** machine, fully provisioned (OD1/OD6) |
| Sam's remaining queue | production DB allow rule `198.37.143.189/32` (Render access, ENV-8) · the dev→main release (2026-08-07 handoff §3 runbook) · bug-hunt design decisions D-a–D-k at leisure |

## 1. What this session shipped (pointers, not narrative)

Twenty PRs merged end-to-end. The records that matter:

- **Decision log** [`2026-08-08-overnight-followups-decision-log.md`](../plans/2026-08-08-overnight-followups-decision-log.md)
  OD1–OD9 — machine provisioning, PG16 volume surgery, every autonomous decision with rationale,
  the one process slip, review-cycle statistics.
- **Bug hunt + remediation**: consolidated findings
  [`docs/bug-hunts/2026-08-08-f008-prerelease-consolidated.md`](../../bug-hunts/2026-08-08-f008-prerelease-consolidated.md)
  (7 bugs fixed, 11 design decisions for Sam, accepted residuals documented at their predicates);
  plan with per-phase ✅ banners in `docs/plans/2026-08-08-f008-prerelease-bug-hunt-remediation-plan.md`.
- **Perf**: disposition + ranked still-opens in
  [`docs/perf-audits/2026-08-08-remediation-status.md`](../../perf-audits/2026-08-08-remediation-status.md);
  shipped quick-wins recorded in OD9 (batch 500, data-layer search debounce, redis aclose;
  SP14 deliberately rejected — reasons in PR #160's body).
- **Coverage campaign** (Sam's directive: **fix ALL 126 gaps**): living wave table in
  [`docs/test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md`](../../test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md)
  §Remediation status. Waves 1–2 merged (#163, #164, #166 — the last two carried small
  input-validation contract changes Sam reviewed). Four per-file gap registers sit beside it —
  they are the work orders.
- **New pitfalls** TEST-22 (spec-minimal ingestion payloads) and TEST-23 (session-scoped fixtures
  demand footprint-free consumers).

## 2. The queue (in order)

1. **Coverage Wave 3** — backend write-path correctness, 11 rows + O2's ingestion-partition pin
   (`background_aggregation.py:720` hard-codes `["item_exchange", "auction"]`; pin it to the enum).
   Register: `docs/test-coverage-reports/subagent-backend-write-findings.md` §2. Mostly test-only →
   Routine.
2. **Coverage Wave 4** — frontend logic (28) + components (10) + the three e2e pins (O1a
   `WirePage` missing `unknown_system_excluded`; O1b localeCompare-vs-ordinal tiebreak; the
   `price: null` fixture pin PR #156 deferred). Registers: the two frontend reports. Five lanes
   per commit.
3. **Coverage Wave 5** — 60 nice-to-haves; sweep last, drop rows earlier waves already covered,
   and record intentional skips in the report's Remediation status.
4. **Reward-per-jump spec + plan** — synthesis, not research: the courier spike
   (`docs/superpowers/specs/2026-08-01-courier-route-jumps-spike.md`, 161 ESI calls / 8.4 s cold)
   and F008 spec §15.2 (the ESI `/route/` GET→POST shape change entangled with the open ESI-4
   pinning decision) carry the groundwork. Produce spec + plan **for Sam's review before any
   implementation** — the route-graph data source is an architectural decision.

Deferred items with conditions: the remaining perf mediums (cache-aside, fan-out semaphore,
QueueHandler, streaming, ingestion metrics) each want their own fresh-context plan against the
perf disposition's write-ups — no upstream blocker, just sizing. The two production-blocked perf
items unblock when Sam re-provisions `RENDER_API_KEY` (ENV-8).

## 3. Process rules the next session MUST carry (Sam asked for these verbatim in the handoff)

**PR rules**
- Conventional Commits on EVERY commit (`type(scope): imperative, lower-case, no period`); this
  repo merges with `--merge` and keeps per-commit history — no squash launders anything.
- Every PR body carries `## Merge classification`: `Routine` / `Review — <domain trigger>` /
  `Escalate — <concern>`. Domain triggers: schema/migrations, public API contract, auth/secrets,
  data-integrity paths. Review-classified PRs are **held for Sam — never agent-merged**.
- Agents merge Routine PRs themselves ONLY after explicitly verifying green:
  `gh pr checks <n> | grep -vE "pass|skipping" && echo BLOCKED || gh pr merge <n> --merge --delete-branch`
  — the check's output must mechanically gate the merge (never `check; merge`, never `--auto`:
  this repo has no required status checks, so `--auto` merges instantly mid-CI).
- Conflicts: rebase in the worktree, `git push --force-with-lease`; codegen conflicts
  (`openapi.json`/`schema.d.ts`) are REGENERATED (`pdm run export-openapi` →
  `npm run generate:api`), never hand-merged.

**Codex adversarial review rules**
- Meaningful PRs (behavior changes, anything non-trivial) get a codex review BEFORE merge:
  `codex exec -m gpt-5.6-sol -c model_reasoning_effort='"high"'` as a background task, prompt via
  **heredoc** (`- <<'EOF'` … `EOF`) — never a double-quoted shell string (backticks execute).
- Start every codex prompt with: untracked `.private-journal/` and `.serena/` are agent tooling,
  OUT OF SCOPE, do not ask — or codex stops with NEEDS_CONTEXT.
- **Re-run codex on every rework.** Historical hit rate: rounds 2–3 found real defects inside
  fixes in four separate campaigns this session, including a repo-wide P1 (env.py offline
  transaction wrapper).
- Trivial PRs (docs, two-line stubs, constant tunes) may skip codex with the skip RECORDED in the
  PR body, per the OD5 precedent.

**Test discipline**
- TDD for all production code (watch RED first); mutation-verify load-bearing tests via
  `cp` snapshot → break → red → restore → green (TEST-12); session-scoped fixtures demand
  footprint-free consumers with restoration in `finally` (TEST-23); never weaken an assertion to
  fix a flake (TEST-2).
- Backend: serialize on
  `DATABASE_URL_TESTS=postgresql+asyncpg://hangar_bay_user:hangar_bay_password@localhost:5432/hangar_bay_test_f008`
  with `ESI_USER_AGENT` exported, `.venv\Scripts\pytest.exe`; `pdm run lint` (via `python -m pdm`).
- Frontend: ALL FIVE lanes green before any completion claim — `npx eslint .` · `npx tsc -b` ·
  `npm run test` · `npm run test:future-clock` · `npm run e2e`.
- Alembic: explicit target revisions in downgrade tests (a relative `-1` re-targets itself when a
  newer migration lands — bit twice); single-head check before and after authoring;
  `SET lock_timeout = '30s'` preamble; guards as emitted SQL under an exclusive lock.
- Fixture regions claimed through **99999976**; next free is **99999977**.

**Machine (Windows) reminders** — full list in OD6 + memory: `python -m pdm`; never commit
`package-lock.json`/`routeTree.gen.ts` churn (`git checkout --` before staging); absolute paths in
shell commands (two relative-`cd` slips this session both mis-resolved `git add` paths).

## 4. Seams

- **#164 and #166 both appended to `test_contracts.py` and both touched `openapi.json`** — resolved
  by rebase (both blocks kept, openapi regenerated). Anyone with a stale checkout of either branch:
  they're merged and deleted; work from `origin/dev`.
- **The coverage report's wave table is the single source of campaign truth** — update it in the
  same PR as each wave (the Living Document Contract applies to it now).
- **`_needs_item_join` and the search predicate** are due to change if Sam takes design decision
  D-a (offered-only EXISTS semantics) — Wave 4/5 test authors should note new search tests may
  need revisiting under D-a and keep them behavior-level, not plan-shape-level.
- **Two testing-pitfall entries this session (TEST-22/23) came from live failures** — read them
  before writing ingestion or migration tests; both traps cost real time here.

## 5. Continuation prompt (paste-ready)

> Hangar Bay: read `docs/superpowers/handoffs/2026-08-09-coverage-campaign-handoff.md` first — its
> §3 process rules (PR classification + verified-green gated merges, codex heredoc reviews with
> rework re-runs, TDD/mutation/five-lane discipline) are binding. State: `origin/dev` at `485a611`+,
> ZERO open PRs (Sam merged all held ones), backend 705 / frontend 322×2 + 140 e2e all green. Only
> Sam does: the production DB allow-rule removal, the dev→main release, design decisions D-a–D-k.
> Your queue, in order: coverage Wave 3 (backend write-path register,
> `docs/test-coverage-reports/subagent-backend-write-findings.md` §2, + pin the ingestion
> type-partition to the enum), Wave 4 (both frontend registers + the three e2e pins O1a/O1b/price-null),
> Wave 5 (nice-to-haves, recording intentional skips), then the reward-per-jump spec+plan (from the
> 2026-08-01 courier spike + F008 §15.2; deliver for Sam's review BEFORE implementing). Update the
> coverage report's wave table in the same PR as each wave. Work from
> `.claude/worktrees/pr-147-handoff-beaace` on the Windows machine (gotchas: decision-log OD6 —
> `python -m pdm`, never commit lockfile/routeTree churn, absolute paths in shell commands); backend
> tests serialize on `DATABASE_URL_TESTS=…/hangar_bay_test_f008` with `ESI_USER_AGENT` exported;
> fixture regions next-free 99999977.

## Appendix — adversarial review of this handoff

**Round 1 — naive fresh agent (2 applied).** Added the zero-open-PRs headline (the superseded
handoff says two PRs are held — a fresh agent must not go looking for them) and the explicit
"Sam merged everything" note with the auto-merged/Sam-merged split.

**Round 2 — recency-bias audit (2 applied).** The session's last hours were coverage waves; added
the mid-session material a coverage-focused reader would miss: the perf mediums as deferred items
with their sizing condition, and the D-a dependency note for future search tests.

**Round 3 — seam auditor (1 applied).** §4's rebase seam — both merged PRs' branches are deleted;
stated plainly so nobody resurrects a stale branch.

**Round 4 — operational guardrails auditor (1 applied).** The relative-`cd` path slips existed
only in the transcript; now in §3's machine reminders. The rest of the session's guardrails were
already durable (OD-entries, pitfalls, PR bodies) — verified rather than duplicated.

**Round 5 — loss-averse audit (2 applied).** The fixture-region high-water mark (99999977 next)
and the wave-table-is-source-of-truth rule were transcript-only; both persisted.

**Round 6 — process-rules fidelity audit (session-specific; 1 applied).** Chosen because Sam
explicitly asked for the codex and PR rules to travel INTO the next session: re-derived §3 against
the actual commands run this session (not from memory of the rules), catching that the merge-gate
one-liner previously read `&& echo` without the blocking semantics — the exact slip OD7's addendum
records. The published form now matches the corrected practice.

**Round 7 — top-to-bottom coherence pass (0 findings).** Full clean pass after rounds 1–6 fixes.
